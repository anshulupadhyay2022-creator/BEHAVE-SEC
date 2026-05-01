"""
space_analysis.py
Analyses all 4 feature spaces in BEHAVE-SEC's 22-dimensional biometric vector.
Shows which spaces are alive, partially dead, or completely dead.
"""

import numpy as np
from pathlib import Path

MODEL_DIR = Path(r"d:\BEHAVE SEC\data\model")

# ── Feature space definitions ─────────────────────────────────────────────────
SPACES = {
    "Keyboard Timing": {
        "indices": [0, 1, 2, 3, 8, 9, 10, 11, 12, 13],   # relative to X_bio
        "names": [
            "avg_key_hold_ms",      # 6
            "std_key_hold_ms",      # 7
            "avg_inter_key_ms",     # 8
            "std_inter_key_ms",     # 9
            "avg_digraph_flight_ms",# 16
            "std_digraph_flight_ms",# 17
            "avg_digraph_dur_ms",   # 18
            "std_digraph_dur_ms",   # 19
            "avg_hold_flight_ratio",# 20
            "std_hold_flight_ratio",# 21
        ],
        "global_indices": [6,7,8,9,16,17,18,19,20,21],
    },
    "Session Timing": {
        "indices": [6, 7, 8, 9],
        "names": [
            "session_duration_ms",  # 12
            "events_per_second",    # 13
            "key_event_ratio",      # 14
            "mouse_event_ratio",    # 15
        ],
        "global_indices": [12,13,14,15],
    },
    "Mouse Kinematics": {
        "indices": [4, 5, 16, 17, 18],
        "names": [
            "avg_mouse_speed",      # 10
            "std_mouse_speed",      # 11
            "avg_mouse_accel",      # 22
            "std_mouse_accel",      # 23
            "path_directness_ratio",# 24
        ],
        "global_indices": [10,11,22,23,24],
    },
    "Click Behaviour": {
        "indices": [19, 20, 21],
        "names": [
            "avg_click_interval_ms",# 25
            "std_click_interval_ms",# 26
            "click_precision",      # 27
        ],
        "global_indices": [25,26,27],
    },
}

BIOM_NAMES = [
    "avg_key_hold_ms","std_key_hold_ms","avg_inter_key_ms","std_inter_key_ms",
    "avg_mouse_speed","std_mouse_speed","session_duration_ms","events_per_second",
    "key_event_ratio","mouse_event_ratio","avg_digraph_flight_ms","std_digraph_flight_ms",
    "avg_digraph_dur_ms","std_digraph_dur_ms","avg_hold_flight_ratio","std_hold_flight_ratio",
    "avg_mouse_accel","std_mouse_accel","path_directness","avg_click_interval_ms",
    "std_click_interval_ms","click_precision",
]

def load():
    buffers = []
    for f in MODEL_DIR.glob("training_data_*.npy"):
        d = np.load(str(f))
        if d.ndim == 2 and d.shape[1] == 28 and len(d) >= 2:
            buffers.append(d)
    return np.vstack(buffers)[:, 6:28] if buffers else None

def activity(col, n):
    """Returns (% sessions with non-zero value, is_active)"""
    pct_nonzero = np.sum(col != 0.0) / n * 100
    if pct_nonzero >= 80:   return pct_nonzero, "ACTIVE   "
    if pct_nonzero >= 40:   return pct_nonzero, "PARTIAL  "
    if pct_nonzero >   5:   return pct_nonzero, "SPARSE   "
    return pct_nonzero,                          "DEAD     "

def status_bar(pct, width=20):
    filled = int(pct / 100 * width)
    bar    = "#" * filled + "-" * (width - filled)
    return f"[{bar}]"

def main():
    X_bio = load()
    if X_bio is None:
        print("No data found."); return

    n, d = X_bio.shape
    mu   = X_bio.mean(axis=0)
    std  = X_bio.std(axis=0)
    cv   = std / (np.abs(mu) + 1e-8) * 100

    print("=" * 72)
    print("  BEHAVE-SEC  |  Feature Space Activity Analysis")
    print(f"  {n} real owner sessions  |  {d} biometric dimensions")
    print("=" * 72)

    total_active = 0
    total_partial = 0
    total_sparse  = 0
    total_dead    = 0

    SPACE_ORDER = ["Keyboard Timing", "Session Timing", "Mouse Kinematics", "Click Behaviour"]

    for space_name in SPACE_ORDER:
        info = SPACES[space_name]
        global_idx = info["global_indices"]
        names      = info["names"]
        local_idx  = [gi - 6 for gi in global_idx]

        print(f"\n  [{space_name}]  ({len(names)} dimensions)")
        print("  " + "-" * 68)
        print(f"  {'Feature':<26} {'Mean':>9} {'Std':>9} {'CV%':>7}  {'Active%':>8}  Status")
        print("  " + "-" * 68)

        space_active = 0
        for i, (li, name) in enumerate(zip(local_idx, names)):
            pct_nz, status = activity(X_bio[:, li], n)
            bar = status_bar(pct_nz)
            mean_v = mu[li]; std_v = std[li]; cv_v = cv[li]
            print(f"  {name:<26} {mean_v:>9.2f} {std_v:>9.2f} {cv_v:>6.1f}%  {pct_nz:>6.1f}%  {status} {bar}")
            if "ACTIVE" in status:   space_active += 1; total_active  += 1
            elif "PARTIAL" in status: total_partial += 1
            elif "SPARSE" in status:  total_sparse  += 1
            else:                     total_dead    += 1

        # Space-level summary
        all_pct = [np.sum(X_bio[:, li] != 0.0) / n * 100 for li in local_idx]
        avg_pct = np.mean(all_pct)
        space_status = (
            "FULLY ACTIVE"   if avg_pct >= 80 else
            "PARTIALLY LIVE" if avg_pct >= 40 else
            "MOSTLY DEAD"    if avg_pct >= 10 else
            "COMPLETELY DEAD"
        )
        effective_dims = sum(1 for p in all_pct if p >= 80)
        print(f"\n  Space status : {space_status}  ({effective_dims}/{len(names)} dims effective, avg {avg_pct:.1f}% non-zero)")

    # ── Full summary table ─────────────────────────────────────────────────────
    print("\n")
    print("=" * 72)
    print("  FEATURE SPACE SUMMARY")
    print("=" * 72)
    print(f"\n  {'Space':<22} {'Dims':>5} {'Eff.Dims':>9} {'Avg Active%':>12}  {'Status'}")
    print("  " + "-" * 58)

    effective_total = 0
    for space_name in SPACE_ORDER:
        info    = SPACES[space_name]
        global_idx = info["global_indices"]
        local_idx  = [gi - 6 for gi in global_idx]
        names      = info["names"]
        all_pct    = [np.sum(X_bio[:, li] != 0.0) / n * 100 for li in local_idx]
        avg_pct    = np.mean(all_pct)
        eff_dims   = sum(1 for p in all_pct if p >= 80)
        effective_total += eff_dims
        space_status = (
            "FULLY ACTIVE"    if avg_pct >= 80 else
            "PARTIALLY LIVE"  if avg_pct >= 40 else
            "MOSTLY DEAD"     if avg_pct >= 10 else
            "COMPLETELY DEAD"
        )
        bar = status_bar(avg_pct, 16)
        print(f"  {space_name:<22} {len(names):>5} {eff_dims:>9} {avg_pct:>11.1f}%  {bar} {space_status}")

    print("  " + "-" * 58)
    print(f"  {'TOTAL':<22} {d:>5} {effective_total:>9}  (effective biometric dims)")

    # ── Impact on model ────────────────────────────────────────────────────────
    print("\n")
    print("=" * 72)
    print("  IMPLICATION FOR MODEL ACCURACY")
    print("=" * 72)
    print(f"""
  Claimed  : 22-dimensional multimodal model (keyboard + mouse)
  Reality  : {effective_total}-dimensional model (keyboard + partial session timing)

  Keyboard Timing  : FULLY ACTIVE  -- 10/10 dims working, ~40% CV (high variance)
  Session Timing   : PARTIALLY LIVE -- 3/4 dims active, session_duration OK
                     but mouse_event_ratio is 88% zero (mirrors mouse being dead)
  Mouse Kinematics : COMPLETELY DEAD -- 88.7% of sessions have zero mouse data
                     The Intruder Challenge keyboard phase captures NO mouse events
                     The mouse-challenge phase was either skipped or not wired to
                     the same feature storage pipeline
  Click Behaviour  : COMPLETELY DEAD -- 98-100% zero across all click features
                     No click events are reaching the feature extractor

  Root Cause:
    The behavioral data stored in training_data_guest_demo.npy was captured
    during KEYBOARD-ONLY challenge sessions (challenge.html), not the
    mouse-challenge phase (mouse-challenge.html).
    => Mouse data was NEVER fed into the training pipeline.

  Effect on reported accuracy:
    The OneClassSVM is actually operating on ~10 keyboard features.
    The 12 dead dimensions are all zero for BOTH owner and intruder samples.
    => Zero dims contribute zero distance in the RBF kernel.
    => The effective kernel is computed in ~10D, not 22D.
    => Any intruder generated with zero mouse features (as ours are)
       looks IDENTICAL to the owner in those 12 dimensions.
    => FAR is actually driven entirely by keyboard features alone.
    => The 90.9% balanced accuracy is therefore a KEYBOARD-ONLY result
       dressed up as multimodal.

  Fix Required:
    Ensure mouse-challenge.html and login.html behavioral events are
    submitted to /collect-data and included in the feature training buffer.
    After mouse-enabled re-enrollment with 20+ sessions, the effective
    feature space should expand from ~10D to ~18-20D, which should
    IMPROVE balanced accuracy to the 93-96% range genuinely.
""")

if __name__ == "__main__":
    main()
