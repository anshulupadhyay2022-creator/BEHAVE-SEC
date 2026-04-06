"""
backend/api/routes/analyze.py
Dedicated ML endpoints:

    POST /analyze           – score a behavioral payload (returns label + score)
    GET  /model/status      – current detector state
    POST /model/retrain     – force retrain on all buffered data
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ml.model import model_manager
from backend.models.schemas import BehavioralDataPayload, FeedbackPayload
from backend.db.engine import AsyncSessionLocal
from backend.db.repository import get_user_by_email, get_user_by_id, update_user
from backend.api.routes.auth import generate_and_send_otp
import datetime as dt
from datetime import timezone


router = APIRouter()


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/analyze")
async def analyze_session(payload: BehavioralDataPayload) -> Dict[str, Any]:
    """
    Extract behavioral features from *payload* and return an anomaly verdict.

    The session is NOT persisted to disk here — use POST /collect-data for that.
    This endpoint is useful for on-demand analysis of arbitrary payloads.
    """
    user_detector = model_manager.get_detector(payload.userId)
    result = user_detector.ingest(payload)
    return {
        "status": "ok",
        "userId": payload.userId,
        "sessionId": payload.sessionId,
        "totalEvents": len(payload.events),
        "anomaly": result,
    }


@router.get("/model/status")
async def model_status(user_id: str) -> Dict[str, Any]:
    """Return the current training state of a specific user's anomaly detector."""
    user_detector = model_manager.get_detector(user_id)
    return {"status": "ok", "detector": user_detector.status}


@router.post("/model/retrain")
async def retrain_model(user_id: str) -> Dict[str, Any]:
    """Trigger an explicit retrain on a specific user's buffered session data."""
    user_detector = model_manager.get_detector(user_id)
    result = user_detector.retrain()
    return {"status": "ok", "retrain": result}


@router.post("/model/feedback")
async def submit_feedback(payload: FeedbackPayload, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Submit feedback on the last analyzed session.
    Controls the active learning loop with a "Poisoning Guard" (Centroid Matching).
    """
    user_detector = model_manager.get_detector(payload.userId)
    
    # If isOwner is provided explicitly, use it. Else fallback to isCorrect loop logic.
    is_owner = payload.isOwner if payload.isOwner is not None else (not payload.isCorrect)
    
    # Attempt to apply feedback
    result = user_detector.handle_feedback(is_owner=is_owner, bypass_drift=payload.bypassDrift)
    
    # If a behavioral drift was detected, trigger the OTP flow (for non-challenge users)
    if result.get("status") == "mfa_required":
        # Look up user by ID (preferred) or Email
        user = await get_user_by_id(db, payload.userId)
        if not user:
            user = await get_user_by_email(db, payload.userId)
            
        if user:
            # Generate and send OTP (mocked in console)
            otp = generate_and_send_otp(user.email)
            user.otp_code = otp
            user.otp_expires_at = dt.datetime.now(timezone.utc) + dt.timedelta(minutes=10)
            user.locked_out = True
            await update_user(db, user)
            
            raise HTTPException(
                status_code=403, 
                detail={
                    "status": "mfa_required",
                    "email": user.email,
                    "message": "Behavioral drift detected. Account locked for safety. Please verify OTP to authorize this update."
                }
            )
            
    return {"status": "ok", "feedback": result}

