"""
backend/api/routes/stats.py
GET /stats  — returns aggregate statistics for all received sessions.
GET /dashboard/summary — returns structured data for the SOC dashboard.

The in-memory store list is defined here and imported by behavioral.py
so both routes operate on the same data without circular imports.
/stats reads from the DATABASE so data survives server restarts.
The in-memory store is kept as a fast cache for the current process.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import AsyncSessionLocal
from backend.db import repository

router = APIRouter()

# Shared in-memory store for this server process lifetime
behavioral_data_storage: List[Dict[str, Any]] = []


# ── DB dependency ─────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session


# ── Route: /stats ─────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_statistics(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Return summary statistics for all sessions — read from the database."""
    rows = await repository.get_all_sessions(db)

    total_sessions = len(rows)
    total_events = sum(r.event_count for r in rows)

    return {
        "totalSessions": total_sessions,
        "totalEvents": total_events,
        "sessions": [
            {
                "userId": r.user_id,
                "sessionId": r.session_id,
                "timestamp": r.collected_at.isoformat() if r.collected_at else None,
                "eventCount": r.event_count,
                "eventBreakdown": r.event_breakdown,
                "anomaly": {
                    "label": r.anomaly_label,
                    "score": r.anomaly_score,
                },
            }
            for r in rows
        ],
    }


# ── Route: /dashboard/summary ─────────────────────────────────────────────────
@router.get("/dashboard/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Return structured data optimised for the SOC-style dashboard:
    - anomaly_trend: last 20 sessions sorted oldest-first for chart rendering
    - detection_stats: count breakdown by anomaly label + bot flags
    - avg_risk_today: mean risk score for sessions collected today
    - recent_feed: last 5 sessions for the live event feed
    """
    rows = await repository.get_all_sessions(db)  # newest-first from DB

    # ── Detection stats ───────────────────────────────────────────────────────
    label_counts: Dict[str, int] = {"normal": 0, "anomaly": 0, "pending": 0}
    bot_flagged = 0
    total_events = 0

    for r in rows:
        lbl = r.anomaly_label or "pending"
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
        total_events += r.event_count or 0

    # ── Average risk today ────────────────────────────────────────────────────
    today = datetime.now(timezone.utc).date()
    today_risks = []
    for r in rows:
        if r.collected_at and r.risk_score is not None:
            # collected_at may be timezone-aware or naive depending on DB
            ts = r.collected_at
            if hasattr(ts, "date"):
                row_date = ts.date() if ts.tzinfo else ts.date()
                if row_date == today:
                    today_risks.append(r.risk_score)

    avg_risk_today = round(sum(today_risks) / len(today_risks), 4) if today_risks else 0.0

    # ── Anomaly trend (last 20, returned oldest→newest for chart) ────────────
    trend_rows = rows[:20]  # rows is newest-first; take top 20
    anomaly_trend = [
        {
            "timestamp": r.collected_at.isoformat() if r.collected_at else None,
            "score": round(r.anomaly_score or 0.0, 4),
            "risk_score": round(r.risk_score or 0.0, 4),
            "label": r.anomaly_label or "pending",
            "sessionId": r.session_id,
        }
        for r in reversed(trend_rows)   # oldest → newest
    ]

    # ── Recent feed (last 5) ──────────────────────────────────────────────────
    recent_feed = [
        {
            "userId": r.user_id,
            "sessionId": r.session_id,
            "timestamp": r.collected_at.isoformat() if r.collected_at else None,
            "label": r.anomaly_label or "pending",
            "risk_score": round(r.risk_score or 0.0, 4),
            "event_count": r.event_count or 0,
            "hijack_suspected": bool(r.hijack_suspected),
        }
        for r in rows[:5]
    ]

    return {
        "totalSessions": len(rows),
        "totalEvents": total_events,
        "detection_stats": label_counts,
        "bot_flagged": bot_flagged,
        "avg_risk_today": avg_risk_today,
        "anomaly_trend": anomaly_trend,
        "recent_feed": recent_feed,
    }


# ── Route: /fingerprint ───────────────────────────────────────────────────────
@router.get("/fingerprint")
async def get_fingerprint(user_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Return raw event data for charting the user's behavioral fingerprint."""
    from sqlalchemy import select
    from backend.db.models import Session
    query = select(Session).where(Session.user_id == user_id).order_by(Session.collected_at.desc()).limit(15)
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    all_events = []
    for sess in sessions:
        if sess.events:
            all_events.extend(sess.events)
            
    return {"status": "ok", "userId": user_id, "events": all_events}

