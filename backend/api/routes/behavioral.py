"""
backend/api/routes/behavioral.py
POST /collect-data  — receives behavioral data from the frontend.

The in-memory store is imported from stats.py so both routes share the same
list without circular imports.  Every session is ALSO persisted to the
database via backend.db.repository.
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schemas import BehavioralDataPayload
from backend.utils.storage import save_to_csv, save_to_json
from backend.ml.model import detector
from backend.db.engine import AsyncSessionLocal
from backend.db import repository

# Shared in-memory store (owned by stats module, imported here)
from backend.api.routes.stats import behavioral_data_storage

router = APIRouter()


# ── DB dependency ─────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session


# ── Route ─────────────────────────────────────────────────────────────────────
@router.post("/collect-data")
async def collect_behavioral_data(
    payload: BehavioralDataPayload,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Receive, validate, persist, analyse, and summarise a behavioral data session."""
    try:
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

        # ── Anomaly detection ────────────────────────────────────────────────
        anomaly_result = detector.ingest(payload)
        print(f"[ML]  Anomaly label={anomaly_result['label']}  "
              f"score={anomaly_result.get('score', 'n/a')}  "
              f"model_ready={anomaly_result['model_ready']}")

        # ── Persist to database ──────────────────────────────────────────────
        await repository.save_session(db, payload, anomaly_result, event_counts)
        print(f"[DB]  Session {payload.sessionId} written to database.")
        print(f"{'=' * 60}\n")

        # Append summary to in-memory store (fast cache for current process)
        behavioral_data_storage.append({
            "userId": payload.userId,
            "sessionId": payload.sessionId,
            "timestamp": datetime.now().isoformat(),
            "eventCount": len(payload.events),
            "eventBreakdown": event_counts,
            "metadata": payload.metadata.model_dump(),
            "events": [event.model_dump() for event in payload.events],
            "anomaly": anomaly_result,
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
