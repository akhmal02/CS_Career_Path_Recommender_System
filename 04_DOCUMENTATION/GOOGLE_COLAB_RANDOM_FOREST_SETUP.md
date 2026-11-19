# Google Colab Setup: Random Forest Career Recommendation Model

This guide explains how to train the CareerCompass machine-learning model in
Google Colab using the synthetic dataset:

```text
career_training_data_dummy.csv
```

The current machine-learning model is:

```text
RandomForestClassifier
```

The model learns from synthetic questionnaire-answer patterns generated from
the system's career profiles. It predicts the most likely career path from a
student's selected questionnaire options.

Important academic note:

```text
The dataset is synthetic. The model can learn the pattern created by the
project's rule-based career profiles, but it has not yet been validated using
real student outcome data.
```

---

## 1. Open Google Colab

1. Go to [Google Colab](https://colab.research.google.com/).
2. Create a new notebook.
3. Rename it to:

```text
CareerCompass_RandomForest_Model.ipynb
```

---

## 2. Upload the Synthetic Dataset

In Colab, run:

```python
from google.colab import files

uploaded = files.upload()
```

Upload this file:

```text
career_training_data_dummy.csv
```

The CSV columns are:

| Column | Meaning |
|---|---|
| `student_id` | Synthetic student ID |
| `target_career` | Career label the model should learn |
| `interests` | Selected interest options |
| `skills` | Selected skill options |
| `work_styles` | Selected work-style options |
| `subjects` | Selected academic subject options |
| `goals` | Selected career-goal options |
| `activities` | Selected activity options |
| `priorities` | Selected career-priority options |

Each answer category stores multiple selected options using `|`, for example:

```text
programming|problem_solving|java
```

---

## 3. Install and Import Required Libraries

```python
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

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
```

---

## 4. Load and Inspect the Dataset

```python
dataset = pd.read_csv("career_training_data_dummy.csv")

print("Dataset shape:", dataset.shape)
dataset.head()
```

Check the career label distribution:

```python
career_counts = dataset["target_career"].value_counts().sort_index()
career_counts
```

Graph:

```python
plt.figure(figsize=(12, 5))
career_counts.plot(kind="bar")
plt.title("Synthetic Data Distribution by Career")
plt.xlabel("Career")
plt.ylabel("Number of Rows")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
```

---

## 5. Prepare Features and Target Label

The system has seven questionnaire categories:

```python
CATEGORY_COLUMNS = [
    "interests",
    "skills",
    "work_styles",
    "subjects",
    "goals",
    "activities",
    "priorities",
]
```

Combine all selected options into one list per student:

```python
def combine_selected_options(row):
    selected = []
    for column in CATEGORY_COLUMNS:
        selected.extend(str(row[column]).split("|"))
    return selected

x_raw = [combine_selected_options(row) for _, row in dataset.iterrows()]
y = dataset["target_career"].astype(str)
```

How the ML learns from the system:

- Each questionnaire answer option becomes a feature.
- `MultiLabelBinarizer` converts selected options into binary columns.
- Example: if a student selected `python`, the `python` feature becomes `1`.
- If the student did not select `python`, the feature becomes `0`.
- The Random Forest learns which answer patterns are commonly connected to each
  `target_career`.

Convert answers into machine-learning features:

```python
mlb_transformer = MultiLabelBinarizer()
x = mlb_transformer.fit_transform(x_raw)

print("Number of ML features:", len(mlb_transformer.classes_))
print("Example features:", mlb_transformer.classes_[:20])
```

---

## 6. Split the Data

Use a stratified split so every career appears fairly in both train and test
sets.

```python
x_train, x_test, y_train, y_test = train_test_split(
    x,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

print("Train rows:", len(y_train))
print("Test rows:", len(y_test))
```

---

## 7. Train the Random Forest Model

```python
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
```

Parameter explanation:

| Parameter | Purpose |
|---|---|
| `n_estimators=400` | Builds 400 decision trees |
| `max_depth=None` | Allows trees to grow fully unless stopped naturally |
| `min_samples_leaf=1` | Allows detailed patterns to be learned |
| `class_weight="balanced"` | Helps if some careers have fewer rows |
| `oob_score=True` | Uses out-of-bag validation for extra reliability checking |
| `bootstrap=True` | Required for OOB scoring |
| `random_state=42` | Makes results repeatable |

---

## 8. Make Predictions

```python
y_pred = model.predict(x_test)
y_prob = model.predict_proba(x_test)

print("Example predicted careers:", y_pred[:10])
```

Show one example with top 3 probabilities:

```python
sample_index = 0
probabilities = y_prob[sample_index]
top_indices = np.argsort(probabilities)[::-1][:3]

print("Actual career:", y_test.iloc[sample_index])
print("Top 3 predicted careers:")

for index in top_indices:
    print(model.classes_[index], round(probabilities[index] * 100, 2), "%")
```

---

## 9. Results

### 9.1 Experimental Results

This experiment trains a Random Forest classifier using 3000 rows of synthetic
career recommendation data. The data was generated from the CareerCompass
questionnaire options and career-profile patterns.

The model receives selected questionnaire answers as binary features and learns
to predict one of the available career paths.

Experiment setup:

| Item | Value |
|---|---|
| Dataset | `career_training_data_dummy.csv` |
| Total rows | 3000 |
| Train/test split | 80% train, 20% test |
| Model | Random Forest Classifier |
| Number of trees | 400 |
| OOB score enabled | Yes |
| Target label | `target_career` |
| Feature method | Multi-label binary encoding |

### 9.2 Performance Metrics

Run:

```python
accuracy = accuracy_score(y_test, y_pred)
misclassification_rate = 1 - accuracy
precision_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
recall_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
precision_weighted = precision_score(y_test, y_pred, average="weighted", zero_division=0)
recall_weighted = recall_score(y_test, y_pred, average="weighted", zero_division=0)
f1_weighted = f1_score(y_test, y_pred, average="weighted", zero_division=0)

metrics_table = pd.DataFrame({
    "Metric": [
        "Accuracy",
        "Misclassification Rate",
        "OOB Score",
        "Macro Precision",
        "Macro Recall",
        "Macro F1 Score",
        "Weighted Precision",
        "Weighted Recall",
        "Weighted F1 Score",
    ],
    "Score": [
        accuracy,
        misclassification_rate,
        model.oob_score_,
        precision_macro,
        recall_macro,
        f1_macro,
        precision_weighted,
        recall_weighted,
        f1_weighted,
    ],
})

metrics_table["Percentage"] = (metrics_table["Score"] * 100).round(2)
metrics_table
```

Expected result from the current local training run:

| Metric | Score |
|---|---:|
| Accuracy | 89.67% |
| Misclassification Rate | 10.33% |
| OOB Score | 87.79% |
| Macro Precision | 0.8982 |
| Macro Recall | 0.8944 |
| Macro F1 Score | 0.8942 |
| Weighted Precision | 0.9005 |
| Weighted Recall | 0.8967 |
| Weighted F1 Score | 0.8965 |

Your Colab result should be very close if the dataset and `random_state=42` are
the same.

### 9.3 Classification Report Table

```python
report_dict = classification_report(
    y_test,
    y_pred,
    output_dict=True,
    zero_division=0,
)

report_table = pd.DataFrame(report_dict).transpose()
report_table
```

### 9.4 Confusion Matrix Graph

```python
matrix = confusion_matrix(y_test, y_pred, labels=model.classes_)

plt.figure(figsize=(14, 10))
sns.heatmap(
    matrix,
    annot=True,
    fmt="d",
    cmap="Blues",
    xticklabels=model.classes_,
    yticklabels=model.classes_,
)
plt.title("Confusion Matrix - Random Forest Career Model")
plt.xlabel("Predicted Career")
plt.ylabel("Actual Career")
plt.xticks(rotation=45, ha="right")
plt.yticks(rotation=0)
plt.tight_layout()
plt.show()
```

### 9.5 Performance Metrics Graph

```python
plot_metrics = metrics_table[
    metrics_table["Metric"].isin([
        "Accuracy",
        "OOB Score",
        "Macro Precision",
        "Macro Recall",
        "Macro F1 Score",
        "Weighted Precision",
        "Weighted Recall",
        "Weighted F1 Score",
    ])
]

plt.figure(figsize=(12, 5))
sns.barplot(data=plot_metrics, x="Metric", y="Percentage")
plt.title("Random Forest Performance Metrics")
plt.ylabel("Percentage")
plt.xlabel("Metric")
plt.ylim(0, 100)
plt.xticks(rotation=35, ha="right")
plt.tight_layout()
plt.show()
```

### 9.6 Feature Importance Graph

```python
importance_table = pd.DataFrame({
    "feature": mlb_transformer.classes_,
    "importance": model.feature_importances_,
}).sort_values("importance", ascending=False)

importance_table.head(20)
```

```python
plt.figure(figsize=(12, 6))
sns.barplot(
    data=importance_table.head(20),
    x="importance",
    y="feature",
)
plt.title("Top 20 Important Questionnaire Features")
plt.xlabel("Importance")
plt.ylabel("Questionnaire Option")
plt.tight_layout()
plt.show()
```

### 9.7 Misclassification Table

```python
results_table = pd.DataFrame({
    "actual": y_test.values,
    "predicted": y_pred,
})

misclassified = results_table[results_table["actual"] != results_table["predicted"]]

print("Total misclassified rows:", len(misclassified))
misclassified.head(20)
```

Graph:

```python
misclassification_by_career = (
    misclassified["actual"]
    .value_counts()
    .rename_axis("career")
    .reset_index(name="misclassified_count")
)

plt.figure(figsize=(12, 5))
sns.barplot(
    data=misclassification_by_career,
    x="career",
    y="misclassified_count",
)
plt.title("Misclassified Test Rows by Actual Career")
plt.xlabel("Actual Career")
plt.ylabel("Misclassified Count")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
```

---

## 10. Save the Model Files

These are the files used by the Flask system:

```python
joblib.dump(model, "career_model.pkl")
joblib.dump(mlb_transformer, "mlb_transformer.pkl")

print("Saved career_model.pkl")
print("Saved mlb_transformer.pkl")
```

Download them from Colab:

```python
files.download("career_model.pkl")
files.download("mlb_transformer.pkl")
```

Place both files in the project folder:

```text
CSC649/
├── career_model.pkl
├── mlb_transformer.pkl
├── demo_app.py
├── recommendation_rules.py
└── career_training_data_dummy.csv
```

---

## 11. How Flask Uses the Trained Model

In the Flask system:

1. The user answers the questionnaire.
2. The selected answer IDs are collected from seven categories.
3. `mlb_transformer.pkl` converts selected IDs into the same binary feature
   format used during training.
4. `career_model.pkl` predicts career probabilities.
5. The app keeps the career ranking rule-based for explainability.
6. The app shows ML confidence as part of the transparent hybrid score.

Current hybrid formula:

```text
Final Score =
(Rule-based Score x 0.65) +
(Random Forest Score x 0.25) +
(Agreement Score x 0.10)
```

Agreement score:

- 100 if the Random Forest top career matches the rule-based career
- 70 if the rule-based career appears in the Random Forest top 3
- 40 if the rule-based career does not appear in the Random Forest top 3

---

## 12. Suggested Academic Explanation

You can explain the ML part like this:

```text
The machine-learning component uses a Random Forest classifier trained on 3000
rows of synthetic questionnaire data. The synthetic data was generated from the
same career-profile logic used by the rule-based recommender, so the model
learns the relationship between selected questionnaire options and career
labels.

The Random Forest model is not used as the main decision maker. The system keeps
the rule-based ranking because it is more explainable for a student career
recommendation system. The ML model acts as a second-opinion confidence check.
The final displayed score combines the rule-based score, ML confidence, and
agreement between both systems.

Because the dataset is synthetic, the accuracy shows that the model learned the
designed recommendation pattern. Future improvement should include real student
survey data or expert-labelled data to improve external reliability.
```

