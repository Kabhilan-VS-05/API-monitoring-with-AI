"""
app_mongodb.py - API Monitoring with MongoDB storage and compression.

Features:
    - MongoDB for scalable data storage
    - BSON compression for efficient storage
    - All features from original app maintained
    - Improved query performance with indexes
    - Data compression for logs and certificates
"""

import threading
import time
import os
import json
import math
import io
import socket
import re
import secrets
import smtplib
import pycurl
import idna
import ssl
import zlib
import base64
from email.message import EmailMessage
from functools import wraps
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, send_from_directory, session, redirect
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
import requests
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None
    print("[Twilio] Library not installed. SMS sending will use non-Twilio fallback providers.")

# Import new integration modules
from github_integration import GitHubIntegration
from issue_integration import IssueIntegration
from log_collector import MongoDBLogHandler, log_api_error, get_recent_logs, get_logs_by_api
from correlation_engine import CorrelationEngine
from ai_predictor import CategoryAwareAIPredictor as AIPredictor
from alert_manager import AlertManager
from ai_alert_manager import AIAlertManager

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to project root for static folders
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if load_dotenv is not None:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
SIMPLE_STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
ADVANCED_STATIC_DIR = os.path.join(PROJECT_ROOT, "static_advanced")
app = Flask(__name__, static_folder=SIMPLE_STATIC_DIR)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.getenv("AUTH_SESSION_DAYS", "7")))
auth_serializer = URLSafeTimedSerializer(app.secret_key)

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000,http://127.0.0.1:5000"
)
if CORS_ORIGINS.strip() == "*":
    CORS(app)
else:
    allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]
    CORS(app, resources={r"/*": {"origins": allowed_origins}})

# AI Training Service URL (runs on separate port)
AI_TRAINING_SERVICE_URL = "http://localhost:5001"

# Connectivity pre-check before API monitoring
NETWORK_TEST_URL = os.getenv("NETWORK_TEST_URL", "https://www.gstatic.com/generate_204")
NETWORK_TEST_URLS = os.getenv("NETWORK_TEST_URLS", NETWORK_TEST_URL)
NETWORK_TEST_TIMEOUT_SECONDS = int(os.getenv("NETWORK_TEST_TIMEOUT_SECONDS", "6"))
NETWORK_MIN_DOWNLOAD_MBPS = float(os.getenv("NETWORK_MIN_DOWNLOAD_MBPS", "0.05"))
NETWORK_MAX_LATENCY_MS = float(os.getenv("NETWORK_MAX_LATENCY_MS", "3000"))

# SLO/Burn-rate configuration
SLO_TARGET_UPTIME_PCT = float(os.getenv("SLO_TARGET_UPTIME_PCT", "99.9"))
SLO_ERROR_BUDGET_WINDOW_DAYS = int(os.getenv("SLO_ERROR_BUDGET_WINDOW_DAYS", "30"))
BURN_RATE_WARNING_1H = float(os.getenv("BURN_RATE_WARNING_1H", "6.0"))
BURN_RATE_WARNING_6H = float(os.getenv("BURN_RATE_WARNING_6H", "3.0"))
BURN_RATE_CRITICAL_1H = float(os.getenv("BURN_RATE_CRITICAL_1H", "14.4"))
BURN_RATE_CRITICAL_6H = float(os.getenv("BURN_RATE_CRITICAL_6H", "6.0"))
BURN_RATE_ALERT_COOLDOWN_MINUTES = int(os.getenv("BURN_RATE_ALERT_COOLDOWN_MINUTES", "30"))

# Authentication configuration
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() in ("1", "true", "yes", "on")
AUTH_REQUIRE_EMAIL_VERIFICATION = os.getenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "true").lower() in ("1", "true", "yes", "on")
AUTH_EMAIL_TOKEN_MAX_AGE_SECONDS = int(os.getenv("AUTH_EMAIL_TOKEN_MAX_AGE_SECONDS", "86400"))
AUTH_SMTP_HOST = os.getenv("AUTH_SMTP_HOST", "smtp.gmail.com")
AUTH_SMTP_PORT = int(os.getenv("AUTH_SMTP_PORT", "587"))
AUTH_SMTP_USERNAME = os.getenv("AUTH_SMTP_USERNAME", "")
AUTH_SMTP_APP_PASSWORD = os.getenv("AUTH_SMTP_APP_PASSWORD", "")
AUTH_SMTP_FROM_EMAIL = os.getenv("AUTH_SMTP_FROM_EMAIL", AUTH_SMTP_USERNAME or "noreply@example.com")
AUTH_EMAIL_SUBJECT = os.getenv("AUTH_EMAIL_SUBJECT", "Verify your API Monitoring account")

# Subscription configuration
FREE_MAX_MONITORS = int(os.getenv("FREE_MAX_MONITORS", "100"))
PREMIUM_INTERVAL_SECONDS = {30, 10, 5, 1}

# WhatsApp notification provider configuration
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://api.example.com/whatsapp/send")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

# SMS notification provider configuration (generic HTTP)
SMS_API_URL = os.getenv("SMS_API_URL", "https://api.example.com/sms/send")
SMS_API_TOKEN = os.getenv("SMS_API_TOKEN")

# Twilio SMS configuration (preferred when set)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

twilio_client = None
if TwilioClient and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        print(f"[Twilio] Failed to initialize client: {e}")

# IVR notification provider configuration
IVR_API_URL = os.getenv("IVR_API_URL", "https://api.example.com/ivr/call")
IVR_API_TOKEN = os.getenv("IVR_API_TOKEN")

# Translation provider configuration
TRANSLATION_API_URL = os.getenv("TRANSLATION_API_URL", "https://translation.googleapis.com/language/translate/v2")
TRANSLATION_API_KEY = os.getenv("TRANSLATION_API_KEY")
SUPPORTED_LANGUAGES = {"EN", "TA", "HI"}

# --- MongoDB Configuration ---
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "api_monitoring")

# Global MongoDB client
mongo_client = None
db = None

# --- Compression Utilities ---
def compress_data(data):
    """Compress string data using zlib and encode to base64."""
    if not data:
        return None
    try:
        compressed = zlib.compress(data.encode('utf-8'), level=9)
        return base64.b64encode(compressed).decode('utf-8')
    except Exception as e:
        print(f"[COMPRESSION ERROR] {e}")
        return data

def decompress_data(compressed_data):
    """Decompress base64 encoded zlib data."""
    if not compressed_data:
        return None
    try:
        decoded = base64.b64decode(compressed_data.encode('utf-8'))
        return zlib.decompress(decoded).decode('utf-8')
    except Exception as e:
        print(f"[DECOMPRESSION ERROR] {e}")
        return compressed_data

# --- MongoDB Connection ---
def init_mongodb():
    """Initialize MongoDB connection and create indexes."""
    global mongo_client, db
    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        mongo_client.server_info()
        db = mongo_client[MONGODB_DB]
        
        # Create collections and indexes
        monitored_apis = db.monitored_apis
        monitoring_logs = db.monitoring_logs
        
        # Indexes for monitored_apis
        try:
            monitored_apis.drop_index("url_1")
        except Exception:
            pass
        monitored_apis.create_index([("user_id", ASCENDING), ("url", ASCENDING)], unique=True)
        monitored_apis.create_index([("category", ASCENDING)])
        monitored_apis.create_index([("is_active", ASCENDING)])
        monitored_apis.create_index([("user_id", ASCENDING)])
        
        # Indexes for monitoring_logs
        monitoring_logs.create_index([("api_id", ASCENDING)])
        monitoring_logs.create_index([("user_id", ASCENDING)])
        monitoring_logs.create_index([("timestamp", DESCENDING)])
        monitoring_logs.create_index([("api_id", ASCENDING), ("timestamp", DESCENDING)])
        monitoring_logs.create_index([("check_skipped", ASCENDING)])
        
        # New collections for developer data
        git_commits = db.git_commits
        issues = db.issues
        application_logs = db.application_logs
        incident_reports = db.incident_reports
        data_correlations = db.data_correlations
        pull_requests = db.pull_requests
        
        # Indexes for git_commits
        git_commits.create_index([("commit_id", ASCENDING)], unique=True)
        git_commits.create_index([("timestamp", DESCENDING)])
        git_commits.create_index([("repository", ASCENDING)])
        
        # Indexes for issues
        issues.create_index([("issue_id", ASCENDING)], unique=True)
        issues.create_index([("state", ASCENDING)])
        issues.create_index([("created_at", DESCENDING)])
        
        # Indexes for application_logs
        application_logs.create_index([("timestamp", DESCENDING)])
        application_logs.create_index([("level", ASCENDING)])
        application_logs.create_index([("api_endpoint", ASCENDING)])
        
        # Indexes for incident_reports
        incident_reports.create_index([("incident_id", ASCENDING)], unique=True)
        incident_reports.create_index([("created_at", DESCENDING)])
        
        # Index for github_settings collection
        github_settings = db.github_settings
        github_settings.create_index([("user_id", ASCENDING)], unique=True)
        
        # Index for alert_history collection
        alert_history = db.alert_history
        alert_history.create_index([("api_id", ASCENDING)])
        alert_history.create_index([("user_id", ASCENDING)])
        alert_history.create_index([("user_id", ASCENDING), ("api_id", ASCENDING)])
        alert_history.create_index([("created_at", DESCENDING)])
        alert_history.create_index([("status", ASCENDING)])
        alert_history.create_index([("alert_type", ASCENDING), ("status", ASCENDING)])

        # Incident grouping and suppression
        alert_incidents = db.alert_incidents
        alert_incidents.create_index([("api_id", ASCENDING), ("status", ASCENDING)])
        alert_incidents.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
        alert_incidents.create_index([("created_at", DESCENDING)])
        alert_incidents.create_index([("incident_id", ASCENDING)], unique=True)

        # AI insights collection for LLM-style summaries
        ai_insights = db.ai_insights
        ai_insights.create_index([("api_id", ASCENDING), ("created_at", DESCENDING)])
        ai_insights.create_index([("training_session_id", ASCENDING)])

        # AI training run history (detailed logs per training session)
        ai_training_runs = db.ai_training_runs
        ai_training_runs.create_index([("api_id", ASCENDING), ("created_at", DESCENDING)])
        ai_training_runs.create_index([("training_session_id", ASCENDING)])

        # Worker responses for field teams
        worker_responses = db.worker_responses
        worker_responses.create_index([("api_id", ASCENDING)])
        worker_responses.create_index([("alert_id", ASCENDING)])
        worker_responses.create_index([("response", ASCENDING)])
        worker_responses.create_index([("worker_id", ASCENDING)])

        translation_cache = db.translation_cache
        translation_cache.create_index([("source_text", ASCENDING), ("target_language", ASCENDING)], unique=True)

        # Authentication collections
        auth_users = db.auth_users
        auth_users.create_index([("email", ASCENDING)], unique=True)
        auth_users.create_index([("created_at", DESCENDING)])

        # Indexes for data_correlations
        data_correlations.create_index([("api_id", ASCENDING)])
        data_correlations.create_index([("timestamp", DESCENDING)])
        data_correlations.create_index([("monitoring_log_id", ASCENDING)])
        
        print(f"[MongoDB] Connected successfully to {MONGODB_DB}")
        print(f"[MongoDB] Initialized 9 collections with indexes")
        
        return True
    except Exception as e:
        print(f"[MongoDB ERROR] Failed to connect: {e}")
        print("[MongoDB] Please ensure MongoDB is running and accessible")
        return False

# --- Utility Functions ---
def now_isoutc():
    return datetime.utcnow().isoformat() + "Z"

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc != ""
    except Exception:
        return False


def parse_iso_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
    if not isinstance(value, str) or not value:
        return None
    raw = value.strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo is None else dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (percentile / 100.0)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * weight)


ROOT_CAUSE_DESCRIPTIONS = {
    "network": "Network connectivity issue between monitor and target",
    "dns": "DNS resolution issue or very slow DNS lookup",
    "tls": "TLS/SSL handshake or certificate problem",
    "timeout": "Request timed out before response completed",
    "5xx": "Server-side HTTP 5xx error from upstream service",
    "auth": "Authentication/authorization failure (401/403)",
    "unknown": "Root cause could not be classified automatically",
}


def classify_root_cause(log_entry):
    if not isinstance(log_entry, dict):
        return "unknown"

    status_code = log_entry.get("status_code")
    try:
        status_code = int(status_code) if status_code is not None else None
    except Exception:
        status_code = None

    error_text = str(log_entry.get("error_message") or log_entry.get("error") or "").lower()
    network_is_up = log_entry.get("network_is_up")
    skip_reason = str(log_entry.get("skip_reason") or "").lower()

    if log_entry.get("check_skipped") or skip_reason == "network_unavailable":
        return "network"
    if "low network" in error_text or "network is unreachable" in error_text:
        return "network"
    if network_is_up is False and not bool(log_entry.get("is_up", True)):
        return "network"

    if status_code in {401, 403, 407}:
        return "auth"
    if status_code is not None and 500 <= status_code <= 599:
        return "5xx"

    timeout_patterns = ("timeout", "timed out", "operation timeout", "read timeout", "connection timeout")
    if any(p in error_text for p in timeout_patterns):
        return "timeout"

    dns_patterns = ("could not resolve host", "name or service not known", "getaddrinfo", "dns")
    if any(p in error_text for p in dns_patterns):
        return "dns"

    tls_patterns = ("ssl", "tls", "certificate", "handshake")
    if any(p in error_text for p in tls_patterns):
        return "tls"

    if not bool(log_entry.get("is_up", True)):
        dns_latency = safe_float(log_entry.get("dns_latency_ms")) or 0.0
        tls_latency = safe_float(log_entry.get("tls_latency_ms")) or 0.0
        if dns_latency >= 2500:
            return "dns"
        if tls_latency >= 2500:
            return "tls"

    return "unknown"


def compute_slo_metrics(api_id, now_utc=None):
    metrics = {
        "slo_target_uptime_pct": SLO_TARGET_UPTIME_PCT,
        "error_budget_window_days": SLO_ERROR_BUDGET_WINDOW_DAYS,
        "uptime_pct_24h": 100.0,
        "avg_latency_24h": 0.0,
        "p95_latency_24h": 0.0,
        "checks_24h": 0,
        "error_budget_remaining_pct": 100.0,
        "error_budget_consumed_pct": 0.0,
        "observed_error_rate_pct_window": 0.0,
        "allowed_error_rate_pct": max(0.0001, 100.0 - SLO_TARGET_UPTIME_PCT),
        "burn_rate_1h": 0.0,
        "burn_rate_6h": 0.0,
        "burn_rate_alert_level": "none",
        "burn_rate_alert_message": "No burn-rate alert",
    }

    if db is None or not api_id:
        return metrics

    now_utc = now_utc or datetime.utcnow()
    budget_days = max(1, int(SLO_ERROR_BUDGET_WINDOW_DAYS))
    start_budget = now_utc - timedelta(days=budget_days)
    start_24h = now_utc - timedelta(hours=24)
    start_6h = now_utc - timedelta(hours=6)
    start_1h = now_utc - timedelta(hours=1)

    cursor = db.monitoring_logs.find(
        {
            "api_id": api_id,
            "timestamp": {"$gte": start_budget.isoformat() + "Z"},
            "check_skipped": {"$ne": True},
        },
        {
            "timestamp": 1,
            "is_up": 1,
            "total_latency_ms": 1,
        },
    )

    total_budget = 0
    down_budget = 0
    total_24h = 0
    up_24h = 0
    total_1h = 0
    down_1h = 0
    total_6h = 0
    down_6h = 0
    latency_24h = []

    for log in cursor:
        ts = parse_iso_datetime(log.get("timestamp"))
        if ts is None:
            continue

        is_up = bool(log.get("is_up", False))
        total_budget += 1
        if not is_up:
            down_budget += 1

        if ts >= start_24h:
            total_24h += 1
            if is_up:
                up_24h += 1
            latency = safe_float(log.get("total_latency_ms"))
            if latency is not None and latency >= 0:
                latency_24h.append(latency)

        if ts >= start_6h:
            total_6h += 1
            if not is_up:
                down_6h += 1

        if ts >= start_1h:
            total_1h += 1
            if not is_up:
                down_1h += 1

    if total_24h > 0:
        metrics["checks_24h"] = total_24h
        metrics["uptime_pct_24h"] = round((up_24h / total_24h) * 100.0, 2)
        if latency_24h:
            metrics["avg_latency_24h"] = round(sum(latency_24h) / len(latency_24h), 2)
            metrics["p95_latency_24h"] = round(calculate_percentile(latency_24h, 95), 2)

    allowed_error_rate = max(1e-9, 1.0 - (SLO_TARGET_UPTIME_PCT / 100.0))
    observed_error_rate_budget = (down_budget / total_budget) if total_budget > 0 else 0.0
    metrics["observed_error_rate_pct_window"] = round(observed_error_rate_budget * 100.0, 4)
    metrics["allowed_error_rate_pct"] = round(allowed_error_rate * 100.0, 4)

    consumed_ratio = observed_error_rate_budget / allowed_error_rate if allowed_error_rate > 0 else 0.0
    consumed_pct = max(0.0, min(100.0, consumed_ratio * 100.0))
    metrics["error_budget_consumed_pct"] = round(consumed_pct, 2)
    metrics["error_budget_remaining_pct"] = round(max(0.0, 100.0 - consumed_pct), 2)

    error_rate_1h = (down_1h / total_1h) if total_1h > 0 else 0.0
    error_rate_6h = (down_6h / total_6h) if total_6h > 0 else 0.0
    burn_1h = error_rate_1h / allowed_error_rate if allowed_error_rate > 0 else 0.0
    burn_6h = error_rate_6h / allowed_error_rate if allowed_error_rate > 0 else 0.0
    metrics["burn_rate_1h"] = round(burn_1h, 2)
    metrics["burn_rate_6h"] = round(burn_6h, 2)

    if total_1h >= 3 and total_6h >= 6 and burn_1h >= BURN_RATE_CRITICAL_1H and burn_6h >= BURN_RATE_CRITICAL_6H:
        metrics["burn_rate_alert_level"] = "critical"
        metrics["burn_rate_alert_message"] = (
            f"Critical burn rate: 1h={burn_1h:.2f}x, 6h={burn_6h:.2f}x error budget consumption"
        )
    elif total_1h >= 3 and total_6h >= 6 and burn_1h >= BURN_RATE_WARNING_1H and burn_6h >= BURN_RATE_WARNING_6H:
        metrics["burn_rate_alert_level"] = "warning"
        metrics["burn_rate_alert_message"] = (
            f"Warning burn rate: 1h={burn_1h:.2f}x, 6h={burn_6h:.2f}x error budget consumption"
        )

    return metrics


def sync_burn_rate_alert(api_id, api_url, slo_metrics, user_id=None):
    if db is None:
        return None

    level = (slo_metrics or {}).get("burn_rate_alert_level", "none")
    user_id = user_id or "default_user"
    open_alert = db.alert_history.find_one(
        {
            "api_id": api_id,
            "user_id": user_id,
            "status": "open",
            "alert_type": "burn_rate",
        },
        sort=[("created_at", DESCENDING)],
    )

    if level in {"warning", "critical"}:
        payload = {
            "severity": level,
            "reason": slo_metrics.get("burn_rate_alert_message"),
            "burn_rate_1h": slo_metrics.get("burn_rate_1h"),
            "burn_rate_6h": slo_metrics.get("burn_rate_6h"),
            "error_budget_remaining_pct": slo_metrics.get("error_budget_remaining_pct"),
            "updated_at": now_isoutc(),
        }
        if open_alert:
            db.alert_history.update_one({"_id": open_alert["_id"]}, {"$set": payload})
            return {"status": "updated"}

        cooldown_cutoff = (datetime.utcnow() - timedelta(minutes=BURN_RATE_ALERT_COOLDOWN_MINUTES)).isoformat() + "Z"
        recent = db.alert_history.find_one(
            {
                "api_id": api_id,
                "user_id": user_id,
                "alert_type": "burn_rate",
                "created_at": {"$gte": cooldown_cutoff},
            }
        )
        if recent:
            return {"status": "suppressed"}

        db.alert_history.insert_one(
            {
                "api_id": api_id,
                "user_id": user_id,
                "api_url": api_url,
                "alert_type": "burn_rate",
                "status": "open",
                "severity": level,
                "reason": slo_metrics.get("burn_rate_alert_message"),
                "burn_rate_1h": slo_metrics.get("burn_rate_1h"),
                "burn_rate_6h": slo_metrics.get("burn_rate_6h"),
                "error_budget_remaining_pct": slo_metrics.get("error_budget_remaining_pct"),
                "created_at": now_isoutc(),
            }
        )
        return {"status": "created"}

    if open_alert:
        db.alert_history.update_one(
            {"_id": open_alert["_id"]},
            {"$set": {"status": "closed", "resolved_at": now_isoutc(), "resolution": "Burn rate normalized"}},
        )
        return {"status": "closed"}

    return {"status": "none"}


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalize_email(email):
    return (email or "").strip().lower()


def is_valid_email(email):
    return bool(EMAIL_RE.match(normalize_email(email)))


def build_email_verification_token(email):
    return auth_serializer.dumps({"email": normalize_email(email)}, salt="email-verify")


def build_email_verification_url(verification_token):
    base_url = os.getenv("AUTH_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    return f"{base_url}/auth/verify-email?token={verification_token}"


def read_email_verification_token(token):
    data = auth_serializer.loads(
        token,
        salt="email-verify",
        max_age=AUTH_EMAIL_TOKEN_MAX_AGE_SECONDS
    )
    return normalize_email(data.get("email"))


def has_smtp_credentials():
    username = (AUTH_SMTP_USERNAME or "").strip()
    app_password = (AUTH_SMTP_APP_PASSWORD or "").strip()
    if not username or not app_password:
        return False

    placeholder_usernames = {"your_email@example.com", "noreply@example.com"}
    placeholder_passwords = {"your_app_password_here", "app_password"}
    if username.lower() in placeholder_usernames:
        return False
    if app_password.lower() in placeholder_passwords:
        return False
    return True


def send_verification_email(to_email, verification_token):
    if not has_smtp_credentials():
        return False, "SMTP credentials not configured. Set AUTH_SMTP_USERNAME and AUTH_SMTP_APP_PASSWORD in .env, then restart."

    verify_link = build_email_verification_url(verification_token)
    msg = EmailMessage()
    msg["Subject"] = AUTH_EMAIL_SUBJECT
    msg["From"] = AUTH_SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg.set_content(
        "Verify your API Monitoring account.\n\n"
        f"Open this link:\n{verify_link}\n\n"
        f"This link expires in {AUTH_EMAIL_TOKEN_MAX_AGE_SECONDS // 3600} hour(s)."
    )

    try:
        with smtplib.SMTP(AUTH_SMTP_HOST, AUTH_SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(AUTH_SMTP_USERNAME, AUTH_SMTP_APP_PASSWORD)
            smtp.send_message(msg)
        return True, None
    except Exception as exc:
        return False, str(exc)


def build_verification_delivery_payload(base_payload, verification_token, sent, error):
    payload = dict(base_payload or {})
    payload["requires_verification"] = True
    payload["email_sent"] = bool(sent)
    if sent:
        return payload
    payload["delivery_error"] = error or "Unable to send verification email"
    payload["dev_verification_token"] = verification_token
    payload["verification_url"] = build_email_verification_url(verification_token)
    return payload


def normalize_subscription_plan(plan):
    value = str(plan or "free").strip().lower()
    if value in {"subscriber", "premium", "pro", "paid", "unlimited"}:
        return "subscriber"
    return "free"


def is_subscriber(user_or_plan):
    if isinstance(user_or_plan, dict):
        plan = normalize_subscription_plan(user_or_plan.get("subscription_plan"))
    else:
        plan = normalize_subscription_plan(user_or_plan)
    return plan == "subscriber"


def subscription_features(plan):
    normalized = normalize_subscription_plan(plan)
    return {
        "plan": normalized,
        "max_monitors": None if normalized == "subscriber" else FREE_MAX_MONITORS,
        "premium_frequency_locked": normalized != "subscriber",
        "community_communication_enabled": normalized == "subscriber",
        "premium_intervals_seconds": sorted(PREMIUM_INTERVAL_SECONDS),
        "free_channels": ["email", "github_issue"],
    }


def minutes_to_seconds(freq_minutes):
    value = safe_float(freq_minutes)
    if value is None or value <= 0:
        return 60
    return int(round(value * 60))


def is_premium_frequency(freq_minutes):
    return minutes_to_seconds(freq_minutes) in PREMIUM_INTERVAL_SECONDS


def get_current_user_id():
    user = get_current_user()
    if not user:
        return None
    return str(user.get("_id"))


def get_user_from_session_or_error():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)
    return user, None


def get_monitor_for_user(api_id, user_id):
    if db is None:
        return None
    try:
        return db.monitored_apis.find_one({"_id": ObjectId(api_id), "user_id": user_id})
    except Exception:
        return None


def ensure_api_access_or_error(api_id, user_id):
    api_doc = get_monitor_for_user(api_id, user_id)
    if not api_doc:
        return None, (jsonify({"error": "API not found or access denied"}), 404)
    return api_doc, None


def get_user_settings(user_id):
    if db is None:
        return None
    return db.github_settings.find_one({"user_id": user_id})


def get_user_plan_by_id(user_id):
    if db is None or not user_id:
        return "free"
    try:
        user = db.auth_users.find_one({"_id": ObjectId(user_id)}, {"subscription_plan": 1})
    except Exception:
        return "free"
    if not user:
        return "free"
    return normalize_subscription_plan(user.get("subscription_plan"))


def require_logged_in_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_subscriber_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if not is_subscriber(user):
            return jsonify({
                "error": "This feature requires subscription",
                "plan": normalize_subscription_plan(user.get("subscription_plan")),
                "required_plan": "subscriber",
            }), 403
        return fn(*args, **kwargs)
    return wrapper

def serialize_objectid(doc):
    """Convert MongoDB ObjectId and datetime to string for JSON serialization."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    
    # Convert datetime objects to ISO format strings
    for key, value in list(doc.items()):
        if isinstance(value, datetime):
            doc[key] = value.isoformat() + "Z"
    
    return doc


def serialize_ai_insight(doc):
    if not doc:
        return None
    serialized = dict(doc)
    serialize_objectid(serialized)
    return serialized


def serialize_worker_response(doc):
    if not doc:
        return None
    serialized = dict(doc)
    serialize_objectid(serialized)
    return serialized


def fetch_worker_responses(api_id, limit=10, user_id=None):
    if db is None or not api_id:
        return []
    query = {"api_id": api_id}
    if user_id:
        query["user_id"] = user_id
    cursor = db.worker_responses.find(query).sort("timestamp", DESCENDING).limit(limit)
    return [serialize_worker_response(doc) for doc in cursor]


def build_whatsapp_message(payload):
    template = (
        "⚠️ API Alert: {api_name}\n"
        "Risk: {risk_percentage}%\n"
        "Cause: {cause_summary}\n"
        "Action: {recommendation}\n\n"
        "Reply:\n"
        "1 - FIXED\n"
        "2 - NEED HELP\n"
        "3 - RETRY"
    )
    return template.format(
        api_name=payload.get("api_name", "Unknown API"),
        risk_percentage=payload.get("risk_percentage", "N/A"),
        cause_summary=payload.get("cause_summary", "Unable to determine cause"),
        recommendation=payload.get("recommendation", "Follow standard recovery steps")
    )


def dispatch_whatsapp_message(phone_number, message_text):
    if not WHATSAPP_API_TOKEN:
        raise RuntimeError("Missing WHATSAPP_API_TOKEN")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}"
    }
    body = {
        "to": phone_number,
        "type": "template",
        "text": message_text,
        "quick_replies": [
            {"label": "FIXED", "metadata": "FIXED"},
            {"label": "NEED HELP", "metadata": "NEED_HELP"},
            {"label": "RETRY", "metadata": "RETRY"}
        ]
    }
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(WHATSAPP_API_URL, json=body, headers=headers, timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    return False, last_error


def build_ivr_script(payload):
    body = (
        f"Emergency alert for {payload.get('api_name', 'Unknown API')}.\n"
        f"Risk level {payload.get('risk_level', 'high')}.\n"
        f"Cause: {payload.get('cause_voice', payload.get('cause_summary', 'Check system'))}.\n"
        "To confirm after action, press 1.\n"
        "To request help, press 2.\n"
        "To repeat this message, press 3."
    )
    return body


def dispatch_ivr_call(phone_number, payload):
    if not IVR_API_TOKEN:
        raise RuntimeError("Missing IVR_API_TOKEN")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {IVR_API_TOKEN}"
    }
    body = {
        "to": phone_number,
        "script": build_ivr_script(payload),
        "api_id": payload.get("api_id"),
        "alert_id": payload.get("alert_id")
    }
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(IVR_API_URL, json=body, headers=headers, timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    return False, last_error


def normalize_ivr_input(digit):
    mapping = {"1": "FIXED", "2": "NEED_HELP", "3": "RETRY"}
    return mapping.get(str(digit).strip(), "UNKNOWN")


def normalize_whatsapp_response(message_body):
    if not message_body:
        return "UNKNOWN"
    text = message_body.strip().upper()
    if text in {"1", "FIXED", "DONE", "RESOLVED"}:
        return "FIXED"
    if "HELP" in text:
        return "NEED_HELP"
    if "RETRY" in text or text == "3":
        return "RETRY"
    return "UNKNOWN"


def build_sms_message(payload):
    parts = [
        f"API ALERT: {payload.get('api_name', 'Unknown')}",
        f"Risk: {payload.get('risk_percentage', 'N/A')}%",
        f"Cause: {payload.get('cause_short', payload.get('cause_summary', 'Check system'))}",
        f"Action: {payload.get('fix_step', payload.get('recommendation', 'Follow standard recovery steps'))}",
        "Reply FIXED or HELP"
    ]
    message = " | ".join(parts)
    return message[:160]


def dispatch_sms_message(phone_number, message_text):
    """Send SMS via Twilio if configured, otherwise fall back to generic HTTP provider.

    This allows local/dev environments to use Twilio credentials, while keeping
    compatibility with the previous SMS_API_URL/SMS_API_TOKEN flow.
    """

    # Preferred path: Twilio
    if twilio_client and TWILIO_MESSAGING_SERVICE_SID:
        try:
            message = twilio_client.messages.create(
                messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
                body=message_text,
                to=phone_number,
            )
            return True, {"sid": message.sid, "status": message.status}
        except Exception as exc:
            # If Twilio is configured but fails, bubble the error
            return False, str(exc)

    # Fallback: generic HTTP provider using SMS_API_URL/SMS_API_TOKEN
    if not SMS_API_TOKEN:
        raise RuntimeError("Missing SMS configuration: either Twilio or SMS_API_TOKEN must be set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SMS_API_TOKEN}"
    }
    body = {
        "to": phone_number,
        "message": message_text
    }
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(SMS_API_URL, json=body, headers=headers, timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    return False, last_error


def store_ai_insight(api_id, insight_payload):
    """Persist LLM-style AI insight entries."""
    if db is None or not api_id or not insight_payload:
        return None

    owner_user_id = None
    try:
        api_doc = db.monitored_apis.find_one({"_id": ObjectId(api_id)}, {"user_id": 1})
        owner_user_id = api_doc.get("user_id") if api_doc else None
    except Exception:
        owner_user_id = None

    insight_doc = {
        "api_id": api_id,
        "user_id": owner_user_id,
        "created_at": insight_payload.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "summary": insight_payload.get("summary"),
        "details": insight_payload.get("details"),
        "risk_level": insight_payload.get("risk_level"),
        "confidence": insight_payload.get("confidence"),
        "risk_score": insight_payload.get("risk_score"),
        "training_session_id": insight_payload.get("training_session_id"),
        "model_version": insight_payload.get("model_version"),
        "actions": insight_payload.get("actions", []),
        "metrics": insight_payload.get("metrics", {}),
        "raw_prediction": insight_payload.get("raw_prediction", {}),
    }

    result = db.ai_insights.insert_one(insight_doc)
    insight_doc["_id"] = result.inserted_id
    return serialize_ai_insight(insight_doc)


def persist_worker_response(doc):
    if db is None or not doc:
        return None
    if not doc.get("user_id") and doc.get("api_id"):
        try:
            api_doc = db.monitored_apis.find_one({"_id": ObjectId(doc["api_id"])}, {"user_id": 1})
            if api_doc and api_doc.get("user_id"):
                doc["user_id"] = api_doc.get("user_id")
        except Exception:
            pass
    doc.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    result = db.worker_responses.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_worker_response(doc)


def get_cached_translation(text, target_language):
    if db is None:
        return None
    if not text or not target_language:
        return None
    cache = db.translation_cache
    cached = cache.find_one({"source_text": text, "target_language": target_language})
    if cached:
        return cached["translated_text"]
    return None


def cache_translation(text, target_language, translated_text):
    if db is None:
        return None
    cache = db.translation_cache
    cache.update_one(
        {"source_text": text, "target_language": target_language},
        {"$set": {"translated_text": translated_text, "updated_at": datetime.utcnow().isoformat() + "Z"}},
        upsert=True
    )


def translate_text(text, target_language):
    if not text or not target_language:
        return ""
    target_language = target_language.upper()
    if target_language not in SUPPORTED_LANGUAGES:
        target_language = "EN"

    cached = get_cached_translation(text, target_language)
    if cached:
        return cached

    if TRANSLATION_API_KEY:
        payload = {
            "q": text,
            "target": target_language.lower(),
            "key": TRANSLATION_API_KEY
        }
        try:
            response = requests.post(TRANSLATION_API_URL, json=payload, timeout=5)
            response.raise_for_status()
            data = response.json()
            translated = (
                data.get("data", {}).get("translations", [])[0].get("translatedText")
                if data.get("data") and data["data"].get("translations")
                else text
            )
        except Exception:
            translated = text
    else:
        params = {
            "q": text,
            "langpair": f"en|{target_language.lower()}"
        }
        try:
            response = requests.get("https://api.mymemory.translated.net/get", params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            translated = data.get("responseData", {}).get("translatedText", text)
        except Exception:
            translated = text

    cache_translation(text, target_language, translated)
    return translated


def update_alert_worker_ack(alert_id, response_type, channel, timestamp):
    if db is None or not alert_id:
        return False
    try:
        object_id = ObjectId(alert_id)
    except Exception:
        return False
    update_payload = {
        "worker_acknowledgment": {
            "response": response_type,
            "channel": channel,
            "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
        }
    }
    db.alert_history.update_one({"_id": object_id}, {"$set": update_payload})
    return True


def get_ai_insights_from_db(api_id, limit=5, user_id=None):
    if db is None:
        return []
    query = {"api_id": api_id}
    if user_id:
        query["user_id"] = user_id
    cursor = db.ai_insights.find(query).sort("created_at", DESCENDING).limit(limit)
    return [serialize_ai_insight(doc) for doc in cursor]


def serialize_training_run(doc):
    if not doc:
        return None
    serialized = dict(doc)
    serialize_objectid(serialized)
    return serialized


def store_ai_training_run(api_id, payload):
    """Persist detailed AI training run summaries."""
    if db is None or not api_id or not payload:
        return None

    owner_user_id = payload.get("user_id")
    if not owner_user_id:
        try:
            api_doc = db.monitored_apis.find_one({"_id": ObjectId(api_id)}, {"user_id": 1})
            owner_user_id = api_doc.get("user_id") if api_doc else None
        except Exception:
            owner_user_id = None

    training_doc = {
        "api_id": api_id,
        "user_id": owner_user_id,
        "training_session_id": payload.get("training_session_id"),
        "mode": payload.get("mode", "full"),
        "status": payload.get("status", "completed"),
        "started_at": payload.get("started_at") or datetime.utcnow().isoformat() + "Z",
        "completed_at": payload.get("completed_at"),
        "duration_seconds": payload.get("duration_seconds"),
        "duration_minutes": payload.get("duration_minutes"),
        "failure_probability": payload.get("failure_probability"),
        "confidence": payload.get("confidence"),
        "risk_level": payload.get("risk_level"),
        "risk_score": payload.get("risk_score"),
        "sample_size": payload.get("sample_size"),
        "model_metadata": payload.get("model_metadata", {}),
        "prediction": payload.get("prediction"),
        "metrics": payload.get("metrics") or payload.get("prediction_metrics"),
        "risk_factors": payload.get("risk_factors", []),
        "log_lines": payload.get("log_lines", []),
        "summary": payload.get("summary"),
        "actions": payload.get("actions", []),
        "created_at": payload.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "alert_sent": payload.get("alert_sent", False)
    }

    result = db.ai_training_runs.insert_one(training_doc)
    training_doc["_id"] = result.inserted_id
    return serialize_training_run(training_doc)


def get_training_runs_from_db(api_id, limit=5, user_id=None):
    if db is None:
        return []
    query = {"api_id": api_id}
    if user_id:
        query["user_id"] = user_id
    cursor = db.ai_training_runs.find(query).sort("created_at", DESCENDING).limit(limit)
    return [serialize_training_run(doc) for doc in cursor]


def get_latest_training_run_from_db(api_id, user_id=None):
    if db is None:
        return None
    query = {"api_id": api_id}
    if user_id:
        query["user_id"] = user_id
    doc = db.ai_training_runs.find_one(query, sort=[("created_at", DESCENDING)])
    return serialize_training_run(doc)


@app.route("/api/ai/training_runs", methods=["POST"])
def receive_training_run():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    api_id = payload.get("api_id")
    if not api_id:
        return jsonify({"error": "api_id required"}), 400

    try:
        stored = store_ai_training_run(api_id, payload)
        return jsonify({"success": True, "training_run": stored})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/training_runs/<api_id>")
@require_logged_in_api
def list_training_runs(api_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    limit = request.args.get("limit", 10, type=int)
    limit = min(max(limit, 1), 100)
    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        runs = get_training_runs_from_db(api_id, limit=limit, user_id=get_current_user_id())
        return jsonify(runs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/training_runs/latest/<api_id>")
@require_logged_in_api
def latest_training_run(api_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        run = get_latest_training_run_from_db(api_id, user_id=get_current_user_id())
        if not run:
            return jsonify({"error": "No training runs found"}), 404
        return jsonify(run)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/notify/whatsapp/send", methods=["POST"])
@require_subscriber_api
def notify_whatsapp_send():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    phone_number = payload.get("phone_number")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    if not phone_number or not api_id or not alert_id:
        return jsonify({"error": "phone_number, api_id, and alert_id are required"}), 400
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error

    message_text = payload.get("message_text") or build_whatsapp_message(payload)
    try:
        success, response_data = dispatch_whatsapp_message(phone_number, message_text)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    if not success:
        return jsonify({"success": False, "error": response_data}), 500

    return jsonify({"success": True, "details": response_data})


@app.route("/notify/whatsapp/receive", methods=["POST"])
def notify_whatsapp_receive():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    phone_number = payload.get("phone_number")
    message_body = payload.get("message_body")
    timestamp = payload.get("timestamp")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")

    if not phone_number or not message_body:
        return jsonify({"error": "phone_number and message_body are required"}), 400

    response_type = normalize_whatsapp_response(message_body)
    response_doc = {
        "phone_number": phone_number,
        "api_id": api_id,
        "alert_id": alert_id,
        "response": response_type,
        "channel": "whatsapp",
        "raw_message": message_body,
        "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
    }
    stored = persist_worker_response(response_doc)
    update_alert_worker_ack(alert_id, response_type, "whatsapp", response_doc["timestamp"])

    return jsonify({"success": True, "worker_response": stored})


@app.route("/notify/sms/send", methods=["POST"])
@require_subscriber_api
def notify_sms_send():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    phone_number = payload.get("phone_number")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    if not phone_number or not api_id or not alert_id:
        return jsonify({"error": "phone_number, api_id, and alert_id are required"}), 400
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error

    message_text = payload.get("message_text") or build_sms_message(payload)
    try:
        success, response_data = dispatch_sms_message(phone_number, message_text)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    if not success:
        return jsonify({"success": False, "error": response_data}), 500

    return jsonify({"success": True, "details": response_data})


@app.route("/notify/sms/receive", methods=["POST"])
def notify_sms_receive():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    phone_number = payload.get("phone_number")
    message_body = payload.get("message_body")
    timestamp = payload.get("timestamp")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")

    if not phone_number or not message_body:
        return jsonify({"error": "phone_number and message_body are required"}), 400

    response_type = normalize_whatsapp_response(message_body)
    response_doc = {
        "phone_number": phone_number,
        "api_id": api_id,
        "alert_id": alert_id,
        "response": response_type,
        "channel": "sms",
        "raw_message": message_body,
        "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
    }
    stored = persist_worker_response(response_doc)
    update_alert_worker_ack(alert_id, response_type, "sms", response_doc["timestamp"])

    return jsonify({"success": True, "worker_response": stored})


@app.route("/notify/ivr/call", methods=["POST"])
@require_subscriber_api
def notify_ivr_call():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    phone_number = payload.get("phone_number")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    if not phone_number or not api_id or not alert_id:
        return jsonify({"error": "phone_number, api_id, and alert_id are required"}), 400
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error

    try:
        success, response_data = dispatch_ivr_call(phone_number, payload)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    if not success:
        return jsonify({"success": False, "error": response_data}), 500

    return jsonify({"success": True, "details": response_data})


@app.route("/notify/ivr/collect", methods=["POST"])
def notify_ivr_collect():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    digit = payload.get("digit")
    phone_number = payload.get("phone_number")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    timestamp = payload.get("timestamp")

    if digit is None or not phone_number:
        return jsonify({"error": "digit and phone_number are required"}), 400

    response_type = normalize_ivr_input(digit)
    response_doc = {
        "phone_number": phone_number,
        "api_id": api_id,
        "alert_id": alert_id,
        "response": response_type,
        "channel": "ivr",
        "raw_message": digit,
        "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
    }
    stored = persist_worker_response(response_doc)
    update_alert_worker_ack(alert_id, response_type, "ivr", response_doc["timestamp"])

    return jsonify({"success": True, "worker_response": stored})


@app.route("/utils/translate", methods=["POST"])
@require_subscriber_api
def utils_translate():
    payload = request.json or {}
    text = payload.get("text")
    target_language = payload.get("target_language", "EN")

    if not text:
        return jsonify({"error": "text is required"}), 400

    translated = translate_text(text, target_language)
    return jsonify({"translated_text": translated, "target_language": target_language.upper()})


@app.route("/incident/acknowledge", methods=["POST"])
@require_logged_in_api
def incident_acknowledge():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    worker_id = payload.get("worker_id")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    response_type = payload.get("response_type")
    timestamp = payload.get("timestamp")

    if not worker_id or not api_id or not alert_id or not response_type:
        return jsonify({"error": "worker_id, api_id, alert_id, and response_type are required"}), 400

    response_type = response_type.upper()
    if response_type not in {"FIXED", "NEED_HELP", "RETRY", "UNKNOWN"}:
        response_type = "UNKNOWN"

    response_doc = {
        "phone_number": payload.get("phone_number"),
        "worker_id": worker_id,
        "user_id": get_current_user_id(),
        "api_id": api_id,
        "alert_id": alert_id,
        "response": response_type,
        "channel": payload.get("channel", "manual"),
        "raw_message": payload.get("notes"),
        "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
    }
    stored = persist_worker_response(response_doc)
    update_alert_worker_ack(alert_id, response_type, "acknowledgement", response_doc["timestamp"])

    return jsonify({"success": True, "worker_response": stored})


# --- Advanced TLS Certificate Fetcher ---
def get_certificate_details_crypto(url):
    """Fetches and parses TLS certificate details using the cryptography library."""
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        port = parsed_url.port or 443
        if parsed_url.scheme != 'https':
            return None

        server_hostname = idna.encode(hostname).decode()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=server_hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
                cipher = ssock.cipher()
                cert = x509.load_der_x509_certificate(der_cert, default_backend())

                sans_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                san_list = [name.value for name in sans_ext.value]

                def _to_utc_iso(dt):
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt.isoformat().replace('+00:00', 'Z')

                return {
                    "subject": cert.subject.rfc4514_string(),
                    "issuer": cert.issuer.rfc4514_string(),
                    "sans": ", ".join(san_list),
                    "valid_from": _to_utc_iso(cert.not_valid_before),
                    "valid_until": _to_utc_iso(cert.not_valid_after),
                    "cipher": f"{cipher[0]} ({cipher[1]}, {cipher[2]} bits)"
                }
    except Exception as e:
        return {"error": f"Cert check failed: {str(e)}"}

# --- URL Type Determination ---
def perform_network_speed_check(timeout=6, test_url=None):
    """
    Quick internet connectivity + speed sanity check.
    Returns latency and estimated download throughput.
    """
    urls = [u.strip() for u in (test_url or NETWORK_TEST_URLS).split(",") if u.strip()]
    if not urls:
        urls = [NETWORK_TEST_URL]

    last_error = None
    last_result = None

    for url in urls:
        result = {
            "network_up": False,
            "latency_ms": None,
            "download_mbps": None,
            "status_code": None,
            "error": None,
            "timestamp": now_isoutc(),
            "test_url": url
        }

        buffer = io.BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(c.TIMEOUT, timeout)
        c.setopt(c.FOLLOWLOCATION, 1)

        try:
            c.perform()
            total_time = max(c.getinfo(c.TOTAL_TIME), 1e-6)
            status_code = int(c.getinfo(c.RESPONSE_CODE))
            size_download = c.getinfo(c.SIZE_DOWNLOAD)
            if not size_download:
                size_download = len(buffer.getvalue())

            latency_ms = total_time * 1000.0
            # Megabits per second
            download_mbps = (size_download * 8.0) / (total_time * 1_000_000.0)

            # NOTE:
            # Endpoints like /generate_204 intentionally return tiny/empty payloads.
            # In that case, treat throughput as informational and do not fail connectivity.
            enforce_speed = float(size_download) >= 1024.0 and NETWORK_MIN_DOWNLOAD_MBPS > 0
            speed_ok = (download_mbps >= NETWORK_MIN_DOWNLOAD_MBPS) if enforce_speed else True
            latency_ok = latency_ms <= NETWORK_MAX_LATENCY_MS
            status_ok = 200 <= status_code < 500
            network_up = status_ok and latency_ok and speed_ok

            result.update({
                "network_up": network_up,
                "latency_ms": round(latency_ms, 2),
                "download_mbps": round(download_mbps, 3),
                "status_code": status_code
            })

            if network_up:
                c.close()
                return result

            if not status_ok:
                last_error = f"status {status_code}"
            elif not latency_ok:
                last_error = f"high latency {latency_ms:.1f}ms"
            elif not speed_ok:
                last_error = f"low speed {download_mbps:.3f}Mbps"
            else:
                last_error = "connectivity check failed"
            result["error"] = last_error
            last_result = result

        except pycurl.error as e:
            last_error = f"{e}"
            result["error"] = last_error
            last_result = result
        finally:
            c.close()

    if last_result:
        return last_result

    return {
        "network_up": False,
        "latency_ms": None,
        "download_mbps": None,
        "status_code": None,
        "error": last_error or "No network test URL configured",
        "timestamp": now_isoutc(),
        "test_url": None
    }


def determine_url_type(content_type):
    """Determines the type of URL based on its Content-Type header."""
    if not content_type:
        return "Unknown"
    ct = content_type.lower()
    if 'application/json' in ct or 'application/vnd.api+json' in ct:
        return "API"
    if 'text/html' in ct:
        return "Website"
    if 'application/xml' in ct or 'text/xml' in ct:
        return "XML Endpoint"
    if 'application/javascript' in ct or 'text/javascript' in ct:
        return "JavaScript File"
    if 'image/' in ct:
        return "Image"
    return "Resource"

# --- Core Latency Check using pycurl ---
def perform_latency_check(url, headers=None, timeout=10, body_snippet_len=1000, required_body_substring=None):
    if headers is None: headers = {}
    
    result = {
        "status_code": None, "up": False, "total_latency_ms": None,
        "dns_latency_ms": None, "tcp_latency_ms": None, "tls_latency_ms": None,
        "server_processing_latency_ms": None, "content_download_latency_ms": None,
        "content_type": None, "body_snippet": None, "certificate_details": None,
        "error": None, "timestamp": now_isoutc(), "url_type": "Unknown"
    }
    
    buffer = io.BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.TIMEOUT, timeout)
    c.setopt(c.FOLLOWLOCATION, 1)
    if headers: c.setopt(c.HTTPHEADER, [f"{key}: {value}" for key, value in headers.items()])
    if hasattr(c, "CERTINFO"):
        c.setopt(c.CERTINFO, 1)
    else:
        print("[PycURL] CERTINFO not supported on this platform; skipping certificate detail collection")

    try:
        c.perform()

        # Latency
        dns_ms = c.getinfo(c.NAMELOOKUP_TIME) * 1000
        tcp_ms = (c.getinfo(c.CONNECT_TIME) - c.getinfo(c.NAMELOOKUP_TIME)) * 1000
        tls_ms = (c.getinfo(c.APPCONNECT_TIME) - c.getinfo(c.CONNECT_TIME)) * 1000 if url.startswith("https") else 0
        server_ms = (c.getinfo(c.PRETRANSFER_TIME) - c.getinfo(c.APPCONNECT_TIME)) * 1000 if url.startswith("https") else (c.getinfo(c.PRETRANSFER_TIME) - c.getinfo(c.CONNECT_TIME)) * 1000
        download_ms = (c.getinfo(c.TOTAL_TIME) - c.getinfo(c.PRETRANSFER_TIME)) * 1000
        total_ms = c.getinfo(c.TOTAL_TIME) * 1000

        # Response
        status_code = c.getinfo(c.RESPONSE_CODE)
        content_type = c.getinfo(c.CONTENT_TYPE)
        body = buffer.getvalue().decode('utf-8', errors='replace')
        snippet = body[:body_snippet_len]

        up = 200 <= status_code < 300
        if required_body_substring and not (snippet and required_body_substring in snippet):
            up = False
            result["error"] = "Required text not found in response body."

        result.update({
            "status_code": status_code, "up": up,
            "total_latency_ms": round(total_ms, 2),
            "dns_latency_ms": round(dns_ms, 2),
            "tcp_latency_ms": round(max(0, tcp_ms), 2),
            "tls_latency_ms": round(max(0, tls_ms), 2),
            "server_processing_latency_ms": round(max(0, server_ms), 2),
            "content_download_latency_ms": round(max(0, download_ms), 2),
            "content_type": content_type, "body_snippet": snippet,
            "url_type": determine_url_type(content_type),
        })

        cert_details = _extract_certificate_from_curl(url, c)
        if cert_details is not None:
            result["certificate_details"] = cert_details

    except pycurl.error as e:
        result.update({ "error": str(e), "up": False })
        if url.lower().startswith("https"):
            fallback_cert = get_certificate_details_crypto(url)
            if fallback_cert is not None:
                result["certificate_details"] = fallback_cert
    finally:
        c.close()

    return result


def _extract_certificate_from_curl(url, curl_handle):
    """Extract certificate metadata from a pycurl handle, with fallback helpers."""
    if not url.lower().startswith("https"):
        return None

    try:
        cert_info = curl_handle.getinfo(pycurl.CERTINFO)
    except (AttributeError, pycurl.error):
        return get_certificate_details_crypto(url)

    if cert_info:
        try:
            server_cert = cert_info[0] if cert_info else []
            info_map = {}
            for key, value in server_cert:
                info_map.setdefault(key, []).append(value)

            def _first(key):
                values = info_map.get(key)
                return values[0] if values else None

            def _parse_date(value):
                if not value:
                    return None
                for fmt in ("%b %d %H:%M:%S %Y %Z", "%Y-%m-%d %H:%M:%S %Z"):
                    try:
                        dt = datetime.strptime(value, fmt)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt.isoformat().replace('+00:00', 'Z')
                    except ValueError:
                        continue
                return value

            sans_raw = _first("Subject Alternative Name")
            if sans_raw:
                sans = ", ".join(part.replace("DNS:", "").strip() for part in sans_raw.split(','))
            else:
                sans = None

            cipher = _first("Cipher")

            details = {
                "subject": _first("Subject"),
                "issuer": _first("Issuer"),
                "sans": sans,
                "valid_from": _parse_date(_first("Start date")),
                "valid_until": _parse_date(_first("Expire date")),
            }

            if cipher:
                details["cipher"] = cipher

            if any(details.values()):
                return details
        except Exception as parse_error:
            fallback = get_certificate_details_crypto(url)
            if isinstance(fallback, dict):
                if fallback.get("error"):
                    fallback["error"] = f"{fallback['error']} | curl parse error: {parse_error}"
                return fallback
            return {"error": f"Curl cert parse error: {parse_error}"}

    return get_certificate_details_crypto(url)

# --- Background Worker for Advanced Monitoring ---
def monitor_worker(sleep_seconds=30):
    print("🚀 Advanced Monitoring worker started.")
    alert_manager = None
    ai_alert_manager = None
    while True:
        try:
            if db is None:
                print("[Monitor] MongoDB not connected, skipping check cycle")
                time.sleep(sleep_seconds)
                continue

            if alert_manager is None:
                alert_manager = AlertManager(db)
            if ai_alert_manager is None:
                ai_alert_manager = AIAlertManager(db)

            monitored_apis = db.monitored_apis
            monitoring_logs = db.monitoring_logs
            network_check = perform_network_speed_check(timeout=NETWORK_TEST_TIMEOUT_SECONDS)
            # Treat network as available unless we have an explicit transport error.
            # This avoids false "Low Network" on zero-byte connectivity endpoints.
            network_is_up = bool(network_check.get("network_up") or not network_check.get("error"))
            if not network_is_up:
                print(
                    f"[Network] Connectivity check failed: "
                    f"latency={network_check.get('latency_ms')}ms, "
                    f"download={network_check.get('download_mbps')}Mbps, "
                    f"error={network_check.get('error')}"
                )

            apis = list(monitored_apis.find({"is_active": True}))

            for api in apis:
                try:
                    api_user_id = api.get("user_id", "default_user")
                    user_plan = get_user_plan_by_id(api_user_id)
                    now = datetime.utcnow()
                    should_check = True
                    last_checked = api.get("last_checked_at")
                    freq_value = api.get("check_frequency_minutes", 1)
                    try:
                        freq = float(freq_value)
                        if freq <= 0:
                            freq = 1.0
                    except (TypeError, ValueError):
                        freq = 1.0

                    # Enforce subscription frequency restrictions at runtime.
                    if is_premium_frequency(freq) and not is_subscriber(user_plan):
                        freq = 1.0  # fallback to 1 minute for free tier

                    if last_checked:
                        try:
                            if isinstance(last_checked, str):
                                last_checked_time = datetime.fromisoformat(last_checked.replace("Z", ""))
                            else:
                                last_checked_time = last_checked
                            if now < last_checked_time + timedelta(minutes=freq):
                                should_check = False
                        except Exception:
                            should_check = True

                    if not should_check:
                        continue

                    h_name = api.get("header_name") or ""
                    h_val = api.get("header_value") or ""
                    headers = {h_name: h_val} if h_name and h_val else {}

                    res = perform_latency_check(api["url"], headers=headers)
                    ts = res.get("timestamp", now_isoutc())
                    cert = res.get("certificate_details") or {}

                    # Compress body snippet if it exists
                    body_snippet_compressed = None
                    if res.get("body_snippet"):
                        body_snippet_compressed = compress_data(res.get("body_snippet"))

                    low_network_for_check = (not res.get("up")) and (not network_is_up)
                    if low_network_for_check:
                        res["error"] = f"Low network: {network_check.get('error') or res.get('error') or 'connectivity issue'}"

                    log_entry = {
                        "api_id": str(api["_id"]),
                        "user_id": api_user_id,
                        "timestamp": ts,
                        "status_code": res.get("status_code"),
                        "is_up": res.get("up"),
                        "total_latency_ms": res.get("total_latency_ms"),
                        "dns_latency_ms": res.get("dns_latency_ms"),
                        "tcp_latency_ms": res.get("tcp_latency_ms"),
                        "tls_latency_ms": res.get("tls_latency_ms"),
                        "server_processing_latency_ms": res.get("server_processing_latency_ms"),
                        "content_download_latency_ms": res.get("content_download_latency_ms"),
                        "error_message": res.get("error"),
                        "content_type": res.get("content_type"),
                        "body_snippet_compressed": body_snippet_compressed,
                        "url_type": "Network" if low_network_for_check else res.get("url_type"),
                        "check_skipped": low_network_for_check,
                        "skip_reason": "network_unavailable" if low_network_for_check else None,
                        "network_is_up": network_is_up,
                        "network_latency_ms": network_check.get("latency_ms"),
                        "network_download_mbps": network_check.get("download_mbps"),
                        "network_status_code": network_check.get("status_code"),
                        "network_error": network_check.get("error"),
                        "network_test_url": network_check.get("test_url"),
                        "tls_cert_subject": cert.get("subject"),
                        "tls_cert_issuer": cert.get("issuer"),
                        "tls_cert_sans": cert.get("sans"),
                        "tls_cert_valid_from": cert.get("valid_from"),
                        "tls_cert_valid_until": cert.get("valid_until"),
                        "tls_cipher": cert.get("cipher")
                    }

                    if not bool(log_entry.get("is_up")):
                        root_cause_hint = classify_root_cause(log_entry)
                        log_entry["root_cause_hint"] = root_cause_hint
                        log_entry["root_cause_details"] = ROOT_CAUSE_DESCRIPTIONS.get(root_cause_hint, ROOT_CAUSE_DESCRIPTIONS["unknown"])
                    else:
                        log_entry["root_cause_hint"] = None
                        log_entry["root_cause_details"] = None

                    result = monitoring_logs.insert_one(log_entry)
                    log_entry["_id"] = result.inserted_id

                    # Auto-correlate with developer data
                    try:
                        correlation_engine = CorrelationEngine(db)
                        correlation_engine.correlate_monitoring_event(log_entry)
                    except Exception as corr_err:
                        print(f"[Correlation] Error: {corr_err}")
                    
                    # System 1: Immediate downtime/recovery alerting
                    try:
                        # Use same status logic as monitoring
                        current_status = (
                            "Low Network"
                            if low_network_for_check
                            else ("Up" if res.get("up") else ("Error" if res.get("error") else "Down"))
                        )
                        if current_status != "Low Network":
                            alert_result = alert_manager.check_and_alert(
                                str(api["_id"]),
                                api["url"],
                                current_status
                            )
                            if alert_result:
                                print(f"[Alert] Downtime/Recovery alert: {alert_result.get('message', 'Success')}")
                    except Exception as alert_err:
                        print(f"[Alert] Error: {alert_err}")
                    
                    # System 2: AI predictive alerting (every 20 mins)
                    try:
                        if not low_network_for_check:
                            ai_alert_result = ai_alert_manager.check_and_alert(
                                str(api["_id"]),
                                api["url"]
                            )
                            if ai_alert_result:
                                print(f"[AI Alert] Prediction alert: {ai_alert_result.get('message', 'Success')}")
                    except Exception as ai_err:
                        print(f"[AI Alert] Error: {ai_err}")

                    new_status = "Low Network" if low_network_for_check else ("Up" if res.get("up") else ("Error" if res.get("error") else "Down"))
                    slo_metrics = compute_slo_metrics(str(api["_id"]))
                    sync_burn_rate_alert(str(api["_id"]), api["url"], slo_metrics, user_id=api_user_id)
                    monitored_apis.update_one(
                        {"_id": api["_id"]},
                        {"$set": {
                            "last_checked_at": ts,
                            "last_status": new_status,
                            "last_network_latency_ms": network_check.get("latency_ms"),
                            "last_network_download_mbps": network_check.get("download_mbps"),
                            "last_network_error": network_check.get("error"),
                            "last_root_cause_hint": log_entry.get("root_cause_hint"),
                            "last_root_cause_details": log_entry.get("root_cause_details"),
                            "slo_target_uptime_pct": slo_metrics.get("slo_target_uptime_pct"),
                            "p95_latency_24h": slo_metrics.get("p95_latency_24h"),
                            "error_budget_remaining_pct": slo_metrics.get("error_budget_remaining_pct"),
                            "burn_rate_1h": slo_metrics.get("burn_rate_1h"),
                            "burn_rate_6h": slo_metrics.get("burn_rate_6h"),
                            "burn_rate_alert_level": slo_metrics.get("burn_rate_alert_level"),
                            "burn_rate_alert_message": slo_metrics.get("burn_rate_alert_message"),
                        }}
                    )

                except Exception as e_inner:
                    print(f"Error checking API ID {api.get('_id')}: {e_inner}")

        except Exception as e:
            print("Monitor worker outer error:", e)

        time.sleep(sleep_seconds)

# --- ROUTING AND ENDPOINTS ---
def get_current_user():
    if db is None:
        return None
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        user = db.auth_users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    return user


def auth_user_payload(user):
    if not user:
        return None
    plan = normalize_subscription_plan(user.get("subscription_plan"))
    return {
        "id": str(user.get("_id")),
        "email": user.get("email"),
        "name": user.get("name"),
        "is_verified": bool(user.get("is_verified")),
        "subscription_plan": plan,
        "subscription_features": subscription_features(plan),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


@app.before_request
def enforce_authentication():
    path = request.path or "/"
    public_exact = {"/", "/ai_showcase", "/check_api", "/last_logs", "/monitored_urls", "/chart_data", "/auth", "/auth/login-page"}
    public_prefixes = ("/static/", "/static_advanced/", "/auth/", "/favicon.ico")
    if path in public_exact or any(path.startswith(prefix) for prefix in public_prefixes):
        return None

    advanced_protected = (
        path.startswith("/advanced_monitor")
        or path.startswith("/api/advanced/")
        or path.startswith("/api/github/")
        or path.startswith("/api/sync/")
        or path.startswith("/api/context/")
        or path.startswith("/api/alert-status/")
        or path.startswith("/api/incidents")
        or path.startswith("/api/worker-responses/")
        or path.startswith("/incident/")
        or path.startswith("/utils/translate")
        or (
            path.startswith("/api/ai/")
            and not path.startswith("/api/ai/training_runs")
        )
    )

    if advanced_protected and not session.get("user_id"):
        if path.startswith("/api/") or path.startswith("/notify/") or path.startswith("/incident/") or path.startswith("/utils/"):
            return jsonify({"error": "Authentication required"}), 401
        return redirect("/auth")

    if not AUTH_REQUIRED:
        return None

    if session.get("user_id"):
        return None

    if path.startswith("/api/") or path.startswith("/notify/") or path.startswith("/incident/"):
        return jsonify({"error": "Authentication required"}), 401
    return redirect("/auth")


@app.route("/auth")
@app.route("/auth/login-page")
def serve_auth_page():
    return send_from_directory(SIMPLE_STATIC_DIR, "auth.html")


@app.route("/auth/register", methods=["POST"])
def auth_register():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    data = request.json or {}
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    name = (data.get("name") or "").strip() or email.split("@")[0]
    requested_plan = normalize_subscription_plan(data.get("subscription_plan"))

    if not is_valid_email(email):
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing = db.auth_users.find_one({"email": email})
    if existing:
        if AUTH_REQUIRE_EMAIL_VERIFICATION and not existing.get("is_verified"):
            token = build_email_verification_token(email)
            sent, error = send_verification_email(email, token)
            db.auth_users.update_one(
                {"_id": existing["_id"]},
                {"$set": {"verification_sent_at": now_isoutc(), "email_delivery_error": error, "updated_at": now_isoutc()}},
            )
            payload = build_verification_delivery_payload(
                {
                    "success": True,
                    "message": "Email already registered but not verified. Verification has been re-issued.",
                },
                token,
                sent,
                error,
            )
            return jsonify(payload), 200
        return jsonify({"error": "Email already registered"}), 409

    now = now_isoutc()
    user_doc = {
        "email": email,
        "name": name,
        "password_hash": generate_password_hash(password),
        "is_verified": not AUTH_REQUIRE_EMAIL_VERIFICATION,
        "subscription_plan": requested_plan if requested_plan == "subscriber" else "free",
        "subscription_status": "active",
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    result = db.auth_users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    if AUTH_REQUIRE_EMAIL_VERIFICATION:
        token = build_email_verification_token(email)
        sent, error = send_verification_email(email, token)
        db.auth_users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"verification_sent_at": now_isoutc(), "email_delivery_error": error}},
        )
        payload = build_verification_delivery_payload(
            {
            "success": True,
            "message": "Registered. Verify your email before login.",
            },
            token,
            sent,
            error,
        )
        return jsonify(payload), 201

    session.permanent = True
    session["user_id"] = str(user_doc["_id"])
    return jsonify({"success": True, "user": auth_user_payload(user_doc)}), 201


@app.route("/auth/resend-verification", methods=["POST"])
def auth_resend_verification():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    data = request.json or {}
    email = normalize_email(data.get("email"))
    if not is_valid_email(email):
        return jsonify({"error": "Valid email is required"}), 400

    user = db.auth_users.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.get("is_verified"):
        return jsonify({"success": True, "message": "Email already verified"}), 200

    token = build_email_verification_token(email)
    sent, error = send_verification_email(email, token)
    db.auth_users.update_one(
        {"_id": user["_id"]},
        {"$set": {"verification_sent_at": now_isoutc(), "email_delivery_error": error}},
    )
    payload = build_verification_delivery_payload(
        {
            "success": True,
            "message": "Verification email sent" if sent else "Verification link generated for local use",
        },
        token,
        sent,
        error,
    )
    return jsonify(payload), 200


@app.route("/auth/verify-email", methods=["GET"])
def auth_verify_email():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "Verification token is required"}), 400

    try:
        email = read_email_verification_token(token)
    except SignatureExpired:
        return jsonify({"error": "Verification token expired"}), 400
    except BadSignature:
        return jsonify({"error": "Invalid verification token"}), 400

    update = db.auth_users.update_one(
        {"email": email},
        {
            "$set": {
                "is_verified": True,
                "verified_at": now_isoutc(),
                "updated_at": now_isoutc(),
            }
        },
    )
    if update.matched_count == 0:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"success": True, "message": "Email verified successfully"})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    data = request.json or {}
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = db.auth_users.find_one({"email": email})
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Invalid email or password"}), 401

    if AUTH_REQUIRE_EMAIL_VERIFICATION and not user.get("is_verified"):
        token = build_email_verification_token(email)
        sent, error = send_verification_email(email, token)
        db.auth_users.update_one(
            {"_id": user["_id"]},
            {"$set": {"verification_sent_at": now_isoutc(), "email_delivery_error": error, "updated_at": now_isoutc()}},
        )
        payload = build_verification_delivery_payload(
            {
                "error": "Email is not verified",
                "message": "Verification email sent. Please verify and login again." if sent else "Email is not verified. Use verification link below for local setup.",
            },
            token,
            sent,
            error,
        )
        return jsonify(payload), 403

    session.permanent = True
    session["user_id"] = str(user["_id"])
    session["user_email"] = user.get("email")
    db.auth_users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now_isoutc()}})
    user["last_login_at"] = now_isoutc()
    return jsonify({"success": True, "user": auth_user_payload(user)})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": auth_user_payload(user)})


@app.route("/auth/subscription", methods=["GET"])
@require_logged_in_api
def auth_get_subscription():
    user = get_current_user()
    plan = normalize_subscription_plan(user.get("subscription_plan"))
    return jsonify({
        "success": True,
        "subscription": {
            "plan": plan,
            "status": user.get("subscription_status", "active"),
            "features": subscription_features(plan),
        }
    })


@app.route("/auth/subscription", methods=["POST"])
@require_logged_in_api
def auth_set_subscription():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    user = get_current_user()
    data = request.json or {}
    plan = normalize_subscription_plan(data.get("plan"))
    db.auth_users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "subscription_plan": plan,
                "subscription_status": "active",
                "subscription_updated_at": now_isoutc(),
            }
        }
    )
    return jsonify({
        "success": True,
        "subscription": {
            "plan": plan,
            "status": "active",
            "features": subscription_features(plan),
        }
    })


@app.route("/api/subscription/capacity", methods=["GET"])
@require_logged_in_api
def estimate_subscription_capacity():
    rps = request.args.get("rps", type=float, default=0.0)
    interval_seconds = request.args.get("interval_seconds", type=float, default=0.0)
    if rps <= 0 or interval_seconds <= 0:
        return jsonify({"error": "rps and interval_seconds must be greater than 0"}), 400
    max_apis = int(rps * interval_seconds)
    return jsonify({
        "rps": rps,
        "interval_seconds": interval_seconds,
        "max_apis_estimate": max_apis,
        "formula": "max_apis = rps * interval_seconds",
    })


@app.route("/")
def serve_index(): 
    return send_from_directory(SIMPLE_STATIC_DIR, "index.html")

@app.route("/static/<path:filename>")
def serve_static(filename): 
    return send_from_directory(SIMPLE_STATIC_DIR, filename)

@app.route("/advanced_monitor")
def serve_advanced_monitor(): 
    return send_from_directory(ADVANCED_STATIC_DIR, "monitor.html")

@app.route("/ai_showcase")
def serve_ai_showcase():
    """Serve the AI capabilities showcase page"""
    return send_from_directory(ADVANCED_STATIC_DIR, "ai_showcase.html")

@app.route('/advanced_monitor/<path:text>', methods=['GET'])
def serve_advanced_proxy(text): 
    return send_from_directory(ADVANCED_STATIC_DIR, "monitor.html")

@app.route("/static_advanced/<path:filename>")
def serve_static_advanced(filename): 
    return send_from_directory(ADVANCED_STATIC_DIR, filename)

@app.route("/check_api", methods=["POST"])
def check_api():
    data = request.json or {}
    api_url = data.get("api_url") or data.get("url")
    if not api_url: 
        return jsonify({"error": "API URL is required"}), 400
    if not is_valid_url(api_url): 
        return jsonify({"error": "Invalid URL"}), 400
    
    h_name = data.get("header_name")
    h_val = data.get("header_value")
    headers = {h_name: h_val} if h_name and h_val else {}
    required_body_substring = data.get("required_body_substring")
    network_check = perform_network_speed_check(timeout=NETWORK_TEST_TIMEOUT_SECONDS)

    try:
        res = perform_latency_check(
            api_url,
            headers=headers,
            required_body_substring=required_body_substring
        )
    except Exception as e:
        error_payload = {
            "api_url": api_url,
            "header_name": h_name or "",
            "header_value": h_val or "",
            "error": f"Unexpected error during check: {e}",
            "up": False
        }
        return jsonify(error_payload), 500

    network_is_up = bool(network_check.get("network_up") or not network_check.get("error"))
    if not network_is_up and not res.get("up"):
        res["error"] = f"Low network: {network_check.get('error') or res.get('error') or 'connectivity issue'}"
        res["url_type"] = "Network"
        res["low_network"] = True
    else:
        res["low_network"] = False

    res.update({
        "api_url": api_url,
        "header_name": h_name or "",
        "header_value": h_val or "",
        "network_check": network_check
    })

    if not bool(res.get("up")):
        root_hint = classify_root_cause({
            "status_code": res.get("status_code"),
            "error_message": res.get("error"),
            "is_up": res.get("up"),
            "dns_latency_ms": res.get("dns_latency_ms"),
            "tls_latency_ms": res.get("tls_latency_ms"),
            "check_skipped": bool(res.get("low_network")),
            "skip_reason": "network_unavailable" if bool(res.get("low_network")) else None,
            "network_is_up": network_is_up,
        })
        res["root_cause_hint"] = root_hint
        res["root_cause_details"] = ROOT_CAUSE_DESCRIPTIONS.get(root_hint, ROOT_CAUSE_DESCRIPTIONS["unknown"])
    else:
        res["root_cause_hint"] = None
        res["root_cause_details"] = None
    
    # Save to MongoDB simple_logs collection
    if db is not None:
        simple_logs = db.simple_logs
        body_compressed = compress_data(res.get("body_snippet")) if res.get("body_snippet") else None
        log_doc = res.copy()
        log_doc["body_snippet_compressed"] = body_compressed
        log_doc.pop("body_snippet", None)
        simple_logs.insert_one(log_doc)
    
    return jsonify(res)

@app.route("/last_logs", methods=["GET"])
def last_logs():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    
    if db is None:
        return jsonify({"logs": [], "total_pages": 0, "current_page": page})
    
    simple_logs = db.simple_logs
    total_items = simple_logs.count_documents({})
    skip = (page - 1) * per_page
    
    logs = list(simple_logs.find().sort("timestamp", DESCENDING).skip(skip).limit(per_page))
    
    # Decompress and serialize
    for log in logs:
        log = serialize_objectid(log)
        if log.get("body_snippet_compressed"):
            log["body_snippet"] = decompress_data(log["body_snippet_compressed"])
            del log["body_snippet_compressed"]
    
    return jsonify({
        "logs": logs,
        "total_pages": math.ceil(total_items / per_page) if per_page else 0,
        "current_page": page
    })

@app.route("/monitored_urls")
def monitored_urls():
    if db is None:
        return jsonify({"urls_data": []})
    
    simple_logs = db.simple_logs
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$api_url",
            "latest": {"$first": "$$ROOT"}
        }},
        {"$replaceRoot": {"newRoot": "$latest"}}
    ]
    
    latest_logs = list(simple_logs.aggregate(pipeline))
    for log in latest_logs:
        serialize_objectid(log)
    
    return jsonify({"urls_data": latest_logs})

@app.route("/chart_data", methods=["GET"])
def chart_data():
    api_url = request.args.get("url")
    
    if db is None:
        return jsonify({"labels": [], "data": []})
    
    simple_logs = db.simple_logs
    logs = list(simple_logs.find({"api_url": api_url}).sort("timestamp", ASCENDING).limit(50))
    
    return jsonify({
        "labels": [log.get("timestamp") for log in logs],
        "data": [log.get("total_latency_ms") for log in logs]
    })

# --- ADVANCED MONITOR API ---
@app.route("/api/advanced/monitors")
@require_logged_in_api
def get_monitors():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        user_id = get_current_user_id()
        monitored_apis = db.monitored_apis
        monitoring_logs = db.monitoring_logs
        
        monitors = list(monitored_apis.find({"user_id": user_id}).sort([("category", ASCENDING), ("url", ASCENDING)]))
        
        for monitor in monitors:
            monitor = serialize_objectid(monitor)
            api_id = monitor["id"]

            slo_metrics = compute_slo_metrics(api_id)
            monitor["avg_latency_24h"] = slo_metrics.get("avg_latency_24h", 0.0)
            monitor["uptime_pct_24h"] = slo_metrics.get("uptime_pct_24h", 100.0)
            monitor["p95_latency_24h"] = slo_metrics.get("p95_latency_24h", 0.0)
            monitor["slo_target_uptime_pct"] = slo_metrics.get("slo_target_uptime_pct", SLO_TARGET_UPTIME_PCT)
            monitor["error_budget_remaining_pct"] = slo_metrics.get("error_budget_remaining_pct", 100.0)
            monitor["error_budget_consumed_pct"] = slo_metrics.get("error_budget_consumed_pct", 0.0)
            monitor["burn_rate_1h"] = slo_metrics.get("burn_rate_1h", 0.0)
            monitor["burn_rate_6h"] = slo_metrics.get("burn_rate_6h", 0.0)
            monitor["burn_rate_alert_level"] = slo_metrics.get("burn_rate_alert_level", "none")
            monitor["burn_rate_alert_message"] = slo_metrics.get("burn_rate_alert_message", "No burn-rate alert")

            # Recent checks
            recent = list(monitoring_logs.find({
                "api_id": api_id,
                "user_id": user_id,
                "check_skipped": {"$ne": True}
            }).sort("timestamp", DESCENDING).limit(15))
            monitor['recent_checks'] = [
                {'is_up': r['is_up'], 'timestamp': r['timestamp']} 
                for r in reversed(recent)
            ]

            latest_failed = monitoring_logs.find_one(
                {"api_id": api_id, "user_id": user_id, "is_up": False},
                sort=[("timestamp", DESCENDING)]
            )
            monitor["last_root_cause_hint"] = (latest_failed or {}).get("root_cause_hint")
            monitor["last_root_cause_details"] = (latest_failed or {}).get("root_cause_details")

        return jsonify(monitors)

    except Exception as e:
        print(f"[DB ERROR] Failed to fetch dashboard monitors: {e}")
        return jsonify({"error": "Failed to retrieve monitor data from server."}), 500

@app.route("/api/advanced/add_monitor", methods=["POST"])
@require_logged_in_api
def add_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    user = get_current_user()
    user_id = str(user["_id"])
    plan = normalize_subscription_plan(user.get("subscription_plan"))
    data = request.json or {}
    url = data.get("url") or data.get("api_url")
    
    if not url or not is_valid_url(url):
        return jsonify({"error": "Valid 'url' is required"}), 400
        
    freq = data.get("check_frequency_minutes", 1)
    try:
        freq = float(freq)
        if freq <= 0:
            freq = 1.0
    except (ValueError, TypeError):
        freq = 1.0

    if is_premium_frequency(freq) and not is_subscriber(plan):
        return jsonify({
            "error": "30s, 10s, 5s, and 1s intervals are subscriber-only",
            "subscription": subscription_features(plan),
        }), 403
    
    monitored_apis = db.monitored_apis

    if not is_subscriber(plan):
        monitor_count = monitored_apis.count_documents({"user_id": user_id})
        if monitor_count >= FREE_MAX_MONITORS:
            return jsonify({
                "error": f"Free plan limit reached ({FREE_MAX_MONITORS} monitors). Upgrade for unlimited monitors.",
                "subscription": subscription_features(plan),
            }), 403
    
    # Check if URL already exists
    if monitored_apis.find_one({"url": url, "user_id": user_id}):
        return jsonify({"error": "This URL is already monitored."}), 409
    
    monitor_doc = {
        "user_id": user_id,
        "url": url,
        "category": data.get("category"),
        "header_name": data.get("header_name"),
        "header_value": data.get("header_value"),
        "check_frequency_minutes": freq,
        "notification_email": data.get("notification_email"),
        "is_active": True,
        "last_checked_at": None,
        "last_status": "Pending"
    }
    
    monitored_apis.insert_one(monitor_doc)
    return jsonify({
        "success": True,
        "message": "Monitor added successfully.",
        "subscription": subscription_features(plan),
    })

@app.route("/api/advanced/update_monitor", methods=["POST"])
@require_logged_in_api
def update_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    user = get_current_user()
    user_id = str(user["_id"])
    plan = normalize_subscription_plan(user.get("subscription_plan"))
    data = request.json or {}
    if "id" not in data:
        return jsonify({"error": "'id' is required"}), 400

    url = data.get("url") or data.get("api_url")
    if not url or not is_valid_url(url):
        return jsonify({"error": "A valid 'url' is required for updating."}), 400

    freq = data.get("check_frequency_minutes", 1)
    try:
        freq = float(freq)
        if freq <= 0:
            freq = 1.0
    except (ValueError, TypeError):
        freq = 1.0

    if is_premium_frequency(freq) and not is_subscriber(plan):
        return jsonify({
            "error": "30s, 10s, 5s, and 1s intervals are subscriber-only",
            "subscription": subscription_features(plan),
        }), 403
    
    monitored_apis = db.monitored_apis
    result = monitored_apis.update_one(
        {"_id": ObjectId(data["id"]), "user_id": user_id},
        {"$set": {
            "url": url,
            "category": data.get("category"),
            "header_name": data.get("header_name"),
            "header_value": data.get("header_value"),
            "check_frequency_minutes": freq,
            "notification_email": data.get("notification_email")
        }}
    )
    if result.matched_count == 0:
        return jsonify({"error": "Monitor not found or access denied"}), 404
    
    return jsonify({"success": True, "message": "Monitor updated successfully."})

@app.route("/api/advanced/delete_monitor", methods=["POST"])
@require_logged_in_api
def delete_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    if "id" not in data: 
        return jsonify({"error": "'id' is required"}), 400
    user_id = get_current_user_id()
    
    monitored_apis = db.monitored_apis
    monitoring_logs = db.monitoring_logs
    
    api_id = data["id"]
    deleted = monitored_apis.delete_one({"_id": ObjectId(api_id), "user_id": user_id})
    if deleted.deleted_count == 0:
        return jsonify({"error": "Monitor not found or access denied"}), 404
    monitoring_logs.delete_many({"api_id": api_id, "user_id": user_id})
    
    return jsonify({"success": True})

@app.route("/api/advanced/history")
@require_logged_in_api
def get_history():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    api_id = request.args.get("id")
    if not api_id: 
        return jsonify({"error": "'id' (api_id) is required"}), 400
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error
    
    page = request.args.get("page", 1, type=int)
    per_page = 15
    
    monitoring_logs = db.monitoring_logs
    total_items = monitoring_logs.count_documents({"api_id": api_id, "user_id": user_id})
    skip = (page - 1) * per_page
    
    logs = list(monitoring_logs.find({"api_id": api_id, "user_id": user_id}).sort("timestamp", DESCENDING).skip(skip).limit(per_page))
    
    for log in logs:
        serialize_objectid(log)
        if log.get("body_snippet_compressed"):
            log["body_snippet"] = decompress_data(log["body_snippet_compressed"])
            del log["body_snippet_compressed"]
    
    return jsonify({
        "history": logs,
        "total_pages": math.ceil(total_items / per_page) if per_page else 0,
        "current_page": page
    })

@app.route("/api/advanced/last_checks/<api_id>")
@require_logged_in_api
def get_last_checks(api_id):
    if db is None:
        return jsonify([])
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error
    
    monitoring_logs = db.monitoring_logs
    logs = list(monitoring_logs.find({
        "api_id": api_id,
        "user_id": user_id,
        "check_skipped": {"$ne": True}
    }).sort("timestamp", DESCENDING).limit(15))
    
    result = [{"is_up": bool(log.get("is_up"))} for log in logs]
    return jsonify(result)

@app.route("/api/advanced/log_details/<log_id>")
@require_logged_in_api
def get_log_details(log_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    monitoring_logs = db.monitoring_logs
    log = monitoring_logs.find_one({"_id": ObjectId(log_id), "user_id": get_current_user_id()})
    
    if not log: 
        return jsonify({"error": "Log not found"}), 404
    
    serialize_objectid(log)
    if log.get("body_snippet_compressed"):
        log["body_snippet"] = decompress_data(log["body_snippet_compressed"])
        del log["body_snippet_compressed"]
    
    if "is_up" in log: 
        log["is_up"] = bool(log["is_up"])
    
    return jsonify(log)

@app.route("/api/advanced/uptime_history/<api_id>")
@require_logged_in_api
def get_uptime_history(api_id):
    """Calculates daily uptime percentage for the last 90 days."""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    monitoring_logs = db.monitoring_logs
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error
    ninety_days_ago = (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
    
    try:
        pipeline = [
            {"$match": {
                "api_id": api_id,
                "user_id": user_id,
                "timestamp": {"$gte": ninety_days_ago},
                "check_skipped": {"$ne": True}
            }},
            {"$group": {
                "_id": {"$substr": ["$timestamp", 0, 10]},
                "total_checks": {"$sum": 1},
                "up_checks": {"$sum": {"$cond": ["$is_up", 1, 0]}}
            }},
            {"$project": {
                "log_date": "$_id",
                "uptime_pct": {"$multiply": [{"$divide": ["$up_checks", "$total_checks"]}, 100]}
            }},
            {"$sort": {"log_date": 1}}
        ]
        
        daily_stats = list(monitoring_logs.aggregate(pipeline))
        stats_dict = {s['log_date']: round(s['uptime_pct'], 2) for s in daily_stats}
        
        # Fill in gaps
        result = []
        for i in range(90):
            day = datetime.utcnow().date() - timedelta(days=i)
            day_str = day.isoformat()
            uptime = stats_dict.get(day_str, None)
            result.append({'date': day_str, 'uptime_pct': uptime})
            
        return jsonify(list(reversed(result)))

    except Exception as e:
        print(f"[DB ERROR] Failed to fetch uptime history for api_id {api_id}: {e}")
        return jsonify({"error": "Failed to retrieve uptime history."}), 500


@app.route("/api/advanced/slo/<api_id>")
@require_logged_in_api
def get_slo_metrics(api_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        user_id = get_current_user_id()
        api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
        if api_error:
            return api_error
        metrics = compute_slo_metrics(api_id)
        metrics["api_id"] = api_id
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/advanced/slo_summary")
@require_logged_in_api
def get_slo_summary():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        user_id = get_current_user_id()
        monitors = list(db.monitored_apis.find({"is_active": True, "user_id": user_id}, {"url": 1}))
        summary = {
            "total_monitors": len(monitors),
            "critical_burn_rate": 0,
            "warning_burn_rate": 0,
            "avg_uptime_pct_24h": 100.0,
            "avg_error_budget_remaining_pct": 100.0,
        }
        if not monitors:
            return jsonify(summary)

        uptime_values = []
        budget_values = []
        for monitor in monitors:
            api_id = str(monitor["_id"])
            metrics = compute_slo_metrics(api_id)
            uptime_values.append(metrics.get("uptime_pct_24h", 100.0))
            budget_values.append(metrics.get("error_budget_remaining_pct", 100.0))
            level = metrics.get("burn_rate_alert_level")
            if level == "critical":
                summary["critical_burn_rate"] += 1
            elif level == "warning":
                summary["warning_burn_rate"] += 1

        summary["avg_uptime_pct_24h"] = round(sum(uptime_values) / len(uptime_values), 2) if uptime_values else 100.0
        summary["avg_error_budget_remaining_pct"] = round(sum(budget_values) / len(budget_values), 2) if budget_values else 100.0
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- DEVELOPER DATA INTEGRATION APIs ---

@app.route("/api/sync/github", methods=["POST"])
@require_logged_in_api
def sync_github():
    """Sync commits and PRs from GitHub using stored settings"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    repo_owner = data.get("repo_owner")
    repo_name = data.get("repo_name")
    since_days = data.get("since_days", 7)
    user_id = get_current_user_id()
    
    # If not provided in request, get from stored settings
    if not repo_owner or not repo_name:
        settings = db.github_settings.find_one({"user_id": user_id})
        if settings:
            repo_owner = settings.get("repo_owner")
            repo_name = settings.get("repo_name")
    
    if not repo_owner or not repo_name:
        return jsonify({"error": "repo_owner and repo_name required. Please save settings first."}), 400
    
    # Try to get token from stored settings first, then fall back to env variable
    github_token = None
    settings = db.github_settings.find_one({"user_id": user_id})
    if settings and "github_token" in settings:
        github_token = settings["github_token"]
    
    if not github_token:
        github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        return jsonify({"error": "GitHub token not configured. Please add token in settings or environment."}), 500
    
    try:
        github = GitHubIntegration(github_token, db)
        
        # Fetch commits
        commit_result = github.fetch_commits(repo_owner, repo_name, since_days)
        
        # Fetch pull requests
        pr_result = github.fetch_pull_requests(repo_owner, repo_name)
        
        return jsonify({
            "success": True,
            "commits": commit_result,
            "pull_requests": pr_result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sync/issues", methods=["POST"])
@require_logged_in_api
def sync_issues():
    """Sync issues from GitHub using stored settings"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    repo_owner = data.get("repo_owner")
    repo_name = data.get("repo_name")
    user_id = get_current_user_id()
    
    # If not provided in request, get from stored settings
    if not repo_owner or not repo_name:
        settings = db.github_settings.find_one({"user_id": user_id})
        if settings:
            repo_owner = settings.get("repo_owner")
            repo_name = settings.get("repo_name")
    
    if not repo_owner or not repo_name:
        return jsonify({"error": "repo_owner and repo_name required. Please save settings first."}), 400
    
    # Try to get token from stored settings first, then fall back to env variable
    github_token = None
    settings = db.github_settings.find_one({"user_id": user_id})
    if settings and "github_token" in settings:
        github_token = settings["github_token"]
    
    if not github_token:
        github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        return jsonify({"error": "GitHub token not configured. Please add token in settings or environment."}), 500
    
    try:
        issue_integration = IssueIntegration(github_token, db)
        result = issue_integration.fetch_github_issues(repo_owner, repo_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alert-status/<api_id>", methods=["GET"])
@require_logged_in_api
def get_alert_status(api_id):
    """Get current alert status for an API (downtime alerts + AI predictions)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        user_id = get_current_user_id()
        api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
        if api_error:
            return api_error
        result = {
            "downtime_alert": None,
            "ai_prediction": None,
            "burn_rate_alert": None
        }
        
        # Check for open downtime alert
        downtime_alert = db.alert_history.find_one({
            "api_id": api_id,
            "user_id": user_id,
            "status": "open",
            "alert_type": "downtime"
        })
        
        if downtime_alert:
            result["downtime_alert"] = {
                "created_at": downtime_alert.get("created_at"),
                "github_issue_number": downtime_alert.get("github_issue_number"),
                "github_issue_url": downtime_alert.get("github_issue_url"),
                "reason": downtime_alert.get("reason"),
                "incident_id": downtime_alert.get("incident_id"),
                "root_cause_hint": downtime_alert.get("root_cause_hint"),
            }
        
        # Check for AI prediction alert
        ai_alert = db.alert_history.find_one({
            "api_id": api_id,
            "user_id": user_id,
            "status": "open",
            "alert_type": "ai_prediction"
        })
        
        if ai_alert:
            result["ai_prediction"] = {
                "failure_probability": ai_alert.get("failure_probability", 0),
                "created_at": ai_alert.get("created_at"),
                "github_issue_number": ai_alert.get("github_issue_number"),
                "github_issue_url": ai_alert.get("github_issue_url"),
                "last_check": ai_alert.get("updated_at") or ai_alert.get("created_at")
            }
            ack = ai_alert.get("worker_acknowledgment")
            if ack:
                result["ai_prediction"]["worker_acknowledgment"] = ack

        burn_rate_alert = db.alert_history.find_one({
            "api_id": api_id,
            "user_id": user_id,
            "status": "open",
            "alert_type": "burn_rate"
        })
        if burn_rate_alert:
            result["burn_rate_alert"] = {
                "severity": burn_rate_alert.get("severity"),
                "reason": burn_rate_alert.get("reason"),
                "burn_rate_1h": burn_rate_alert.get("burn_rate_1h"),
                "burn_rate_6h": burn_rate_alert.get("burn_rate_6h"),
                "error_budget_remaining_pct": burn_rate_alert.get("error_budget_remaining_pct"),
                "created_at": burn_rate_alert.get("created_at"),
                "updated_at": burn_rate_alert.get("updated_at"),
            }

        incident_status = db.alert_incidents.find_one(
            {"api_id": api_id, "user_id": user_id, "status": "open"},
            sort=[("created_at", DESCENDING)]
        )
        if incident_status:
            result["incident_status"] = {
                "incident_id": incident_status.get("incident_id"),
                "status": incident_status.get("status"),
                "created_at": incident_status.get("created_at"),
                "last_seen_at": incident_status.get("last_seen_at"),
                "failure_events": incident_status.get("failure_events", 0),
                "suppressed_alerts": incident_status.get("suppressed_alerts", 0),
                "root_cause_hint": incident_status.get("root_cause_hint"),
                "latest_reason": incident_status.get("latest_reason"),
            }
        else:
            result["incident_status"] = None

        result["worker_responses"] = fetch_worker_responses(api_id, limit=5, user_id=user_id)
        # Don't try to predict on-demand, just show if alert exists
        # AI predictions happen in background every 20 minutes

        return jsonify(result)
        
    except Exception as e:
        print(f"[Alert Status] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/worker-responses/<api_id>")
@require_logged_in_api
def get_worker_responses(api_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    limit = request.args.get("limit", 20, type=int)
    limit = min(max(limit, 1), 100)
    try:
        user_id = get_current_user_id()
        api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
        if api_error:
            return api_error
        responses = fetch_worker_responses(api_id, limit=limit, user_id=user_id)
        return jsonify(responses)
    except Exception as e:
        print(f"[Worker Responses] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/github/create-downtime-alert", methods=["POST"])
@require_logged_in_api
def create_downtime_alert():
    """Create a GitHub issue for API downtime"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    api_id = data.get("api_id")
    user_id = get_current_user_id()
    
    if not api_id:
        return jsonify({"error": "api_id required"}), 400
    
    # Get GitHub settings
    settings = db.github_settings.find_one({"user_id": user_id})
    if not settings:
        return jsonify({"error": "GitHub settings not configured"}), 400
    
    repo_owner = settings.get("repo_owner")
    repo_name = settings.get("repo_name")
    github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        return jsonify({"error": "GitHub token not configured"}), 500
    
    try:
        # Get API details
        api = db.monitored_apis.find_one({"_id": ObjectId(api_id), "user_id": user_id})
        if not api:
            return jsonify({"error": "API not found"}), 404
        
        # Get latest downtime log
        latest_log = db.monitoring_logs.find_one(
            {"api_id": api_id, "user_id": user_id, "is_up": False, "check_skipped": {"$ne": True}},
            sort=[("timestamp", -1)]
        )
        
        if not latest_log:
            return jsonify({"error": "No downtime detected"}), 404
        
        # Prepare downtime data
        downtime_data = {
            "timestamp": latest_log.get("timestamp"),
            "status_code": latest_log.get("status_code"),
            "error_message": latest_log.get("error_message"),
            "total_latency_ms": latest_log.get("total_latency_ms"),
            "dns_latency_ms": latest_log.get("dns_latency_ms"),
            "tcp_latency_ms": latest_log.get("tcp_latency_ms"),
            "tls_latency_ms": latest_log.get("tls_latency_ms"),
            "server_processing_latency_ms": latest_log.get("server_processing_latency_ms"),
            "url_type": latest_log.get("url_type"),
            "root_cause_hint": latest_log.get("root_cause_hint"),
            "root_cause_details": latest_log.get("root_cause_details"),
            "incident_id": f"INC-{int(time.time())}",
            "history_summary": f"API has been down since {latest_log.get('timestamp')}"
        }
        
        # Create GitHub issue
        issue_integration = IssueIntegration(github_token, db)
        result = issue_integration.create_downtime_alert(
            repo_owner, repo_name, api["url"], downtime_data
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/commits", methods=["GET"])
@require_logged_in_api
def get_commits():
    """Get recent commits"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    hours = request.args.get("hours", 24, type=int)
    github_token = os.getenv("GITHUB_TOKEN", "")
    
    github = GitHubIntegration(github_token, db)
    commits = github.get_recent_commits(hours)
    
    for commit in commits:
        serialize_objectid(commit)
    
    return jsonify(commits)

@app.route("/api/issues", methods=["GET"])
@require_logged_in_api
def get_issues():
    """Get issues"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    state = request.args.get("state", "all")
    
    if state == "open":
        issues = list(db.issues.find({"state": "open"}).sort("created_at", -1).limit(50))
    else:
        issues = list(db.issues.find().sort("created_at", -1).limit(50))
    
    for issue in issues:
        serialize_objectid(issue)
    
    return jsonify(issues)

@app.route("/api/logs", methods=["GET"])
@require_logged_in_api
def get_logs():
    """Get application logs"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    hours = request.args.get("hours", 24, type=int)
    level = request.args.get("level")
    
    logs = get_recent_logs(db, hours, level)
    
    for log in logs:
        serialize_objectid(log)
    
    return jsonify(logs)

@app.route("/api/incidents", methods=["POST"])
@require_logged_in_api
def create_incident():
    """Create a new incident report"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    user_id = get_current_user_id()
    
    incident_doc = {
        "incident_id": f"INC-{int(time.time())}",
        "title": data.get("title"),
        "summary": data.get("summary"),
        "severity": data.get("severity", "medium"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "duration_minutes": data.get("duration_minutes"),
        "affected_apis": data.get("affected_apis", []),
        "root_cause": data.get("root_cause"),
        "fix_applied": data.get("fix_applied"),
        "prevention_steps": data.get("prevention_steps"),
        "related_commits": data.get("related_commits", []),
        "related_issues": data.get("related_issues", []),
        "created_by": data.get("created_by"),
        "user_id": user_id,
        "created_at": now_isoutc()
    }
    
    db.incident_reports.insert_one(incident_doc)
    serialize_objectid(incident_doc)
    
    return jsonify({"success": True, "incident": incident_doc})

@app.route("/api/incidents", methods=["GET"])
@require_logged_in_api
def get_incidents():
    """Get all incident reports"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    incidents = list(db.incident_reports.find({"user_id": get_current_user_id()}).sort("created_at", -1).limit(50))
    
    for incident in incidents:
        serialize_objectid(incident)
    
    return jsonify(incidents)

# --- GITHUB SETTINGS APIs ---

@app.route("/api/github/settings", methods=["POST"])
@require_logged_in_api
def save_github_settings():
    """Save or update GitHub repository settings including token"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    repo_owner = data.get("repo_owner", "").strip()
    repo_name = data.get("repo_name", "").strip()
    github_token = data.get("github_token", "").strip()
    
    if not repo_owner or not repo_name:
        return jsonify({"error": "repo_owner and repo_name are required"}), 400
    
    try:
        user_id = get_current_user_id()
        settings_doc = {
            "user_id": user_id,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "updated_at": now_isoutc()
        }
        
        # Only update token if provided (for security, don't overwrite with empty)
        if github_token:
            settings_doc["github_token"] = github_token
        
        # Upsert: update if exists, insert if not
        db.github_settings.update_one(
            {"user_id": user_id},
            {"$set": settings_doc},
            upsert=True
        )
        
        return jsonify({
            "success": True,
            "message": "GitHub settings saved successfully",
            "settings": {
                "repo_owner": repo_owner,
                "repo_name": repo_name,
                "has_token": bool(github_token)
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/github/settings", methods=["GET"])
@require_logged_in_api
def get_github_settings():
    """Get saved GitHub repository settings (token masked for security)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        settings = db.github_settings.find_one({"user_id": get_current_user_id()})
        
        if settings:
            serialize_objectid(settings)
            # Mask token for security - only show if it exists
            if "github_token" in settings:
                settings["has_token"] = True
                settings["github_token"] = "****" + settings["github_token"][-4:] if len(settings["github_token"]) > 4 else "****"
            else:
                settings["has_token"] = False
            return jsonify(settings)
        else:
            return jsonify({"repo_owner": "", "repo_name": "", "has_token": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/github/export-dataset", methods=["POST"])
@require_logged_in_api
def export_monitoring_dataset():
    """Export monitoring data as CSV and push to GitHub repository"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        user_id = get_current_user_id()
        # Get GitHub settings
        settings = db.github_settings.find_one({"user_id": user_id})
        if not settings:
            return jsonify({"error": "GitHub settings not configured. Please save settings first."}), 400
        
        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
        if not github_token:
            return jsonify({"error": "GitHub token not configured in settings or environment"}), 500
        
        # Get monitoring data from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        logs = list(db.monitoring_logs.find({
            "timestamp": {"$gte": thirty_days_ago.isoformat()},
            "user_id": user_id,
        }).sort("timestamp", -1).limit(10000))
        
        if not logs:
            return jsonify({"error": "No monitoring data found"}), 404
        
        # Convert to CSV format
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "timestamp", "api_id", "url", "status_code", "is_up", 
            "total_latency_ms", "dns_latency_ms", "tcp_latency_ms", 
            "tls_latency_ms", "server_processing_latency_ms", 
            "content_download_latency_ms", "error_message", "url_type"
        ])
        
        # Write data rows
        for log in logs:
            writer.writerow([
                log.get("timestamp", ""),
                log.get("api_id", ""),
                log.get("url", ""),
                log.get("status_code", ""),
                log.get("is_up", False),
                log.get("total_latency_ms", 0),
                log.get("dns_latency_ms", 0),
                log.get("tcp_latency_ms", 0),
                log.get("tls_latency_ms", 0),
                log.get("server_processing_latency_ms", 0),
                log.get("content_download_latency_ms", 0),
                log.get("error_message", ""),
                log.get("url_type", "")
            ])
        
        csv_content = output.getvalue()
        
        # Push to GitHub using GitHub API
        import requests
        import base64
        
        file_path = "datasets/monitoring_data.csv"
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists to get SHA
        existing_file = requests.get(api_url, headers=headers)
        sha = None
        if existing_file.status_code == 200:
            sha = existing_file.json().get("sha")
        
        # Prepare payload
        payload = {
            "message": f"Update monitoring dataset - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": base64.b64encode(csv_content.encode()).decode(),
            "branch": "main"
        }
        
        if sha:
            payload["sha"] = sha
        
        # Push to GitHub
        response = requests.put(api_url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            return jsonify({
                "success": True,
                "message": "Dataset exported to GitHub successfully",
                "file_url": response.json().get("content", {}).get("html_url"),
                "records_exported": len(logs)
            })
        else:
            return jsonify({
                "error": f"GitHub API error: {response.status_code}",
                "details": response.json()
            }), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/context/<api_id>")
@require_logged_in_api
def get_developer_context(api_id):
    """Get all developer context for an API"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        user_id = get_current_user_id()
        api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
        if api_error:
            return api_error
        # Get latest monitoring log
        latest_log = db.monitoring_logs.find_one(
            {"api_id": api_id, "user_id": user_id},
            sort=[("timestamp", -1)]
        )
        
        if not latest_log:
            return jsonify({"error": "No logs found"}), 404
        
        # Get or create correlation
        correlation_engine = CorrelationEngine(db)
        correlation = db.data_correlations.find_one({
            "monitoring_log_id": str(latest_log["_id"])
        })
        
        if not correlation:
            # Create correlation
            correlation = correlation_engine.correlate_monitoring_event(latest_log)
        
        if not correlation:
            return jsonify({"commits": [], "issues": [], "logs": [], "incidents": []})
        
        # Fetch related data
        commits = list(db.git_commits.find({
            "commit_id": {"$in": correlation.get("commit_ids", [])}
        }))
        
        issues = list(db.issues.find({
            "issue_id": {"$in": correlation.get("issue_ids", [])}
        }))
        
        logs = []
        for log_id in correlation.get("log_ids", []):
            try:
                log = db.application_logs.find_one({"_id": ObjectId(log_id)})
                if log:
                    logs.append(log)
            except:
                pass
        
        incidents = list(db.incident_reports.find({
            "incident_id": {"$in": correlation.get("incident_ids", [])}
        }))
        
        # Serialize all
        for commit in commits:
            serialize_objectid(commit)
        for issue in issues:
            serialize_objectid(issue)
        for log in logs:
            serialize_objectid(log)
        for incident in incidents:
            serialize_objectid(incident)
        
        return jsonify({
            "commits": commits,
            "issues": issues,
            "logs": logs,
            "incidents": incidents,
            "correlation_score": correlation.get("correlation_score", 0)
        })
        
    except Exception as e:
        print(f"[Context API] Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- AI/ML PREDICTION APIs ---

@app.route("/api/ai/train", methods=["POST"])
@require_logged_in_api
def train_ai_model():
    """
    Train AI model by calling separate training service
    Always uses FULL training (50 epochs) since it runs on separate port
    """
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    api_id = data.get("api_id")
    force_retrain = data.get("force_retrain", False)
    
    if not api_id:
        return jsonify({"error": "api_id required"}), 400
    user_id = get_current_user_id()
    api_doc, api_error = ensure_api_access_or_error(api_id, user_id)
    if api_error:
        return api_error
    
    try:
        # Always use FULL training (runs on separate port, won't block)
        endpoint = f"{AI_TRAINING_SERVICE_URL}/train/full"
        print(f"[AI Train] FULL training requested for API {api_id}")
        
        # Call training service (non-blocking, runs on separate port)
        try:
            response = requests.post(
                endpoint,
                json={"api_id": api_id, "force_retrain": force_retrain},
                timeout=1  # Don't wait for response, just trigger
            )
        except requests.exceptions.Timeout:
            # Timeout is expected - training is running in background
            pass
        except requests.exceptions.ConnectionError:
            return jsonify({
                "error": "AI Training Service not available. Please start it on port 5001"
            }), 503
        
        # Update last_ai_training timestamp immediately
        from bson import ObjectId
        db.monitored_apis.update_one(
            {"_id": ObjectId(api_id), "user_id": user_id},
            {"$set": {"last_ai_training": datetime.utcnow()}}
        )
        
        return jsonify({
            "success": True,
            "message": "Full training started on separate service (Port 5001)",
            "mode": "full",
            "epochs": 50,
            "service_port": 5001
        })
        
    except Exception as e:
        print(f"[AI Train] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/predict/<api_id>")
@require_logged_in_api
def predict_failure(api_id):
    """Predict if API will fail in next hour"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        ai = AIPredictor(db)
        prediction = ai.predict_failure(api_id)
        return jsonify(prediction)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/anomalies/<api_id>")
@require_logged_in_api
def detect_anomalies(api_id):
    """Detect anomalies in API performance"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    hours = request.args.get("hours", 24, type=int)
    
    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        ai = AIPredictor(db)
        anomalies = ai.detect_anomalies(api_id, hours)
        return jsonify(anomalies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/insights/<api_id>")
@require_logged_in_api
def get_ai_insights(api_id):
    """Get AI-generated insights and recommendations.

    This endpoint now also stores a richer, LLM-style summary in MongoDB
    (ai_insights collection) while preserving the existing card-style
    insights array used by the frontend.
    """
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        ai = AIPredictor(db)

        # Core prediction used for narrative + metrics
        prediction = ai.predict_failure(api_id)

        # Existing card-style insights for the UI
        insights = ai.generate_insights(api_id) or []

        # Build an LLM-style natural language summary
        try:
            failure_prob = float(prediction.get("failure_probability") or 0.0)
        except (TypeError, ValueError):
            failure_prob = 0.0

        try:
            confidence = float(prediction.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        risk_score = int(prediction.get("risk_score") or round(failure_prob * 100))
        category = prediction.get("category") or "API"
        risk_level = (prediction.get("risk_level") or
                      ("high" if failure_prob >= 0.70 else
                       "medium" if failure_prob >= 0.40 else
                       "low"))
        model_name = prediction.get("model") or "LSTM + Autoencoder"
        last_trained = prediction.get("last_trained")
        model_accuracy = prediction.get("model_accuracy")
        model_auc = prediction.get("model_auc")
        risk_factors = prediction.get("risk_factors") or []

        # High-level narrative
        summary_parts = []
        summary_parts.append(
            f"The {category} is currently assessed as {risk_level.upper()} risk "
            f"with a risk score of {risk_score}/100 and estimated failure probability "
            f"around {failure_prob*100:.1f}% (confidence ~{confidence*100:.0f}%)."
        )

        if last_trained:
            summary_parts.append(
                f"The model {model_name} was last trained at {last_trained}."
            )
        else:
            summary_parts.append(
                f"The model {model_name} has limited training metadata available; "
                f"results should be interpreted with caution."
            )

        if isinstance(model_accuracy, (int, float)) or isinstance(model_auc, (int, float)):
            acc_txt = f"accuracy ~{model_accuracy*100:.1f}%" if isinstance(model_accuracy, (int, float)) else None
            auc_txt = f"AUC ~{model_auc:.3f}" if isinstance(model_auc, (int, float)) else None
            perf_bits = ", ".join(bit for bit in [acc_txt, auc_txt] if bit)
            if perf_bits:
                summary_parts.append(f"Training performance: {perf_bits}.")

        if risk_factors:
            summary_parts.append(
                "Key contributing factors include: " + "; ".join(risk_factors[:3]) + "."
            )
        elif prediction.get("reason"):
            summary_parts.append(prediction["reason"])

        summary_text = " ".join(summary_parts)

        # Recommended actions for operators
        actions = [
            "Review recent deployments and code changes touching this API.",
            "Monitor latency, error rate, and HTTP status trends closely.",
            "Inspect logs around recent anomalies for root-cause clues.",
        ]

        # Store structured insight in MongoDB (best-effort; ignore failures)
        try:
            insight_payload = {
                "summary": summary_text,
                "details": prediction.get("reason"),
                "risk_level": risk_level,
                "confidence": confidence,
                "risk_score": risk_score,
                "training_session_id": None,
                "model_version": prediction.get("model_version"),
                "actions": actions,
                "metrics": {
                    "failure_probability": failure_prob,
                    "model_accuracy": model_accuracy,
                    "model_auc": model_auc,
                },
                "raw_prediction": prediction,
            }
            store_ai_insight(api_id, insight_payload)
        except Exception as store_err:
            print(f"[AI Insights] Failed to store insight: {store_err}")

        # Prepend a summary card so the UI shows a clear narrative first
        insights = list(insights)  # ensure list copy
        insights.insert(0, {
            "type": "summary",
            "title": "AI Summary",
            "message": summary_text,
            "details": prediction.get("reason") or "",
            "action": actions[0],
        })

        return jsonify(insights)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/insights/history/<api_id>")
@require_logged_in_api
def get_ai_insights_history(api_id):
    """Return stored AI insight history for an API from MongoDB."""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    try:
        api_doc, api_error = ensure_api_access_or_error(api_id, get_current_user_id())
        if api_error:
            return api_error
        history = get_ai_insights_from_db(api_id, limit=20, user_id=get_current_user_id())
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/similar_incidents", methods=["POST"])
@require_logged_in_api
def find_similar_incidents():
    """Find similar past incidents"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    current_issue = data.get("issue", "")
    
    if not current_issue:
        return jsonify({"error": "Issue description required"}), 400
    
    try:
        ai = AIPredictor(db)
        similar = ai.find_similar_incidents(current_issue)
        
        # Serialize ObjectIds
        for item in similar:
            if "incident" in item:
                serialize_objectid(item["incident"])
        
        return jsonify(similar)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Main Execution ---
if __name__ == "__main__":
    if not init_mongodb():
        print("[ERROR] Failed to initialize MongoDB. Exiting...")
        exit(1)
    
    try:
        monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        monitor_thread.start()
        print("[Monitor] Background thread started.")
    except Exception as e:
        print(f"[Monitor ERROR] Could not start monitor thread: {e}")
    
    try:
        flask_debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes", "on")
        app.run(port=5000, debug=flask_debug, use_reloader=False)
    except Exception as e:
        print(f"[Flask ERROR] Could not start Flask app: {e}")
