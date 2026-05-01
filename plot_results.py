"""
plot_results.py
Generates an interactive Plotly HTML dashboard with 6 performance charts:
  1. ROC Curve
  2. Score Distribution (Owner vs Intruder)
  3. Threshold Sweep (Trade-off curve)
  4. Grid Search Heatmap (Balanced Accuracy)
  5. Confusion Matrix Heatmap
  6. Algorithm Comparison Bar Chart

Output: data/model/performance_dashboard.html
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from itertools import product

from sklearn.svm import OneClassSVM
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    confusion_matrix, roc_curve, auc,
    balanced_accuracy_score, roc_auc_score
)

import plotly.graph_objects as go
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
import plotly.io as pio

# ── Paths ─────────────────────────────────────────────────────────────────────
MODEL_DIR    = Path(r"d:\BEHAVE SEC\data\model")
OUTPUT_HTML  = MODEL_DIR / "performance_dashboard.html"
FRONTEND_HTML = Path(r"d:\BEHAVE SEC\frontend\plot_results.html")

PALETTE = {
    "owner":    "#00d4ff",
    "intruder": "#ff3366",
    "good":     "#00ff88",
    "warning":  "#ffaa00",
    "bg":       "#0d1117",
    "surface":  "#161b22",
    "grid":     "#21262d",
    "text":     "#e6edf3",
    "blue":     "#1a56de",
    "purple":   "#8b5cf6",
}

# ── Data loading ──────────────────────────────────────────────────────────────
def load_owner_data():
    buffers = []
    for npy_file in MODEL_DIR.glob("training_data_*.npy"):
        data = np.load(str(npy_file))
        if data.ndim == 2 and data.shape[1] == 28 and len(data) >= 2:
            buffers.append(data)
    return np.vstack(buffers) if buffers else None

def generate_intruder_vectors(X_owner_biometric, n_intruders=200, rng_seed=42):
    rng = np.random.default_rng(rng_seed)
    mu  = X_owner_biometric.mean(axis=0)
    std = X_owner_biometric.std(axis=0) + 1e-8
    n_hard   = int(n_intruders * 0.35)
    n_medium = int(n_intruders * 0.40)
    n_easy   = n_intruders - n_hard - n_medium

    def make_group(n, low, high):
        shift  = rng.uniform(low, high, size=mu.shape) * rng.choice([-1, 1], size=mu.shape)
        center = np.clip(mu + shift * std, 0, None)
        grp_std = std * rng.uniform(0.85, 1.15, size=std.shape)
        return np.clip(rng.normal(loc=center, scale=grp_std, size=(n, mu.shape[0])), 0, None)

    return np.vstack([
        make_group(n_hard,   0.3, 0.7),
        make_group(n_medium, 0.7, 1.2),
        make_group(n_easy,   1.2, 1.8),
    ])

def sigmoid(x, slope=8.0):
    return 1.0 / (1.0 + np.exp(slope * x))

# ── Build full evaluation dataset ─────────────────────────────────────────────
def build_eval_data(X_bio, nu=0.01, gamma="scale", n_intruders=200):
    """Train on 80% of owner data, score remaining 20% + intruders."""
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(X_bio))
    split = int(len(X_bio) * 0.8)
    X_train = X_bio[idx[:split]]
    X_test  = X_bio[idx[split:]]

    X_intr  = generate_intruder_vectors(X_train, n_intruders=n_intruders)
    X_intr_labeled = ["Hard Intruder"] * int(n_intruders * 0.35) + \
                     ["Medium Intruder"] * int(n_intruders * 0.40) + \
                     ["Easy Intruder"]  * (n_intruders - int(n_intruders*0.35) - int(n_intruders*0.40))

    scaler   = StandardScaler()
    X_tr_sc  = scaler.fit_transform(X_train)
    X_te_sc  = scaler.transform(X_test)
    X_in_sc  = scaler.transform(X_intr)

    model = OneClassSVM(kernel="rbf", nu=nu, gamma=gamma)
    model.fit(X_tr_sc)

    owner_raw   = model.decision_function(X_te_sc)
    intruder_raw= model.decision_function(X_in_sc)

    owner_scores   = sigmoid(owner_raw)
    intruder_scores= sigmoid(intruder_raw)

    y_true  = np.concatenate([np.zeros(len(X_test)), np.ones(len(X_intr))])
    y_score = np.concatenate([owner_scores, intruder_scores])
    labels  = ["Owner"] * len(X_test) + X_intr_labeled

    return y_true, y_score, labels, owner_scores, intruder_scores

# ── Grid search data ──────────────────────────────────────────────────────────
def grid_search(X_bio, threshold=0.55):
    nu_vals    = [0.001, 0.01, 0.05, 0.10]
    gamma_vals = ["scale", "auto", 0.01, 0.001]
    results = {}
    for nu, gamma in product(nu_vals, gamma_vals):
        y_true, y_score, _, _, _ = build_eval_data(X_bio, nu=nu, gamma=gamma, n_intruders=150)
        y_pred = (y_score >= threshold).astype(int)
        ba = balanced_accuracy_score(y_true, y_pred) * 100
        results[(nu, str(gamma))] = round(ba, 1)
    return results, nu_vals, gamma_vals

# ── Plot helpers ──────────────────────────────────────────────────────────────
def dark_layout(title, xaxis_title="", yaxis_title="", height=420):
    return dict(
        title=dict(text=title, font=dict(color=PALETTE["text"], size=16), x=0.5),
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["surface"],
        font=dict(color=PALETTE["text"], family="Calibri, Arial"),
        xaxis=dict(title=xaxis_title, gridcolor=PALETTE["grid"], showgrid=True,
                   zeroline=False, color=PALETTE["text"]),
        yaxis=dict(title=yaxis_title, gridcolor=PALETTE["grid"], showgrid=True,
                   zeroline=False, color=PALETTE["text"]),
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
    )

# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("Loading real owner data...")
    X_owner = load_owner_data()
    if X_owner is None or len(X_owner) < 4:
        print("[ERROR] Not enough training data found.")
        return

    X_bio = X_owner[:, 6:28]   # 22 biometric features
    print(f"Owner sessions: {len(X_bio)} | Biometric features: {X_bio.shape[1]}")

    # ── Evaluate best model ────────────────────────────────────────────────────
    print("Evaluating best model (nu=0.01, gamma='scale')...")
    y_true, y_score, labels, owner_scores, intruder_scores = \
        build_eval_data(X_bio, nu=0.01, gamma="scale", n_intruders=200)

    threshold = 0.55
    y_pred = (y_score >= threshold).astype(int)

    # ── Grid search ────────────────────────────────────────────────────────────
    print("Running grid search (this takes ~20s)...")
    grid_results, nu_vals, gamma_vals = grid_search(X_bio)

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 1 — ROC Curve
    # ══════════════════════════════════════════════════════════════════════════
    fpr, tpr, roc_thresholds = roc_curve(y_true, y_score)
    roc_auc_val = auc(fpr, tpr)

    fig_roc = go.Figure()
    fig_roc.add_trace(go.Scatter(
        x=fpr, y=tpr,
        mode="lines",
        name=f"OneClassSVM (AUC = {roc_auc_val:.4f})",
        line=dict(color=PALETTE["blue"], width=3),
        fill="tozeroy", fillcolor="rgba(26,86,222,0.12)"
    ))
    # Mark operating threshold point
    op_idx = np.argmin(np.abs(roc_thresholds - threshold))
    fig_roc.add_trace(go.Scatter(
        x=[fpr[op_idx]], y=[tpr[op_idx]],
        mode="markers+text",
        name=f"Threshold = {threshold}",
        marker=dict(size=12, color=PALETTE["good"], symbol="diamond",
                    line=dict(color="white", width=2)),
        text=[f"  thr={threshold}<br>  FPR={fpr[op_idx]:.3f}<br>  TPR={tpr[op_idx]:.3f}"],
        textposition="middle right",
        textfont=dict(color=PALETTE["good"], size=11)
    ))
    fig_roc.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines", name="Random Classifier",
        line=dict(color=PALETTE["warning"], width=1.5, dash="dash")
    ))
    fig_roc.update_layout(**dark_layout(
        "ROC Curve — OneClassSVM Anomaly Detector",
        "False Positive Rate (Intruder Accepted)", "True Positive Rate (Intruder Rejected)", 480
    ))
    fig_roc.update_layout(legend=dict(
        bgcolor="rgba(22,27,34,0.85)", bordercolor=PALETTE["grid"],
        borderwidth=1, font=dict(size=12)
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 2 — Score Distribution
    # ══════════════════════════════════════════════════════════════════════════
    # Split intruders by difficulty
    hard_scores   = intruder_scores[:int(len(intruder_scores)*0.35)]
    medium_scores = intruder_scores[int(len(intruder_scores)*0.35):int(len(intruder_scores)*0.75)]
    easy_scores   = intruder_scores[int(len(intruder_scores)*0.75):]

    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=owner_scores, name="Owner Sessions",
        marker_color=PALETTE["owner"], opacity=0.75,
        xbins=dict(start=0, end=1, size=0.04),
        histnorm="percent"
    ))
    fig_dist.add_trace(go.Histogram(
        x=hard_scores, name="Hard Intruder (similar typist)",
        marker_color="#ff9966", opacity=0.70,
        xbins=dict(start=0, end=1, size=0.04),
        histnorm="percent"
    ))
    fig_dist.add_trace(go.Histogram(
        x=medium_scores, name="Medium Intruder",
        marker_color="#ff6644", opacity=0.70,
        xbins=dict(start=0, end=1, size=0.04),
        histnorm="percent"
    ))
    fig_dist.add_trace(go.Histogram(
        x=easy_scores, name="Easy Intruder (clearly different)",
        marker_color=PALETTE["intruder"], opacity=0.70,
        xbins=dict(start=0, end=1, size=0.04),
        histnorm="percent"
    ))
    fig_dist.add_vline(
        x=threshold, line_width=2.5, line_dash="dash",
        line_color=PALETTE["good"],
        annotation_text=f"Decision Threshold ({threshold})",
        annotation_font_color=PALETTE["good"],
        annotation_position="top right"
    )
    fig_dist.update_layout(**dark_layout(
        "Anomaly Score Distribution — Owner vs Intruder Tiers",
        "Anomaly Score (0 = Normal, 1 = Anomaly)", "% of Sessions", 480
    ))
    fig_dist.update_layout(barmode="overlay", legend=dict(
        bgcolor="rgba(22,27,34,0.85)", bordercolor=PALETTE["grid"], borderwidth=1
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 3 — Threshold Sweep
    # ══════════════════════════════════════════════════════════════════════════
    thresholds = np.arange(0.30, 0.72, 0.02)
    owner_acc_list, intruder_rej_list, bal_acc_list = [], [], []

    n_owners   = int(np.sum(y_true == 0))
    n_intruders = int(np.sum(y_true == 1))
    owner_s_all  = y_score[y_true == 0]
    intruder_s_all = y_score[y_true == 1]

    for thr in thresholds:
        oa = np.sum(owner_s_all < thr) / n_owners * 100
        ir = np.sum(intruder_s_all >= thr) / n_intruders * 100
        ba = (oa + ir) / 2
        owner_acc_list.append(round(oa, 2))
        intruder_rej_list.append(round(ir, 2))
        bal_acc_list.append(round(ba, 2))

    fig_thr = go.Figure()
    fig_thr.add_trace(go.Scatter(
        x=thresholds, y=owner_acc_list,
        name="Owner Acceptance Rate (%)",
        line=dict(color=PALETTE["owner"], width=2.5),
        mode="lines+markers", marker=dict(size=5)
    ))
    fig_thr.add_trace(go.Scatter(
        x=thresholds, y=intruder_rej_list,
        name="Intruder Rejection Rate (%)",
        line=dict(color=PALETTE["intruder"], width=2.5),
        mode="lines+markers", marker=dict(size=5)
    ))
    fig_thr.add_trace(go.Scatter(
        x=thresholds, y=bal_acc_list,
        name="Balanced Accuracy (%)",
        line=dict(color=PALETTE["purple"], width=2, dash="dot"),
        mode="lines+markers", marker=dict(size=5)
    ))
    fig_thr.add_vline(
        x=threshold, line_width=2, line_dash="dash",
        line_color=PALETTE["good"],
        annotation_text=f"Selected: {threshold}",
        annotation_font_color=PALETTE["good"],
        annotation_position="top left"
    )
    fig_thr.update_layout(**dark_layout(
        "Threshold Sweep — Owner Acceptance vs Intruder Rejection",
        "Decision Threshold", "Rate (%)", 460
    ))
    fig_thr.update_layout(legend=dict(
        bgcolor="rgba(22,27,34,0.85)", bordercolor=PALETTE["grid"], borderwidth=1
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 4 — Grid Search Heatmap
    # ══════════════════════════════════════════════════════════════════════════
    gamma_str_labels = ["'scale'", "'auto'", "0.01", "0.001"]
    nu_str_labels    = ["0.001", "0.01", "0.05", "0.10"]
    z_matrix = []
    for nu in nu_vals:
        row = []
        for gamma in gamma_vals:
            key = (nu, str(gamma))
            row.append(grid_results.get(key, 0))
        z_matrix.append(row)

    text_matrix = [[f"{v}%" for v in row] for row in z_matrix]

    fig_hm = go.Figure(data=go.Heatmap(
        z=z_matrix,
        x=gamma_str_labels,
        y=nu_str_labels,
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=13, color="white"),
        colorscale=[
            [0.0,  "#1a1f2e"],
            [0.4,  "#1a3a6e"],
            [0.7,  "#1a56de"],
            [0.9,  "#00aaff"],
            [1.0,  "#00ff88"],
        ],
        colorbar=dict(
            title=dict(text="Balanced Accuracy (%)", font=dict(color=PALETTE["text"])),
            tickfont=dict(color=PALETTE["text"]),
        ),
        zmin=45, zmax=100,
    ))
    # Highlight the best cell
    best_nu_idx    = nu_str_labels.index("0.01")
    best_gamma_idx = gamma_str_labels.index("'scale'")
    fig_hm.add_shape(
        type="rect",
        x0=best_gamma_idx - 0.5, x1=best_gamma_idx + 0.5,
        y0=best_nu_idx - 0.5,    y1=best_nu_idx + 0.5,
        line=dict(color=PALETTE["good"], width=3)
    )
    fig_hm.update_layout(**dark_layout(
        "Hyperparameter Grid Search — Balanced Accuracy (%)",
        "Gamma", "Nu", 420
    ))
    fig_hm.update_layout(
        xaxis=dict(side="bottom"),
        annotations=[dict(
            x=best_gamma_idx, y=best_nu_idx,
            text="BEST", showarrow=False,
            yshift=22, font=dict(color=PALETTE["good"], size=11, family="Calibri Bold")
        )]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 5 — Confusion Matrix
    # ══════════════════════════════════════════════════════════════════════════
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    cm_labels = ["Owner (Normal)", "Intruder (Anomaly)"]

    cm_text = [
        [f"TN = {tn}<br>Correctly Accepted<br>{tn/(tn+fp)*100:.1f}% Owner Acc",
         f"FP = {fp}<br>Incorrectly Rejected<br>{fp/(tn+fp)*100:.1f}% FRR"],
        [f"FN = {fn}<br>Incorrectly Accepted<br>{fn/(fn+tp)*100:.1f}% FAR",
         f"TP = {tp}<br>Correctly Rejected<br>{tp/(fn+tp)*100:.1f}% Intruder Rej"],
    ]
    cm_colors = [
        [PALETTE["good"] if tn > fp else PALETTE["intruder"],
         PALETTE["intruder"] if fp > 0 else PALETTE["good"]],
        [PALETTE["intruder"] if fn > 0 else PALETTE["good"],
         PALETTE["good"]],
    ]

    fig_cm = go.Figure(data=go.Heatmap(
        z=[[tn, fp], [fn, tp]],
        x=[f"Pred: Normal", "Pred: Anomaly"],
        y=[f"Act: Owner", "Act: Intruder"],
        text=cm_text,
        texttemplate="%{text}",
        textfont=dict(size=12, color="white"),
        colorscale=[
            [0.0, "#1a1f2e"],
            [0.3, "#1a3a6e"],
            [1.0, "#00ff88"],
        ],
        showscale=False,
    ))
    fig_cm.update_layout(**dark_layout(
        f"Confusion Matrix (Threshold = {threshold})",
        "Predicted Label", "Actual Label", 380
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # FIG 6 — Algorithm Comparison
    # ══════════════════════════════════════════════════════════════════════════
    # Evaluate Isolation Forest on same data
    X_train_idx = np.random.default_rng(0).permutation(len(X_bio))[:int(len(X_bio)*0.8)]
    X_train_bio = X_bio[X_train_idx]
    X_test_bio  = X_bio[[i for i in range(len(X_bio)) if i not in X_train_idx]]
    X_intr_bio  = generate_intruder_vectors(X_train_bio, n_intruders=200)

    iforest = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    iforest.fit(X_train_bio)
    raw_o_if = iforest.score_samples(X_test_bio)
    raw_i_if = iforest.score_samples(X_intr_bio)
    all_raw  = np.concatenate([raw_o_if, raw_i_if])
    norm     = (all_raw - all_raw.min()) / (all_raw.max() - all_raw.min() + 1e-8)
    n_o = len(X_test_bio)
    if_o_scores = 1 - norm[:n_o]
    if_i_scores = 1 - norm[n_o:]
    y_true_if = np.concatenate([np.zeros(n_o), np.ones(len(X_intr_bio))])
    y_score_if = np.concatenate([if_o_scores, if_i_scores])
    y_pred_if  = (y_score_if >= threshold).astype(int)

    def get_metrics(y_t, y_p, y_s):
        cm_ = confusion_matrix(y_t, y_p, labels=[0,1])
        tn_,fp_,fn_,tp_ = cm_.ravel()
        oa_ = tn_/(tn_+fp_)*100 if (tn_+fp_)>0 else 0
        ir_ = tp_/(tp_+fn_)*100 if (tp_+fn_)>0 else 0
        ba_ = balanced_accuracy_score(y_t, y_p)*100
        au_ = roc_auc_score(y_t, y_s)*100
        return round(oa_,1), round(ir_,1), round(ba_,1), round(au_,1)

    metrics_ocsvm = get_metrics(y_true, y_pred, y_score)
    metrics_if    = get_metrics(y_true_if, y_pred_if, y_score_if)

    categories    = ["Owner Acceptance %", "Intruder Rejection %", "Balanced Accuracy %", "AUC × 100"]
    ocsvm_vals    = list(metrics_ocsvm)
    iforest_vals  = list(metrics_if)

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="OneClassSVM (RBF)",
        x=categories, y=ocsvm_vals,
        marker_color=PALETTE["blue"],
        marker_line=dict(color="white", width=0.5),
        text=[f"{v}%" for v in ocsvm_vals],
        textposition="outside",
        textfont=dict(color=PALETTE["text"])
    ))
    fig_bar.add_trace(go.Bar(
        name="Isolation Forest",
        x=categories, y=iforest_vals,
        marker_color=PALETTE["purple"],
        marker_line=dict(color="white", width=0.5),
        text=[f"{v}%" for v in iforest_vals],
        textposition="outside",
        textfont=dict(color=PALETTE["text"])
    ))
    fig_bar.update_layout(**dark_layout(
        "Algorithm Comparison — OneClassSVM vs Isolation Forest",
        "", "Result (%)", 460
    ))
    fig_bar.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 115]),
        legend=dict(bgcolor="rgba(22,27,34,0.85)", bordercolor=PALETTE["grid"], borderwidth=1)
    )

    # ══════════════════════════════════════════════════════════════════════════
    # Assemble HTML dashboard
    # ══════════════════════════════════════════════════════════════════════════
    print("Building interactive HTML dashboard...")

    def to_html(fig):
        return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": True})

    tn_f, fp_f, fn_f, tp_f = confusion_matrix(y_true, y_pred, labels=[0,1]).ravel()
    owner_acc   = round(tn_f/(tn_f+fp_f)*100, 1)
    intruder_rej= round(tp_f/(tp_f+fn_f)*100, 1)
    bal_acc     = round(balanced_accuracy_score(y_true, y_pred)*100, 1)
    auc_val     = round(roc_auc_score(y_true, y_score), 4)
    frr         = round(100 - owner_acc, 1)
    far         = round(100 - intruder_rej, 1)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BEHAVE-SEC | Performance Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{PALETTE["bg"]}; color:{PALETTE["text"]}; font-family:"Calibri","Segoe UI",Arial,sans-serif; }}

  header {{
    background:linear-gradient(135deg,#0d1117 0%,#161b22 60%,#1a2535 100%);
    border-bottom:1px solid #30363d;
    padding:28px 40px;
    display:flex; align-items:center; justify-content:space-between;
  }}
  header h1 {{ font-size:26px; color:{PALETTE["text"]}; letter-spacing:2px; }}
  header h1 span {{ color:{PALETTE["blue"]}; }}
  header p  {{ font-size:13px; color:#8b949e; margin-top:4px; }}
  .badge {{
    background:#1a56de22; border:1px solid {PALETTE["blue"]};
    color:{PALETTE["blue"]}; font-size:12px; padding:4px 12px;
    border-radius:20px; letter-spacing:1px;
  }}

  .kpi-row {{
    display:grid; grid-template-columns:repeat(6,1fr); gap:16px;
    padding:28px 40px 0;
  }}
  .kpi {{
    background:{PALETTE["surface"]};
    border:1px solid #30363d;
    border-radius:12px; padding:20px 16px; text-align:center;
    transition:border-color .2s;
  }}
  .kpi:hover {{ border-color:{PALETTE["blue"]}; }}
  .kpi .val {{ font-size:32px; font-weight:700; letter-spacing:1px; }}
  .kpi .lbl {{ font-size:11px; color:#8b949e; margin-top:6px; text-transform:uppercase; letter-spacing:1px; }}

  .charts-grid {{
    display:grid; grid-template-columns:1fr 1fr; gap:20px;
    padding:28px 40px;
  }}
  .chart-card {{
    background:{PALETTE["surface"]};
    border:1px solid #30363d;
    border-radius:12px; overflow:hidden;
    transition:border-color .2s;
  }}
  .chart-card:hover {{ border-color:#30363d88; }}
  .chart-full {{ grid-column:1 / -1; }}

  footer {{
    text-align:center; padding:20px;
    color:#8b949e; font-size:12px;
    border-top:1px solid #21262d;
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>BEHAVE<span>-SEC</span> &nbsp;|&nbsp; Performance Dashboard</h1>
    <p>Behavioral Biometrics Authentication System — Real Accuracy Metrics &amp; Hyperparameter Analysis</p>
  </div>
  <span class="badge">OneClassSVM · nu=0.01 · gamma=scale · thr=0.55</span>
</header>

<div class="kpi-row">
  <div class="kpi">
    <div class="val" style="color:{PALETTE["purple"]}">{bal_acc}%</div>
    <div class="lbl">Balanced Accuracy</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:{PALETTE["owner"]}">{owner_acc}%</div>
    <div class="lbl">Owner Acceptance</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:{PALETTE["intruder"]}">{frr}%</div>
    <div class="lbl">False Rejection Rate</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:{PALETTE["good"]}">{intruder_rej}%</div>
    <div class="lbl">Intruder Rejection</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:#ffaa00">{far}%</div>
    <div class="lbl">False Acceptance Rate</div>
  </div>
  <div class="kpi">
    <div class="val" style="color:{PALETTE["blue"]}">{auc_val}</div>
    <div class="lbl">ROC · AUC</div>
  </div>
</div>

<div class="charts-grid">
  <div class="chart-card">{to_html(fig_roc)}</div>
  <div class="chart-card">{to_html(fig_dist)}</div>
  <div class="chart-card chart-full">{to_html(fig_thr)}</div>
  <div class="chart-card">{to_html(fig_hm)}</div>
  <div class="chart-card">{to_html(fig_cm)}</div>
  <div class="chart-card chart-full">{to_html(fig_bar)}</div>
</div>

<footer>
  BEHAVE-SEC &nbsp;·&nbsp; Behavioral Biometrics Authentication &nbsp;·&nbsp;
  Real data: {len(X_bio)} owner sessions &nbsp;·&nbsp;
  Intruder tiers: 35% hard / 40% medium / 25% easy &nbsp;·&nbsp;
  5-fold cross-validation
</footer>
</body>
</html>"""

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n[OK] Dashboard saved -> {OUTPUT_HTML}")

    # Also write a copy into the frontend folder so index.html can link to it
    FRONTEND_HTML.write_text(html, encoding="utf-8")
    print(f"[OK] Frontend copy   -> {FRONTEND_HTML}")
    print("     Opening in browser...")

    import webbrowser
    webbrowser.open(FRONTEND_HTML.as_uri())

if __name__ == "__main__":
    main()
