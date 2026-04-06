import requests, time, random

uid = "e2e_test_" + str(int(time.time()))
base = int(time.time() * 1000)

for i in range(15):
    evts = []
    t = base
    for c in "hello world test":
        evts.append({"eventType": "keydown", "timestamp": int(t), "relativeTime": int(t - base), "key": c, "keyCode": ord(c)})
        t += random.gauss(80, 10)
        evts.append({"eventType": "keyup", "timestamp": int(t), "relativeTime": int(t - base), "key": c, "keyCode": ord(c)})
        t += random.gauss(120, 20)
    p = {"userId": uid, "sessionId": f"s{i}", "events": evts, "metadata": {"userAgent": "t", "screenWidth": 1920, "screenHeight": 1080, "sessionDuration": int(t - base)}}
    r = requests.post("http://localhost:8000/analyze", json=p)
    d = r.json()
    a = d["anomaly"]
    print(f"  {i}: label={a['label']} score={a['score']} ready={a['model_ready']} samples={a['samples_collected']}")
