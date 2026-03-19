"""
Aggregate all API routers into a single combined router.
Import this in backend/main.py with:
    from backend.api.routes import router
"""

from fastapi import APIRouter

from backend.api.routes.behavioral import router as behavioral_router
from backend.api.routes.stats import router as stats_router
from backend.api.routes.analyze import router as analyze_router
from backend.api.routes.auth import router as auth_router
from backend.api.routes.ws import router as ws_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth")
router.include_router(ws_router)
router.include_router(behavioral_router)
router.include_router(stats_router)
router.include_router(analyze_router)
