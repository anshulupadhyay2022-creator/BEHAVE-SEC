import requests
import time
import random

def generate_payload(user_id, session_id, base_speed, hold_mean):
    events = []
    base_time = int(time.time() * 1000)
    current_time = base_time
    
    phrase = "The quick brown fox jumps over the lazy dog."
    for char in phrase:
        # Keydown
        events.append({
            "eventType": "keydown",
            "timestamp": int(current_time),
            "relativeTime": int(current_time - base_time),
            "key": char,
            "keyCode": ord(char)
        })
        
        # Hold time
        hold = random.gauss(hold_mean, 10)
        current_time += hold
        
        # Keyup
        events.append({
            "eventType": "keyup",
            "timestamp": int(current_time),
            "relativeTime": int(current_time - base_time),
            "key": char,
            "keyCode": ord(char)
        })
        
        # Flight time to next key
        flight = random.gauss(base_speed, 20)
        current_time += flight
        
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

user_id = "test_user_999"

# Training data: 10 sessions with 200ms flight, 80ms hold
train_payloads = [generate_payload(user_id, f"train_{i}", 200, 80) for i in range(10)]

for p in train_payloads:
    res = requests.post("http://localhost:8000/analyze", json=p)
    if res.json().get('anomaly', {}).get('label') != 'pending':
        print("Trained.")

# Test data 1: exact same distribution (The Owner)
owner_test = generate_payload(user_id, "test_owner", 200, 80)
res_owner = requests.post("http://localhost:8000/analyze", json=owner_test).json()
print("Owner Test:", res_owner)

# Test data 2: different distribution (The Friend)
friend_test = generate_payload(user_id, "test_friend", 350, 120)  # Much slower
res_friend = requests.post("http://localhost:8000/analyze", json=friend_test).json()
print("Friend Test:", res_friend)
