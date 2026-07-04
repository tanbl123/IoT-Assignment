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
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
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

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=None, class_weight="balanced", random_state=42)
    clf.fit(X_tr, y_tr)

    # honest evaluation
    cv = cross_val_score(clf, X, y, cv=5, scoring="f1")
    print(f"5-fold CV F1: {cv.mean():.3f} +/- {cv.std():.3f}")
    y_pred = clf.predict(X_te)
    print("\nHold-out report:\n", classification_report(y_te, y_pred, digits=3))
    print("Confusion matrix (rows=true, cols=pred):\n", confusion_matrix(y_te, y_pred))
    print("\nFeature importances:")
    for name, imp in sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                            key=lambda t: -t[1]):
        print(f"  {name:20s} {imp:.3f}")

    joblib.dump({"model": clf, "features": FEATURE_NAMES}, MODEL_PATH)
    print(f"\nSaved model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
