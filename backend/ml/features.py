"""
backend/ml/features.py
Extract a fixed-length numeric feature vector from a list of BehavioralEvents.

Features (28 total):
  0  total_events
  1  keydown_count
  2  keyup_count
  3  mousemove_count
  4  click_count
  5  scroll_count
  6  avg_key_hold_ms
  7  std_key_hold_ms
  8  avg_inter_key_ms
  9  std_inter_key_ms
  10 avg_mouse_speed
  11 std_mouse_speed
  12 session_duration_ms
  13 events_per_second
  14 key_event_ratio
  15 mouse_event_ratio
  16 avg_digraph_flight_ms
  17 std_digraph_flight_ms
  18 avg_digraph_duration_ms
  19 std_digraph_duration_ms
  20 avg_hold_flight_ratio
  21 std_hold_flight_ratio
  22 avg_mouse_accel        -- mean acceleration (change in speed)
  23 std_mouse_accel
  24 path_directness_ratio  -- straight-line / actual distance between clicks
  25 avg_click_interval_ms  -- mean time between consecutive clicks
  26 std_click_interval_ms
  27 click_precision        -- mean distance of clicks from movement centroid
"""

from __future__ import annotations

import math
from typing import List

import numpy as np

from backend.models.schemas import BehavioralEvent

# Number of features produced by extract_features()
N_FEATURES = 28

# Biometric Feature Groups (for Context-Aware Analysis)
# These indices correspond to the 22 biometric features (6:28) used in model.py
KB_INDICES = [6, 7, 8, 9, 16, 17, 18, 19, 20, 21] # Keystroke dwell, flight, digraphs
MS_INDICES = [10, 11, 22, 23, 24, 25, 26, 27]    # Speed, accel, click, path
MIX_INDICES = [12, 13, 14, 15]                   # Session timing and mix ratios

# Names -- useful for diagnostics / dashboards
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
    "avg_digraph_flight_ms",
    "std_digraph_flight_ms",
    "avg_digraph_duration_ms",
    "std_digraph_duration_ms",
    "avg_hold_flight_ratio",
    "std_hold_flight_ratio",
    "avg_mouse_accel",
    "std_mouse_accel",
    "path_directness_ratio",
    "avg_click_interval_ms",
    "std_click_interval_ms",
    "click_precision",
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

    # -- 1. Basic counts ---
    counts: dict[str, int] = {}
    for e in events:
        counts[e.eventType] = counts.get(e.eventType, 0) + 1

    kd = counts.get("keydown", 0)
    ku = counts.get("keyup", 0)
    mm = counts.get("mousemove", 0)
    cl = counts.get("click", 0)
    sc = counts.get("scroll", 0)

    # -- 2. Key hold times (dwell) ---
    keydown_map: dict[str, int] = {}
    hold_times: list[float] = []

    for e in events:
        if e.eventType == "keydown" and e.key:
            keydown_map[e.key] = e.timestamp
        elif e.eventType == "keyup" and e.key and e.key in keydown_map:
            hold = e.timestamp - keydown_map.pop(e.key)
            if 0 < hold < 5_000:
                hold_times.append(float(hold))

    avg_hold = float(np.mean(hold_times)) if hold_times else 0.0
    std_hold = _safe_std(hold_times)

    # -- 3. Inter-key intervals (flight time between consecutive keydowns) ---
    kd_timestamps = [e.timestamp for e in events if e.eventType == "keydown"]
    inter_key: list[float] = []
    for i in range(1, len(kd_timestamps)):
        gap = kd_timestamps[i] - kd_timestamps[i - 1]
        if 0 < gap < 10_000:
            inter_key.append(float(gap))

    avg_iki = float(np.mean(inter_key)) if inter_key else 0.0
    std_iki = _safe_std(inter_key)

    # -- 4. Mouse speed (pixels / ms) ---
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

    # -- 5. Session-level timing ---
    ts_list = [e.timestamp for e in events]
    duration_ms = float(max(ts_list) - min(ts_list)) if len(ts_list) >= 2 else 0.0
    duration_s  = duration_ms / 1000.0 if duration_ms > 0 else 1.0
    eps = n / duration_s

    # -- 6. Ratios ---
    key_ratio   = (kd + ku) / n
    mouse_ratio = (mm + cl + sc) / n

    # -- 7. Digraph features (key-pair transition timing) ---
    # These capture the unique muscle-memory transitions between key pairs.
    # They are the #1 most discriminative feature in keystroke dynamics research.

    key_events_ordered = [
        e for e in events if e.eventType in ("keydown", "keyup") and e.key
    ]

    digraph_flights: list[float] = []    # keyup(N) -> keydown(N+1)
    digraph_durations: list[float] = []  # keydown(N) -> keyup(N+1) spanning two chars
    hold_flight_ratios: list[float] = []

    prev_keyup_ts: float | None = None
    prev_hold_time: float | None = None
    last_kd_ts: dict[str, int] = {}

    for e in key_events_ordered:
        if e.eventType == "keydown" and e.key:
            last_kd_ts[e.key] = e.timestamp
            # Digraph flight: time from previous keyup to this keydown
            if prev_keyup_ts is not None:
                flight = e.timestamp - prev_keyup_ts
                if 0 < flight < 5_000:
                    digraph_flights.append(float(flight))
                    # Hold-to-flight ratio
                    if prev_hold_time is not None and flight > 0:
                        ratio = prev_hold_time / flight
                        if 0 < ratio < 100:
                            hold_flight_ratios.append(ratio)

        elif e.eventType == "keyup" and e.key:
            prev_keyup_ts = e.timestamp
            if e.key in last_kd_ts:
                hold = e.timestamp - last_kd_ts[e.key]
                if 0 < hold < 5_000:
                    prev_hold_time = float(hold)
                else:
                    prev_hold_time = None

    # Digraph duration: keydown(N) -> keyup(N+1) for consecutive keydown pairs
    kd_events = [e for e in events if e.eventType == "keydown" and e.key]
    ku_events = [e for e in events if e.eventType == "keyup" and e.key]
    keyup_lookup: dict[str, list[int]] = {}
    for e in ku_events:
        if e.key:
            keyup_lookup.setdefault(e.key, []).append(e.timestamp)

    for i in range(len(kd_events) - 1):
        kd_curr = kd_events[i]
        kd_next = kd_events[i + 1]
        if kd_next.key and kd_next.key in keyup_lookup and keyup_lookup[kd_next.key]:
            for ku_ts in keyup_lookup[kd_next.key]:
                if ku_ts >= kd_next.timestamp:
                    dur = ku_ts - kd_curr.timestamp
                    if 0 < dur < 10_000:
                        digraph_durations.append(float(dur))
                    break

    avg_di_flight = float(np.mean(digraph_flights)) if digraph_flights else 0.0
    std_di_flight = _safe_std(digraph_flights)
    avg_di_duration = float(np.mean(digraph_durations)) if digraph_durations else 0.0
    std_di_duration = _safe_std(digraph_durations)
    avg_hf_ratio = float(np.mean(hold_flight_ratios)) if hold_flight_ratios else 0.0
    std_hf_ratio = _safe_std(hold_flight_ratios)

    # -- 8. Mouse acceleration (change in speed between consecutive moves) ---
    accelerations: list[float] = []
    for i in range(1, len(speeds)):
        accel = speeds[i] - speeds[i - 1]
        accelerations.append(accel)

    avg_accel = float(np.mean(accelerations)) if accelerations else 0.0
    std_accel = _safe_std(accelerations)

    # -- 9. Path directness & Click Intervals ---
    click_events = [
        e for e in events
        if e.eventType == "click"
        and e.clientX is not None and e.clientY is not None
    ]
    click_intervals: list[float] = []

    for i in range(1, len(click_events)):
        prev_c, curr_c = click_events[i - 1], click_events[i]
        dt = curr_c.timestamp - prev_c.timestamp
        if 0 < dt < 30_000:
            click_intervals.append(float(dt))

    avg_click_int = float(np.mean(click_intervals)) if click_intervals else 0.0
    std_click_int = _safe_std(click_intervals)

    # Path directness over the entire session's mouse trajectory
    path_direct = 0.0
    if len(mouse_events) >= 2:
        start_m, end_m = mouse_events[0], mouse_events[-1]
        straight = math.hypot(end_m.clientX - start_m.clientX, end_m.clientY - start_m.clientY)  # type: ignore[operator]
        
        actual_dist = 0.0
        for i in range(1, len(mouse_events)):
            p, c = mouse_events[i - 1], mouse_events[i]
            actual_dist += math.hypot(c.clientX - p.clientX, c.clientY - p.clientY)  # type: ignore[operator]
            
        if actual_dist > 0:
            path_direct = float(straight / actual_dist)

    # -- 10. Click precision (mean distance of clicks from click centroid) ---
    if len(click_events) >= 2:
        cx = float(np.mean([e.clientX for e in click_events if e.clientX is not None]))
        cy = float(np.mean([e.clientY for e in click_events if e.clientY is not None]))
        click_dists = [
            math.hypot(e.clientX - cx, e.clientY - cy)  # type: ignore[operator]
            for e in click_events
            if e.clientX is not None and e.clientY is not None
        ]
        click_prec = float(np.mean(click_dists)) if click_dists else 0.0
    else:
        click_prec = 0.0

    # -- Assemble ---
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
        avg_di_flight,
        std_di_flight,
        avg_di_duration,
        std_di_duration,
        avg_hf_ratio,
        std_hf_ratio,
        avg_accel,
        std_accel,
        path_direct,
        avg_click_int,
        std_click_int,
        click_prec,
    ], dtype=np.float64)
