"""
Evaluate the fall-detection model and produce result outputs *from the dataset*.

Reads data/dataset.csv (7 features + label + recording group), reproduces the
honest evaluation used in train_model.py, and can:
  * return the metrics as a dict          -> compute_metrics()
  * fill the HTML dashboard template       -> render_dashboard(data)
  * save matplotlib charts + metrics.json  -> make_figures(data)

Run as a script to generate everything into figures/ + results-dashboard.html:
    python evaluate_and_plot.py

Or serve it as a live website (see app.py):
    python app.py     ->  http://127.0.0.1:5000

Every number is computed live from dataset.csv — nothing is hard-coded, so the
charts/dashboard never go stale. This is SEPARATE from live_inference.py (the
real-time sensor/camera detection): run it on demand to show the metrics.
"""

from __future__ import annotations
import os
import re
import json
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedGroupKFold
from sklearn.metrics import (classification_report, confusion_matrix,
                             recall_score, precision_score)

from feature_extraction import FEATURE_NAMES

DATA_PATH = os.path.join("data", "dataset.csv")
FIG_DIR   = "figures"
TEMPLATE  = "dashboard_template.html"
OUT_HTML  = "results-dashboard.html"

TEAL, INDIGO = "#0E9E8E", "#4C6EF5"
GOOD, WARN, CRIT = "#128A4C", "#B96E1B", "#C93A3A"
INK, MUTED, GRID = "#1f2a27", "#5C6B69", "#E4E9E7"
IMAGE_FEATURES = {"bbox_aspect_ratio", "centroid_height", "frame_motion"}


def new_rf():
    return RandomForestClassifier(n_estimators=200, class_weight="balanced",
                                  random_state=42)


def compute_metrics(data_path=DATA_PATH) -> dict:
    """Compute every metric live from the dataset and return a JSON-ready dict."""
    df = pd.read_csv(data_path)
    X = df[FEATURE_NAMES].values
    y = df["label"].values
    groups = df["group"].values
    subj = np.array([int(re.search(r"Subject(\d+)", g).group(1)) for g in groups])

    cv = cross_val_score(new_rf(), X, y, cv=StratifiedGroupKFold(n_splits=5),
                         groups=groups, scoring="f1")

    tr, te = next(StratifiedGroupKFold(n_splits=4).split(X, y, groups))
    clf = new_rf().fit(X[tr], y[tr])
    y_pred = clf.predict(X[te])
    rep = classification_report(y[te], y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y[te], y_pred)
    fall, nf = rep["1"], rep["0"]

    loso = []
    for s in sorted(np.unique(subj)):
        m = subj == s
        if y[m].sum() == 0:
            continue
        mdl = new_rf().fit(X[~m], y[~m])
        p = mdl.predict(X[m])
        loso.append({"subject": int(s),
                     "recall": round(float(recall_score(y[m], p, pos_label=1, zero_division=0)), 3),
                     "precision": round(float(precision_score(y[m], p, pos_label=1, zero_division=0)), 3),
                     "falls": int(y[m].sum())})
    loso_recall = round(float(np.mean([r["recall"] for r in loso])), 3)
    loso_prec = round(float(np.mean([r["precision"] for r in loso])), 3)

    importances = sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                         key=lambda t: t[1], reverse=True)

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dataset": {"windows": len(df), "falls": int((y == 1).sum()),
                    "not_falls": int((y == 0).sum()),
                    "recordings": len(np.unique(groups)),
                    "subjects": len(np.unique(subj))},
        "cv": {"mean": round(float(cv.mean()), 3), "std": round(float(cv.std()), 3)},
        "holdout": {
            "fall": {"precision": round(fall["precision"], 3), "recall": round(fall["recall"], 3),
                     "f1": round(fall["f1-score"], 3), "support": int(fall["support"])},
            "notfall": {"precision": round(nf["precision"], 3), "recall": round(nf["recall"], 3),
                        "f1": round(nf["f1-score"], 3), "support": int(nf["support"])},
            "accuracy": round(rep["accuracy"], 3),
            "support_total": int(fall["support"] + nf["support"]),
            "cm": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
                   "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
        },
        "loso": {"recall": loso_recall, "precision": loso_prec, "per_subject": loso},
        "features": [{"name": n, "importance": round(float(v), 3),
                      "modality": "image" if n in IMAGE_FEATURES else "motion"}
                     for n, v in importances],
    }


def render_dashboard(data, template_path=TEMPLATE) -> str:
    """Return the dashboard HTML with the live metrics injected."""
    with open(template_path, encoding="utf-8") as f:
        tpl = f.read()
    return tpl.replace("__DATA__", json.dumps(data))


def _style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.set_axisbelow(True)


def make_figures(data, fig_dir=FIG_DIR):
    """Save the 4 result charts as PNGs (for the report/slides)."""
    os.makedirs(fig_dir, exist_ok=True)
    h = data["holdout"]

    # 1) metrics bar
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=150)
    vals = [h["fall"]["precision"], h["fall"]["recall"], h["fall"]["f1"]]
    bars = ax.bar(["Precision", "Recall", "F1-score"], vals,
                  color=[INDIGO, TEAL, "#7A8B88"], width=0.62, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}", ha="center",
                va="bottom", fontsize=11, color=INK, fontweight="bold")
    ax.set_ylim(0, 1.08); ax.set_ylabel("score", color=MUTED, fontsize=10)
    ax.set_title("Fall-class metrics (hold-out)", color=INK, fontsize=12, fontweight="bold", pad=10)
    ax.yaxis.grid(True, color=GRID, lw=1); _style(ax)
    fig.tight_layout(); fig.savefig(f"{fig_dir}/metrics_bar.png", facecolor="white"); plt.close(fig)

    # 2) confusion matrix
    cm = [[h["cm"]["tn"], h["cm"]["fp"]], [h["cm"]["fn"], h["cm"]["tp"]]]
    fig, ax = plt.subplots(figsize=(4.8, 4.2), dpi=150)
    cell_c = [["#E2F1EF", "#F7ECDD"], ["#F7E3E3", "#E4F3EA"]]
    txt_c = [[TEAL, WARN], [CRIT, GOOD]]
    notes = [["true negative", "false alarm"], ["missed fall", "fall caught"]]
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color=cell_c[i][j], zorder=1))
            ax.text(j, i - 0.08, f"{cm[i][j]}", ha="center", va="center",
                    fontsize=22, fontweight="bold", color=txt_c[i][j], zorder=2)
            ax.text(j, i + 0.28, notes[i][j], ha="center", va="center",
                    fontsize=9, color=MUTED, zorder=2)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["not-fall", "fall"]); ax.set_yticklabels(["not-fall", "fall"])
    ax.set_xlabel("Predicted", color=INK, fontsize=11, fontweight="bold")
    ax.set_ylabel("Actual", color=INK, fontsize=11, fontweight="bold")
    ax.set_title("Confusion matrix (hold-out)", color=INK, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlim(-0.5, 1.5); ax.set_ylim(1.5, -0.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, length=0, labelsize=10)
    fig.tight_layout(); fig.savefig(f"{fig_dir}/confusion_matrix.png", facecolor="white"); plt.close(fig)

    # 3) per-subject LOSO
    ps = data["loso"]["per_subject"]
    fig, ax = plt.subplots(figsize=(7.6, 5.2), dpi=150)
    ys = np.arange(len(ps))
    ax.barh(ys - 0.2, [r["recall"] for r in ps], height=0.38, color=TEAL, label="Recall", zorder=3)
    ax.barh(ys + 0.2, [r["precision"] for r in ps], height=0.38, color=INDIGO, label="Precision", zorder=3)
    ax.set_yticks(ys); ax.set_yticklabels([f"S{r['subject']}" for r in ps]); ax.invert_yaxis()
    ax.set_xlim(0, 1.05)
    ax.axvline(data["loso"]["recall"], color=TEAL, ls="--", lw=1, alpha=0.6)
    ax.axvline(data["loso"]["precision"], color=INDIGO, ls="--", lw=1, alpha=0.6)
    ax.set_xlabel("score", color=MUTED, fontsize=10)
    ax.set_title(f"Leave-one-subject-out  (avg recall {data['loso']['recall']:.0%}, "
                 f"precision {data['loso']['precision']:.0%})", color=INK, fontsize=12,
                 fontweight="bold", pad=10)
    ax.xaxis.grid(True, color=GRID, lw=1)
    ax.legend(frameon=False, fontsize=10, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    _style(ax)
    fig.tight_layout(); fig.savefig(f"{fig_dir}/per_subject_loso.png", facecolor="white"); plt.close(fig)

    # 4) feature importances
    feats = data["features"][::-1]
    fig, ax = plt.subplots(figsize=(7.0, 3.8), dpi=150)
    fvals = [f["importance"] for f in feats]
    bars = ax.barh([f["name"] for f in feats], fvals,
                   color=[INDIGO if f["modality"] == "image" else TEAL for f in feats],
                   height=0.66, zorder=3)
    for b, v in zip(bars, fvals):
        ax.text(v + 0.004, b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center",
                fontsize=9, color=MUTED)
    ax.set_xlim(0, max(fvals) * 1.16)
    ax.set_title("Feature importances  (teal = motion, indigo = image)",
                 color=INK, fontsize=12, fontweight="bold", pad=10)
    ax.xaxis.grid(True, color=GRID, lw=1); _style(ax)
    fig.tight_layout(); fig.savefig(f"{fig_dir}/feature_importances.png", facecolor="white"); plt.close(fig)


def main():
    data = compute_metrics()
    d, h = data["dataset"], data["holdout"]
    print(f"Loaded {d['windows']} windows | {d['falls']} fall / {d['not_falls']} not-fall "
          f"| {d['recordings']} recordings | {d['subjects']} subjects")
    print(f"\n5-fold grouped CV F1 : {data['cv']['mean']:.3f} +/- {data['cv']['std']:.3f}")
    print(f"Hold-out fall class  : precision {h['fall']['precision']:.3f}  "
          f"recall {h['fall']['recall']:.3f}  F1 {h['fall']['f1']:.3f}")
    print(f"Subject-independent  : recall {data['loso']['recall']:.1%}  "
          f"precision {data['loso']['precision']:.1%}")

    make_figures(data)
    with open(f"{FIG_DIR}/metrics.json", "w") as f:
        json.dump(data, f, indent=2)
    if os.path.exists(TEMPLATE):
        with open(OUT_HTML, "w", encoding="utf-8") as f:
            f.write(render_dashboard(data))
        print(f"\nSaved 4 charts + metrics.json to {FIG_DIR}/, and {OUT_HTML} (live numbers).")
        print(f"Tip: run  python app.py  to serve it as a live website instead.")
    else:
        print(f"\nSaved charts + metrics.json to {FIG_DIR}/ ({TEMPLATE} missing).")


if __name__ == "__main__":
    main()
