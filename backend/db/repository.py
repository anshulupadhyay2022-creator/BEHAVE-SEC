"""
backend/db/repository.py
Async CRUD helpers – thin wrappers around the ORM so routes stay clean.
"""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Session as SessionRow
from backend.db.models import User as UserRow


# ── Write ────────────────────────────────────────────────────────────────────

async def save_session(
    db: AsyncSession,
    payload: Any,          # BehavioralDataPayload
    anomaly_result: Dict[str, Any],
    event_counts: Dict[str, int],
    ip_address: str | None = None,
    risk_score: float | None = None,
    hijack_suspected: bool = False,
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
        ip_address=ip_address,
        risk_score=risk_score,
        hijack_suspected=hijack_suspected,
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

async def get_last_session_by_user(db: AsyncSession, user_id: str) -> SessionRow | None:
    """Return the most recent session for a given user."""
    result = await db.execute(
        select(SessionRow).where(SessionRow.user_id == user_id).order_by(SessionRow.collected_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


# ── Users ────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> UserRow | None:
    """Look up a user by email."""
    result = await db.execute(select(UserRow).where(UserRow.email == email))
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: str) -> UserRow | None:
    """Look up a user by id."""
    result = await db.execute(select(UserRow).where(UserRow.id == user_id))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, full_name: str, email: str, password_hash: str) -> UserRow:
    """Create a new user and return it."""
    row = UserRow(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row

async def update_user(db: AsyncSession, user: UserRow) -> UserRow:
    """Update user (e.g., OTP or locked_out state)."""
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

