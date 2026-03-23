import numpy as np
from sklearn.svm import OneClassSVM

np.random.seed(42)
# Simulate 10 owner sessions (8 features: 6 to 14 from the array)
X_train = np.random.normal(loc=[80, 10, 200, 20, 0, 0, 15000, 1.5], scale=[10, 2, 20, 5, 0, 0, 500, 0.1], size=(10, 8))

# Simulate 1 Owner test
X_owner = np.random.normal(loc=[80, 10, 200, 20, 0, 0, 15000, 1.5], scale=[10, 2, 20, 5, 0, 0, 500, 0.1], size=(1, 8))

# Simulate 1 Friend test (very different rhythm)
X_friend = np.random.normal(loc=[120, 15, 350, 40, 0, 0, 25000, 0.8], scale=[10, 2, 20, 5, 0, 0, 500, 0.1], size=(1, 8))

model = OneClassSVM(kernel="rbf", nu=0.1, gamma="scale")
model.fit(X_train)

raw_train = model.decision_function(X_train)
raw_owner = model.decision_function(X_owner)
raw_friend = model.decision_function(X_friend)

print("Raw Train:", raw_train)
print("Raw Owner:", raw_owner)
print("Raw Friend:", raw_friend)

def sigmoid(raw):
    return float(1.0 / (1.0 + np.exp(5.0 * raw)))

print("Owner Normalised:", sigmoid(raw_owner[0]))
print("Friend Normalised:", sigmoid(raw_friend[0]))
