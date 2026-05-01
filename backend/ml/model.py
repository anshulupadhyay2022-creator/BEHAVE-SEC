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
from backend.models.schemas import BehavioralDataPayload, BehavioralEvent

logger = logging.getLogger(__name__)

# ── Tuned Constants (from tune_model.py grid-search) ─────────────────────────
MIN_SAMPLES_TO_TRAIN: int = 10          # collect at least this many sessions
RANDOM_STATE:  int = 42

# Optimal OneClassSVM hyperparameters — strict mode.
# nu=0.05: more support vectors -> tighter decision boundary around the owner.
OCSVM_NU:     float = 0.05
OCSVM_GAMMA:  str | float = "scale"

# Sigmoid mapping: raw SVM decision score -> [0, 1] anomaly probability.
# Higher slope = sharper transition — small score differences yield large
# probability jumps, making the model less forgiving near the boundary.
SIGMOID_SLOPE:  float = 12.0
SIGMOID_OFFSET: float = 0.0

# Default threshold used before any calibration has run.
# After the first retrain, each user gets their OWN calibrated threshold
# persisted in data/model/threshold_<userId>.txt
DEFAULT_THRESHOLD:  float = 0.50   # strict default — flags anomalies earlier

# Adaptive calibration settings — strict mode
# Threshold = p<OWNER_PERCENTILE> of owner scores + THRESHOLD_MARGIN
# Lower percentile = tighter fit; the top 15% of borderline owner sessions
# may be flagged, strongly penalising any behavioural drift.
OWNER_PERCENTILE:  float = 85.0   # accept only 85% of own sessions
THRESHOLD_MARGIN:  float = 0.00   # no cushion — boundary as tight as possible
THRESHOLD_MIN:     float = 0.45
THRESHOLD_MAX:     float = 0.55   # hard cap — prevents permissive thresholds


class AnomalyDetector:
    """Thread-safe, persistent wrapper around IsolationForest."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self._model: Any | None = None
        self._buffer: list[np.ndarray] = []   # feature vectors not yet trained
        self._lock = Lock()
        self._model_path   = Path(settings.MODEL_DIR) / f"anomaly_detector_{self.user_id}.pkl"
        self._data_path    = Path(settings.MODEL_DIR) / f"training_data_{self.user_id}.npy"
        self._centroid_path= Path(settings.MODEL_DIR) / f"master_centroid_{self.user_id}.npy"
        self._threshold_path = Path(settings.MODEL_DIR) / f"threshold_{self.user_id}.txt"
        self._global_model_path = Path(settings.MODEL_DIR) / "global_human_model.pkl"
        self._last_fv: np.ndarray | None = None
        self._master_centroid: np.ndarray | None = None
        self._global_model: Any | None = None
        # Per-user adaptive threshold — recalibrated on every retrain
        self._threshold: float = DEFAULT_THRESHOLD

        # Restore previously saved model, data, centroid, and threshold
        self._load()
        self._load_data()
        self._load_centroid()
        self._load_global_model()
        self._load_threshold()

    # ── Public API ─────────────────────────────────────────────────────────────

    def ingest(self, payload: BehavioralDataPayload) -> dict[str, Any]:
        """
        Extract features from *payload*, add to buffer, auto-train if threshold
        is reached, then return an anomaly result dict.
        """
        fv = extract_features(payload.events)
        self._last_fv = fv  # Store for feedback loop

        with self._lock:
            # ── SECURITY: Only buffer sessions BEFORE the model is trained.
            # Once the personal model exists, sessions are NO LONGER auto-buffered.
            # New data enters the training set ONLY when the owner clicks
            # "This is me" (handle_feedback(is_owner=True)).
            # This prevents intruder sessions from poisoning the model.
            if self._model is None and len(self._buffer) < 50:
                self._buffer.append(fv)
                self._save_data()

            n_buffered = len(self._buffer)

            # Auto-train once we have enough samples and no trained model yet
            if self._model is None and n_buffered >= MIN_SAMPLES_TO_TRAIN:
                self._train()

            if self._model is None:
                res = {
                    "label": "pending",
                    "score": 0.0,
                    "model_ready": False,
                    "samples_collected": n_buffered,
                    "samples_needed": MIN_SAMPLES_TO_TRAIN,
                }
                # Even if user model is pending, check for Bot Activity
                if self._global_model is not None:
                    kb_slice = fv[[6, 7, 8, 9, 16, 17]].reshape(1, -1)
                    global_pred = self._global_model.predict(kb_slice)[0]
                    res["bot_detection"] = {
                        "is_human": bool(global_pred == 1),
                        "label": "human" if global_pred == 1 else "bot"
                    }
                else:
                    res["bot_detection"] = {"is_human": True, "label": "human"}
                
                # Deterministic Kinematic Check (Zero-Day Mouse Curve)
                if fv[3] > 10 and fv[24] >= 0.999:
                    res["bot_detection"]["is_human"] = False
                    res["bot_detection"]["label"] = "bot (kinematic pattern)"

                return res

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

    def verify_login_signature(self, kb_events: list[BehavioralEvent], ms_events: list[BehavioralEvent]) -> dict[str, Any]:
        """
        Verify a user's behavioral signature during login.
        Returns both Identity Match and Humanity (Bot Detection) scores.
        """
        events = kb_events + ms_events
        fv = extract_features(events)
        
        with self._lock:
            result = {"status": "success", "feature_vector": fv.tolist()}
            
            # 1. Identity Verification (Personal Model)
            if self._model is not None:
                id_res = self._score(fv)
                result.update({
                    "identity_label": id_res["label"],
                    "identity_score": id_res["score"],
                    "threshold":      id_res["threshold"],   # expose per-user adaptive threshold
                    "model_ready": True
                })
                if self._master_centroid is not None:
                    sim = self._calculate_similarity(fv, self._master_centroid)
                    result["similarity"] = round(sim, 4)
            else:
                result["identity_label"] = "pending"
                result["identity_score"] = 0.0
                result["threshold"]      = DEFAULT_THRESHOLD
                result["model_ready"]    = False
                result["message"]        = "No personal model trained yet."


            # 2. Humanity Verification (Global Model / Bot Detection)
            if self._global_model is not None:
                # CMU mapping uses indices [6, 7, 8, 9, 16, 17] for core rhythm
                kb_slice = fv[[6, 7, 8, 9, 16, 17]].reshape(1, -1)
                global_pred = self._global_model.predict(kb_slice)[0]
                
                # In OneClassSVM, 1 is inlier (human), -1 is outlier (bot/anomaly)
                raw_score = float(self._global_model.decision_function(kb_slice)[0])
                # Normalize global score to 0..1 (higher = more human)
                humanity_score = float(1.0 / (1.0 + np.exp(-2.0 * raw_score)))
                
                result["bot_detection"] = {
                    "is_human": bool(global_pred == 1),
                    "humanity_score": round(humanity_score, 4),
                    "label": "human" if global_pred == 1 else "bot"
                }
            else:
                result["bot_detection"] = {"is_human": True, "humanity_score": 1.0, "label": "human"}

            # Deterministic Kinematic Check (Zero-Day Mouse Curve)
            # If > 10 mouse moves and perfectly straight line (>= 0.999)
            if fv[3] > 10 and fv[24] >= 0.999:
                result["bot_detection"]["is_human"] = False
                result["bot_detection"]["humanity_score"] = 0.0
                result["bot_detection"]["label"] = "bot (kinematic pattern)"

            
            return result

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
                "algorithm": "OneClassSVM",
                "nu": OCSVM_NU,
                "gamma": OCSVM_GAMMA,
                "threshold": self._threshold,
                "threshold_calibrated": self._threshold != DEFAULT_THRESHOLD,
            }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _train(self) -> None:
        """Fit One-Class SVM on *self._buffer*. Must hold *self._lock*."""
        if not self._buffer:
            return

        X_full = np.vstack(self._buffer)

        # Use only the 22 biometric features [6:28]
        X_raw = X_full[:, 6:28]

        # ── StandardScaler ────────────────────────────────────────────────────
        from sklearn.preprocessing import StandardScaler
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X_raw)

        # Store feature means for context-aware imputation in _score()
        self._feature_means = np.mean(X_raw, axis=0)

        # ── Fit tuned OneClassSVM ─────────────────────────────────────────────
        model = OneClassSVM(kernel="rbf", nu=OCSVM_NU, gamma=OCSVM_GAMMA)
        model.fit(X_scaled)

        self._model = model
        self._master_centroid = np.mean(X_full, axis=0)

        self._save()
        self._save_centroid()

        # ── Adaptive threshold calibration ────────────────────────────────────
        # Score every known-owner session through the freshly-trained model.
        # Set threshold = p<OWNER_PERCENTILE> of those scores + THRESHOLD_MARGIN.
        # This means the threshold tightens/relaxes automatically as more real
        # sessions are enrolled — each feedback click genuinely improves accuracy.
        self._calibrate_threshold(X_scaled)

        logger.info(
            "OneClassSVM trained on %d samples (nu=%.3f, gamma=%s) | "
            "adaptive threshold=%.4f (p%.0f + %.2f margin).",
            len(self._buffer), OCSVM_NU, OCSVM_GAMMA,
            self._threshold, OWNER_PERCENTILE, THRESHOLD_MARGIN
        )

    def _calibrate_threshold(self, X_owner_scaled: np.ndarray) -> None:
        """
        Recalculate the anomaly threshold from the owner's own sessions.

        Strategy:
          1. Score every owner session (they are all inside the boundary).
          2. Find the Nth-percentile of those scores (default p95).
          3. Add a small margin so the top 5% of borderline owner sessions
             are still accepted without tipping into intruder territory.
          4. Clamp to [THRESHOLD_MIN, THRESHOLD_MAX].

        Must be called with self._lock held and self._model already set.
        """
        assert self._model is not None

        if X_owner_scaled.shape[0] < 2:
            # Not enough data to calibrate — keep previous threshold
            logger.warning("Too few samples to calibrate threshold; keeping %.4f.", self._threshold)
            return

        raw_scores = self._model.decision_function(X_owner_scaled)          # shape (n,)
        owner_anomaly_scores = 1.0 / (1.0 + np.exp(SIGMOID_SLOPE * raw_scores))  # sigmoid

        p_val = float(np.percentile(owner_anomaly_scores, OWNER_PERCENTILE))
        new_threshold = float(np.clip(p_val + THRESHOLD_MARGIN, THRESHOLD_MIN, THRESHOLD_MAX))

        old = self._threshold
        self._threshold = new_threshold
        self._save_threshold()

        logger.info(
            "Threshold calibrated: %.4f -> %.4f  "
            "(p%.0f of owner scores=%.4f, margin=%.2f, n=%d sessions)",
            old, new_threshold, OWNER_PERCENTILE, p_val, THRESHOLD_MARGIN,
            X_owner_scaled.shape[0]
        )

    def _score(self, fv: np.ndarray) -> dict[str, Any]:
        """Score a single feature vector using the adaptive per-user threshold."""
        assert self._model is not None

        keydown_count   = fv[1]
        mousemove_count = fv[3]

        x_biometric = fv[6:28].copy()

        from backend.ml.features import KB_INDICES, MS_INDICES

        # Context-aware imputation: if a modality is absent, use stored means
        if keydown_count == 0 and hasattr(self, "_feature_means"):
            for idx in KB_INDICES:
                x_biometric[idx - 6] = self._feature_means[idx - 6]

        if mousemove_count == 0 and hasattr(self, "_feature_means"):
            for idx in MS_INDICES:
                x_biometric[idx - 6] = self._feature_means[idx - 6]

        # Scale using the fitted scaler (must match training transform)
        if hasattr(self, "_scaler") and self._scaler is not None:
            x = self._scaler.transform(x_biometric.reshape(1, -1))
        else:
            x = x_biometric.reshape(1, -1)

        raw_score  = float(self._model.decision_function(x)[0])
        normalised = float(np.clip(
            1.0 / (1.0 + np.exp(SIGMOID_SLOPE * raw_score + SIGMOID_OFFSET)),
            0.0, 1.0
        ))

        # Use the per-user adaptive threshold — updated after every retrain
        result = {
            "label": "normal" if normalised < self._threshold else "anomaly",
            "score": round(normalised, 4),
            "threshold": round(self._threshold, 4),   # expose to frontend
            "model_ready": True,
            "mode": "keyboard-only" if mousemove_count == 0 else "multimodal",
            "samples_trained_on": len(self._buffer),
            "raw_decision": round(raw_score, 4),
        }

        # Humanity Verification (Global Model / Bot Detection)
        if self._global_model is not None:
            kb_slice = fv[[6, 7, 8, 9, 16, 17]].reshape(1, -1)
            global_pred = self._global_model.predict(kb_slice)[0]
            raw_humanity = float(self._global_model.decision_function(kb_slice)[0])
            humanity_score = float(1.0 / (1.0 + np.exp(-2.0 * raw_humanity)))
            result["bot_detection"] = {
                "is_human": bool(global_pred == 1),
                "humanity_score": round(humanity_score, 4),
                "label": "human" if global_pred == 1 else "bot"
            }
        else:
            result["bot_detection"] = {"is_human": True, "humanity_score": 1.0, "label": "human"}

        # Deterministic Kinematic Check (Zero-Day Mouse Curve)
        if fv[3] > 10 and fv[24] >= 0.999:
            result["bot_detection"]["is_human"] = False
            result["bot_detection"]["humanity_score"] = 0.0
            result["bot_detection"]["label"] = "bot (kinematic pattern)"


        return result

    def _save(self) -> None:
        """Persist the fitted model and scaler to disk. Must hold *self._lock*."""
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "scaler": getattr(self, "_scaler", None),
                     "feature_means": getattr(self, "_feature_means", None)},
                    self._model_path)

    def _save_threshold(self) -> None:
        """Persist the calibrated threshold so it survives server restarts."""
        try:
            self._threshold_path.parent.mkdir(parents=True, exist_ok=True)
            self._threshold_path.write_text(str(self._threshold))
        except Exception as exc:
            logger.warning("Could not save threshold: %s", exc)

    def _load_threshold(self) -> None:
        """Load the per-user calibrated threshold from disk."""
        if self._threshold_path.exists():
            try:
                self._threshold = float(self._threshold_path.read_text().strip())
                logger.info("Loaded adaptive threshold %.4f from %s",
                            self._threshold, self._threshold_path)
            except Exception as exc:
                logger.warning("Could not load threshold (%s) — using default %.4f.",
                               exc, DEFAULT_THRESHOLD)
                self._threshold = DEFAULT_THRESHOLD

    def _load(self) -> None:
        """Load the previously saved model + scaler bundle from disk."""
        if self._model_path.exists():
            try:
                bundle = joblib.load(self._model_path)
                if isinstance(bundle, dict):
                    self._model = bundle.get("model")
                    self._scaler = bundle.get("scaler")
                    self._feature_means = bundle.get("feature_means")
                else:
                    # Legacy: plain model object saved by older code
                    self._model = bundle
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
        np.save(str(self._centroid_path), self._master_centroid)
        logger.info("Saved master centroid to %s", self._centroid_path)

    def _load_centroid(self) -> None:
        """Load the master centroid from disk."""
        if self._centroid_path.exists():
            try:
                self._master_centroid = np.load(str(self._centroid_path))
                logger.info("Loaded master centroid from %s", self._centroid_path)
            except Exception as exc:
                logger.warning("Could not load master centroid (%s).", exc)
                self._master_centroid = None

    def _load_global_model(self) -> None:
        """Load the global human baseline model from disk."""
        if self._global_model_path.exists():
            try:
                self._global_model = joblib.load(self._global_model_path)
                logger.info("Loaded Global Human Baseline from %s", self._global_model_path)
            except Exception as exc:
                logger.warning("Could not load global human model (%s).", exc)
                self._global_model = None

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

