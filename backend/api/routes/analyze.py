"""
backend/api/routes/analyze.py
Dedicated ML endpoints:

    POST /analyze           – score a behavioral payload (returns label + score)
    GET  /model/status      – current detector state
    POST /model/retrain     – force retrain on all buffered data
"""

from typing import Any, Dict

from fastapi import APIRouter

from backend.ml.model import detector
from backend.models.schemas import BehavioralDataPayload

router = APIRouter()


@router.post("/analyze")
async def analyze_session(payload: BehavioralDataPayload) -> Dict[str, Any]:
    """
    Extract behavioral features from *payload* and return an anomaly verdict.

    The session is NOT persisted to disk here — use POST /collect-data for that.
    This endpoint is useful for on-demand analysis of arbitrary payloads.
    """
    result = detector.ingest(payload)
    return {
        "status": "ok",
        "userId": payload.userId,
        "sessionId": payload.sessionId,
        "totalEvents": len(payload.events),
        "anomaly": result,
    }


@router.get("/model/status")
async def model_status() -> Dict[str, Any]:
    """Return the current training state of the anomaly detector."""
    return {"status": "ok", "detector": detector.status}


@router.post("/model/retrain")
async def retrain_model() -> Dict[str, Any]:
    """Trigger an explicit retrain on all buffered session data."""
    result = detector.retrain()
    return {"status": "ok", "retrain": result}
