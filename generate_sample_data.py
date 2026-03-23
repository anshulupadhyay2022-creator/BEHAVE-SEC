import json
import time
import random
import uuid
import sys
import os
from pathlib import Path

# Add the project root to sys.path so we can import backend
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.models.schemas import BehavioralEvent, SessionMetadata, BehavioralDataPayload
from backend.ml.model import model_manager

def generate_session_events(is_anomalous=False):
    events = []
    num_events = random.randint(50, 200) if not is_anomalous else random.randint(20, 50)
    current_time = int(time.time() * 1000)
    
    # ── Parameters ──
    # Normal user types smoothly and moves mouse steadily.
    # Anomalous user types erratically, either very slow or highly varied.
    base_inter_key_ms = random.randint(100, 300) if not is_anomalous else random.randint(400, 1500)
    key_hold_ms = random.randint(30, 80) if not is_anomalous else random.randint(10, 200)
    mouse_speed = random.randint(1, 5) if not is_anomalous else random.randint(10, 50)
    
    x, y = 100, 100
    
    for i in range(num_events):
        event_type = random.choices(
            ["keydown", "keyup", "mousemove", "click", "scroll"],
            weights=[0.3, 0.3, 0.3, 0.05, 0.05]
        )[0]
        
        # Add jitter
        jitter = random.randint(-20, 20) if not is_anomalous else random.randint(-100, 400)
        current_time += abs(base_inter_key_ms + jitter)

        event_data = {
            "eventType": event_type,
            "timestamp": current_time,
            "relativeTime": current_time - (current_time - i * base_inter_key_ms)
        }

        if event_type in ["keydown", "keyup"]:
            event_data["key"] = random.choice(["a", "b", "c", "Enter", "Space"])
            event_data["keyCode"] = 65
        elif event_type == "mousemove":
            x += mouse_speed * random.choice([1, -1]) + (random.randint(-5, 5) if is_anomalous else random.randint(-1, 1))
            y += mouse_speed * random.choice([1, -1]) + (random.randint(-5, 5) if is_anomalous else random.randint(-1, 1))
            event_data["clientX"] = max(0, min(1920, int(x)))
            event_data["clientY"] = max(0, min(1080, int(y)))
        elif event_type == "click":
            event_data["target"] = "button"
        elif event_type == "scroll":
            event_data["scrollY"] = random.randint(0, 1000)

        events.append(BehavioralEvent(**event_data))

    return events

def create_payload(events, user_id=None):
    return BehavioralDataPayload(
        userId=user_id or str(uuid.uuid4()),
        sessionId=str(uuid.uuid4()),
        events=events,
        metadata=SessionMetadata(
            userAgent="Mozilla/5.0",
            screenWidth=1920,
            screenHeight=1080,
            sessionDuration=events[-1].timestamp - events[0].timestamp if len(events) > 1 else 1000
        )
    )

def main():
    print("Generating sample data to train the Isolation Forest model...")
    num_normal = 12
    num_anomalous = 3
    
    payloads = []
    
    user1_id = "user-normal-100"
    user2_id = "user-anomalous-200"
    
    # Generate Normal Profiles
    for _ in range(num_normal):
        events = generate_session_events(is_anomalous=False)
        payloads.append(create_payload(events, user_id=user1_id))
        
    # Generate Anomalous Profiles
    for _ in range(num_anomalous):
        events = generate_session_events(is_anomalous=True)
        payloads.append(create_payload(events, user_id=user2_id))

    # Shuffle the payloads to mix normal and anomalous data
    random.shuffle(payloads)
    
    # Save a couple to disk so the user can inspect them
    with open("sample_normal_payload.json", "w") as f:
        f.write(payloads[0].model_dump_json(indent=2))
        
    with open("sample_anomalous_payload.json", "w") as f:
        # Find one anomalous
        anom = [p for p in payloads if len(p.events) < 55][0]
        f.write(anom.model_dump_json(indent=2))

    print("Saved sample JSON files to 'sample_normal_payload.json' and 'sample_anomalous_payload.json'")
    
    print(f"\nTraining model with {len(payloads)} sessions...")
    for payload in payloads:
        user_detector = model_manager.get_detector(payload.userId)
        res = user_detector.ingest(payload)
        status = user_detector.status
        print(f"Session ingested for user {payload.userId}. Model trained: {status['trained']} (Buffer: {status['samples_in_buffer']}/{status['min_samples_to_train']})")
        
    print("\nModel status after ingestion (for first user):")
    first_user_detector = model_manager.get_detector(payloads[0].userId)
    final_status = first_user_detector.status
    for k, v in final_status.items():
        print(f"  {k}: {v}")

    print("\nTraining complete! The ML model is now trained and saved in your data/model directory.")

if __name__ == "__main__":
    main()
