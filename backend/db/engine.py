"""
backend/db/engine.py
Async SQLAlchemy engine + session factory.

DATABASE_URL examples
  SQLite (local dev – zero-config):
      sqlite+aiosqlite:///./data/behave_sec.db
  PostgreSQL (production):
      postgresql+asyncpg://user:password@host:5432/behave_sec
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # set True to log every SQL statement for debugging
    future=True,
)

# ── Session factory ──────────────────────────────────────────────────────────
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
