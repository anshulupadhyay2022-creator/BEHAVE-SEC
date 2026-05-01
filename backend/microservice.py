from fastapi import FastAPI, HTTPException
from backend.models.schemas import BehavioralDataPayload
from backend.ml.model import model_manager
import logging

from fastapi.middleware.cors import CORSMiddleware
import logging

app = FastAPI(title="BEHAVE-SEC ML Node", description="Python Microservice for Isolation Forest execution")
logger = logging.getLogger(__name__)

# Add CORS so frontend can hit port 8000 directly if C# proxy is bypassed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze_behavior(payload: BehavioralDataPayload):
    try:
        user_detector = model_manager.get_detector(payload.userId)
        # ingest extracts features, trains if needed, and returns scores
        anomaly_result = user_detector.ingest(payload)
        return {"anomaly": anomaly_result}
    except Exception as exc:
        logger.error(f"Analysis failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/model/feedback")
async def model_feedback(data: dict):
    user_id = data.get("userId")
    is_owner = data.get("isOwner")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing userId")
    try:
        user_detector = model_manager.get_detector(user_id)
        result = user_detector.handle_feedback(is_owner)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
