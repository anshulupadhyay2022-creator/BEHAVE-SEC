"""
backend/api/routes/behavioral.py
POST /collect-data  — receives behavioral data from the frontend.

The in-memory store is imported from stats.py so both routes share the same
list without circular imports.  Every session is ALSO persisted to the
database via backend.db.repository.
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schemas import BehavioralDataPayload
from backend.utils.storage import save_to_csv, save_to_json
from backend.ml.model import model_manager
from backend.db.engine import AsyncSessionLocal, get_db
from backend.db import repository
from backend.db.models import User, Session
from backend.api.routes.auth import get_current_user, generate_and_send_otp
from backend.api.routes.ws import manager as ws_manager
from backend.core.security.replay import replay_defender

# Shared in-memory store (owned by stats module, imported here)
from backend.api.routes.stats import behavioral_data_storage

router = APIRouter()


# ── DB dependency ─────────────────────────────────────────────────────────────
# async def get_db() -> AsyncSession:  # type: ignore[return]
#     async with AsyncSessionLocal() as session:
#         yield session


# ── Route ─────────────────────────────────────────────────────────────────────
@router.post("/collect-data")
async def collect_behavioral_data(
    request: Request,
    payload: BehavioralDataPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Receive, validate, persist, analyse, and summarise a behavioral data session."""
    try:
        # 1. Defend against Replay Attacks
        if replay_defender.is_replay(payload.events):
            raise HTTPException(status_code=400, detail="Replay Attack Detected: Identical Behavioral Payload")

        # Tally events by type
        event_counts: Dict[str, int] = {}
        for event in payload.events:
            event_counts[event.eventType] = event_counts.get(event.eventType, 0) + 1

        print(f"\n{'=' * 60}")
        print("[DATA] RECEIVED BEHAVIORAL DATA")
        print(f"{'=' * 60}")
        print(f"User ID    : {payload.userId}")
        print(f"Session ID : {payload.sessionId}")
        print(f"Total Events: {len(payload.events)}")
        print(f"Duration   : {payload.metadata.sessionDuration / 1000:.2f} seconds")
        print("\nEvent Breakdown:")
        for event_type, count in event_counts.items():
            print(f"  - {event_type}: {count}")

        json_file = save_to_json(payload)
        csv_file = save_to_csv(payload)
        print(f"\n[OK] Data saved to {json_file} and {csv_file}")

        # ── Setup Security Context ──────────────────────────────────────────
        payload.userId = current_user.id
        ip_address = request.client.host if request.client else "unknown"
        hijack_suspected = False
        
        last_session = await repository.get_last_session_by_user(db, current_user.id)
        if last_session:
            if last_session.ip_address and ip_address and last_session.ip_address != ip_address and ip_address != "unknown":
                hijack_suspected = True
            if last_session.user_agent and payload.metadata.userAgent and last_session.user_agent != payload.metadata.userAgent:
                hijack_suspected = True

        # ── Anomaly detection ────────────────────────────────────────────────
        user_detector = model_manager.get_detector(payload.userId)
        anomaly_result = user_detector.ingest(payload)
        anomaly_score = float(anomaly_result.get("score", 0.0))
        risk_score = (anomaly_score * 0.7) + (0.3 if hijack_suspected else 0.0)
        risk_score = min(risk_score, 1.0)
        
        print(f"[ML]  Anomaly label={anomaly_result['label']}  "
              f"score={anomaly_score}  "
              f"model_ready={anomaly_result['model_ready']}")
        print(f"[RISK] Score: {risk_score:.2f} | Hijacking: {hijack_suspected}")

        # ── Automated Logout & MFA ───────────────────────────────────────────
        force_logout = False
        if anomaly_score > 0.7 or risk_score > 0.8:
            print("[ALERT] High risk detected. Locking user account and requiring MFA.")
            current_user.locked_out = True
            otp_code = generate_and_send_otp(current_user.email)
            current_user.otp_code = otp_code
            from datetime import datetime, timezone, timedelta
            current_user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            await repository.update_user(db, current_user)
            force_logout = True

        # ── Persist to database ──────────────────────────────────────────────
        await repository.save_session(
            db, payload, anomaly_result, event_counts,
            ip_address=ip_address, risk_score=risk_score, hijack_suspected=hijack_suspected
        )
        print(f"[DB]  Session {payload.sessionId} written to database.")
        print(f"{'=' * 60}\n")
        
        # ── Real-time WebSocket Notifications ─────────────────────────────────
        ws_payload = {
            "type": "new_session",
            "userId": current_user.id,
            "userEmail": current_user.email,
            "eventsCount": len(payload.events),
            "riskScore": round(risk_score * 100, 2),
            "anomalyLabel": anomaly_result.get("label", "pending"),
            "anomalyScore": anomaly_score,
            "hijackSuspected": hijack_suspected,
            "forceLogout": force_logout,
        }
        await ws_manager.broadcast(ws_payload)
        if force_logout:
            await ws_manager.send_personal_message({"type": "force_logout", "reason": "Anomaly detected. MFA required."}, current_user.id)

        # Append summary to in-memory store (fast cache for current process)
        behavioral_data_storage.append({
            "userId": current_user.id,
            "sessionId": payload.sessionId,
            "timestamp": datetime.now().isoformat(),
            "eventCount": len(payload.events),
            "eventBreakdown": event_counts,
            "metadata": payload.metadata.model_dump(),
            "events": [event.model_dump() for event in payload.events],
            "anomaly": anomaly_result,
            "riskScore": risk_score,
        })

        return {
            "status": "success",
            "message": f"Stored {len(payload.events)} events",
            "data": {
                "userId": payload.userId,
                "sessionId": payload.sessionId,
                "eventsReceived": len(payload.events),
                "eventBreakdown": event_counts,
                "filesCreated": [json_file, csv_file],
            },
            "anomaly": anomaly_result,
        }

    except Exception as exc:
        print(f"\n[ERROR] Error processing data: {exc}\n")
        raise HTTPException(status_code=500, detail=f"Error processing data: {exc}") from exc
