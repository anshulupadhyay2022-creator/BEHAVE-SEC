"""
backend/db/models.py
SQLAlchemy ORM model for the `sessions` table.
"""

import uuid

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Session(Base):
    """One row per behavioral data session collected from the frontend."""

    __tablename__ = "sessions"

    # Primary key – UUID stored as a string for broad DB compatibility
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Session identifiers
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Timing
    collected_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Device metadata
    user_agent: Mapped[str | None] = mapped_column(String(512))
    screen_width: Mapped[int | None] = mapped_column(Integer)
    screen_height: Mapped[int | None] = mapped_column(Integer)
    session_duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Aggregated event info
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_breakdown: Mapped[dict | None] = mapped_column(JSON)   # {"keydown": 45, ...}
    events: Mapped[list | None] = mapped_column(JSON)            # full event array

    # Anomaly detection output
    anomaly_label: Mapped[str | None] = mapped_column(String(32))   # "normal" / "anomaly" / "pending"
    anomaly_score: Mapped[float | None] = mapped_column(Float)
