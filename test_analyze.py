import requests
import json
import time
import random

payload = {
    "userId": "challenge_user_12345",
    "sessionId": f"train_sess_0_{int(time.time()*1000)}",
    "events": [
        {
            "eventType": "keydown",
            "timestamp": int(time.time()*1000),
            "relativeTime": 0,
            "key": "a",
            "keyCode": 65
        } for _ in range(30)
    ],
    "metadata": {
        "userAgent": "TestAgent",
        "screenWidth": 1920,
        "screenHeight": 1080,
        "sessionDuration": 5000
    }
}

try:
    print("Sending POST request to /analyze...")
    res = requests.post('http://localhost:8000/analyze', json=payload, timeout=5)
    print("Response matched:", res.status_code)
    print("Response text:", res.text)
except Exception as e:
    print("Exception occurred:", type(e).__name__, str(e))
