# Career Path Recommendation System

A Flask application that uses transparent rule-based scoring plus a Random
Forest confidence check for 16 Computer Science careers. Supabase provides
PostgreSQL storage and email/password authentication.

## Architecture

- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Authentication: Supabase Auth
- Database: Supabase PostgreSQL
- Recommendation engine: Python rules in `recommendation_rules.py`
- ML support: Random Forest model in `career_model.pkl`
- Chatbot: Gemini when configured, offline fallback when unavailable

Supabase calls database structures **tables**, not collections.

## Supabase tables

| Table | Purpose |
|---|---|
| `profiles` | Student name, email, programme, study year, and role |
| `career_paths` | The 16 careers and suggested courses |
| `skills` | Reusable skill catalogue |
| `career_path_skills` | Many-to-many link between careers and skills |
| `questionnaire_options` | Available answers for all seven categories |
| `recommendation_rules` | Optional database-managed weighted rules |
| `questionnaire_submissions` | One row for each completed questionnaire |
| `submission_answers` | One row for every selected answer |
| `recommendation_results` | The three ranked results for each submission |

Passwords are not stored in these tables. Supabase Auth securely manages them
inside its protected `auth.users` system table.

## 1. Create a Supabase project

1. Open <https://supabase.com/dashboard>.
2. Select **New project**.
3. Choose an organization, project name, database password, and nearby region.
4. Wait until the project finishes provisioning.

## 2. Create the tables

1. In the project dashboard, open **SQL Editor**.
2. Select **New query**.
3. Open `supabase_schema.sql` from this project.
4. Paste the entire file into the query editor.
5. Select **Run**.
6. Open **Table Editor** and confirm the nine public tables exist.

The SQL also:

- Seeds all 16 career paths.
- Creates a profile automatically whenever an Auth user signs up.
- Enables Row Level Security.
- Restricts profiles, submissions, answers, and results to their owner.
- Allows public read access only to career and rule reference data.

## 3. Configure authentication

Open **Authentication > Providers > Email**.

For the easiest local demonstration, disable **Confirm email**. New users will
be signed in immediately.

For a more realistic setup, leave it enabled and configure:

- **Authentication > URL Configuration > Site URL**:
  `http://127.0.0.1:5000`
- Add `http://127.0.0.1:5000/**` to redirect URLs.

With confirmation enabled, students must click the email link before signing
in. Supabase may require custom SMTP configuration for reliable production
email delivery.

## 4. Get the API credentials

Open the project's **Connect** dialog or **Project Settings > API** and copy:

- Project URL
- Publishable key, or the legacy `anon` key if that is what the dashboard shows

Do not use the `service_role` or secret key in this Flask student application.
The publishable/anon key is designed to work with Row Level Security.

## 5. Configure the project

In PowerShell:

```powershell
cd C:\Users\user\Documents\Codex\2026-06-10\files-mentioned-by-the-user-master\CSC649
Copy-Item .env.example .env
notepad .env
```

Enter the values:

```dotenv
SECRET_KEY=replace-with-a-long-random-value
SUPABASE_URL=https://your-project-reference.supabase.co
SUPABASE_KEY=your-publishable-or-anon-key
FLASK_DEBUG=1
```

Generate a Flask secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env`.

## 6. Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app run --debug --host 127.0.0.1 --port 5000
```

Open <http://127.0.0.1:5000>.

## 7. Test the Supabase workflow

1. Create a student account.
2. Check **Authentication > Users** for the account.
3. Check **Table Editor > profiles** for its automatically created profile.
4. Update the profile in the web application.
5. Complete the questionnaire.
6. Check `questionnaire_submissions` for one new row.
7. Check `submission_answers` for the selected answers.
8. Check `recommendation_results` for three ranked rows.
9. Sign out and sign back in to confirm the account persists.

## How recommendation rules work

The current scoring rules remain in `recommendation_rules.py`. Seven category
weights total 100 points. Each career receives a proportional category score
based on matching selected answers. The top three careers are persisted in
Supabase.

The `questionnaire_options` and `recommendation_rules` tables are included so a
future admin dashboard can move rule management from Python into PostgreSQL.
That migration is optional and does not change the current scoring behavior.

## Machine-learning integration

The project now runs as a hybrid system:

- The rule-based engine remains the primary, explainable recommendation.
- `career_model.pkl` provides a Random Forest second opinion.
- `mlb_transformer.pkl` converts selected questionnaire IDs into the 94 binary
  features expected by the model.
- The result page shows the rule-based score, ML confidence, system agreement,
  recommendation level, and final hybrid recommendation score.
- The final score is transparent:
  `(Rule score x 0.65) + (ML confidence x 0.25) + (Agreement score x 0.10)`.
- No artificial minimum percentage floor is applied.

The two trusted model files belong in the project root:

```text
CSC649/
├── career_model.pkl
├── mlb_transformer.pkl
├── app.py
└── demo_app.py
```

`demo_app.py` loads the files once at startup with Joblib. On questionnaire
submission, the selected IDs from all seven categories are flattened into one
list and transformed:

```python
encoded = ML_TRANSFORMER.transform([selected_ids])
predicted_key = ML_MODEL.predict(encoded)[0]
probabilities = ML_MODEL.predict_proba(encoded)[0]
```

The model was trained with scikit-learn `1.6.1`, so `requirements.txt` pins that
exact version. Using a different version can make pickle loading unreliable.

Model confidence is not the same as the rule-based match percentage:

- Match percentage is an explainable score out of 100.
- ML confidence is the Random Forest's probability estimate for a class.

Only load pickle files that you created or trust. Pickle/Joblib files can
execute code during loading.

The synthetic data generator is stored separately in
`generate_career_data.py`. To run it, install its optional packages:

```powershell
pip install pandas Faker
python generate_career_data.py
```

## Local fallback

If `SUPABASE_URL` or `SUPABASE_KEY` is absent, the application still runs with
temporary in-memory accounts. Those accounts and results disappear when Flask
restarts. Configure Supabase before testing persistence.

## Security notes

- Supabase Auth handles password hashing and credential storage.
- Flask stores the Supabase access and refresh tokens in an HTTP-only session.
- Row Level Security verifies that users access only their own records.
- The application uses a publishable/anon key, never a service-role key.
- CSRF tokens protect state-changing forms.
- Production deployment should use HTTPS and a strong `SECRET_KEY`.
