"""
Evaluate the fall-detection model and generate result charts *from the dataset*.

Reads data/dataset.csv (the 7 features + label + recording group), reproduces the
honest evaluation used in train_model.py, and writes:

  figures/metrics_bar.png            precision / recall / F1 for the fall class
  figures/confusion_matrix.png       hold-out confusion matrix
  figures/per_subject_loso.png       leave-one-subject-out recall & precision
  figures/feature_importances.png    what the Random Forest relies on
  figures/metrics.json               all numbers, machine-readable
  results-dashboard.html             self-contained web dashboard, live numbers
                                     (dashboard_template.html filled from the data)

Every number and bar is computed live from dataset.csv — nothing is hard-coded —
so the charts and dashboard are genuine output of your data. Change the dataset,
re-run, and everything updates; the outputs are git-ignored (never stale).

This is SEPARATE from live_inference.py (the real-time sensor/camera detection):
run it on demand when you want to see or present the metrics, not during a live
demo.

Run:  python evaluate_and_plot.py
"""

from __future__ import annotations
import os
import re
import json
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")               # headless: just write PNG files
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedGroupKFold
from sklearn.metrics import (classification_report, confusion_matrix,
                             recall_score, precision_score, f1_score)

from feature_extraction import FEATURE_NAMES

DATA_PATH = os.path.join("data", "dataset.csv")
FIG_DIR   = "figures"

# palette (matches the HTML dashboard)
TEAL, INDIGO = "#0E9E8E", "#4C6EF5"
GOOD, WARN, CRIT = "#128A4C", "#B96E1B", "#C93A3A"
INK, MUTED, GRID = "#1f2a27", "#5C6B69", "#E4E9E7"
IMAGE_FEATURES = {"bbox_aspect_ratio", "centroid_height", "frame_motion"}


def new_rf():
    return RandomForestClassifier(n_estimators=200, class_weight="balanced",
                                  random_state=42)


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.set_axisbelow(True)


def main():
    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_NAMES].values
    y = df["label"].values
    groups = df["group"].values
    subj = np.array([int(re.search(r"Subject(\d+)", g).group(1)) for g in groups])
    os.makedirs(FIG_DIR, exist_ok=True)

    n_subjects = len(np.unique(subj))
    n_records = len(np.unique(groups))
    print(f"Loaded {len(df)} windows | {int((y==1).sum())} fall / {int((y==0).sum())} "
          f"not-fall | {n_records} recordings | {n_subjects} subjects")

    # ---- cross-validated F1 (grouped) ----
    cv = cross_val_score(new_rf(), X, y, cv=StratifiedGroupKFold(n_splits=5),
                         groups=groups, scoring="f1")

    # ---- grouped hold-out for the per-class report + confusion matrix ----
    tr, te = next(StratifiedGroupKFold(n_splits=4).split(X, y, groups))
    clf = new_rf().fit(X[tr], y[tr])
    y_pred = clf.predict(X[te])
    rep = classification_report(y[te], y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y[te], y_pred)
    fall = rep["1"]

    # ---- leave-one-subject-out ----
    loso = []
    for s in sorted(np.unique(subj)):
        m = subj == s
        if y[m].sum() == 0:
            continue
        mdl = new_rf().fit(X[~m], y[~m])
        p = mdl.predict(X[m])
        loso.append({
            "subject": int(s),
            "recall": recall_score(y[m], p, pos_label=1, zero_division=0),
            "precision": precision_score(y[m], p, pos_label=1, zero_division=0),
            "falls": int(y[m].sum()),
        })
    loso_recall = float(np.mean([r["recall"] for r in loso]))
    loso_prec = float(np.mean([r["precision"] for r in loso]))

    # ---- feature importances ----
    importances = sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                         key=lambda t: t[1], reverse=True)

    # ---------- console summary ----------
    print(f"\n5-fold grouped CV F1 : {cv.mean():.3f} +/- {cv.std():.3f}")
    print(f"Hold-out fall class  : precision {fall['precision']:.3f}  "
          f"recall {fall['recall']:.3f}  F1 {fall['f1-score']:.3f}")
    print(f"Subject-independent  : recall {loso_recall:.1%}  precision {loso_prec:.1%} "
          f"(avg over {len(loso)} held-out subjects)")

    # ---------- 1) metrics bar ----------
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=150)
    names = ["Precision", "Recall", "F1-score"]
    vals = [fall["precision"], fall["recall"], fall["f1-score"]]
    cols = [INDIGO, TEAL, "#7A8B88"]
    bars = ax.bar(names, vals, color=cols, width=0.62, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center", va="bottom", fontsize=11, color=INK, fontweight="bold")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("score", color=MUTED, fontsize=10)
    ax.set_title("Fall-class metrics (hold-out)", color=INK, fontsize=12,
                 fontweight="bold", pad=10)
    ax.yaxis.grid(True, color=GRID, lw=1)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/metrics_bar.png", facecolor="white")
    plt.close(fig)

    # ---------- 2) confusion matrix ----------
    fig, ax = plt.subplots(figsize=(4.8, 4.2), dpi=150)
    labels = ["not-fall", "fall"]
    ax.imshow(cm, cmap="BuGn", alpha=0.0)              # keep frame, colour cells manually
    cell_c = [[ "#E2F1EF", "#F7ECDD"], ["#F7E3E3", "#E4F3EA"]]
    txt_c  = [[TEAL, WARN], [CRIT, GOOD]]
    notes  = [["true negative", "false alarm"], ["missed fall", "fall caught"]]
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, color=cell_c[i][j], zorder=1))
            ax.text(j, i-0.08, f"{cm[i, j]}", ha="center", va="center",
                    fontsize=22, fontweight="bold", color=txt_c[i][j], zorder=2)
            ax.text(j, i+0.28, notes[i][j], ha="center", va="center",
                    fontsize=9, color=MUTED, zorder=2)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted", color=INK, fontsize=11, fontweight="bold")
    ax.set_ylabel("Actual", color=INK, fontsize=11, fontweight="bold")
    ax.set_title("Confusion matrix (hold-out)", color=INK, fontsize=12,
                 fontweight="bold", pad=10)
    ax.set_xlim(-0.5, 1.5); ax.set_ylim(1.5, -0.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, length=0, labelsize=10)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/confusion_matrix.png", facecolor="white")
    plt.close(fig)

    # ---------- 3) per-subject LOSO ----------
    fig, ax = plt.subplots(figsize=(7.6, 5.2), dpi=150)
    ys = np.arange(len(loso))
    rec = [r["recall"] for r in loso]
    pre = [r["precision"] for r in loso]
    ax.barh(ys - 0.2, rec, height=0.38, color=TEAL, label="Recall", zorder=3)
    ax.barh(ys + 0.2, pre, height=0.38, color=INDIGO, label="Precision", zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"S{r['subject']}" for r in loso])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.05)
    ax.axvline(loso_recall, color=TEAL, ls="--", lw=1, alpha=0.6, zorder=2)
    ax.axvline(loso_prec, color=INDIGO, ls="--", lw=1, alpha=0.6, zorder=2)
    ax.set_xlabel("score", color=MUTED, fontsize=10)
    ax.set_title(f"Leave-one-subject-out  (avg recall {loso_recall:.0%}, "
                 f"precision {loso_prec:.0%})", color=INK, fontsize=12,
                 fontweight="bold", pad=10)
    ax.xaxis.grid(True, color=GRID, lw=1)
    ax.legend(frameon=False, fontsize=10, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/per_subject_loso.png", facecolor="white")
    plt.close(fig)

    # ---------- 4) feature importances ----------
    fig, ax = plt.subplots(figsize=(7.0, 3.8), dpi=150)
    fnames = [n for n, _ in importances][::-1]
    fvals = [v for _, v in importances][::-1]
    fcols = [INDIGO if n in IMAGE_FEATURES else TEAL for n in fnames]
    bars = ax.barh(fnames, fvals, color=fcols, height=0.66, zorder=3)
    for b, v in zip(bars, fvals):
        ax.text(v + 0.004, b.get_y() + b.get_height() / 2, f"{v:.3f}",
                va="center", fontsize=9, color=MUTED)
    ax.set_xlim(0, max(fvals) * 1.16)
    ax.set_title("Feature importances  (teal = motion, indigo = image)",
                 color=INK, fontsize=12, fontweight="bold", pad=10)
    ax.xaxis.grid(True, color=GRID, lw=1)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/feature_importances.png", facecolor="white")
    plt.close(fig)

    # ---------- structured metrics (drives both metrics.json and the dashboard) ----------
    nf = rep["0"]
    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dataset": {"windows": len(df), "falls": int((y == 1).sum()),
                    "not_falls": int((y == 0).sum()),
                    "recordings": n_records, "subjects": n_subjects},
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
        "loso": {"recall": round(loso_recall, 3), "precision": round(loso_prec, 3),
                 "per_subject": [{"subject": r["subject"],
                                  "recall": round(r["recall"], 3),
                                  "precision": round(r["precision"], 3),
                                  "falls": r["falls"]} for r in loso]},
        "features": [{"name": n, "importance": round(float(v), 3),
                      "modality": "image" if n in IMAGE_FEATURES else "motion"}
                     for n, v in importances],
    }
    with open(f"{FIG_DIR}/metrics.json", "w") as f:
        json.dump(data, f, indent=2)

    # ---------- fill the HTML dashboard template with the LIVE numbers ----------
    tpl_path, out_html = "dashboard_template.html", "results-dashboard.html"
    if os.path.exists(tpl_path):
        with open(tpl_path, encoding="utf-8") as f:
            tpl = f.read()
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(tpl.replace("__DATA__", json.dumps(data)))
        print(f"\nSaved 4 charts + metrics.json to {FIG_DIR}/, and {out_html} (live numbers).")
    else:
        print(f"\nSaved 4 charts + metrics.json to {FIG_DIR}/ "
              f"({tpl_path} missing — skipped HTML dashboard).")


if __name__ == "__main__":
    main()
