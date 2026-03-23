import numpy as np
from sklearn.ensemble import IsolationForest

# Simulate 10 training samples (inliers) with small variance
np.random.seed(42)
X_train = np.random.normal(loc=[100, 20, 150, 30, 0, 0, 10000, 2], scale=[5, 1, 10, 2, 0, 0, 500, 0.1], size=(10, 8))

# Simulate 1 outlier (the friend) with different properties
X_test = np.array([[150, 40, 200, 50, 0, 0, 14000, 1.5]])

model = IsolationForest(
    n_estimators=100,
    contamination="auto",
    random_state=42,
    n_jobs=1
)
model.fit(X_train)

raw_train = model.decision_function(X_train)
raw_test = model.decision_function(X_test)

print("Train raw scores:", raw_train)
print("Test raw score:", raw_test)

def normalize(raw):
    return float(np.clip(-raw + 0.5, 0.0, 1.0))

print("Train normalized:", [normalize(r) for r in raw_train])
print("Test normalized:", [normalize(r) for r in raw_test])
