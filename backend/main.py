"""
backend/main.py
FastAPI application factory for BEHAVE-SEC.

Start via:
    uvicorn backend.main:app --reload
or through the project's init_backend.py initializer.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.api.routes import router
from backend.db.engine import engine, AsyncSessionLocal
from backend.db.models import Base
from backend.db.repository import get_user_by_email, create_user
from backend.core.security import get_password_hash


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run CREATE TABLE IF NOT EXISTS on startup (dev-friendly, no manual migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] Tables ready.")

    # Auto-create admin user for testing
    async with AsyncSessionLocal() as session:
        existing = await get_user_by_email(session, "admin@behave.sec")
        if not existing:
            await create_user(session, "Admin User", "admin@behave.sec", get_password_hash("password"))
            print("[DB] Created default 'admin@behave.sec' user.")

    yield
    # Optional: close engine on shutdown
    await engine.dispose()


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    application = FastAPI(
        title="BEHAVE-SEC API",
        description="Backend API for collecting and analysing behavioral biometric data.",
        version="2.0.0",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Root health-check ────────────────────────────────────
    @application.get("/")
    async def root() -> Dict[str, Any]:
        return {
            "message": "BEHAVE-SEC API is running",
            "version": "2.0.0",
            "status": "operational",
            "endpoints": {
                "collect_data": "POST /collect-data",
                "get_stats": "GET /stats",
            },
        }

    # ── API routes ───────────────────────────────────────────
    application.include_router(router)

    return application


# Module-level app instance used by Uvicorn
app = create_app()
