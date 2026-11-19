"""Canonical application entry point.

The current application uses Supabase for authentication and persistence.
All routes and recommendation logic live in demo_app.py while the project
retains this conventional app.py entry point for `flask --app app run`.
"""

from demo_app import app


if __name__ == "__main__":
    app.run(debug=True)

