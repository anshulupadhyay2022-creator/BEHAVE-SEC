"""
backend/api/routes/stats.py
GET /stats  — returns aggregate statistics for all received sessions.

The in-memory store list is defined here and imported by behavioral.py
so both routes operate on the same data without circular imports.
/stats reads from the DATABASE so data survives server restarts.
The in-memory store is kept as a fast cache for the current process.
"""

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


# ── Route ─────────────────────────────────────────────────────────────────────
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
