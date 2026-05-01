import os
import requests
import pandas as pd
import numpy as np
import joblib
from io import StringIO
from sklearn.svm import OneClassSVM
from pathlib import Path

# Constants
CSV_URL = "https://raw.githubusercontent.com/rakshithca/KeyStroke-Dynamics/master/keystroke.csv"
MODEL_DIR = "d:/BEHAVE SEC/data/behavioral"
OUTPUT_MODEL = os.path.join(MODEL_DIR, "global_human_model.pkl")
N_FEATURES = 28

def download_data():
    print(f"Downloading CMU Keystroke Dataset from: {CSV_URL}")
    response = requests.get(CSV_URL)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))

def process_to_features(df):
    print("Mapping CSV columns to BEHAVE-SEC 28-feature format...")
    
    # Identify column groups
    h_cols = [c for c in df.columns if c.startswith('H.')]
    dd_cols = [c for c in df.columns if c.startswith('DD.')]
    ud_cols = [c for c in df.columns if c.startswith('UD.')]
    
    feature_vectors = []
    
    for _, row in df.iterrows():
        fv = np.zeros(N_FEATURES)
        
        # Mapping keystroke timings (Indices 6 to 9 and 16 to 19)
        # 6: avg_key_hold_ms
        # 7: std_key_hold_ms
        # 8: avg_inter_key_ms
        # 9: std_inter_key_ms
        # 16: avg_di_flight_ms
        # 17: std_di_flight_ms
        
        hold_times = row[h_cols].values * 1000.0 # Convert to ms
        inter_key = row[dd_cols].values * 1000.0
        flight_times = row[ud_cols].values * 1000.0
        
        fv[6] = np.mean(hold_times)
        fv[7] = np.std(hold_times)
        fv[8] = np.mean(inter_key)
        fv[9] = np.std(inter_key)
        
        fv[16] = np.mean(flight_times)
        fv[17] = np.std(flight_times)
        
        # Basic counts for consistency (though less critical for global model)
        fv[0] = 50 # roughly 50 events
        fv[1] = 25 # keydowns
        fv[2] = 25 # keyups
        
        # Add reasonable defaults for mouse features (since dataset is KB only)
        # We set them to 0 but with 0 variance so they don't impact the SVM heavily 
        # as long as we only use the RBF kernel on KB indices for "Humanity" checks.
        
        feature_vectors.append(fv)
        
    return np.array(feature_vectors)

def train_and_save():
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    df = download_data()
    X = process_to_features(df)
    
    print(f"Training One-Class SVM on {len(X)} human samples...")
    # We train on the FULL vector but highlight KB indices [6:10, 16:18] as core
    # The Global model will serve as a baseline for "Human Keystroke Rhythm"
    model = OneClassSVM(kernel="rbf", nu=0.05, gamma="scale")
    
    # Slice to only keystroke features for the global baseline
    # Indices: 6, 7, 8, 9, 16, 17
    kb_indices = [6, 7, 8, 9, 16, 17]
    X_kb = X[:, kb_indices]
    
    model.fit(X_kb)
    
    joblib.dump(model, OUTPUT_MODEL)
    print(f"SUCCESS: Global Human Model saved to {OUTPUT_MODEL}")

if __name__ == "__main__":
    train_and_save()
