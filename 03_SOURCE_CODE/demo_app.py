import secrets
import json
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib import request as url_request
from urllib.error import URLError, HTTPError

import joblib
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from supabase import Client, create_client
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
load_dotenv(".env.local")

from config import Config
from recommendation_rules import (
    CAREER_PROFILES,
    CATEGORY_CONFIG,
    QUESTION_OPTIONS,
    match_tier,
)


app = Flask(__name__)
app.config.from_object(Config)
DEMO_USERS = {}
RESULT_CACHE = {}
ML_RESULT_CACHE = {}
CHAT_HISTORY_CACHE = {}

import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent

def resolve_and_load_ml():
    """Automatically locate or extract ML assets (handles GitHub zip packaging)."""
    model_path = PROJECT_ROOT / "career_model.pkl"
    transformer_path = PROJECT_ROOT / "mlb_transformer.pkl"
    
    # Check if transformer is in 02_EXPERIMENTAL_DATA
    if not transformer_path.exists():
        alt_tf = REPO_ROOT / "02_EXPERIMENTAL_DATA" / "mlb_transformer.pkl"
        if alt_tf.exists():
            transformer_path = alt_tf
            
    # Check if model exists, if not auto-extract from zip
    if not model_path.exists():
        alt_model = REPO_ROOT / "02_EXPERIMENTAL_DATA" / "career_model.pkl"
        if alt_model.exists():
            model_path = alt_model
        else:
            zip_candidates = [
                REPO_ROOT / "02_EXPERIMENTAL_DATA" / "career_model.zip",
                PROJECT_ROOT / "career_model.zip"
            ]
            for zc in zip_candidates:
                if zc.exists():
                    print(f"Extracting ML model from {zc.name}...")
                    with zipfile.ZipFile(zc, 'r') as zf:
                        zf.extractall(PROJECT_ROOT)
                    if (PROJECT_ROOT / "career_model.pkl").exists():
                        model_path = PROJECT_ROOT / "career_model.pkl"
                    break

    if not model_path.exists() or not transformer_path.exists():
        return None, None, "Model files missing."
    try:
        model = joblib.load(model_path)
        transformer = joblib.load(transformer_path)
        print("ML Model and MultiLabelBinarizer successfully loaded!")
        return model, transformer, None
    except Exception as error:
        return None, None, str(error)

def load_ml_assets():
    return resolve_and_load_ml()


ML_MODEL, ML_TRANSFORMER, ML_LOAD_ERROR = load_ml_assets()

CAREER_CARD_META = {
    "software": {"icon": "code", "badges": ["Code", "Algorithms", "Systems"]},
    "web": {"icon": "layers", "badges": ["Frontend", "Backend", "APIs"]},
    "mobile": {"icon": "phone", "badges": ["Android", "iOS", "UI"]},
    "data": {"icon": "chart", "badges": ["SQL", "Reports", "Insights"]},
    "security": {"icon": "shield", "badges": ["Threats", "Defense", "Networks"]},
    "networking": {"icon": "network", "badges": ["Routing", "Servers", "Troubleshooting"]},
    "design": {"icon": "pen", "badges": ["Figma", "UX", "Research"]},
    "database": {"icon": "database", "badges": ["SQL", "Design", "Backup"]},
    "ai": {"icon": "brain", "badges": ["Python", "Models", "Math"]},
    "data_scientist": {"icon": "line", "badges": ["Stats", "ML", "Research"]},
    "cloud": {"icon": "cloud", "badges": ["AWS", "Linux", "Deploy"]},
    "business_analyst": {"icon": "trending", "badges": ["Process", "Data", "Users"]},
    "game": {"icon": "game", "badges": ["Unity", "Gameplay", "Graphics"]},
    "devops": {"icon": "infinity", "badges": ["CI/CD", "Docker", "Ops"]},
    "systems_analyst": {"icon": "fork", "badges": ["Systems", "Requirements", "Process"]},
    "qa_automation": {"icon": "clipboard", "badges": ["Testing", "Selenium", "Automation"]},
}


def supabase_enabled():
    return bool(app.config["SUPABASE_URL"] and app.config["SUPABASE_KEY"])


def clear_auth_session():
    """Remove local auth data when Supabase rejects an expired/rotated session."""
    preserved_csrf = session.get("csrf_token")
    session.clear()
    if preserved_csrf:
        session["csrf_token"] = preserved_csrf


def get_supabase(authenticated=False):
    if not supabase_enabled():
        return None
    client: Client = create_client(
        app.config["SUPABASE_URL"],
        app.config["SUPABASE_KEY"],
    )
    if authenticated:
        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
        if not access_token or not refresh_token:
            clear_auth_session()
            return None
        try:
            auth_response = client.auth.set_session(access_token, refresh_token)
        except Exception:
            clear_auth_session()
            return None
        if auth_response and auth_response.session:
            session["access_token"] = auth_response.session.access_token
            session["refresh_token"] = auth_response.session.refresh_token
            if auth_response.user:
                session["user_id"] = auth_response.user.id
                session["user_email"] = auth_response.user.email
                session["user_name"] = (
                    auth_response.user.user_metadata.get("full_name")
                    or auth_response.user.email.split("@")[0]
                )
    return client


def save_auth_session(auth_response):
    if not auth_response.session:
        return
    session["access_token"] = auth_response.session.access_token
    session["refresh_token"] = auth_response.session.refresh_token
    session["user_id"] = auth_response.user.id
    session["user_email"] = auth_response.user.email
    session["user_name"] = (
        auth_response.user.user_metadata.get("full_name")
        or auth_response.user.email.split("@")[0]
    )


def get_latest_submission_id(client, force_refresh=False):
    """Return the user's newest saved questionnaire submission from Supabase."""
    existing_submission_id = session.get("latest_submission_id")
    if existing_submission_id and not force_refresh:
        return existing_submission_id
    if not client or not session.get("user_id"):
        return None
    rows = (
        client.table("questionnaire_submissions")
        .select("id")
        .eq("user_id", session["user_id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        session["latest_submission_id"] = rows[0]["id"]
        return rows[0]["id"]
    return None


def get_latest_profile_recommendations(client):
    """Return the user's latest top 3 saved recommendation summary."""
    latest_submission_id = get_latest_submission_id(client, force_refresh=True)
    if not latest_submission_id:
        return []
    rows = (
        client.table("recommendation_results")
        .select("match_percentage,match_tier,explanation,career_paths(name)")
        .eq("submission_id", latest_submission_id)
        .order("rank_position")
        .execute()
        .data
    )
    if not rows:
        session.pop("latest_recommendation", None)
        return []
    recommendations = [
        {
            "name": row["career_paths"]["name"],
            "percentage": (row.get("explanation") or {}).get(
                "final_score",
                row["match_percentage"],
            ),
            "tier": row["match_tier"],
            "label": (row.get("explanation") or {}).get(
                "recommendation_level",
                f"{row['match_tier']} Match",
            ),
        }
        for row in rows[:3]
    ]
    session["latest_recommendation"] = recommendations[0]
    return recommendations


def get_latest_top_recommendation(client):
    """Return rank #1 from the user's latest saved recommendation set."""
    recommendations = get_latest_profile_recommendations(client)
    return recommendations[0] if recommendations else None


def align_ml_with_rule_recommendations(ml_result, rule_recommendations):
    """Show ML confidence beside the rule-based top 3 instead of reranking careers."""
    if not ml_result or not ml_result.get("available"):
        return ml_result
    model_scores = ml_result.get("all_model_scores") or {
        prediction["key"]: prediction["confidence"]
        for prediction in ml_result.get("model_top_predictions", ml_result.get("top_predictions", []))
    }
    aligned_predictions = [
        {
            "key": item["key"],
            "name": item["career_path"]["name"],
            "confidence": item.get("ml_confidence", model_scores.get(item["key"], 0)),
            "rule_percentage": item.get("rule_based_score", item.get("rule_percentage", item["percentage"])),
            "final_score": item["percentage"],
            "agreement_score": item.get("agreement_score", 40),
        }
        for item in rule_recommendations
    ]
    ml_result["top_predictions"] = aligned_predictions
    ml_result["rule_key"] = rule_recommendations[0]["key"]
    ml_result["rule_name"] = rule_recommendations[0]["career_path"]["name"]
    ml_result["rule_confidence"] = aligned_predictions[0]["confidence"]
    ml_result["agrees_with_rules"] = ml_result.get("predicted_key") == rule_recommendations[0]["key"]
    ml_result["display_mode"] = "rule_aligned"
    return ml_result


def recommendation_level(score):
    if score >= 80:
        return "Strong Match"
    if score >= 60:
        return "Good Match"
    if score >= 40:
        return "Moderate Match"
    return "Low Match"


def hybrid_explanation(rule_score, ml_score, agreement_score):
    if rule_score >= 80 and ml_score >= 60:
        return (
            "This recommendation is strongly supported by both the rule-based "
            "profile match and the Random Forest model."
        )
    if rule_score >= 80 and ml_score < 60:
        return (
            "This recommendation is mainly supported by rule-based matching. "
            "The Random Forest confidence is lower, so treat it as guidance rather "
            "than a final career decision."
        )
    if ml_score < 40:
        return (
            "The Random Forest confidence is low, so this result should be treated "
            "as guidance and compared carefully with your interests, skills, and goals."
        )
    if agreement_score >= 70:
        return (
            "The model gives some support to this rule-based recommendation because "
            "it appears within the Random Forest's stronger career signals."
        )
    return (
        "This recommendation has some rule-based evidence, but the model does not "
        "strongly agree. Treat it as an exploration option."
    )


def apply_hybrid_scores_to_recommendations(recommendations, ml_result):
    """Apply the transparent hybrid score while keeping rule-based ranking."""
    if not ml_result or not ml_result.get("available"):
        for item in recommendations:
            item["rule_based_score"] = item["percentage"]
            item["ml_confidence"] = None
            item["agreement_score"] = None
            item["final_score"] = item["percentage"]
            item["recommendation_level"] = recommendation_level(item["percentage"])
            item["hybrid_explanation"] = (
                "Machine learning is unavailable, so this result uses the rule-based score only."
            )
        return recommendations
    model_scores = ml_result.get("all_model_scores") or {
        prediction["key"]: prediction["confidence"]
        for prediction in ml_result.get("top_predictions", [])
    }
    rf_top_key = ml_result.get("predicted_key")
    rf_top_three = [
        prediction["key"]
        for prediction in ml_result.get("model_top_predictions", ml_result.get("top_predictions", []))[:3]
    ]
    for item in recommendations:
        rule_percentage = item.get("rule_based_score", item.get("rule_percentage", item["percentage"]))
        raw_ml_score = round(model_scores.get(item["key"], 0), 1)
        if item["key"] == rf_top_key:
            agreement_score = 100
        elif item["key"] in rf_top_three:
            agreement_score = 70
        else:
            agreement_score = 40
        final_score = round(
            (rule_percentage * 0.65)
            + (raw_ml_score * 0.25)
            + (agreement_score * 0.10)
        )
        item["rule_based_score"] = rule_percentage
        item["rule_percentage"] = rule_percentage
        item["ml_confidence"] = raw_ml_score
        item["raw_ml_confidence"] = raw_ml_score
        item["agreement_score"] = agreement_score
        item["final_score"] = final_score
        item["percentage"] = final_score
        item["recommendation_level"] = recommendation_level(final_score)
        item["hybrid_explanation"] = hybrid_explanation(rule_percentage, raw_ml_score, agreement_score)
        item["tier"], item["tier_description"] = match_tier(final_score)
    return recommendations


def csrf_token():
    session.setdefault("csrf_token", secrets.token_hex(24))
    return session["csrf_token"]


@app.context_processor
def helpers():
    return {"csrf_token": csrf_token}


def valid_csrf():
    return request.form.get("csrf_token") == session.get("csrf_token")


def password_is_strong(password):
    return len(password) >= 8


def friendly_auth_error(error):
    message = str(error)
    lowered = message.lower()
    if "email not confirmed" in lowered or "confirm" in lowered:
        return "This account exists but the email is not confirmed yet. Please verify your email, then sign in again."
    if "invalid login credentials" in lowered or "invalid credentials" in lowered:
        return "Invalid email or password. Please check the email, password, and whether the email has been confirmed."
    if "already registered" in lowered or "already exists" in lowered:
        return "An account with this email already exists. Try signing in or use Forgot password."
    if "weak password" in lowered:
        return "The new password is too weak. Use at least 8 characters."
    if "expired" in lowered:
        return "This link or session has expired. Please request a new password-reset email."
    return f"Supabase authentication error: {message}"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_email"):
            flash("Create an account or sign in before using this feature.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def redirect_to_login_after_expired_session():
    flash("Your login session has expired. Please sign in again.", "warning")
    return redirect(url_for("login", next=request.path))


def gemini_status():
    api_key = app.config.get("GEMINI_API_KEY", "").strip()
    model = app.config.get("GEMINI_MODEL", "").strip()
    if not api_key:
        return {
            "ready": False,
            "label": "Offline fallback",
            "detail": "No Gemini API key is configured.",
        }
    if not model:
        return {
            "ready": False,
            "label": "Gemini model missing",
            "detail": "Set GEMINI_MODEL in .env.local.",
        }
    return {
        "ready": True,
        "label": "Gemini configured",
        "detail": f"Using {model}.",
    }


CHATBOT_PERSONA = (
    "You are Career Path Assistant for a Computer Science career path recommendation "
    "system. Answer the student's exact question directly first. Do not tell the "
    "student to refer to suggested questions, previous suggestions, or the result page "
    "unless the question specifically asks about their saved recommendation. If the "
    "student asks about a career path, explain responsibilities, suitable interests, "
    "useful technical skills, soft skills, and beginner next steps. If the student asks "
    "for a suggestion, give 2-4 practical options with short reasons. If the student "
    "asks about their personal questionnaire result but no result data is provided, say "
    "you can explain generally and ask them to complete or open their questionnaire "
    "result. Do not invent match percentages or claim certainty. Keep answers friendly, "
    "concise, and structured with short paragraphs or bullets."
)


QUESTIONNAIRE_MAPPER_PERSONA = (
    "You are an option-mapping assistant for a Computer Science career questionnaire. "
    "Your task is not to recommend careers and not to chat. Read the student's free-text "
    "description and map it only to the provided valid option codes for one questionnaire "
    "category. Return strict JSON only, with keys: selected_codes, explanation. "
    "selected_codes must be an array of valid option codes only. Respect the category "
    "minimum and maximum number of options. Choose fewer options when the text is unclear. "
    "Do not invent option codes. Keep explanation to one short sentence."
)


OPTION_KEYWORDS = {
    "interests": {
        "software": ["software", "system", "application", "program"],
        "web": ["web", "website", "browser", "frontend", "backend", "full stack"],
        "mobile": ["mobile", "android", "ios", "app", "phone"],
        "data": ["data", "report", "analytics", "insight", "dashboard"],
        "security": ["security", "cyber", "hack", "protect", "threat"],
        "networking": ["network", "server", "router", "infrastructure"],
        "design": ["design", "ui", "ux", "interface", "user-friendly"],
        "database": ["database", "sql", "data management"],
        "ai": ["ai", "artificial intelligence", "machine learning", "automation"],
        "cloud": ["cloud", "deploy", "aws", "azure", "hosting"],
        "games": ["game", "interactive"],
        "research": ["research", "experiment", "paper"],
        "testing": ["test", "quality", "qa", "bug"],
    },
    "skills": {
        "programming": ["programming", "coding", "code"],
        "problem_solving": ["problem solving", "logic", "algorithm"],
        "debugging": ["debug", "bug", "fix"],
        "html_css": ["html", "css"],
        "javascript": ["javascript", "js"],
        "python": ["python"],
        "java": ["java", "c#"],
        "statistics": ["statistics", "statistical"],
        "data_visualization": ["visualization", "chart", "dashboard"],
        "security": ["security", "cyber"],
        "networking": ["network", "tcp", "ip"],
        "linux": ["linux"],
        "creativity": ["creative", "creativity", "visual"],
        "communication": ["communication", "present", "explain"],
        "user_research": ["user research", "interview", "feedback"],
        "sql": ["sql", "query"],
        "database_design": ["database design", "schema"],
        "mathematics": ["math", "mathematics"],
        "attention_detail": ["detail", "careful"],
        "troubleshooting": ["troubleshoot", "diagnose"],
        "test_design": ["test case", "test design"],
        "automated_testing": ["automated test", "automation testing"],
        "documentation": ["documentation", "write"],
    },
    "work_styles": {
        "independent": ["independent", "alone", "focus"],
        "team": ["team", "collaborate", "group"],
        "analytical": ["analysis", "analytical", "investigate"],
        "creative": ["creative", "design"],
        "hands_on": ["hands-on", "configure", "practical"],
        "structured": ["structured", "procedure", "standard"],
        "experimental": ["experiment", "uncertain", "try"],
        "user_facing": ["user", "client", "people"],
        "careful_systematic": ["careful", "systematic", "patient"],
    },
    "subjects": {
        "programming": ["programming"],
        "software_engineering": ["software engineering"],
        "web_development": ["web"],
        "mobile_development": ["mobile"],
        "statistics": ["statistics"],
        "data_science": ["data science"],
        "cybersecurity": ["cybersecurity", "security"],
        "networking": ["network"],
        "operating_systems": ["operating system", "os"],
        "design": ["design", "multimedia"],
        "human_computer_interaction": ["hci", "human computer", "ux"],
        "database": ["database"],
        "artificial_intelligence": ["artificial intelligence", "ai"],
        "mathematics": ["math", "mathematics"],
        "cloud_computing": ["cloud"],
        "software_testing": ["testing", "qa"],
    },
    "goals": {
        "build_products": ["build product", "digital product", "software"],
        "create_websites": ["website", "web"],
        "create_apps": ["app", "mobile"],
        "business_insights": ["business insight", "data-driven", "report"],
        "protect_systems": ["protect", "security", "threat"],
        "manage_infrastructure": ["infrastructure", "server", "network"],
        "improve_experience": ["user experience", "easier", "usable"],
        "manage_data": ["manage data", "organize data"],
        "intelligent_systems": ["intelligent", "ai", "automation"],
        "technical_leadership": ["leadership", "lead"],
        "freelance": ["freelance", "independent"],
        "research_innovation": ["research", "innovation"],
        "improve_quality": ["quality", "testing", "reliable"],
    },
    "activities": {
        "coding_features": ["coding", "feature"],
        "debugging": ["debug", "fix bug"],
        "building_interfaces": ["interface", "screen", "ui"],
        "prototyping": ["prototype"],
        "analyzing_data": ["analyze data"],
        "creating_dashboards": ["dashboard", "chart"],
        "investigating_incidents": ["incident", "investigate"],
        "testing_security": ["security test", "vulnerability"],
        "configuring_devices": ["configure", "device", "router"],
        "monitoring_systems": ["monitor", "system health"],
        "interviewing_users": ["interview user"],
        "designing_flows": ["flow", "user journey"],
        "writing_queries": ["query", "sql"],
        "organizing_data": ["organize data"],
        "training_models": ["train model", "machine learning"],
        "reading_research": ["read research", "paper"],
        "testing_features": ["test feature"],
        "reproducing_bugs": ["reproduce bug"],
        "writing_tests": ["write tests", "automated test"],
        "checking_requirements": ["requirement", "defect"],
    },
    "priorities": {
        "high_demand": ["demand", "job", "employ"],
        "creative_expression": ["creative"],
        "technical_depth": ["technical depth", "expert"],
        "visible_impact": ["impact", "users"],
        "stability": ["stable", "stability"],
        "continuous_learning": ["learning", "new technology"],
        "remote_flexibility": ["remote", "flexible"],
        "social_contribution": ["help", "protect", "social"],
        "quality_assurance": ["quality", "fewer defect", "testing"],
    },
}


def fallback_option_suggestions(category, description):
    text = description.lower()
    max_count = CATEGORY_CONFIG[category]["maximum"]
    scores = []
    valid_codes = {code for code, _ in QUESTION_OPTIONS[category]}
    for code, keywords in OPTION_KEYWORDS.get(category, {}).items():
        if code not in valid_codes:
            continue
        score = sum(1 for keyword in keywords if keyword in text)
        if score:
            scores.append((score, code))
    scores.sort(key=lambda item: (-item[0], item[1]))
    selected_codes = [code for _, code in scores[:max_count]]
    return {
        "selected_codes": selected_codes,
        "explanation": (
            "Suggested using local keyword support."
            if selected_codes
            else "No strong option match was found. Please choose manually."
        ),
        "source": "offline",
    }


def suggest_options_with_gemini(category, description):
    if category not in CATEGORY_CONFIG:
        return {"error": "Unknown questionnaire category."}, 400
    cleaned_description = " ".join(description.split())[:500]
    if len(cleaned_description) < 8:
        return {"error": "Please write a little more detail before matching your description."}, 400

    status = gemini_status()
    if not status["ready"]:
        return fallback_option_suggestions(category, cleaned_description), 200

    option_lines = "\n".join(
        f"- {code}: {label}"
        for code, label in QUESTION_OPTIONS[category]
    )
    config = CATEGORY_CONFIG[category]
    prompt = (
        f"{QUESTIONNAIRE_MAPPER_PERSONA}\n\n"
        f"Category: {category}\n"
        f"Category label: {config['label']}\n"
        f"Minimum choices: {config['minimum']}\n"
        f"Maximum choices: {config['maximum']}\n\n"
        f"Valid options:\n{option_lines}\n\n"
        f"Student description:\n{cleaned_description}\n\n"
        "Return JSON only. Do not include markdown, labels, or introductory text. "
        "The first character must be { and the last character must be }. "
        "Example format: "
        "{\"selected_codes\":[\"valid_code_1\",\"valid_code_2\"],\"explanation\":\"Short reason.\"}"
    )
    api_key = app.config.get("GEMINI_API_KEY", "").strip()
    model = app.config.get("GEMINI_MODEL", "").strip()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json",
        },
    }
    req = url_request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with url_request.urlopen(req, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        candidates = body.get("candidates", [])
        parts = candidates[0]["content"].get("parts", []) if candidates else []
        raw_answer = " ".join(part.get("text", "") for part in parts).strip()
        parsed = json.loads(raw_answer)
        valid_codes = {code for code, _ in QUESTION_OPTIONS[category]}
        selected_codes = [
            code for code in parsed.get("selected_codes", [])
            if code in valid_codes
        ][: config["maximum"]]
        if not selected_codes:
            return fallback_option_suggestions(category, cleaned_description), 200
        return {
            "selected_codes": selected_codes,
            "explanation": parsed.get("explanation", "Matched choices from your description."),
            "source": "gemini",
        }, 200
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return fallback_option_suggestions(category, cleaned_description), 200


def offline_chatbot_reply(message):
    text = message.lower()
    if any(word in text for word in ["cyber", "security", "hacking", "secure"]):
        return (
            "Cybersecurity suits students who enjoy investigating risks, protecting systems, "
            "and thinking carefully about how attackers might break things.\n\n"
            "You would usually learn networking basics, Linux, Python or scripting, web security, "
            "risk analysis, and incident response. A good beginner step is to build a small home "
            "lab, practise TryHackMe-style rooms, and document what you learned in a portfolio."
        )
    if any(word in text for word in ["data scientist", "data science", "data analyst", "analytics"]):
        return (
            "Data Analyst is better if you enjoy dashboards, reports, SQL, Excel or Power BI, and "
            "explaining patterns to people. Data Scientist is better if you enjoy statistics, "
            "machine learning, Python, experiments, and predictive models.\n\n"
            "A practical next step is to take one public dataset, clean it, visualize it, and write "
            "a short explanation of the business insight."
        )
    if any(word in text for word in ["software", "full stack", "web developer", "mobile", "app developer"]):
        return (
            "Software, full stack, web, and mobile paths suit students who enjoy building usable "
            "applications and solving logic problems. Full stack focuses on frontend plus backend; "
            "mobile focuses on Android, iOS, or cross-platform apps.\n\n"
            "Start with one complete project: login, database, CRUD features, clean UI, and a short "
            "README. That proves more than only listing programming languages."
        )
    if any(word in text for word in ["ai", "machine learning", "ml engineer", "ai engineer"]):
        return (
            "AI Engineer suits students who enjoy Python, data, model behaviour, and turning models "
            "into useful features. You need programming, basic statistics, machine learning concepts, "
            "data preparation, and model evaluation.\n\n"
            "Begin with a small classifier or recommender, explain the dataset honestly, then compare "
            "accuracy with simple baselines so the result is believable."
        )
    if any(word in text for word in ["cloud", "devops", "network", "network engineer"]):
        return (
            "Cloud, DevOps, and Network paths suit students who like infrastructure, deployment, "
            "automation, reliability, and how systems communicate. Useful skills include Linux, "
            "networking, Docker, CI/CD, cloud basics, monitoring, and scripting.\n\n"
            "A strong beginner project is deploying a small web app with environment variables, logs, "
            "and a clear deployment diagram."
        )
    if any(word in text for word in ["ui", "ux", "designer", "design"]):
        return (
            "UI/UX Designer suits students who enjoy user research, interface design, accessibility, "
            "prototyping, and improving how people experience a system. Technical knowledge still "
            "helps because you can design realistic screens developers can build.\n\n"
            "Start by redesigning one existing app screen, explaining the user problem, your wireframe, "
            "and why your final design improves usability."
        )
    if "what career" in text or "which career" in text or "suit me" in text:
        return (
            "I can suggest a direction, but I should not invent a personal match score without your "
            "questionnaire answers. In general: choose Software/Full Stack if you enjoy building apps, "
            "Data if you enjoy patterns and reports, Cybersecurity if you enjoy investigation and risk, "
            "AI if you enjoy models and experiments, and UI/UX if you enjoy user problems and design.\n\n"
            "Tell me your favourite subjects, strongest skills, and what type of work you enjoy, and I "
            "can narrow it down."
        )
    if "score" in text or "percent" in text or "match" in text:
        return (
            "The score comes from seven rule-based categories: interests, skills, "
            "work style, subjects, goals, activities, and priorities. A stronger "
            "match means more of your selected answers align with that career profile."
        )
    if "skill" in text:
        return (
            "The safest skills to improve for most CS career paths are programming fundamentals, "
            "SQL or data handling, Git, problem solving, communication, and portfolio writing.\n\n"
            "After that, specialise based on your target path: security tools for Cybersecurity, "
            "dashboards for Data Analyst, ML basics for AI, or frontend/backend skills for Full Stack."
        )
    if "portfolio" in text or "project" in text:
        return (
            "A good CS portfolio project should solve a clear problem, use the skills "
            "for your target career, and include a short README explaining your choices."
        )
    if "career" in text or "path" in text:
        return (
            "Compare the top three recommendations, not only the first one. Look at why "
            "each path suits you, the skills to improve, and whether the daily work sounds enjoyable."
        )
    return (
        "Here is a direct way to think about it: tell me the career path or problem you are asking "
        "about, and I will explain what it means, who it suits, what skills you need, and one beginner "
        "step you can take. For example, you can ask: 'Is cybersecurity suitable for me?' or 'What "
        "skills should I improve for data analyst?'"
    )


def ask_gemini(message):
    api_key = app.config.get("GEMINI_API_KEY", "").strip()
    model = app.config.get("GEMINI_MODEL", "").strip()
    if not gemini_status()["ready"]:
        return offline_chatbot_reply(message), "offline"

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{CHATBOT_PERSONA}\n\n"
                            f"Student question:\n{message}\n\n"
                            "Answer directly. If possible, use 3-5 bullets and one practical next step."
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.45,
            "maxOutputTokens": 280,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = url_request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with url_request.urlopen(req, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        candidates = body.get("candidates", [])
        parts = candidates[0]["content"].get("parts", []) if candidates else []
        answer = " ".join(part.get("text", "") for part in parts).strip()
        return answer or offline_chatbot_reply(message), "gemini"
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return offline_chatbot_reply(message), "offline"


def get_chat_history():
    cache_key = session.get("user_id") or session.get("user_email")
    cached_messages = CHAT_HISTORY_CACHE.get(cache_key, []) if cache_key else []
    if not supabase_enabled():
        return cached_messages
    if not session.get("user_id") or not session.get("access_token") or not session.get("refresh_token"):
        return cached_messages
    try:
        client = get_supabase(authenticated=True)
        if client is None:
            return cached_messages
        conversation_id = session.get("chat_conversation_id")
        if not conversation_id:
            rows = (
                client.table("chat_conversations")
                .select("id")
                .eq("user_id", session["user_id"])
                .eq("status", "active")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            if rows:
                conversation_id = rows[0]["id"]
                session["chat_conversation_id"] = conversation_id
        if not conversation_id:
            return cached_messages
        messages = (
            client.table("chat_messages")
            .select("role,content,metadata,created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .limit(30)
            .execute()
            .data
        )
        return messages or cached_messages
    except Exception:
        return cached_messages


def save_chat_exchange(user_message, assistant_reply, source):
    cache_key = session.get("user_id") or session.get("user_email")
    if cache_key:
        cached_messages = CHAT_HISTORY_CACHE.setdefault(cache_key, [])
        cached_messages.extend([
            {
                "role": "user",
                "content": user_message,
                "metadata": {},
            },
            {
                "role": "assistant",
                "content": assistant_reply,
                "metadata": {"source": source},
            },
        ])
        del cached_messages[:-30]
    if not supabase_enabled():
        return
    if not session.get("user_id") or not session.get("access_token") or not session.get("refresh_token"):
        return
    try:
        client = get_supabase(authenticated=True)
        if client is None:
            return
        conversation_id = session.get("chat_conversation_id")
        if not conversation_id:
            conversation = (
                client.table("chat_conversations")
                .insert({
                    "user_id": session["user_id"],
                    "title": user_message[:80],
                    "model": app.config.get("GEMINI_MODEL") if source == "gemini" else "offline-fallback",
                })
                .execute()
                .data[0]
            )
            conversation_id = conversation["id"]
            session["chat_conversation_id"] = conversation_id
        rows = [
            {
                "conversation_id": conversation_id,
                "user_id": session["user_id"],
                "role": "user",
                "content": user_message,
                "status": "completed",
            },
            {
                "conversation_id": conversation_id,
                "user_id": session["user_id"],
                "role": "assistant",
                "content": assistant_reply,
                "status": "completed",
                "metadata": {"source": source},
            },
        ]
        client.table("chat_messages").insert(rows).execute()
        (
            client.table("chat_conversations")
            .update({"updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", conversation_id)
            .execute()
        )
    except Exception:
        pass


def option_labels():
    return {
        category: dict(options)
        for category, options in QUESTION_OPTIONS.items()
    }


def predict_with_ml(answers, rule_recommendations):
    """Return a non-explanatory ML second opinion for comparison with rules."""
    if ML_MODEL is None or ML_TRANSFORMER is None:
        return {
            "available": False,
            "error": ML_LOAD_ERROR or "Machine-learning assets are unavailable.",
        }

    selected_ids = [
        option
        for category in CATEGORY_CONFIG
        for option in answers.get(category, [])
    ]
    known_features = set(ML_TRANSFORMER.classes_)
    unknown_features = sorted(set(selected_ids) - known_features)
    usable_ids = [option for option in selected_ids if option in known_features]

    try:
        encoded = ML_TRANSFORMER.transform([usable_ids])
        predicted_key = str(ML_MODEL.predict(encoded)[0])
        probabilities = ML_MODEL.predict_proba(encoded)[0]
        all_model_scores = {
            str(ML_MODEL.classes_[index]): round(float(probability) * 100, 1)
            for index, probability in enumerate(probabilities)
        }
        ranked_indices = probabilities.argsort()[::-1][:3]
        model_top_predictions = [
            {
                "key": str(ML_MODEL.classes_[index]),
                "name": CAREER_PROFILES.get(
                    str(ML_MODEL.classes_[index]), {}
                ).get("name", str(ML_MODEL.classes_[index]).replace("_", " ").title()),
                "confidence": round(float(probabilities[index]) * 100, 1),
            }
            for index in ranked_indices
        ]
        rule_key = rule_recommendations[0]["key"]
        ml_result = {
            "available": True,
            "predicted_key": predicted_key,
            "predicted_name": CAREER_PROFILES.get(predicted_key, {}).get(
                "name", predicted_key.replace("_", " ").title()
            ),
            "confidence": model_top_predictions[0]["confidence"],
            "top_predictions": model_top_predictions,
            "model_top_predictions": model_top_predictions,
            "all_model_scores": all_model_scores,
            "rule_key": rule_key,
            "rule_name": rule_recommendations[0]["career_path"]["name"],
            "agrees_with_rules": predicted_key == rule_key,
            "unknown_features": unknown_features,
        }
        return align_ml_with_rule_recommendations(ml_result, rule_recommendations)
    except Exception as error:
        return {"available": False, "error": str(error)}


def calculate_recommendations(answers):
    labels = option_labels()
    recommendations = []

    for career_key, career in CAREER_PROFILES.items():
        category_breakdown = []
        total_points = 0.0
        all_matches = []
        all_mismatches = []

        for category, config in CATEGORY_CONFIG.items():
            selected = answers[category]
            profile_values = set(career["profile"][category])
            matched = [value for value in selected if value in profile_values]
            unmatched = [value for value in selected if value not in profile_values]

            # A category earns its full weight when every selected answer supports
            # the career. Mixed evidence earns a proportional part of the weight.
            points = config["weight"] * (len(matched) / len(selected))
            total_points += points
            all_matches.extend((category, value) for value in matched)
            all_mismatches.extend((category, value) for value in unmatched)

            category_breakdown.append({
                "label": config["label"],
                "points": round(points, 1),
                "maximum": config["weight"],
                "matched": [labels[category][value] for value in matched],
                "unmatched": [labels[category][value] for value in unmatched],
            })

        percentage = round(total_points)
        tier, tier_description = match_tier(percentage)
        selected_skills = set(answers["skills"])
        matched_core = [
            labels["skills"][skill]
            for skill in career["core_skills"]
            if skill in selected_skills
        ]
        missing_core = [
            labels["skills"][skill]
            for skill in career["core_skills"]
            if skill not in selected_skills
        ]

        strongest = sorted(
            category_breakdown,
            key=lambda item: (item["points"] / item["maximum"], item["points"]),
            reverse=True,
        )[:3]
        weakest = sorted(
            [item for item in category_breakdown if item["points"] < item["maximum"]],
            key=lambda item: item["points"] / item["maximum"],
        )[:2]

        fit_details = []
        for item in strongest:
            if item["matched"]:
                fit_details.append(
                    f"{item['label']} contributed {item['points']} of "
                    f"{item['maximum']} points because you selected "
                    f"{', '.join(item['matched'])}."
                )

        gap_details = []
        for item in weakest:
            if item["unmatched"]:
                gap_details.append(
                    f"{item['label']} reduced the match because "
                    f"{', '.join(item['unmatched'])} is not a primary signal "
                    f"for this career profile."
                )
        if missing_core:
            gap_details.append(
                f"Core skills not selected: {', '.join(missing_core)}. "
                "These are development targets, not automatic disqualifiers."
            )

        if percentage >= 95:
            coach_tip = (
                f"Your profile is highly aligned with {career['name']}. Build one "
                f"portfolio project and begin {career['courses'][0]} to turn this "
                "strong fit into practical evidence."
            )
        elif percentage >= 80:
            next_step = missing_core[0] if missing_core else "a portfolio project"
            coach_tip = (
                f"You have a credible foundation for {career['name']}. Prioritize "
                f"{next_step} and speak with someone working in the field before "
                "making a final decision."
            )
        else:
            coach_tip = (
                f"Treat {career['name']} as an exploration option. Try a short "
                f"beginner course in {career['courses'][0]} and a small practical "
                "task, then reassess your interest."
            )

        recommendations.append({
            "key": career_key,
            "career_path": career,
            "score": round(total_points, 1),
            "percentage": percentage,
            "tier": tier,
            "tier_description": tier_description,
            "category_breakdown": category_breakdown,
            "fit_details": fit_details,
            "gap_details": gap_details or [
                "No major conflict was found between your selected preferences and this career profile."
            ],
            "matched_skills": matched_core,
            "skills_to_improve": missing_core,
            "coach_tip": coach_tip,
        })

    recommendations.sort(
        key=lambda item: (-item["percentage"], item["career_path"]["name"])
    )
    return recommendations[:3]


def read_answers():
    return {
        category: request.form.getlist(category)
        for category in CATEGORY_CONFIG
    }


def read_answer_texts():
    return {
        category: " ".join(request.form.get(f"{category}_text", "").split())[:500]
        for category in CATEGORY_CONFIG
        if request.form.get(f"{category}_text", "").strip()
    }


def validate_answers(answers):
    errors = []
    for category, config in CATEGORY_CONFIG.items():
        count = len(answers[category])
        if count < config["minimum"] or count > config["maximum"]:
            errors.append(
                f"{config['label']} requires {config['minimum']} to "
                f"{config['maximum']} choices."
            )
    return errors


@app.route("/")
def index():
    labels = option_labels()
    paths = [
        {
            "key": key,
            "name": career["name"],
            "short_description": career["description"],
            "href": url_for("career_detail", career_key=key),
            "search_text": " ".join(
                labels["skills"][skill] for skill in career["core_skills"]
            ),
            "icon": CAREER_CARD_META.get(key, {}).get("icon", "code"),
            "badges": CAREER_CARD_META.get(key, {}).get("badges", []),
        }
        for key, career in CAREER_PROFILES.items()
    ]
    return render_template("index.html", paths=paths)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if not valid_csrf():
            return "Invalid form token. Reload the page.", 400
        name = " ".join(request.form.get("name", "").split())[:100]
        email = request.form.get("email", "").strip().lower()[:255]
        password = request.form.get("password", "")
        if not name or "@" not in email or not password_is_strong(password):
            flash("Enter a name, valid email, and password of at least 8 characters.", "danger")
        elif not supabase_enabled() and email in DEMO_USERS:
            flash("An account with that email already exists.", "danger")
        else:
            if supabase_enabled():
                try:
                    response = get_supabase().auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {"data": {"full_name": name}},
                    })
                    if response.session:
                        save_auth_session(response)
                        flash("Account created. You can now complete the questionnaire.", "success")
                        return redirect(url_for("questionnaire"))
                    flash(
                        "Account created. Check your email to confirm it, then sign in.",
                        "success",
                    )
                    return redirect(url_for("login"))
                except Exception as error:
                    flash(friendly_auth_error(error), "danger")
            else:
                DEMO_USERS[email] = {
                    "name": name,
                    "email": email,
                    "password_hash": generate_password_hash(password),
                    "program": "",
                    "year": "",
                }
                session["user_email"] = email
                session["user_name"] = name
                flash(
                    "Local fallback account created. Configure Supabase to make it persistent.",
                    "warning",
                )
                return redirect(url_for("questionnaire"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not valid_csrf():
            return "Invalid form token. Reload the page.", 400
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if supabase_enabled():
            try:
                response = get_supabase().auth.sign_in_with_password({
                    "email": email,
                    "password": password,
                })
                save_auth_session(response)
            except Exception as error:
                flash(friendly_auth_error(error), "danger")
                return render_template("login.html")
        else:
            user = DEMO_USERS.get(email)
            if not user or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "danger")
                return render_template("login.html")
            session["user_email"] = email
            session["user_name"] = user["name"]

        destination = request.args.get("next", "")
        if not destination.startswith("/"):
            destination = url_for("index")
        return redirect(destination)
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if not valid_csrf():
            return "Invalid form token. Reload the page.", 400
        email = request.form.get("email", "").strip().lower()[:255]
        if "@" not in email:
            flash("Enter the email address you used to register.", "danger")
            return render_template("forgot_password.html")
        if not supabase_enabled():
            flash("Password reset requires Supabase Auth to be configured.", "warning")
            return render_template("forgot_password.html")
        try:
            redirect_to = url_for("reset_password", _external=True)
            get_supabase().auth.reset_password_for_email(email, {"redirect_to": redirect_to})
            flash("If the email is registered, Supabase will send a password-reset link.", "success")
            return redirect(url_for("login"))
        except Exception as error:
            flash(friendly_auth_error(error), "danger")
    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        if not valid_csrf():
            return "Invalid form token. Reload the page.", 400
        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        access_token = request.form.get("access_token", "")
        refresh_token = request.form.get("refresh_token", "")
        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
            return render_template("reset_password.html")
        if not password_is_strong(new_password):
            flash("Password must be at least 8 characters.", "danger")
            return render_template("reset_password.html")
        if not supabase_enabled():
            flash("Password reset requires Supabase Auth to be configured.", "warning")
            return render_template("reset_password.html")
        if not access_token or not refresh_token:
            flash("The reset link is missing or expired. Please request a new password-reset email.", "danger")
            return render_template("reset_password.html")
        try:
            client = get_supabase()
            client.auth.set_session(access_token, refresh_token)
            client.auth.update_user({"password": new_password})
            try:
                client.auth.sign_out()
            except Exception:
                pass
            session.clear()
            flash("Password updated. Please sign in using your new password.", "success")
            return redirect(url_for("login"))
        except Exception as error:
            flash(friendly_auth_error(error), "danger")
    return render_template("reset_password.html")


@app.post("/logout")
@login_required
def logout():
    if not valid_csrf():
        return "Invalid form token. Reload the page.", 400
    if supabase_enabled():
        try:
            client = get_supabase(authenticated=True)
            if client:
                client.auth.sign_out()
        except Exception:
            pass
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if supabase_enabled():
        client = get_supabase(authenticated=True)
        if client is None:
            return redirect_to_login_after_expired_session()
        try:
            rows = (
                client.table("profiles")
                .select("*")
                .eq("id", session["user_id"])
                .limit(1)
                .execute()
                .data
            )
            if not rows:
                flash("Your profile record is missing. Run database.sql in Supabase.", "danger")
                return redirect(url_for("index"))
            row = rows[0]
            user = {
                "name": row["full_name"],
                "email": row["email"],
                "program": row["program"],
                "year": row["study_year"],
            }
        except Exception as error:
            flash(f"Could not load your Supabase profile: {error}", "danger")
            return redirect(url_for("index"))
    else:
        user = DEMO_USERS.get(session["user_email"])
        if not user:
            session.clear()
            return redirect(url_for("signup"))

    if request.method == "POST":
        if not valid_csrf():
            return "Invalid form token. Reload the page.", 400
        full_name = " ".join(request.form.get("name", "").split())[:100]
        program = " ".join(request.form.get("program", "").split())[:100]
        study_year = request.form.get("year", "")[:30]
        if supabase_enabled():
            try:
                (
                    client.table("profiles")
                    .update({
                        "full_name": full_name,
                        "program": program,
                        "study_year": study_year,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    .eq("id", session["user_id"])
                    .execute()
                )
            except Exception as error:
                flash(f"Could not update your profile: {error}", "danger")
                return redirect(url_for("profile"))
        else:
            user["name"] = full_name
            user["program"] = program
            user["year"] = study_year
        session["user_name"] = full_name
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    latest = None
    latest_recommendations = []
    if supabase_enabled():
        try:
            latest_recommendations = get_latest_profile_recommendations(client)
            latest = latest_recommendations[0] if latest_recommendations else None
        except Exception:
            latest = None
            latest_recommendations = []
    else:
        latest = session.get("latest_recommendation")
        latest_recommendations = [latest] if latest else []
    return render_template(
        "profile.html",
        user=user,
        latest=latest,
        latest_recommendations=latest_recommendations,
    )


@app.post("/profile/change-password")
@login_required
def change_password():
    if not valid_csrf():
        return "Invalid form token. Reload the page.", 400
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("profile"))
    if not password_is_strong(new_password):
        flash("New password must be at least 8 characters.", "danger")
        return redirect(url_for("profile"))

    email = session["user_email"].strip().lower()
    if supabase_enabled():
        try:
            client = get_supabase()
            auth_response = client.auth.sign_in_with_password({
                "email": email,
                "password": current_password,
            })
            save_auth_session(auth_response)
            client = get_supabase(authenticated=True)
            if client is None:
                return redirect_to_login_after_expired_session()
            client.auth.update_user({"password": new_password})
            try:
                client = get_supabase(authenticated=True)
                if client:
                    client.auth.sign_out()
            except Exception:
                pass
            session.clear()
            flash("Password changed successfully. Please sign in again with the new password.", "success")
            return redirect(url_for("login"))
        except Exception as error:
            flash(friendly_auth_error(error), "danger")
            return redirect(url_for("profile"))

    user = DEMO_USERS.get(email)
    if not user or not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile"))
    user["password_hash"] = generate_password_hash(new_password)
    session.clear()
    flash("Password changed for the local demo account. Please sign in again.", "success")
    return redirect(url_for("login"))


@app.route("/career/<career_key>")
def career_detail(career_key):
    career = CAREER_PROFILES.get(career_key)
    if not career:
        return "Career path not found.", 404
    labels = option_labels()
    return render_template(
        "career_detail.html",
        career=career,
        career_key=career_key,
        core_skills=[labels["skills"][value] for value in career["core_skills"]],
        interests=[labels["interests"][value] for value in career["profile"]["interests"]],
        work_styles=[labels["work_styles"][value] for value in career["profile"]["work_styles"]],
        activities=[labels["activities"][value] for value in career["profile"]["activities"]],
    )


@app.route("/chatbot")
@login_required
def chatbot_page():
    status = gemini_status()
    return render_template(
        "chatbot.html",
        gemini_ready=status["ready"],
        gemini_status=status,
        chat_history=get_chat_history(),
    )


@app.post("/chatbot/message")
@login_required
def chatbot_message():
    if not valid_csrf():
        return jsonify({"error": "Invalid form token. Reload the page."}), 400
    message = " ".join(request.form.get("message", "").split())[:600]
    if not message:
        return jsonify({"error": "Please enter a question."}), 400
    reply, source = ask_gemini(message)
    save_chat_exchange(message, reply, source)
    return jsonify({"reply": reply, "source": source})


@app.post("/questionnaire/suggest-options")
@login_required
def questionnaire_suggest_options():
    if not valid_csrf():
        return jsonify({"error": "Invalid form token. Reload the page."}), 400
    category = request.form.get("category", "")
    description = request.form.get("description", "")
    payload, status_code = suggest_options_with_gemini(category, description)
    return jsonify(payload), status_code


@app.route("/questionnaire", methods=["GET", "POST"])
@login_required
def questionnaire():
    if request.method == "POST":
        if request.form.get("csrf_token") != session.get("csrf_token"):
            return "Invalid form token. Reload the page.", 400

        answers = read_answers()
        errors = validate_answers(answers)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "questionnaire.html",
                options=QUESTION_OPTIONS,
                categories=CATEGORY_CONFIG,
                submitted=request.form,
            )

        recommendations = calculate_recommendations(answers)
        answer_texts = read_answer_texts()
        ml_result = predict_with_ml(answers, recommendations)
        recommendations = apply_hybrid_scores_to_recommendations(recommendations, ml_result)
        ml_result = align_ml_with_rule_recommendations(ml_result, recommendations)
        cache_key = session.get("user_id") or session["user_email"]
        RESULT_CACHE[cache_key] = recommendations
        ML_RESULT_CACHE[cache_key] = ml_result
        session["latest_recommendation"] = {
            "name": recommendations[0]["career_path"]["name"],
            "percentage": recommendations[0]["percentage"],
            "tier": recommendations[0]["tier"],
            "label": recommendations[0].get("recommendation_level", f"{recommendations[0]['tier']} Match"),
        }

        if supabase_enabled():
            try:
                client = get_supabase(authenticated=True)
                if client is None:
                    raise RuntimeError("Your login session expired before the result could be saved. Please sign in again.")
                recommendation_summary = [
                    {
                        "rank_position": rank,
                        "career_key": item["key"],
                        "career_name": item["career_path"]["name"],
                        "match_percentage": item["percentage"],
                        "match_tier": item["tier"],
                        "final_score": item.get("final_score", item["percentage"]),
                        "recommendation_level": item.get("recommendation_level"),
                    }
                    for rank, item in enumerate(recommendations, start=1)
                ]
                submission_payload = {
                    "user_id": session["user_id"],
                    "answers": {
                        "selected_options": answers,
                        "text_descriptions": answer_texts,
                    },
                    "recommendation_summary": recommendation_summary,
                }
                try:
                    submission = (
                        client.table("questionnaire_submissions")
                        .insert(submission_payload)
                        .execute()
                        .data[0]
                    )
                except Exception as insert_error:
                    if "recommendation_summary" not in str(insert_error):
                        raise
                    submission_payload.pop("recommendation_summary", None)
                    submission = (
                        client.table("questionnaire_submissions")
                        .insert(submission_payload)
                        .execute()
                        .data[0]
                    )
                answer_rows = [
                    {
                        "submission_id": submission["id"],
                        "category": category,
                        "option_code": option,
                    }
                    for category, options in answers.items()
                    for option in options
                ]
                answer_rows_saved = True
                if answer_rows:
                    try:
                        client.table("submission_answers").insert(answer_rows).execute()
                    except Exception:
                        answer_rows_saved = False

                slugs = [item["key"] for item in recommendations]
                career_rows = (
                    client.table("career_paths")
                    .select("id,slug")
                    .in_("slug", slugs)
                    .execute()
                    .data
                )
                career_ids = {row["slug"]: row["id"] for row in career_rows}
                result_rows = []
                for rank, item in enumerate(recommendations, start=1):
                    result_rows.append({
                        "submission_id": submission["id"],
                        "user_id": session["user_id"],
                        "career_path_id": career_ids[item["key"]],
                        "rank_position": rank,
                        "score": item["score"],
                        "match_percentage": item["percentage"],
                        "match_tier": item["tier"],
                        "explanation": {
                            "tier_description": item["tier_description"],
                            "category_breakdown": item["category_breakdown"],
                            "fit_details": item["fit_details"],
                            "gap_details": item["gap_details"],
                            "matched_skills": item["matched_skills"],
                            "skills_to_improve": item["skills_to_improve"],
                            "rule_percentage": item.get("rule_percentage", item["percentage"]),
                            "raw_ml_confidence": item.get("raw_ml_confidence"),
                            "rule_based_score": item.get("rule_based_score"),
                            "ml_confidence": item.get("ml_confidence"),
                            "agreement_score": item.get("agreement_score"),
                            "final_score": item.get("final_score", item["percentage"]),
                            "recommendation_level": item.get("recommendation_level"),
                            "hybrid_explanation": item.get("hybrid_explanation"),
                            "ml_comparison": ml_result,
                            "answer_rows_saved": answer_rows_saved,
                        },
                        "coach_tip": item["coach_tip"],
                    })
                client.table("recommendation_results").insert(result_rows).execute()
                session["latest_submission_id"] = submission["id"]
                try:
                    (
                        client.table("questionnaire_submissions")
                        .delete()
                        .eq("user_id", session["user_id"])
                        .neq("id", submission["id"])
                        .execute()
                    )
                except Exception as cleanup_error:
                    flash(
                        "Your latest recommendation was saved, but older saved results could not be removed. "
                        f"Update the Supabase delete policy if this keeps happening: {cleanup_error}",
                        "warning",
                    )
            except Exception as error:
                flash(
                    f"Your recommendation was calculated, but Supabase could not save it: {error}",
                    "warning",
                )
        return redirect(url_for("result"))

    return render_template(
        "questionnaire.html",
        options=QUESTION_OPTIONS,
        categories=CATEGORY_CONFIG,
        submitted=request.form,
    )


@app.route("/result")
@login_required
def result():
    cache_key = session.get("user_id") or session["user_email"]
    recommendations = RESULT_CACHE.get(cache_key)
    ml_result = ML_RESULT_CACHE.get(cache_key)
    if not recommendations and supabase_enabled():
        try:
            client = get_supabase(authenticated=True)
            if client is None:
                return redirect_to_login_after_expired_session()
            latest_submission_id = get_latest_submission_id(client)
            if not latest_submission_id:
                return redirect(url_for("questionnaire"))
            rows = (
                client
                .table("recommendation_results")
                .select(
                    "rank_position,score,match_percentage,match_tier,"
                    "explanation,coach_tip,"
                    "career_paths(slug,name,description,suggested_courses)"
                )
                .eq("submission_id", latest_submission_id)
                .order("rank_position")
                .execute()
                .data
            )
            recommendations = []
            for row in rows:
                explanation = row["explanation"]
                if ml_result is None:
                    ml_result = explanation.get("ml_comparison")
                recommendations.append({
                    "key": row["career_paths"]["slug"],
                    "career_path": {
                        "name": row["career_paths"]["name"],
                        "description": row["career_paths"]["description"],
                        "courses": row["career_paths"]["suggested_courses"],
                    },
                    "score": row["score"],
                    "percentage": row["match_percentage"],
                    "tier": row["match_tier"],
                    "tier_description": explanation["tier_description"],
                    "category_breakdown": explanation["category_breakdown"],
                    "fit_details": explanation["fit_details"],
                    "gap_details": explanation["gap_details"],
                    "matched_skills": explanation["matched_skills"],
                    "skills_to_improve": explanation["skills_to_improve"],
                    "rule_based_score": explanation.get(
                        "rule_based_score",
                        explanation.get("rule_percentage", row["match_percentage"]),
                    ),
                    "rule_percentage": explanation.get("rule_percentage", row["match_percentage"]),
                    "ml_confidence": explanation.get(
                        "ml_confidence",
                        explanation.get("raw_ml_confidence"),
                    ),
                    "raw_ml_confidence": explanation.get("raw_ml_confidence"),
                    "agreement_score": explanation.get("agreement_score"),
                    "final_score": explanation.get("final_score", row["match_percentage"]),
                    "recommendation_level": explanation.get(
                        "recommendation_level",
                        recommendation_level(row["match_percentage"]),
                    ),
                    "hybrid_explanation": explanation.get("hybrid_explanation", ""),
                    "coach_tip": row["coach_tip"],
                })
        except Exception:
            recommendations = None
    if not recommendations:
        return redirect(url_for("questionnaire"))
    recommendations = apply_hybrid_scores_to_recommendations(recommendations, ml_result)
    ml_result = align_ml_with_rule_recommendations(ml_result, recommendations)
    return render_template(
        "result.html",
        saved={
            "name": recommendations[0]["career_path"]["name"],
            "short_description": recommendations[0]["career_path"]["description"],
            "suggested_courses": ", ".join(recommendations[0]["career_path"]["courses"]),
            "match_percentage": recommendations[0]["percentage"],
        },
        result=recommendations[0],
        recommendations=recommendations,
        ml_result=ml_result,
    )


@app.route("/admin/login")
def admin_login():
    flash("Admin management is not enabled in the current Supabase student build.", "warning")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
