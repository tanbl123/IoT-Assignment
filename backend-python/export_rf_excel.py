from __future__ import annotations

import os

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

from feature_extraction import FEATURE_NAMES


DATA_PATH = "data/dataset.csv"
MODEL_PATH = "fall_rf.joblib"

OUTPUT_DIR = "random_forest_csv_results"


def main():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.read_csv(DATA_PATH)

    required_cols = FEATURE_NAMES + ["label"]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing column in dataset.csv: {col}")

    X = df[FEATURE_NAMES]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    summary_df = pd.DataFrame({
        "Metric": [
            "Accuracy",
            "Precision",
            "Recall",
            "F1-score",
        ],
        "Value": [
            accuracy,
            precision,
            recall,
            f1,
        ],
    })

    report_df = pd.DataFrame(
        classification_report(
            y_test,
            y_pred,
            target_names=["Not Fall", "Fall"],
            output_dict=True,
            zero_division=0,
        )
    ).transpose()

    cm_df = pd.DataFrame(
        confusion_matrix(y_test, y_pred),
        index=["Actual Not Fall", "Actual Fall"],
        columns=["Predicted Not Fall", "Predicted Fall"],
    )

    importance_df = pd.DataFrame({
        "Feature": FEATURE_NAMES,
        "Importance": model.feature_importances_,
    }).sort_values(by="Importance", ascending=False)

    prediction_df = X_test.copy()
    prediction_df["actual_label"] = y_test.values
    prediction_df["predicted_label"] = y_pred
    prediction_df["fall_probability"] = y_prob

    # Save Random Forest results as CSV files
    summary_df.to_csv(
        os.path.join(OUTPUT_DIR, "rf_summary.csv"),
        index=False,
    )

    report_df.to_csv(
        os.path.join(OUTPUT_DIR, "rf_classification_report.csv"),
    )

    cm_df.to_csv(
        os.path.join(OUTPUT_DIR, "rf_confusion_matrix.csv"),
    )

    importance_df.to_csv(
        os.path.join(OUTPUT_DIR, "rf_feature_importance.csv"),
        index=False,
    )

    prediction_df.to_csv(
        os.path.join(OUTPUT_DIR, "rf_prediction_details.csv"),
        index=False,
    )

    # Save trained Random Forest model
    joblib.dump(
        {
            "model": model,
            "features": FEATURE_NAMES,
        },
        MODEL_PATH,
    )

    print("========== RANDOM FOREST RESULT ==========")
    print(f"Accuracy:  {accuracy:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1-score:  {f1:.3f}")
    print("==========================================")
    print(f"CSV folder saved as: {OUTPUT_DIR}")
    print(f"Model saved as: {MODEL_PATH}")


if __name__ == "__main__":
    main()