"""
verify_features.py
Quick verification that the new 22-feature extractor and model work end-to-end.
"""
import requests
import time
import random

def generate_payload(user_id, session_id, base_speed, hold_mean):
    events = []
    base_time = int(time.time() * 1000)
    current_time = base_time
    
    phrase = "The quick brown fox jumps over the lazy dog."
    for char in phrase:
        events.append({
            "eventType": "keydown",
            "timestamp": int(current_time),
            "relativeTime": int(current_time - base_time),
            "key": char,
            "keyCode": ord(char)
        })
        hold = random.gauss(hold_mean, 10)
        current_time += max(hold, 5)
        events.append({
            "eventType": "keyup",
            "timestamp": int(current_time),
            "relativeTime": int(current_time - base_time),
            "key": char,
            "keyCode": ord(char)
        })
        flight = random.gauss(base_speed, 20)
        current_time += max(flight, 5)
        
    return {
        "userId": user_id,
        "sessionId": session_id,
        "events": events,
        "metadata": {
            "userAgent": "TestAgent",
            "screenWidth": 1920,
            "screenHeight": 1080,
            "sessionDuration": int(current_time - base_time)
        }
    }

user_id = "verify_user_" + str(int(time.time()))

# Train: 15 sessions with owner's rhythm
print("Training 15 sessions...")
for i in range(15):
    speed_factor = random.uniform(0.90, 1.10)
    p = generate_payload(user_id, f"train_{i}", 140 * speed_factor, 80 * speed_factor)
    res = requests.post("http://localhost:8000/analyze", json=p)
    data = res.json()
    status = data.get('anomaly', {}).get('label', 'error')
    if i == 14:
        print(f"  Session {i}: {status} (score={data.get('anomaly',{}).get('score', 'N/A')})")

# Test owner (should be normal, low score)
print("\nTesting OWNER (should be normal)...")
for i in range(5):
    speed_factor = random.uniform(0.90, 1.10)
    p = generate_payload(user_id, f"owner_test_{i}", 140 * speed_factor, 80 * speed_factor)
    res = requests.post("http://localhost:8000/analyze", json=p)
    data = res.json()
    anom = data.get('anomaly', {})
    print(f"  Owner test {i}: label={anom.get('label')} score={anom.get('score')}")

# Test intruder (should be anomaly, high score)
print("\nTesting INTRUDER (should be anomaly)...")
for i in range(5):
    speed_factor = random.uniform(0.85, 1.15)
    p = generate_payload(user_id, f"intruder_test_{i}", 300 * speed_factor, 120 * speed_factor)
    res = requests.post("http://localhost:8000/analyze", json=p)
    data = res.json()
    anom = data.get('anomaly', {})
    print(f"  Intruder test {i}: label={anom.get('label')} score={anom.get('score')}")
