"""
Train the Random Forest fall classifier.

Input:  data/dataset.csv  — one row per labelled event.
        Columns: the 7 features in feature_extraction.FEATURE_NAMES, plus a
        'label' column (1 = fall, 0 = not-fall).

Output: fall_rf.joblib    — the trained model + scaler, loaded by live_inference.py

Dataset options (ML approach still undecided):
  A) Public dataset — UP-Fall Detection Dataset is a common choice. You'd write a
     small adapter that reads its accelerometer/vision data and computes the same
     7 features, then writes dataset.csv. See data/README.md.
  B) Collect your own — log windows from your ESP32 with a label, then run this.

A tiny synthetic sample is generated if dataset.csv is missing, so the pipeline
runs end-to-end today. REPLACE it with real data before reporting results.
"""

from __future__ import annotations
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (train_test_split, cross_val_score,
                                     StratifiedGroupKFold)
from sklearn.metrics import classification_report, confusion_matrix, recall_score
import joblib

from feature_extraction import FEATURE_NAMES

DATA_PATH  = os.path.join("data", "dataset.csv")
MODEL_PATH = "fall_rf.joblib"


def make_synthetic(n=400, seed=42) -> pd.DataFrame:
    """Placeholder data so the script runs before real data exists. NOT for results."""
    rng = np.random.default_rng(seed)
    # not-fall: low peak accel, small tilt change, upright centroid
    nf = pd.DataFrame({
        "sma": rng.normal(1.0, 0.2, n), "peak_accel": rng.normal(1.5, 0.3, n),
        "tilt_change": rng.normal(10, 5, n), "stillness": rng.normal(0.4, 0.1, n),
        "bbox_aspect_ratio": rng.normal(0.5, 0.1, n), "centroid_height": rng.normal(0.4, 0.1, n),
        "frame_motion": rng.normal(5, 2, n), "label": 0,
    })
    # fall: high peak accel, big tilt change, low wide centroid, then stillness
    fa = pd.DataFrame({
        "sma": rng.normal(2.0, 0.3, n), "peak_accel": rng.normal(4.0, 0.6, n),
        "tilt_change": rng.normal(75, 10, n), "stillness": rng.normal(0.8, 0.1, n),
        "bbox_aspect_ratio": rng.normal(1.6, 0.3, n), "centroid_height": rng.normal(0.8, 0.1, n),
        "frame_motion": rng.normal(20, 5, n), "label": 1,
    })
    return pd.concat([nf, fa], ignore_index=True).sample(frac=1, random_state=seed)


def main():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        print(f"Loaded {len(df)} rows from {DATA_PATH}")
    else:
        print(f"[warning] {DATA_PATH} not found — using SYNTHETIC data. "
              f"Replace with real data before reporting results.")
        os.makedirs("data", exist_ok=True)
        df = make_synthetic()
        df.to_csv(DATA_PATH.replace("dataset", "sample"), index=False)

    X = df[FEATURE_NAMES].values
    y = df["label"].values
    groups = df["group"].values if "group" in df.columns else None

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=None, class_weight="balanced", random_state=42)

    # honest evaluation
    if groups is not None and len(np.unique(groups)) >= 5:
        # Group-aware: windows from the same recording (SubjectXActivityYTrialZ)
        # never land in train AND test together, so the score isn't inflated by
        # near-duplicate overlapping windows. This is the number to report.
        n_groups = len(np.unique(groups))
        print(f"Leakage-free evaluation: StratifiedGroupKFold over {n_groups} "
              f"recordings (no overlapping-window leakage between train/test).")
        cv_scores = cross_val_score(clf, X, y, cv=StratifiedGroupKFold(n_splits=5),
                                    groups=groups, scoring="f1")
        tr_idx, te_idx = next(StratifiedGroupKFold(n_splits=4).split(X, y, groups))
        X_tr, X_te, y_tr, y_te = X[tr_idx], X[te_idx], y[tr_idx], y[te_idx]
    else:
        print("[note] no 'group' column — using a plain stratified split. This "
              "can look optimistic when windows overlap. Rebuild dataset.csv with "
              "build_dataset_upfall.py to get leakage-free evaluation.")
        cv_scores = cross_val_score(clf, X, y, cv=5, scoring="f1")
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.25, stratify=y, random_state=42)

    clf.fit(X_tr, y_tr)
    print(f"5-fold CV F1: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")
    y_pred = clf.predict(X_te)
    print("\nHold-out report:\n",
          classification_report(y_te, y_pred, digits=3, zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):\n", confusion_matrix(y_te, y_pred))
    print("\nFeature importances:")
    for name, imp in sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                            key=lambda t: -t[1]):
        print(f"  {name:20s} {imp:.3f}")

    # The number that actually matters for a fall detector: are falls caught?
    n_fall_total = int((y == 1).sum())
    fall_recall = recall_score(y_te, y_pred, pos_label=1, zero_division=0)
    print(f"\n>>> Fall-detection recall (falls actually caught): {fall_recall:.1%}")
    print("    (Judge the model by THIS + the confusion matrix, not overall accuracy —")
    print("     on imbalanced data accuracy is high even if no falls are detected.)")
    if n_fall_total < 40:
        print(f"\n[warning] only {n_fall_total} fall samples in the whole dataset. "
              f"That is too few to train/evaluate reliably — the model may never "
              f"predict 'fall'. Add more fall trials (UP-Fall Activities 1-5) to "
              f"data/upfall_raw/, rebuild with build_dataset_upfall.py, and re-run.")

    joblib.dump({"model": clf, "features": FEATURE_NAMES}, MODEL_PATH)
    print(f"\nSaved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
