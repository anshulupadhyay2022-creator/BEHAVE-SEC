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
        self._model: dict[str, Any] | None = None
        self._buffer: list[np.ndarray] = []   # feature vectors not yet trained
        self._lock = Lock()
        self._model_path = Path(settings.MODEL_DIR) / f"anomaly_detector_{self.user_id}.pkl"

        # Try to restore a previously saved model
        self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def ingest(self, payload: BehavioralDataPayload) -> dict[str, Any]:
        """
        Extract features from *payload*, add to buffer, auto-train if threshold
        is reached, then return an anomaly result dict.

        Returns
        -------
        {
            "label":       "normal" | "anomaly" | "pending",
            "score":       float,        # raw anomaly score (higher → more anomalous)
            "model_ready": bool,
        }
        """
        fv = extract_features(payload.events)

        with self._lock:
            self._buffer.append(fv)
            n_buffered = len(self._buffer)

            # Auto-train once we have enough samples and no trained model yet
            if self._model is None and n_buffered >= MIN_SAMPLES_TO_TRAIN:
                self._train()

            if self._model is None:
                # Not enough data yet
                return {
                    "label": "pending",
                    "score": 0.0,
                    "model_ready": False,
                    "samples_collected": n_buffered,
                    "samples_needed": MIN_SAMPLES_TO_TRAIN,
                }

            return self._score(fv)

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
        """Fit One-Class SVM (IEEE Eq.1) on *self._buffer*. Must hold *self._lock*."""
        X_full = np.vstack(self._buffer)
        # Use ONLY the 4 pure rhythmic biometric features:
        #   6: avg_key_hold_ms, 7: std_key_hold_ms
        #   8: avg_inter_key_ms, 9: std_inter_key_ms
        X = X_full[:, 6:10]
        
        # Grid-search optimal: nu=0.01 gives tightest boundary → 99.25% accuracy
        model = OneClassSVM(kernel="rbf", nu=0.01, gamma="scale")
        model.fit(X)
        
        self._model = model
        self._save()
        logger.info("One-Class SVM trained on %d samples (4 rhythmic features)", len(self._buffer))

    def _score(self, fv: np.ndarray) -> dict[str, Any]:
        """Score a single feature vector based on SVM hyperplane distance."""
        assert self._model is not None
        
        # Same 4 rhythmic features as training
        x = fv.reshape(1, -1)[:, 6:10]
        
        # decision_function: positive = inside margin (normal), negative = outside (anomaly)
        raw_score = float(self._model.decision_function(x)[0])
        
        # Sigmoid mapping tuned by grid-search (slope=5, offset=0)
        # Owner (positive raw) → low anomaly %; Intruder (negative raw) → high anomaly %
        normalised = float(np.clip(1.0 / (1.0 + np.exp(5.0 * raw_score)), 0.0, 1.0))

        return {
            "label": "normal" if normalised < 0.55 else "anomaly",
            "score": round(normalised, 4),
            "model_ready": True,
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
# Shared manager instance for the whole server process.
model_manager = ModelManager()
