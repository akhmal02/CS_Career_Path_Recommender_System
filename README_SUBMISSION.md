# CSC649 Submission Package

This folder contains the required project submission materials:

## 01_DATASET

- `career_training_data_dummy.csv`  
  Synthetic dataset used to train and evaluate the Random Forest career prediction model.

- `generate_career_data.py`  
  Script used to generate the synthetic questionnaire-based training dataset.

## 02_EXPERIMENTAL_DATA

- `random_forest_training_report.txt`  
  Experimental results for the Random Forest model, including accuracy, precision, recall, F1 score, OOB score, misclassification rate, classification report, and confusion matrix.

- `decision_tree_training_report.txt`  
  Baseline comparison report for the Decision Tree model.

- `confusion_matrix_random_forest.png`  
  Confusion matrix graph for the Random Forest model.

- `train_random_forest_model.py`  
  Training script used to train and evaluate the Random Forest model.

- `career_model.pkl`  
  Trained Random Forest model file used by the system.

- `mlb_transformer.pkl`  
  Multi-label binarizer transformer used to encode questionnaire features.

## 03_SOURCE_CODE

Contains the main Flask system source code, templates, static assets, recommendation rules, requirements, and Supabase SQL schema.

Important files:

- `demo_app.py` - main Flask application
- `recommendation_rules.py` - rule-based recommendation logic
- `templates/` - HTML pages
- `static/` - CSS and JavaScript
- `supabase_schema.sql` - database schema
- `requirements.txt` - app dependencies
- `requirements-training.txt` - ML training dependencies

## 04_DOCUMENTATION

Contains project summary, current system update, Supabase table documentation, and Google Colab Random Forest setup guide.

## Not Included

- `.env.local` is not included because it contains private API keys and Supabase credentials.
- `.venv/` is not included because dependencies can be installed using `requirements.txt`.
- `__pycache__/`, logs, and backup folders are excluded because they are not required for assessment.
