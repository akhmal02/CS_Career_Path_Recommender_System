# CareerCompass Current System Update

Updated: 12 July 2026

## 1. Project Overview

CareerCompass is a web-based Career Path Recommendation System for Computer
Science students. It recommends suitable career paths based on users'
interests, skills, preferred work styles, academic strengths, goals,
activities, and career priorities.

The current system combines:

- Rule-based recommendation
- Random Forest machine-learning confidence
- Hybrid recommendation scoring
- Supabase authentication and database storage
- LLM-assisted questionnaire option mapping
- Gemini chatbot assistant with offline fallback
- TasteSkill-inspired UI polish for the homepage and questionnaire helper

The system keeps the rule-based recommender as the main ranking method because
it is transparent and easier to justify academically.

## 2. Main User Flow

1. User signs up or logs in.
2. User opens the career questionnaire.
3. User selects options for seven questionnaire categories.
4. User may also type free-text descriptions for each category.
5. The LLM can suggest matching existing options based on the user's text.
6. The rule-based recommender calculates the top three career matches.
7. The Random Forest model provides ML confidence for the same careers.
8. The system calculates the final hybrid recommendation score.
9. The result is saved into Supabase.
10. The user can review the latest top three recommendations from the profile page.

## 3. Questionnaire Update

The questionnaire now includes a text box for each main question category:

- Interests
- Current skills
- Preferred work style
- Academic strengths
- Career goals
- Preferred activities
- Career priorities

Each section has a button:

```text
Match my description
```

The LLM does not replace the questionnaire. It only maps the user's free-text
description to existing questionnaire option codes.

Example:

```text
User text:
I enjoy building websites, designing interfaces, and creating mobile apps.

Suggested option codes:
web, design, mobile
```

The user can still review and change the selected options before submitting.

## 3.1 UI Polish Update

The homepage was refined using a TasteSkill v2-inspired approach focused on
reducing generic AI-looking design. The update applies UI design locks for a
clear blue and emerald visual direction, expressive typography choices,
atmospheric background texture, stronger hero composition, asymmetric dashboard
cards, purposeful hover motion, reduced-motion safety, and friendlier
questionnaire helper wording.

This update only affects the user interface. The recommendation logic,
database structure, ML model, Supabase integration, and scoring formula remain
unchanged.

## 4. LLM Option Mapping

The LLM feature uses a separate persona from the chatbot.

Purpose:

```text
Map free-text descriptions to valid questionnaire option codes only.
```

The LLM mapper must:

- Return valid option codes only
- Respect the minimum and maximum selection limit
- Avoid inventing new options
- Avoid recommending careers directly
- Return structured JSON

If Gemini is unavailable or returns an invalid response, the system uses an
offline keyword-matching fallback so the feature still works during a demo.

## 5. Rule-Based Recommendation

The rule-based recommender remains the main recommendation method.

It uses seven weighted categories:

| Category | Weight |
|---|---:|
| Interests | 20 |
| Current skills | 25 |
| Preferred work style | 10 |
| Academic strengths | 15 |
| Career goals | 10 |
| Preferred activities | 15 |
| Career priorities | 5 |
| Total | 100 |

The system compares the user's selected options with predefined career profiles
in `recommendation_rules.py`.

The top three careers are ranked using the rule-based score.

## 6. Machine Learning Update

The current ML model is:

```text
RandomForestClassifier
```

Main files:

```text
career_training_data_dummy.csv
career_model.pkl
mlb_transformer.pkl
train_random_forest_model.py
random_forest_training_report.txt
```

The Random Forest model is trained using 3000 synthetic questionnaire records.
It acts as a supporting confidence checker, not the main decision-maker.

Current training result:

| Metric | Result |
|---|---:|
| Accuracy | 89.67% |
| Misclassification rate | 10.33% |
| OOB score | 87.79% |
| Macro precision | 0.8982 |
| Macro recall | 0.8944 |
| Macro F1 score | 0.8942 |
| Weighted precision | 0.9005 |
| Weighted recall | 0.8967 |
| Weighted F1 score | 0.8965 |

Important note:

```text
The ML accuracy is measured on synthetic data. It shows that the model learned
the designed questionnaire pattern, but it is not yet validated using real
student outcome data.
```

## 7. Hybrid Recommendation Score

The final score shown to the user combines three values:

- Rule-based match
- ML confidence
- System agreement

Formula:

```text
Final Score =
(Rule-based Match x 0.65) +
(ML Confidence x 0.25) +
(System Agreement x 0.10)
```

Reason for the weights:

| Component | Weight | Reason |
|---|---:|---|
| Rule-based match | 65% | Main explainable recommender |
| ML confidence | 25% | Supporting ML evidence |
| System agreement | 10% | Measures whether both systems agree |

Recommendation levels:

| Final score | Level |
|---:|---|
| 80-100% | Strong Match |
| 60-79% | Good Match |
| 40-59% | Moderate Match |
| Below 40% | Low Match |

## 8. System Agreement

System agreement compares the rule-based recommendation with the Random Forest
model prediction.

| Agreement score | Meaning |
|---:|---|
| 100 | Random Forest top career is the same as the rule-based career |
| 70 | Rule-based career appears in the Random Forest top 3 |
| 40 | Rule-based career does not appear in the Random Forest top 3 |

Example:

```text
Rule-based Match = 78
ML Confidence = 34.5
System Agreement = 70

Final Score =
(78 x 0.65) + (34.5 x 0.25) + (70 x 0.10)
= 50.7 + 8.625 + 7
= 66.325
≈ 66%
```

## 9. Result Page Update

The result page now shows:

- Final Recommendation Score
- Recommendation Level
- Rule-based Match
- ML Confidence
- System Agreement
- Short explanation
- Score calculation explanation

The old ML prediction toggle was replaced with:

```text
How this score is calculated
```

This section explains the formula and substitutes the user's actual values so
the user understands how the final score was produced.

## 10. Profile Page Update

The profile page displays the latest saved top three recommendations from the
database.

It now reads the same stored hybrid values used by the result page:

- `explanation.final_score`
- `explanation.recommendation_level`

This ensures the profile page matches the result page.

## 11. Supabase Database

Current core tables:

| Table | Purpose |
|---|---|
| `profiles` | User profile information |
| `career_paths` | Career path reference data |
| `questionnaire_options` | Available questionnaire choices |
| `questionnaire_submissions` | Submitted answers and text descriptions |
| `submission_answers` | Selected option codes |
| `recommendation_results` | Top three saved recommendation results |

The new LLM textbox feature does not require a new table. The typed text is
stored in the existing `questionnaire_submissions.answers` JSON field.

Current JSON structure:

```json
{
  "selected_options": {
    "interests": ["web", "mobile"],
    "skills": ["python", "sql"]
  },
  "text_descriptions": {
    "interests": "I like building websites and mobile apps",
    "skills": "I know Python and SQL"
  }
}
```

Recommended database improvements:

- Add a foreign key from `submission_answers.submission_id` to
  `questionnaire_submissions.id`
- Add `created_at` to `submission_answers`
- Add a unique constraint on `questionnaire_options(category, code)`

## 12. Chatbot Update

The chatbot uses Gemini when configured.

If Gemini is unavailable, the chatbot uses offline fallback responses.

The chatbot is separate from the questionnaire LLM mapper.

| Feature | Purpose |
|---|---|
| Gemini chatbot | Answers career-related questions |
| LLM questionnaire mapper | Suggests existing questionnaire options from text |
| Offline fallback | Keeps the system usable when Gemini fails |

## 13. Important Files

| File | Purpose |
|---|---|
| `demo_app.py` | Main Flask routes, Supabase logic, Gemini logic, scoring flow |
| `recommendation_rules.py` | Rule-based profiles, categories, options, tiers |
| `train_random_forest_model.py` | Random Forest training and evaluation |
| `career_training_data_dummy.csv` | Synthetic ML training dataset |
| `career_model.pkl` | Trained Random Forest model |
| `mlb_transformer.pkl` | Feature transformer for questionnaire option codes |
| `templates/questionnaire.html` | Questionnaire UI with LLM text boxes |
| `templates/result.html` | Hybrid result display and calculation explanation |
| `templates/profile.html` | Latest saved recommendation display |
| `static/script.js` | Wizard, LLM suggestion, chatbot, and result toggle behavior |
| `static/style.css` | Application styling |

## 14. Current Localhost

Current local development URL:

```text
http://127.0.0.1:5000/
```

## 15. Academic Explanation

The system uses a rule-based recommender as the main recommendation method
because it is transparent and explainable. A Random Forest model is added as a
supporting machine-learning component to provide confidence evidence. The final
recommendation score combines the rule-based score, ML confidence, and system
agreement score. This allows the system to include machine learning while still
keeping the recommendation process understandable for students and evaluators.

The LLM-assisted questionnaire feature improves usability by helping users map
their own written descriptions to existing questionnaire options. It does not
replace the recommendation engine and does not create new scoring rules.

## 16. Current Status

Implemented:

- User signup and login
- Supabase authentication
- Profile management
- Career library
- Rule-based recommender
- Random Forest confidence support
- Hybrid final score
- System agreement score
- Result calculation explanation
- Latest top three recommendation saving
- Profile latest recommendation display
- LLM-assisted questionnaire option suggestions
- Gemini chatbot
- Offline fallback for chatbot and option mapping
- Google Colab Random Forest setup guide

Future improvements:

- Train and evaluate using real student data
- Compare Random Forest with Decision Tree and other ML models
- Add administrator dashboard for career paths and questionnaire options
- Add recommendation history page
- Add detailed career salary, demand, certification, and roadmap information
- Add optional AI suggestion logging table if detailed LLM audit history is required
