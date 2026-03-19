"""
backend/core/config.py
Application-wide settings loaded from environment variables (or .env via init_backend.py).
"""

import os


class Settings:
    """Central configuration object.  All values come from environment variables."""

    # Directory where JSON/CSV session files are saved
    DATA_DIR: str = os.environ.get("DATA_DIR", "data/behavioral")

    # Directory where trained ML model files are saved
    MODEL_DIR: str = os.environ.get("MODEL_DIR", "data/model")

    # Comma-separated list of allowed CORS origins, or '*' for any
    CORS_ORIGINS: list[str] = os.environ.get("CORS_ORIGINS", "*").split(",")

    # Database URL — SQLite for local dev, PostgreSQL for production
    # Override by setting DATABASE_URL in .env
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/behave_sec.db",  # local default
    )

    # Uvicorn / server settings (used by init_backend.py; kept here for reference)
    HOST: str = os.environ.get("BACKEND_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("BACKEND_PORT", "8000"))
    WORKERS: int = int(os.environ.get("BACKEND_WORKERS", "1"))


# Singleton instance – import this everywhere
settings = Settings()

# Ensure runtime directories exist when this module is first imported
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.MODEL_DIR, exist_ok=True)
