"""Train and evaluate the career recommendation Random Forest model.

This script uses the local dummy training dataset, evaluates the model with a
stratified holdout test set, and saves the trained model files used by Flask.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer


PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "career_training_data_dummy.csv"
MODEL_PATH = PROJECT_ROOT / "career_model.pkl"
TRANSFORMER_PATH = PROJECT_ROOT / "mlb_transformer.pkl"
REPORT_PATH = PROJECT_ROOT / "random_forest_training_report.txt"

CATEGORY_COLUMNS = [
    "interests",
    "skills",
    "work_styles",
    "subjects",
    "goals",
    "activities",
    "priorities",
]


def combine_selected_options(row):
    selected = []
    for column in CATEGORY_COLUMNS:
        selected.extend(str(row[column]).split("|"))
    return selected


def train():
    dataset = pd.read_csv(DATASET_PATH)
    x_raw = [combine_selected_options(row) for _, row in dataset.iterrows()]
    y = dataset["target_career"].astype(str)

    transformer = MultiLabelBinarizer()
    x = transformer.fit_transform(x_raw)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=400,
        max_depth=None,
        min_samples_leaf=1,
        class_weight="balanced",
        oob_score=True,
        bootstrap=True,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    misclassification_rate = 1 - accuracy
    precision_macro = precision_score(y_test, predictions, average="macro", zero_division=0)
    recall_macro = recall_score(y_test, predictions, average="macro", zero_division=0)
    f1_macro = f1_score(y_test, predictions, average="macro", zero_division=0)
    precision_weighted = precision_score(y_test, predictions, average="weighted", zero_division=0)
    recall_weighted = recall_score(y_test, predictions, average="weighted", zero_division=0)
    f1_weighted = f1_score(y_test, predictions, average="weighted", zero_division=0)
    report = classification_report(y_test, predictions, zero_division=0)
    matrix = confusion_matrix(y_test, predictions, labels=model.classes_)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(transformer, TRANSFORMER_PATH)

    REPORT_PATH.write_text(
        "\n".join(
            [
                "Random Forest Career Model Training Report",
                "==========================================",
                f"Dataset: {DATASET_PATH.name}",
                f"Total rows: {len(dataset)}",
                f"Train rows: {len(y_train)}",
                f"Test rows: {len(y_test)}",
                "Model: RandomForestClassifier",
                "Parameters:",
                "  n_estimators=400",
                "  max_depth=None",
                "  min_samples_leaf=1",
                "  class_weight=balanced",
                "  bootstrap=True",
                "  oob_score=True",
                "  random_state=42",
                "",
                f"Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)",
                f"Misclassification Rate: {misclassification_rate:.4f} ({misclassification_rate * 100:.2f}%)",
                f"OOB Score: {model.oob_score_:.4f} ({model.oob_score_ * 100:.2f}%)",
                "",
                "Macro Average Metrics:",
                f"  Precision: {precision_macro:.4f}",
                f"  Recall: {recall_macro:.4f}",
                f"  F1 Score: {f1_macro:.4f}",
                "",
                "Weighted Average Metrics:",
                f"  Precision: {precision_weighted:.4f}",
                f"  Recall: {recall_weighted:.4f}",
                f"  F1 Score: {f1_weighted:.4f}",
                "",
                "Classification Report:",
                report,
                "",
                "Confusion Matrix Labels:",
                ", ".join(model.classes_),
                "",
                "Confusion Matrix:",
                str(matrix),
                "",
                "Important note:",
                "This accuracy is measured on synthetic dummy data generated from the project's rule-based profiles.",
                "It proves the model learned the dummy-data pattern, not that it is validated on real student outcomes.",
            ]
        ),
        encoding="utf-8",
    )

    return accuracy


if __name__ == "__main__":
    final_accuracy = train()
    print(f"Random Forest accuracy: {final_accuracy:.4f} ({final_accuracy * 100:.2f}%)")
    print(f"Saved model to: {MODEL_PATH}")
    print(f"Saved transformer to: {TRANSFORMER_PATH}")
    print(f"Saved report to: {REPORT_PATH}")
