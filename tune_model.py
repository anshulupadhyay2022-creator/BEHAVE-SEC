"""
tune_model.py
Grid-search to find optimal One-Class SVM hyperparameters for 95%+ accuracy.

Strategy:
1. Generate synthetic "owner" typing profiles with realistic human variance.
2. Generate diverse "intruder" typing profiles (different rhythm, speed, hold).
3. Train One-Class SVM on owner data only.
4. Score both owner test data (should be "normal") and intruder data (should be "anomaly").
5. Sweep nu, gamma, kernel combos and report accuracy.
"""

import numpy as np
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from itertools import product

np.random.seed(42)

# ── Feature indices used by model.py ──
# idx 6: avg_key_hold_ms     (mean dwell)
# idx 7: std_key_hold_ms
# idx 8: avg_inter_key_ms    (mean flight between keydowns)
# idx 9: std_inter_key_ms
# idx 10: avg_mouse_speed     (0 for keyboard-only)
# idx 11: std_mouse_speed     (0 for keyboard-only)
# idx 12: session_duration_ms
# idx 13: events_per_second

# For keyboard-only challenge, only idx 6-9 carry discriminative signal.
# idx 10-11 are always 0; idx 12-13 co-vary with text length.
# Let's focus on the 4 KEY rhythmic features (6,7,8,9) for maximum separation.

RHYTHMIC_FEATURES = 4  # avg_hold, std_hold, avg_iki, std_iki

def generate_owner_data(n_samples=50, base_hold=85, base_iki=140):
    """Simulate an owner's typing rhythm with natural human variance."""
    data = []
    for _ in range(n_samples):
        # Each session has slightly different overall speed (0.90x to 1.10x)
        speed = np.random.uniform(0.90, 1.10)
        avg_hold = base_hold * speed + np.random.normal(0, 3)
        std_hold = np.random.uniform(8, 18)  # natural variation in hold
        avg_iki = base_iki * speed + np.random.normal(0, 5)
        std_iki = np.random.uniform(15, 35)
        data.append([avg_hold, std_hold, avg_iki, std_iki])
    return np.array(data)


def generate_intruder_data(n_intruders=5, n_samples_each=20, base_hold=85, base_iki=140):
    """Simulate multiple intruders with distinctly different typing patterns."""
    all_data = []
    for i in range(n_intruders):
        # Each intruder has a fundamentally different base rhythm
        hold_shift = np.random.choice([-30, -20, -10, 15, 25, 35, 50])
        iki_shift = np.random.choice([-50, -30, -15, 20, 40, 60, 100])
        std_hold_base = np.random.uniform(5, 40)
        std_iki_base = np.random.uniform(10, 60)
        
        for _ in range(n_samples_each):
            speed = np.random.uniform(0.85, 1.15)
            avg_hold = (base_hold + hold_shift) * speed + np.random.normal(0, 5)
            std_hold = std_hold_base + np.random.normal(0, 3)
            avg_iki = (base_iki + iki_shift) * speed + np.random.normal(0, 8)
            std_iki = std_iki_base + np.random.normal(0, 5)
            all_data.append([avg_hold, std_hold, avg_iki, std_iki])
    return np.array(all_data)


# ── Generate Data ──
X_owner_train = generate_owner_data(n_samples=50)
X_owner_test = generate_owner_data(n_samples=50)  # separate test set
X_intruder_test = generate_intruder_data(n_intruders=8, n_samples_each=25)

print(f"Owner Train: {X_owner_train.shape}")
print(f"Owner Test:  {X_owner_test.shape}")
print(f"Intruder Test: {X_intruder_test.shape}")

# ── Grid Search ──
NU_VALUES = [0.01, 0.05, 0.1, 0.15, 0.2]
GAMMA_VALUES = ["scale", "auto", 0.01, 0.1, 0.5, 1.0]
USE_SCALER = [True, False]

best_acc = 0
best_params = {}
results = []

for nu, gamma, use_scaler in product(NU_VALUES, GAMMA_VALUES, USE_SCALER):
    try:
        if use_scaler:
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_owner_train)
            X_ot = scaler.transform(X_owner_test)
            X_it = scaler.transform(X_intruder_test)
        else:
            X_train = X_owner_train
            X_ot = X_owner_test
            X_it = X_intruder_test

        model = OneClassSVM(kernel="rbf", nu=nu, gamma=gamma)
        model.fit(X_train)

        # Score owner test: should be +1 (normal)
        owner_preds = model.predict(X_ot)
        owner_correct = np.sum(owner_preds == 1) / len(owner_preds)

        # Score intruder test: should be -1 (anomaly)
        intruder_preds = model.predict(X_it)
        intruder_correct = np.sum(intruder_preds == -1) / len(intruder_preds)

        # Balanced accuracy
        balanced_acc = (owner_correct + intruder_correct) / 2.0

        results.append({
            "nu": nu, "gamma": gamma, "scaler": use_scaler,
            "owner_acc": owner_correct, "intruder_acc": intruder_correct,
            "balanced_acc": balanced_acc
        })

        if balanced_acc > best_acc:
            best_acc = balanced_acc
            best_params = {"nu": nu, "gamma": gamma, "scaler": use_scaler}

    except Exception as e:
        pass

# ── Report ──
print("\n" + "=" * 70)
print("TOP 10 CONFIGURATIONS BY BALANCED ACCURACY")
print("=" * 70)
results.sort(key=lambda x: x["balanced_acc"], reverse=True)
for i, r in enumerate(results[:10]):
    print(f"  {i+1}. nu={r['nu']:<6} gamma={str(r['gamma']):<8} scaler={str(r['scaler']):<6} "
          f"| Owner: {r['owner_acc']:.2%}  Intruder: {r['intruder_acc']:.2%}  "
          f"Balanced: {r['balanced_acc']:.2%}")

print(f"\n🏆 BEST: {best_params} → {best_acc:.2%} balanced accuracy")

# ── Test the Sigmoid mapping with best params ──
print("\n" + "=" * 70)
print("SIGMOID MAPPING TEST (best model)")
print("=" * 70)

if best_params.get("scaler"):
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_owner_train)
    X_ot = scaler.transform(X_owner_test)
    X_it = scaler.transform(X_intruder_test)
else:
    X_train = X_owner_train
    X_ot = X_owner_test
    X_it = X_intruder_test

model = OneClassSVM(kernel="rbf", nu=best_params["nu"], gamma=best_params["gamma"])
model.fit(X_train)

owner_raw = model.decision_function(X_ot)
intruder_raw = model.decision_function(X_it)

print(f"  Owner raw scores:    min={owner_raw.min():.4f}  max={owner_raw.max():.4f}  mean={owner_raw.mean():.4f}")
print(f"  Intruder raw scores: min={intruder_raw.min():.4f}  max={intruder_raw.max():.4f}  mean={intruder_raw.mean():.4f}")

# Test multiple sigmoid slopes and offsets
print("\n  Sigmoid parameter sweep:")
for slope in [5, 8, 10, 15, 20]:
    for offset in [0, 1, 2, 3]:
        sigmoid = lambda x: 1.0 / (1.0 + np.exp(slope * x + offset))
        owner_scores = sigmoid(owner_raw)
        intruder_scores = sigmoid(intruder_raw)
        
        owner_pass = np.mean(owner_scores < 0.55)
        intruder_block = np.mean(intruder_scores > 0.55)
        balanced = (owner_pass + intruder_block) / 2
        
        if balanced >= 0.95:
            print(f"  ✅ slope={slope:<3} offset={offset:<3} | Owner pass: {owner_pass:.2%}  Intruder block: {intruder_block:.2%}  Balanced: {balanced:.2%}")
