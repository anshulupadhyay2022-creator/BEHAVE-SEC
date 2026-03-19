"""
backend/ml/features.py
Extract a fixed-length numeric feature vector from a list of BehavioralEvents.

Features (16 total):
  0  total_events
  1  keydown_count
  2  keyup_count
  3  mousemove_count
  4  click_count
  5  scroll_count
  6  avg_key_hold_ms       – mean dwell time (keydown→keyup for same key)
  7  std_key_hold_ms
  8  avg_inter_key_ms      – mean flight time between consecutive keydowns
  9  std_inter_key_ms
  10 avg_mouse_speed       – mean pixel/ms between successive mousemove events
  11 std_mouse_speed
  12 session_duration_ms
  13 events_per_second
  14 key_event_ratio        – (keydown+keyup) / total
  15 mouse_event_ratio      – (mousemove+click+scroll) / total
"""

from __future__ import annotations

import math
from typing import List

import numpy as np

from backend.models.schemas import BehavioralEvent

# Number of features produced by extract_features()
N_FEATURES = 16

# Names – useful for diagnostics / dashboards
FEATURE_NAMES = [
    "total_events",
    "keydown_count",
    "keyup_count",
    "mousemove_count",
    "click_count",
    "scroll_count",
    "avg_key_hold_ms",
    "std_key_hold_ms",
    "avg_inter_key_ms",
    "std_inter_key_ms",
    "avg_mouse_speed",
    "std_mouse_speed",
    "session_duration_ms",
    "events_per_second",
    "key_event_ratio",
    "mouse_event_ratio",
]


def _safe_std(values: list[float]) -> float:
    """Return std-dev of *values*, or 0 when fewer than 2 samples."""
    return float(np.std(values)) if len(values) >= 2 else 0.0


def extract_features(events: List[BehavioralEvent]) -> np.ndarray:
    """
    Convert a list of BehavioralEvent objects to a 1-D numpy feature vector.

    Always returns an array of shape (N_FEATURES,) regardless of how many
    events are present (missing values become 0).
    """
    n = len(events)
    if n == 0:
        return np.zeros(N_FEATURES, dtype=np.float64)

    # ── 1. Basic counts ──────────────────────────────────────────────────────
    counts: dict[str, int] = {}
    for e in events:
        counts[e.eventType] = counts.get(e.eventType, 0) + 1

    kd = counts.get("keydown", 0)
    ku = counts.get("keyup", 0)
    mm = counts.get("mousemove", 0)
    cl = counts.get("click", 0)
    sc = counts.get("scroll", 0)

    # ── 2. Key hold times (dwell) ────────────────────────────────────────────
    # Match each keydown with the nearest subsequent keyup of the same key
    keydown_map: dict[str, int] = {}  # key → timestamp of last keydown
    hold_times: list[float] = []

    for e in events:
        if e.eventType == "keydown" and e.key:
            keydown_map[e.key] = e.timestamp
        elif e.eventType == "keyup" and e.key and e.key in keydown_map:
            hold = e.timestamp - keydown_map.pop(e.key)
            if 0 < hold < 5_000:   # ignore implausible values
                hold_times.append(float(hold))

    avg_hold = float(np.mean(hold_times)) if hold_times else 0.0
    std_hold = _safe_std(hold_times)

    # ── 3. Inter-key intervals (flight time between consecutive keydowns) ─────
    kd_timestamps = [e.timestamp for e in events if e.eventType == "keydown"]
    inter_key: list[float] = []
    for i in range(1, len(kd_timestamps)):
        gap = kd_timestamps[i] - kd_timestamps[i - 1]
        if 0 < gap < 10_000:
            inter_key.append(float(gap))

    avg_iki = float(np.mean(inter_key)) if inter_key else 0.0
    std_iki = _safe_std(inter_key)

    # ── 4. Mouse speed (pixels / ms) ─────────────────────────────────────────
    mouse_events = [
        e for e in events
        if e.eventType == "mousemove"
        and e.clientX is not None and e.clientY is not None
    ]
    speeds: list[float] = []
    for i in range(1, len(mouse_events)):
        prev, curr = mouse_events[i - 1], mouse_events[i]
        dt = curr.timestamp - prev.timestamp
        if dt > 0:
            dx = curr.clientX - prev.clientX   # type: ignore[operator]
            dy = curr.clientY - prev.clientY   # type: ignore[operator]
            speeds.append(math.hypot(dx, dy) / dt)

    avg_speed = float(np.mean(speeds)) if speeds else 0.0
    std_speed = _safe_std(speeds)

    # ── 5. Session-level timing ───────────────────────────────────────────────
    ts_list = [e.timestamp for e in events]
    duration_ms = float(max(ts_list) - min(ts_list)) if len(ts_list) >= 2 else 0.0
    duration_s  = duration_ms / 1000.0 if duration_ms > 0 else 1.0  # avoid /0
    eps = n / duration_s

    # ── 6. Ratios ─────────────────────────────────────────────────────────────
    key_ratio   = (kd + ku) / n
    mouse_ratio = (mm + cl + sc) / n

    # ── Assemble ──────────────────────────────────────────────────────────────
    return np.array([
        n,
        kd,
        ku,
        mm,
        cl,
        sc,
        avg_hold,
        std_hold,
        avg_iki,
        std_iki,
        avg_speed,
        std_speed,
        duration_ms,
        eps,
        key_ratio,
        mouse_ratio,
    ], dtype=np.float64)
