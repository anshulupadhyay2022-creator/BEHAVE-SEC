# Walkthrough - Global Mouse Kinematics Bot Check

Following your directive, I have implemented an immediate, "Zero-Day" bot protection mechanism that leverages the mouse **curvature ratio** (path directness) to catch intruders/scripts on the *very first login snippet*.

This system acts as a deterministic "Global Mouse Baseline" that perfectly complements our existing Global Keystroke Rhythm model.

## Key Technical Updates

### 1. Robust Curve Engine upgrade
`backend/ml/features.py` (Feature #24)
- **Before:** The curve ratio (`path_directness_ratio`) was only calculated *between* repeated sequence clicks, meaning a single "Sign In" click wouldn't have a trackable curve.
- **After:** The engine now tracks the overarching session trajectory. It calculates the geometrically perfect straight line from the very first mouse wiggle to your final click, and divides that by the sum of every tiny, curving pixel movement your hand actually made.

### 2. Global Bot Tripwire
`backend/ml/model.py` (AnomalyDetector)
- A deterministic security tripwire has been placed inside `verify_login_signature` and `ingest`. 
- **The Rule:** If the session involves over 10 raw mouse movements and the resulting path curvature ratio is `≥ 0.999` (meaning the path was 99.9% aligned with a perfect geometric straight line), the system immediately overrides all other metrics and flags the session as a **Bot**.
- **Impact:** An attacker attempting to inject a straight-line Selenium or PyAutoGUI script will be blocked with extreme prejudice, *even if the account has no prior behavioral training*.

## Results & Next Steps
- The Global Bot Protection module now tracks **both Keystroke Rhythm and Mouse Kinematic Curves**.
- Try interacting with the dashboard or login page using a programmatic script to move the mouse to the target. The system will throw an immediate kinematic anomaly alert!
