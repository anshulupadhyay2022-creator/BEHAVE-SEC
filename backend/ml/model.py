"""
backend/ml/model.py
AnomalyDetector – thin wrapper around sklearn's IsolationForest.

Lifecycle
---------
1. On first import, the detector loads an existing model from disk (if any).
2. Each session submitted via /collect-data adds its feature vector to a
   pending buffer.
3. Once MIN_SAMPLES_TO_TRAIN vectors accumulate, the model trains automatically.
4. After training, every new session is scored in real-time.
5. The model can be explicitly retrained at any time via POST /model/retrain.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
from sklearn.svm import OneClassSVM

from backend.core.config import settings
from backend.ml.features import N_FEATURES, extract_features
from backend.models.schemas import BehavioralDataPayload

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_SAMPLES_TO_TRAIN: int = 10          # collect at least this many sessions
CONTAMINATION: float | str = "auto"    # expected fraction of anomalies
N_ESTIMATORS:  int = 100               # number of trees in the forest
RANDOM_STATE:  int = 42


class AnomalyDetector:
    """Thread-safe, persistent wrapper around IsolationForest."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self._model: Any | None = None
        self._buffer: list[np.ndarray] = []   # feature vectors not yet trained
        self._lock = Lock()
        self._model_path = Path(settings.MODEL_DIR) / f"anomaly_detector_{self.user_id}.pkl"
        self._data_path = Path(settings.MODEL_DIR) / f"training_data_{self.user_id}.npy"
        self._master_centroid_path = Path(settings.MODEL_DIR) / f"master_centroid_{self.user_id}.npy"
        self._last_fv: np.ndarray | None = None
        self._master_centroid: np.ndarray | None = None

        # Try to restore previously saved model, data, and centroid
        self._load()
        self._load_data()
        self._load_centroid()

    # ── Public API ─────────────────────────────────────────────────────────────

    def ingest(self, payload: BehavioralDataPayload) -> dict[str, Any]:
        """
        Extract features from *payload*, add to buffer, auto-train if threshold
        is reached, then return an anomaly result dict.
        """
        fv = extract_features(payload.events)
        self._last_fv = fv  # Store for feedback loop

        with self._lock:
            # We only auto-buffer during initial training or periodic collection.
            # For the "Intruder" challenge, we usually only add via feedback.
            # But for this demo, let's keep auto-buffering until we hit 50 samples.
            if len(self._buffer) < 50:
                self._buffer.append(fv)
                self._save_data()

            n_buffered = len(self._buffer)

            # Auto-train once we have enough samples and no trained model yet
            if self._model is None and n_buffered >= MIN_SAMPLES_TO_TRAIN:
                self._train()

            if self._model is None:
                return {
                    "label": "pending",
                    "score": 0.0,
                    "model_ready": False,
                    "samples_collected": n_buffered,
                    "samples_needed": MIN_SAMPLES_TO_TRAIN,
                }

            return self._score(fv)

    def handle_feedback(self, is_owner: bool, bypass_drift: bool = False) -> dict[str, Any]:
        """
        Active Learning: Use user feedback to improve the model.
        If is_owner is True, we add the last analyzed vector to the buffer and retrain.
        """
        with self._lock:
            if not is_owner:
                return {"success": True, "message": "Feedback received (intruder confirmed, no training required)"}
            
            if self._last_fv is None:
                return {"success": False, "message": "No recent session found to train on."}

            # POISONING PROTECTION: Check for drift before accepting owner feedback
            # Only for non-challenge users.
            if not bypass_drift and not self._is_profile_consistent(self._last_fv):
                return {
                    "success": False, 
                    "status": "mfa_required", 
                    "message": "Behavioral signature mismatch. Step-up authentication required to verify this update."
                }

            # Add the owner session (whether misidentified or correctly identified) to the training set
            self._buffer.append(self._last_fv)
            self._save_data()
            self._train()
            
            return {
                "success": True, 
                "message": "Model updated with your feedback! Profile reinforced.",
                "new_sample_count": len(self._buffer)
            }

    def _calculate_similarity(self, fv1: np.ndarray, fv2: np.ndarray) -> float:
        """Calculate Cosine Similarity between two feature vectors."""
        # Biometric features only [6:28]
        v1 = fv1[6:28]
        v2 = fv2[6:28]
        
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = np.dot(v1, v2) / (norm1 * norm2)
        return float(similarity)

    def _is_profile_consistent(self, new_fv: np.ndarray) -> bool:
        """
        Check if the new session is consistent with the established master profile.
        Returns True if similarity >= DRIFT_SIMILARITY_THRESHOLD or no profile exists.
        """
        if self._master_centroid is None or self.user_id.startswith("challenge_"):
            return True
            
        similarity = self._calculate_similarity(new_fv, self._master_centroid)
        is_consistent = similarity >= settings.DRIFT_SIMILARITY_THRESHOLD
        
        if not is_consistent:
            logger.warning("Behavioral DRIFT detected for user %s (Sim: %.4f < Threshold: %.2f)", 
                           self.user_id, similarity, settings.DRIFT_SIMILARITY_THRESHOLD)
        return is_consistent

    def retrain(self) -> dict[str, Any]:
        """Force a retrain on all buffered feature vectors.  Returns status."""
        with self._lock:
            if len(self._buffer) < 2:
                return {"success": False, "reason": "Not enough data to train (need ≥ 2 sessions)"}
            self._train()
            return {
                "success": True,
                "trained_on": len(self._buffer),
                "model_path": str(self._model_path),
            }

    @property
    def status(self) -> dict[str, Any]:
        """Return current detector state (thread-safe snapshot)."""
        with self._lock:
            return {
                "trained": self._model is not None,
                "samples_in_buffer": len(self._buffer),
                "min_samples_to_train": MIN_SAMPLES_TO_TRAIN,
                "model_path": str(self._model_path),
                "model_exists_on_disk": self._model_path.exists(),
                "n_estimators": N_ESTIMATORS,
                "contamination": CONTAMINATION,
            }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _train(self) -> None:
        """Fit One-Class SVM on *self._buffer*. Must hold *self._lock*."""
        if not self._buffer:
            return
            
        X_full = np.vstack(self._buffer)
        
        # Biometric features slice [6:28]
        X = X_full[:, 6:28]
        
        # Save feature means for multimodal "context-aware" imputation
        self._feature_means = np.mean(X, axis=0)
        
        model = OneClassSVM(kernel="rbf", nu=0.01, gamma="scale")
        model.fit(X)
        
        self._model = model
        
        # After a successful train, update the Master Centroid if it's the first time
        # or if we are reinforcing a trusted session.
        self._master_centroid = np.mean(X_full, axis=0)
        
        self._save()
        self._save_centroid()
        logger.info("One-Class SVM trained on %d samples. Master centroid updated.", len(self._buffer))

    def _score(self, fv: np.ndarray) -> dict[str, Any]:
        """Score a single feature vector based on SVM hyperplane distance."""
        assert self._model is not None
        
        keydown_count = fv[1]
        mousemove_count = fv[3]
        
        x_biometric = fv[6:28].copy()
        
        from backend.ml.features import KB_INDICES, MS_INDICES
        
        if keydown_count == 0 and hasattr(self, "_feature_means"):
            for idx in KB_INDICES:
                x_biometric[idx - 6] = self._feature_means[idx - 6]
        
        if mousemove_count == 0 and hasattr(self, "_feature_means"):
            for idx in MS_INDICES:
                x_biometric[idx - 6] = self._feature_means[idx - 6]
        
        x = x_biometric.reshape(1, -1)
        raw_score = float(self._model.decision_function(x)[0])
        normalised = float(np.clip(1.0 / (1.0 + np.exp(5.0 * raw_score)), 0.0, 1.0))

        return {
            "label": "normal" if normalised < 0.90 else "anomaly",
            "score": round(normalised, 4),
            "model_ready": True,
            "mode": "keyboard-only" if mousemove_count == 0 else "multimodal",
            "samples_trained_on": len(self._buffer),
        }

    def _save(self) -> None:
        """Persist the fitted model to disk. Must hold *self._lock*."""
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, self._model_path)

    def _load(self) -> None:
        """Load a previously saved model from disk (called at startup)."""
        if self._model_path.exists():
            try:
                self._model = joblib.load(self._model_path)
                logger.info("AnomalyDetector loaded from %s", self._model_path)
            except Exception as exc:   # noqa: BLE001
                logger.warning("Could not load saved model (%s) — starting fresh.", exc)
                self._model = None

    def _save_data(self) -> None:
        """Save the training buffer to disk."""
        if not self._buffer:
            return
        np.save(str(self._data_path), np.array(self._buffer))
        logger.info("Saved %d training samples to %s", len(self._buffer), self._data_path)

    def _load_data(self) -> None:
        """Load training samples from disk."""
        if self._data_path.exists():
            try:
                data = np.load(str(self._data_path))
                self._buffer = [row for row in data]
                logger.info("Loaded %d training samples from %s", len(self._buffer), self._data_path)
            except Exception as exc:
                logger.warning("Could not load training data (%s) — starting fresh.", exc)
                self._buffer = []

    def _save_centroid(self) -> None:
        """Save the master centroid to disk."""
        if self._master_centroid is None:
            return
        np.save(str(self._master_centroid_path), self._master_centroid)
        logger.info("Saved master centroid to %s", self._master_centroid_path)

    def _load_centroid(self) -> None:
        """Load the master centroid from disk."""
        if self._master_centroid_path.exists():
            try:
                self._master_centroid = np.load(str(self._master_centroid_path))
                logger.info("Loaded master centroid from %s", self._master_centroid_path)
            except Exception as exc:
                logger.warning("Could not load master centroid (%s).", exc)
                self._master_centroid = None

class ModelManager:
    """Manages active detectors for multiple users."""
    def __init__(self) -> None:
        self._detectors: dict[str, AnomalyDetector] = {}
        self._lock = Lock()
        
    def get_detector(self, user_id: str) -> AnomalyDetector:
        with self._lock:
            if user_id not in self._detectors:
                self._detectors[user_id] = AnomalyDetector(user_id=user_id)
            return self._detectors[user_id]

# ── Singleton ─────────────────────────────────────────────────────────────────
model_manager = ModelManager()

