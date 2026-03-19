"""
backend/utils/storage.py
Helper functions for persisting behavioral data to disk (JSON and CSV).
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from backend.core.config import settings
from backend.models.schemas import BehavioralDataPayload

# Resolve DATA_DIR to an absolute path anchored at the project root
# (two levels up from this file: backend/utils/ → backend/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = (_PROJECT_ROOT / settings.DATA_DIR).resolve()
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_to_json(payload: BehavioralDataPayload) -> str:
    """Serialize the full payload to a JSON file and return the file path."""
    filename = str(_DATA_DIR / f"session_{payload.sessionId}.json")
    data = {
        "userId": payload.userId,
        "sessionId": payload.sessionId,
        "collectedAt": datetime.now().isoformat(),
        "metadata": payload.metadata.model_dump(),
        "events": [event.model_dump() for event in payload.events],
    }
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return filename


def save_to_csv(payload: BehavioralDataPayload) -> str:
    """Write each event as a CSV row and return the file path."""
    filename = str(_DATA_DIR / f"session_{payload.sessionId}.csv")
    fieldnames = [
        "Event Type", "Timestamp", "Relative Time (ms)",
        "Key", "Key Code", "Client X", "Client Y",
        "Page X", "Page Y", "Scroll X", "Scroll Y",
        "Target Element", "Target ID", "Target Name",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for event in payload.events:
            writer.writerow({
                "Event Type": event.eventType,
                "Timestamp": datetime.fromtimestamp(event.timestamp / 1000).isoformat(),
                "Relative Time (ms)": event.relativeTime,
                "Key": event.key or "",
                "Key Code": event.keyCode or "",
                "Client X": event.clientX or "",
                "Client Y": event.clientY or "",
                "Page X": event.pageX or "",
                "Page Y": event.pageY or "",
                "Scroll X": event.scrollX or "",
                "Scroll Y": event.scrollY or "",
                "Target Element": event.target or "",
                "Target ID": event.targetId or "",
                "Target Name": event.targetName or "",
            })
    return filename
