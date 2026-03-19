"""
backend/db/repository.py
Async CRUD helpers – thin wrappers around the ORM so routes stay clean.
"""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Session as SessionRow


# ── Write ────────────────────────────────────────────────────────────────────

async def save_session(
    db: AsyncSession,
    payload: Any,          # BehavioralDataPayload
    anomaly_result: Dict[str, Any],
    event_counts: Dict[str, int],
) -> SessionRow:
    """Insert a new session row and return it."""
    meta = payload.metadata

    row = SessionRow(
        user_id=payload.userId,
        session_id=payload.sessionId,
        user_agent=getattr(meta, "userAgent", None),
        screen_width=getattr(meta, "screenWidth", None),
        screen_height=getattr(meta, "screenHeight", None),
        session_duration_ms=getattr(meta, "sessionDuration", None),
        event_count=len(payload.events),
        event_breakdown=event_counts,
        events=[e.model_dump() for e in payload.events],
        anomaly_label=anomaly_result.get("label"),
        anomaly_score=anomaly_result.get("score"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Read ─────────────────────────────────────────────────────────────────────

async def get_all_sessions(db: AsyncSession) -> List[SessionRow]:
    """Return all session rows ordered newest-first."""
    result = await db.execute(select(SessionRow).order_by(SessionRow.collected_at.desc()))
    return list(result.scalars().all())


async def get_session_by_id(db: AsyncSession, session_id: str) -> SessionRow | None:
    """Return a single session by its session_id, or None if not found."""
    result = await db.execute(
        select(SessionRow).where(SessionRow.session_id == session_id)
    )
    return result.scalar_one_or_none()
