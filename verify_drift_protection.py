import numpy as np
from backend.ml.model import AnomalyDetector
from backend.core.config import settings
import logging

# Disable logging for cleaner output
logging.basicConfig(level=logging.ERROR)

def verify_protection():
    user_id = "test_owner_123"
    detector = AnomalyDetector(user_id)
    
    # 1. Simulate Owner Enrollment (10 consistent sessions)
    print("--- Phase 1: Enrollment ---")
    owner_samples = []
    for _ in range(10):
        # Base biometric vector (22 features)
        # We'll use a fixed pattern for the owner
        fv = np.zeros(28)
        fv[6:28] = 100.0 + np.random.normal(0, 2, 22) # Mean 100
        owner_samples.append(fv)
        detector._last_fv = fv
        detector.handle_feedback(is_owner=True)
    
    print(f"Model trained on {len(detector._buffer)} owner samples.")
    print(f"Master Centroid established: {detector._master_centroid is not None}")
    
    # 2. Simulate Attacker Poisoning (Orthogonal/Very different rhythm)
    print("\n--- Phase 2: Poisoning Attempt ---")
    # Attacker has a completely different 'shape'
    attacker_fv = np.zeros(28)
    # Owner was around 100 on all 22 biometric indices.
    # Attacker will have 1000 on the first 11, and 0 on the last 11.
    attacker_fv[6:17] = 1000.0
    attacker_fv[17:28] = 0.0
    
    detector._last_fv = attacker_fv
    
    # Check similarity manually for debug
    sim = detector._calculate_similarity(attacker_fv, detector._master_centroid)
    print(f"Calculated Similarity: {sim:.4f} (Threshold: {settings.DRIFT_SIMILARITY_THRESHOLD})")
    
    res = detector.handle_feedback(is_owner=True)
    
    if res.get("status") == "mfa_required":
        print("SUCCESS: Poisoning attempt blocked! System returned 'mfa_required'.")
        print(f"Detail: {res['message']}")
    else:
        print("FAILURE: Poisoning attempt was NOT blocked.")
        print(f"Result: {res}")

    # 3. Verify Challenge Bypass
    print("\n--- Phase 3: Challenge Mode (No Protection) ---")
    challenge_detector = AnomalyDetector("challenge_hacker")
    # Enroll
    for _ in range(10):
        fv = np.zeros(28)
        fv[6:28] = 100.0 + np.random.normal(0, 2, 22)
        challenge_detector._last_fv = fv
        challenge_detector.handle_feedback(is_owner=True)
    
    # Poison
    challenge_detector._last_fv = attacker_fv
    res_challenge = challenge_detector.handle_feedback(is_owner=True)
    
    if res_challenge.get("success") == True:
        print("SUCCESS: Challenge mode bypassed drift check as requested (for demo).")
    else:
        print("FAILURE: Challenge mode blocked the update unintentionally.")

if __name__ == "__main__":
    verify_protection()
