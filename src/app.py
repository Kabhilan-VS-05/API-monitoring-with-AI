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
import pycurl
import idna
import ssl
import zlib
import base64
import random
from functools import wraps
from copy import deepcopy
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in the project root (one level up from src/)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path)
    print("=== Email Config Debug ===")
    print(f"Looking for .env at: {env_path}")
    print(f".env exists: {os.path.exists(env_path)}")
    print(f"EMAIL_USERNAME: {os.getenv('EMAIL_USERNAME')}")
    print(f"EMAIL_PASSWORD: {'*' * len(os.getenv('EMAIL_PASSWORD', ''))}")
    print(f"EMAIL_FROM_ADDRESS: {os.getenv('EMAIL_FROM_ADDRESS')}")
    print(f"EMAIL_SMTP_SERVER: {os.getenv('EMAIL_SMTP_SERVER')}")
    print(f"EMAIL_SMTP_PORT: {os.getenv('EMAIL_SMTP_PORT')}")
    print("========================")
except ImportError:
    print("Warning: python-dotenv not installed. Environment variables may not be loaded from .env file")

# Import new integration modules
try:
    from github_integration import GitHubIntegration
except ImportError:
    GitHubIntegration = None

try:
    from issue_integration import IssueIntegration
except ImportError:
    IssueIntegration = None

try:
    from log_collector import MongoDBLogHandler, log_api_error, get_recent_logs, get_logs_by_api
except ImportError:
    MongoDBLogHandler = log_api_error = get_recent_logs = get_logs_by_api = None

try:
    from correlation_engine import CorrelationEngine
except ImportError:
    CorrelationEngine = None

try:
    from ai_predictor import CategoryAwareAIPredictor as AIPredictor
except ImportError:
    AIPredictor = None

try:
    from alert_manager import AlertManager
except ImportError:
    AlertManager = None

try:
    from ai_alert_manager import AIAlertManager
except ImportError:
    AIAlertManager = None

# Friend's improvements - now integrated
try:
    from auth_manager import create_user, authenticate, create_access_token, role_required
except ImportError:
    create_user = authenticate = create_access_token = role_required = None

try:
    from security_manager import decrypt_if_needed
except ImportError:
    def decrypt_if_needed(value):
        return value

try:
    from self_healing import SelfHealingManager
except ImportError:
    SelfHealingManager = None

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to project root for static folders
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SIMPLE_STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
ADVANCED_STATIC_DIR = os.path.join(PROJECT_ROOT, "static_advanced")
app = Flask(__name__, static_folder=SIMPLE_STATIC_DIR)
CORS(app)

# Serve advanced static files
@app.route("/static_advanced/<path:filename>")
def serve_advanced_static(filename):
    return send_from_directory(ADVANCED_STATIC_DIR, filename)

# Advanced dashboard page
@app.route("/advanced_monitor")
def advanced_monitor():
    return send_from_directory(ADVANCED_STATIC_DIR, "monitor.html")

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
        monitored_apis.create_index([("url", ASCENDING)], unique=True)
        monitored_apis.create_index([("category", ASCENDING)])
        monitored_apis.create_index([("is_active", ASCENDING)])
        
        # Indexes for monitoring_logs
        monitoring_logs.create_index([("api_id", ASCENDING)])
        monitoring_logs.create_index([("timestamp", DESCENDING)])
        monitoring_logs.create_index([("api_id", ASCENDING), ("timestamp", DESCENDING)])
        
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
        alert_history.create_index([("created_at", DESCENDING)])
        alert_history.create_index([("status", ASCENDING)])

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


# --- Phase 2 Demo Mock State ---
def _demo_timestamp():
    return now_isoutc()


DEMO_INCIDENT = {
    "incident_id": "INC-DEMO",
    "status": "Mitigating",
    "severity": "High",
    "assigned_to": {"name": "Dr. Rao", "role": "NGO Leader"},
    "api": {
        "id": "api_demo",
        "name": "Patient Bed Availability",
        "url": "https://health.example.org/beds"
    },
    "started_at": _demo_timestamp(),
    "summary": "AI predicted DB saturation impacting hospital updates",
}

DEMO_CHAT = [
    {
        "id": "msg1",
        "author": "Aisha (Field Worker)",
        "role": "Field Worker",
        "message": "Bed counts are stale for the last 20 minutes.",
        "timestamp": _demo_timestamp()
    },
    {
        "id": "msg2",
        "author": "AI Co-Pilot",
        "role": "AI",
        "message": "Telemetry shows DB latency ↑180%. Suggest checking replication lag.",
        "timestamp": _demo_timestamp()
    }
]

DEMO_TIMELINE = [
    {"type": "alert", "label": "AI Prediction", "detail": "Risk 82%", "timestamp": _demo_timestamp()},
    {"type": "action", "label": "Restarted read replica", "detail": "DevOps", "timestamp": _demo_timestamp()}
]

DEMO_CAUSAL_GRAPH = {
    "nodes": [
        {"id": "API", "label": "Patient API", "status": "warning"},
        {"id": "DB", "label": "Beds DB", "status": "critical"},
        {"id": "Cache", "label": "Cache Layer", "status": "normal"},
        {"id": "Network", "label": "WAN", "status": "warning"}
    ],
    "edges": [
        {"from": "API", "to": "Cache"},
        {"from": "Cache", "to": "DB"},
        {"from": "API", "to": "Network"}
    ],
    "root_cause": "DB",
    "confidence": 0.87,
    "insight": "Write throughput spike saturated DB CPU at 92%"
}

DEMO_SIM_HISTORY = []

ROLE_PERMISSIONS = {
    "create_incident": {"Admin", "Developer"},
    "assign_incident": {"Admin", "NGO Leader"},
    "update_status": {"Admin", "NGO Leader"},
    "run_simulation": {"Admin", "Developer"},
}


def _get_request_role():
    return (request.headers.get("X-Demo-Role") or request.args.get("demo_role") or "Field Worker").strip() or "Field Worker"


def require_roles(allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            role = _get_request_role()
            if role not in allowed_roles:
                return jsonify({"error": "Forbidden", "required_roles": sorted(list(allowed_roles))}), 403
            request.demo_role = role
            return func(*args, **kwargs)
        return wrapper
    return decorator


def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc != ""
    except Exception:
        return False

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


def fetch_worker_responses(api_id, limit=10):
    if db is None or not api_id:
        return []
    cursor = db.worker_responses.find({"api_id": api_id}).sort("timestamp", DESCENDING).limit(limit)
    return [serialize_worker_response(doc) for doc in cursor]


def build_email_message(payload):
    """Build email message content from alert payload."""
    subject = f"API Alert: {payload.get('api_name', 'Unknown')} - {payload.get('status', 'Check Required')}"
    
    body_parts = [
        f"API Name: {payload.get('api_name', 'Unknown')}",
        f"Status: {payload.get('status', 'Unknown')}",
        f"Risk Level: {payload.get('risk_percentage', 'N/A')}%",
        f"Cause: {payload.get('cause_short', payload.get('cause_summary', 'Check system'))}",
        f"Recommended Action: {payload.get('fix_step', payload.get('recommendation', 'Follow standard recovery steps'))}",
        "",
        "Please check the dashboard for more details and take appropriate action.",
        "Reply with 'FIXED' if you have resolved this issue."
    ]
    
    body = "\n".join(body_parts)
    return subject, body


def dispatch_email_message(email_address, payload):
    """Send email notification using SMTP."""
    if not EMAIL_USERNAME or not EMAIL_PASSWORD or not EMAIL_FROM_ADDRESS:
        raise RuntimeError("Missing email configuration: EMAIL_USERNAME, EMAIL_PASSWORD, and EMAIL_FROM_ADDRESS must be set")
    
    subject, body = build_email_message(payload)
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM_ADDRESS
    msg['To'] = email_address
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_FROM_ADDRESS, email_address, text)
        server.quit()
        
        # Log the email notification to database
        if db is not None:
            notifications = db.notifications
            notification_doc = {
                "channel": "email",
                "email_address": email_address,
                "message": subject,
                "payload": payload,
                "api_id": payload.get("api_id"),
                "timestamp": datetime.now(timezone.utc),
                "status": "sent"
            }
            notifications.insert_one(notification_doc)
        
        return True, {"message": "Email sent successfully"}
    except Exception as exc:
        # Log failed email attempt
        if db is not None:
            notifications = db.notifications
            notification_doc = {
                "channel": "email",
                "email_address": email_address,
                "message": subject,
                "payload": payload,
                "api_id": payload.get("api_id"),
                "timestamp": datetime.now(timezone.utc),
                "status": "failed",
                "error": str(exc)
            }
            notifications.insert_one(notification_doc)
        
        return False, str(exc)


@app.route("/notify/email/send", methods=["POST"])
def notify_email_send():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    email_address = payload.get("email_address")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")
    
    if not email_address or not api_id or not alert_id:
        return jsonify({"error": "email_address, api_id, and alert_id are required"}), 400

    try:
        success, response_data = dispatch_email_message(email_address, payload)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    if not success:
        return jsonify({"success": False, "error": response_data}), 500

    return jsonify({"success": True, "details": response_data})


@app.route("/notify/email/receive", methods=["POST"])
def notify_email_receive():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    payload = request.json or {}
    email_address = payload.get("email_address")
    message_body = payload.get("message_body")
    timestamp = payload.get("timestamp")
    api_id = payload.get("api_id")
    alert_id = payload.get("alert_id")

    if not email_address or not message_body:
        return jsonify({"error": "email_address and message_body are required"}), 400

    response_type = normalize_email_response(message_body)
    response_doc = {
        "email_address": email_address,
        "api_id": api_id,
        "alert_id": alert_id,
        "response": response_type,
        "channel": "email",
        "raw_message": message_body,
        "timestamp": timestamp or datetime.utcnow().isoformat() + "Z"
    }
    stored = persist_worker_response(response_doc)
    update_alert_worker_ack(alert_id, response_type, "email", response_doc["timestamp"])

    return jsonify({"success": True, "worker_response": stored})

 # --- Advanced Monitor Minimal Fast Endpoints ---
 @app.route("/api/advanced/monitors")
 def advanced_get_monitors():
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     try:
         monitors = []
         for doc in db.monitored_apis.find():
             d = dict(doc)
             d = serialize_objectid(d)
             d.setdefault("api_name", d.get("name") or d.get("url"))
             d.setdefault("priority", d.get("priority", "medium"))
             d.setdefault("impact_score", d.get("impact_score", 50))
             d.setdefault("last_status", d.get("last_status", "Pending"))
             # numeric defaults
             try:
                 d["avg_latency_24h"] = float(d.get("avg_latency_24h", 0.0))
             except Exception:
                 d["avg_latency_24h"] = 0.0
             try:
                 d["uptime_pct_24h"] = float(d.get("uptime_pct_24h", 0.0))
             except Exception:
                 d["uptime_pct_24h"] = 0.0
             d.setdefault("recent_checks", [])
             monitors.append(d)
         return jsonify(monitors)
     except Exception as exc:
         return jsonify({"error": str(exc)}), 500

 @app.route("/api/advanced/history")
 def advanced_get_history():
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     api_id = request.args.get("id")
     if not api_id:
         return jsonify({"error": "id is required"}), 400
     try:
         col = db.monitoring_logs
         # Try string id first
         cur = col.find({"api_id": api_id}).sort("timestamp", DESCENDING).limit(50)
         history = list(cur)
         if not history:
             try:
                 oid = ObjectId(api_id)
                 history = list(col.find({"api_id": oid}).sort("timestamp", DESCENDING).limit(50))
             except Exception:
                 history = []
         out = []
         for h in history:
             ts = h.get("timestamp")
             if isinstance(ts, datetime):
                 ts = ts.isoformat() + "Z"
             out.append({
                 "timestamp": ts,
                 "is_up": bool(h.get("up", h.get("is_up", False))),
                 "response_time": h.get("total_latency_ms") or h.get("response_time"),
                 "status_code": h.get("status_code"),
                 "error": h.get("error"),
             })
         return jsonify({"history": out, "total_pages": 1, "current_page": 1})
     except Exception as exc:
         return jsonify({"error": str(exc), "history": [], "total_pages": 1, "current_page": 1}), 500

 @app.route("/api/advanced/add_monitor", methods=["POST"])
 def advanced_add_monitor():
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     payload = request.json or {}
     url = payload.get("url")
     category = payload.get("category")
     if not url or not category:
         return jsonify({"error": "url and category are required"}), 400
     try:
         doc = {
             "api_name": payload.get("api_name") or url,
             "url": url,
             "category": category,
             "priority": payload.get("priority", "medium"),
             "impact_score": int(payload.get("impact_score", 50)),
             "emergency_contact": payload.get("emergency_contact"),
             "fallback_url": payload.get("fallback_url"),
             "check_interval": int(payload.get("check_interval", 30)),
             "check_frequency_minutes": max(0.5, float(payload.get("check_interval", 30)) / 60.0),
             "is_active": True,
             "created_at": datetime.utcnow(),
             "last_status": payload.get("last_status", "Pending"),
         }
         res = db.monitored_apis.insert_one(doc)
         return jsonify({"success": True, "id": str(res.inserted_id)})
     except Exception as exc:
         return jsonify({"success": False, "error": str(exc)}), 500

 @app.route("/api/advanced/update_monitor", methods=["POST"])
 def advanced_update_monitor():
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     payload = request.json or {}
     api_id = payload.get("id")
     if not api_id:
         return jsonify({"error": "id is required"}), 400
     try:
         # Build update fields only for provided keys
         update_fields = {}
         for key in [
             "api_name", "url", "category", "priority", "impact_score",
             "emergency_contact", "fallback_url", "header_name", "header_value",
             "notification_email", "check_interval", "check_frequency_minutes"
         ]:
             if key in payload and payload.get(key) is not None:
                 update_fields[key] = payload.get(key)
         # Keep frequency coherence if only minutes provided
         if "check_frequency_minutes" in update_fields and "check_interval" not in update_fields:
             try:
                 mins = float(update_fields["check_frequency_minutes"]) or 1.0
                 update_fields["check_interval"] = int(max(10, mins * 60))
             except Exception:
                 pass
         # Execute update
         try:
             res = db.monitored_apis.update_one({"_id": ObjectId(api_id)}, {"$set": update_fields})
         except Exception:
             res = db.monitored_apis.update_one({"id": api_id}, {"$set": update_fields})
         return jsonify({"success": True, "modified": res.modified_count})
     except Exception as exc:
         return jsonify({"success": False, "error": str(exc)}), 500

 @app.route("/api/advanced/delete_monitor", methods=["POST"])
 def advanced_delete_monitor():
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     payload = request.json or {}
     api_id = payload.get("id")
     if not api_id:
         return jsonify({"error": "id is required"}), 400
     try:
         # Try delete by string id then ObjectId
         res = db.monitored_apis.delete_one({"_id": ObjectId(api_id)})
     except Exception:
         res = db.monitored_apis.delete_one({"id": api_id})
     return jsonify({"success": True, "deleted": res.deleted_count})

 @app.route("/api/advanced/log_details/<log_id>")
 def advanced_log_details(log_id):
     if db is None:
         return jsonify({"error": "Database not connected"}), 500
     try:
         col = db.monitoring_logs
         try:
             doc = col.find_one({"_id": ObjectId(log_id)})
         except Exception:
             doc = col.find_one({"id": log_id})
         if not doc:
             return jsonify({"error": "Log not found"}), 404
         # Normalize fields expected by UI
         url_type = doc.get("url_type")
         if not url_type and doc.get("content_type"):
             url_type = determine_url_type(doc.get("content_type"))
         result = {
             "url": doc.get("url"),
             "url_type": url_type or "Unknown",
             "timestamp": (doc.get("timestamp").isoformat() + "Z") if isinstance(doc.get("timestamp"), datetime) else doc.get("timestamp"),
             "is_up": bool(doc.get("up", doc.get("is_up", False))),
             "status_code": doc.get("status_code"),
             "error_message": doc.get("error"),
             "total_latency_ms": doc.get("total_latency_ms"),
             "dns_latency_ms": doc.get("dns_latency_ms"),
             "tcp_latency_ms": doc.get("tcp_latency_ms"),
             "tls_latency_ms": doc.get("tls_latency_ms"),
             "server_processing_latency_ms": doc.get("server_processing_latency_ms"),
             "content_download_latency_ms": doc.get("content_download_latency_ms"),
         }
         # Map certificate fields if present in nested structure
         cert = doc.get("certificate_details") or {}
         if isinstance(cert, dict):
             result.update({
                 "tls_cert_subject": cert.get("subject"),
                 "tls_cert_issuer": cert.get("issuer"),
                 "tls_cert_sans": cert.get("sans"),
                 "tls_cert_valid_from": cert.get("valid_from"),
                 "tls_cert_valid_until": cert.get("valid_until"),
             })
         return jsonify(result)
     except Exception as exc:
         return jsonify({"error": str(exc)}), 500

 @app.route("/api/alerts/timeline")
 def alerts_timeline():
     if db is None:
         return jsonify({"alerts": []})
     try:
         cur = db.alert_history.find().sort("created_at", DESCENDING).limit(25)
         alerts = []
         for a in cur:
             item = {
                 "type": a.get("type", "alert"),
                 "severity": a.get("severity", "medium"),
                 "message": a.get("message") or a.get("summary") or "",
                 "timestamp": (a.get("created_at").isoformat() + "Z") if isinstance(a.get("created_at"), datetime) else a.get("created_at"),
                 "api_id": str(a.get("api_id")) if a.get("api_id") else None,
                 "api_url": a.get("api_url"),
             }
             alerts.append(item)
         return jsonify({"alerts": alerts})
     except Exception:
         return jsonify({"alerts": []})

@app.route("/utils/translate", methods=["POST"])
def utils_translate():
    payload = request.json or {}
    text = payload.get("text")
    target_language = payload.get("target_language", "EN")

    if not text:
        return jsonify({"error": "text is required"}), 400

    translated = translate_text(text, target_language)
    return jsonify({"translated_text": translated, "target_language": target_language.upper()})


@app.route("/incident/acknowledge", methods=["POST"])
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
def perform_latency_check(url, headers=None, timeout=10, body_snippet_len=500, required_body_substring=None):
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
    while True:
        try:
            if db is None:
                print("[Monitor] MongoDB not connected, skipping check cycle")
                time.sleep(sleep_seconds)
                continue
                
            monitored_apis = db.monitored_apis
            monitoring_logs = db.monitoring_logs
            
            apis = list(monitored_apis.find({"is_active": True}))

            for api in apis:
                try:
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

                    log_entry = {
                        "api_id": str(api["_id"]),
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
                        "url_type": res.get("url_type"),
                        "tls_cert_subject": cert.get("subject"),
                        "tls_cert_issuer": cert.get("issuer"),
                        "tls_cert_sans": cert.get("sans"),
                        "tls_cert_valid_from": cert.get("valid_from"),
                        "tls_cert_valid_until": cert.get("valid_until"),
                        "tls_cipher": cert.get("cipher")
                    }

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
                        alert_manager = AlertManager(db)
                        # Use same status logic as monitoring
                        current_status = "Up" if res.get("up") else ("Error" if res.get("error") else "Down")
                        alert_result = alert_manager.check_and_alert(
                            str(api["_id"]), 
                            api["url"], 
                            current_status
                        )
                        if alert_result:
                            print(f"[Alert] Downtime/Recovery alert: {alert_result.get('message', 'Success')}")
                    except Exception as alert_err:
                        print(f"[Alert] Error: {alert_err}")
                    
                    # System 2: AI predictive alerting (every 15 mins)
                    try:
                        ai_alert_manager = AIAlertManager(db)
                        ai_alert_result = ai_alert_manager.check_and_alert(
                            str(api["_id"]),
                            api["url"]
                        )
                        if ai_alert_result:
                            print(f"[AI Alert] Prediction alert: {ai_alert_result.get('message', 'Success')}")
                    except Exception as ai_err:
                        print(f"[AI Alert] Error: {ai_err}")

                    new_status = "Up" if res.get("up") else ("Error" if res.get("error") else "Down")
                    monitored_apis.update_one(
                        {"_id": api["_id"]},
                        {"$set": {"last_checked_at": ts, "last_status": new_status}}
                    )

                except Exception as e_inner:
                    print(f"Error checking API ID {api.get('_id')}: {e_inner}")

        except Exception as e:
            print("Monitor worker outer error:", e)

        time.sleep(sleep_seconds)

# --- ROUTING AND ENDPOINTS ---
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

@app.route("/api/contacts", methods=["GET", "POST", "DELETE"])
def manage_contacts():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    contacts_collection = db.contacts
    
    if request.method == "GET":
        contacts = list(contacts_collection.find({}, {"_id": 0}))
        return jsonify({"contacts": contacts})
    
    elif request.method == "POST":
        contact = request.json or {}
        if not contact.get("email") or not contact.get("name"):
            return jsonify({"error": "Name and email are required"}), 400
        
        contact["created_at"] = datetime.now(timezone.utc)
        result = contacts_collection.insert_one(contact)
        return jsonify({"success": True, "id": str(result.inserted_id)})
    
    elif request.method == "DELETE":
        contact_id = request.args.get("id")
        if not contact_id:
            return jsonify({"error": "Contact ID is required"}), 400
        
        try:
            contacts_collection.delete_one({"_id": ObjectId(contact_id)})
            return jsonify({"success": True})
        except:
            return jsonify({"error": "Invalid contact ID"}), 400


def send_api_down_alert(api_url, api_name=None, status="down", error_message=None):
    """Send email alerts to contacts monitoring this API with AI predictions and translations."""
    if db is None:
        return
    
    contacts_collection = db.contacts
    # Find contacts who are monitoring this API - check multiple fields
    contacts = list(contacts_collection.find({
        "$or": [
            {"apis": {"$in": [api_url]}},
            {"apis": {"$in": [api_name]}},
            {"apis": {"$in": [api_url.split('/')[2] if '/' in api_url else api_url]}},  # Domain matching
            {"apis": {"$regex": api_url, "$options": "i"}}  # Partial match
        ]
    }))
    
    if not contacts:
        print(f"No contacts found monitoring API: {api_url}")
        return
    
    print(f"Found {len(contacts)} contacts for API {api_url}: {[c['email'] for c in contacts]}")
    
    # Get AI predictions for this API
    ai_predictions = get_ai_predictions_for_api(api_url)
    
    # Send email to each contact with their preferred language
    for contact in contacts:
        try:
            # Translate alert message to contact's preferred language
            translated_message = translate_alert_message(
                f"API {status} alert for {api_name or api_url}",
                contact.get("language", "EN")
            )
            
            # Create email payload with AI predictions
            email_payload = {
                "api_url": api_url,
                "api_name": api_name or api_url,
                "status": status,
                "error_message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "alert_type": "api_down" if status == "down" else "api_up",
                "contact_name": contact["name"],
                "contact_language": contact.get("language", "EN"),
                "translated_message": translated_message,
                "ai_predictions": ai_predictions,
                "github_issue_reference": generate_github_issue_reference(api_url, api_name)
            }
            
            success, response = dispatch_email_message(contact["email"], email_payload)
            
            # Log to notifications collection
            notifications = db.notifications
            notification_doc = {
                "channel": "email",
                "email_address": contact["email"],
                "contact_name": contact["name"],
                "contact_language": contact.get("language", "EN"),
                "message": translated_message,
                "api_url": api_url,
                "api_name": api_name,
                "alert_type": email_payload["alert_type"],
                "ai_predictions": ai_predictions,
                "github_issue_ref": email_payload["github_issue_reference"],
                "timestamp": datetime.now(timezone.utc),
                "status": "sent" if success else "failed",
                "details": error_message
            }
            if not success:
                notification_doc["error"] = response
            
            notifications.insert_one(notification_doc)
            
        except Exception as e:
            print(f"Error sending alert to {contact['email']}: {e}")
            # Log failed attempt
            notifications = db.notifications
            notification_doc = {
                "channel": "email",
                "email_address": contact["email"],
                "contact_name": contact["name"],
                "contact_language": contact.get("language", "EN"),
                "message": f"API {status} alert",
                "api_url": api_url,
                "api_name": api_name,
                "alert_type": "api_down" if status == "down" else "api_up",
                "timestamp": datetime.now(timezone.utc),
                "status": "failed",
                "error": str(e),
                "details": error_message
            }
            notifications.insert_one(notification_doc)


def get_ai_predictions_for_api(api_url):
    """Get latest AI predictions for an API."""
    try:
        if db is None or "ai_predictions" not in db.list_collection_names():
            return None
        
        # Get latest prediction for this API
        prediction = db.ai_predictions.find_one(
            {"api_id": api_url},
            sort=[("timestamp", -1)]
        )
        
        if prediction:
            return {
                "failure_probability": prediction.get("failure_probability", 0),
                "confidence": prediction.get("confidence", 0),
                "risk_level": prediction.get("risk_level", "UNKNOWN"),
                "predicted_failure_time": prediction.get("predicted_failure_time"),
                "last_updated": prediction.get("timestamp")
            }
        return None
        
    except Exception as e:
        print(f"Error fetching AI predictions: {e}")
        return None


def translate_alert_message(message, target_language):
    """Translate alert message to target language."""
    try:
        # Simple translation map for common languages
        translations = {
            "EN": message,
            "TA": f"எச்சரிக்கை: {message}",  # Tamil prefix
            "HI": f"चेतावनी: {message}",     # Hindi prefix
            "ES": f"Alerta: {message}",       # Spanish
            "FR": f"Alerte: {message}",       # French
            "DE": f"Warnung: {message}",      # German
            "ZH": f"警报: {message}",         # Chinese
            "JA": f"警告: {message}",         # Japanese
        }
        
        translated = translations.get(target_language.upper(), message)
        
        # For more complex translations, you could integrate with Google Translate API
        # if TRANSLATION_API_KEY is available in environment
        if target_language.upper() not in translations and os.getenv("TRANSLATION_API_KEY"):
            try:
                import requests
                response = requests.post(
                    f"https://translation.googleapis.com/language/translate/v2?key={os.getenv('TRANSLATION_API_KEY')}",
                    json={
                        "q": message,
                        "source": "en",
                        "target": target_language.lower()
                    }
                )
                if response.status_code == 200:
                    translated = response.json()["data"]["translations"][0]["translatedText"]
            except:
                pass  # Fallback to original message
        
        return translated
        
    except Exception as e:
        print(f"Translation error: {e}")
        return message


def generate_github_issue_reference(api_url, api_name=None):
    """Generate GitHub issue reference for API incidents."""
    try:
        # Create a unique issue ID based on timestamp and API
        issue_id = f"API-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{hash(api_url) % 1000:03d}"
        
        # Generate GitHub-style issue URL (you would need to configure your repo)
        github_repo = os.getenv("GITHUB_REPO", "your-org/your-repo")
        issue_url = f"https://github.com/{github_repo}/issues/{issue_id}"
        
        return {
            "issue_id": issue_id,
            "issue_url": issue_url,
            "title": f"API Incident: {api_name or api_url}",
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        print(f"Error generating GitHub reference: {e}")
        return {
            "issue_id": f"API-{datetime.now(timezone.utc).strftime('%Y%m%d')}-001",
            "issue_url": "#",
            "title": f"API Incident: {api_name or api_url}",
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat()
        }


@app.route("/api/alerts/timeline", methods=["GET"])
def get_alerts_timeline():
    if db is None:
        return jsonify({"alerts": []}), 500
    
    try:
        # Get recent alerts from various collections
        alerts = []
        
        # Get recent API checks (logs)
        if "simple_logs" in db.list_collection_names():
            simple_logs = db.simple_logs
            recent_logs = list(simple_logs.find(
                {"up": False},  # Only failed checks
                {"_id": 0, "api_url": 1, "error": 1, "timestamp": 1}
            ).sort("timestamp", -1).limit(10))
            
            for log in recent_logs:
                alerts.append({
                    "type": "api_down",
                    "message": f"API check failed",
                    "details": log.get("error", "Unknown error"),
                    "api_url": log.get("api_url"),
                    "timestamp": log.get("timestamp"),
                    "severity": "high"
                })
        
        # Get recent email notifications
        if "notifications" in db.list_collection_names():
            notifications = db.notifications
            recent_emails = list(notifications.find(
                {"channel": "email", "status": "sent"},
                {"_id": 0, "email_address": 1, "message": 1, "timestamp": 1, "api_id": 1, "api_url": 1}
            ).sort("timestamp", -1).limit(10))
            
            for email in recent_emails:
                alerts.append({
                    "type": "email_sent",
                    "message": "Alert sent",
                    "details": f"to {email.get('email_address')}",
                    "api_id": email.get("api_id"),
                    "api_url": email.get("api_url"),
                    "timestamp": email.get("timestamp"),
                    "severity": "medium"
                })
        
        # Get AI predictions
        if "ai_predictions" in db.list_collection_names():
            ai_predictions = db.ai_predictions
            recent_predictions = list(ai_predictions.find(
                {"failure_probability": {"$gt": 0.5}},  # High risk predictions
                {"_id": 0, "api_id": 1, "failure_probability": 1, "confidence": 1, "timestamp": 1}
            ).sort("timestamp", -1).limit(10))
            
            for pred in recent_predictions:
                risk_pct = pred.get("failure_probability", 0) * 100
                alerts.append({
                    "type": "ai_alert",
                    "message": f"AI Alert: {risk_pct:.0f}% failure risk",
                    "details": f"confidence: {pred.get('confidence', 0) * 100:.0f}%",
                    "api_id": pred.get("api_id"),
                    "timestamp": pred.get("timestamp"),
                    "severity": "medium" if risk_pct < 70 else "high"
                })
        
        # Add some sample data if no alerts exist
        if not alerts:
            alerts.append({
                "type": "info",
                "message": "System monitoring active",
                "details": "No recent alerts to display",
                "timestamp": datetime.now(timezone.utc),
                "severity": "low"
            })
        
        # Sort all alerts by timestamp
        alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return jsonify({"alerts": alerts[:20]})  # Return latest 20 alerts
        
    except Exception as e:
        print(f"Error fetching alerts timeline: {e}")
        return jsonify({"alerts": []}), 500


@app.route("/api/ai/training_runs/<api_id>", methods=["GET"])
def get_training_runs(api_id):
    """Get AI training runs for a specific API."""
    if db is None:
        return jsonify([])
    
    try:
        # Check if training data exists in ai_training_runs collection
        if "ai_training_runs" in db.list_collection_names():
            training_collection = db.ai_training_runs
            runs = list(training_collection.find(
                {"api_id": api_id},
                {"_id": 0}
            ).sort("started_at", -1).limit(15))
            
            if runs:
                return jsonify(runs)
        
        # Generate sample training data if none exists
        sample_runs = generate_sample_training_data(api_id)
        
        # Save sample data to database for future use
        if "ai_training_runs" in db.list_collection_names():
            training_collection = db.ai_training_runs
            for run in sample_runs:
                run["api_id"] = api_id
                training_collection.insert_one(run.copy())
        
        return jsonify(sample_runs)
        
    except Exception as e:
        print(f"Error fetching training runs: {e}")
        return jsonify([])

def generate_sample_training_data(api_id):
    """Generate sample AI training data for demonstration."""
    import random
    from datetime import datetime, timedelta
    
    risk_factors_list = [
        ["High response time variability", "Recent error rate increase", "SSL certificate expiring soon"],
        ["Memory usage trending upward", "Database connection pool exhaustion", "Weekend downtime pattern"],
        ["Third-party dependency latency", "Geographic routing issues", "Cache miss rate high"],
        ["CPU utilization spikes", "Network packet loss", "Authentication token refresh failures"]
    ]
    
    actions_list = [
        ["Scale up resources", "Optimize database queries", "Implement caching"],
        ["Update SSL certificates", "Add health checks", "Configure auto-retry"],
        ["Load balancer reconfiguration", "Memory optimization", "Connection pooling"],
        ["CDN configuration", "Database indexing", "API rate limiting"]
    ]
    
    summaries = [
        "Model training completed with 85% accuracy. API shows stable performance patterns.",
        "Training detected potential failure risks. Recommended immediate actions implemented.",
        "AI model updated with latest metrics. Performance improvements noted.",
        "Training session identified critical risk factors. Preventive measures suggested."
    ]
    
    runs = []
    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    
    for i in range(5):  # Generate 5 sample runs
        start_time = base_time + timedelta(days=i*6, hours=random.randint(1, 23))
        duration = random.uniform(45, 180)  # 45 seconds to 3 minutes
        
        run = {
            "started_at": start_time.isoformat(),
            "completed_at": (start_time + timedelta(seconds=duration)).isoformat(),
            "duration_seconds": duration,
            "status": "completed",
            "failure_probability": random.uniform(0.1, 0.9),
            "confidence": random.uniform(0.7, 0.95),
            "risk_level": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
            "risk_factors": random.choice(risk_factors_list),
            "actions": random.choice(actions_list),
            "summary": random.choice(summaries),
            "model_version": f"v2.{i+1}.0",
            "training_samples": random.randint(1000, 5000),
            "accuracy": random.uniform(0.75, 0.95),
            "log_lines": [
                f"Training started with {random.randint(1000, 5000)} samples",
                f"Epoch {random.randint(10, 50)}: loss = {random.uniform(0.1, 0.5):.3f}",
                f"Validation accuracy: {random.uniform(0.75, 0.95):.3f}",
                "Model saved successfully",
                "Training completed"
            ]
        }
        runs.append(run)
    
    # Also generate some AI predictions for the timeline
    generate_ai_predictions(api_id)
    
    return sorted(runs, key=lambda x: x["started_at"], reverse=True)

def generate_ai_predictions(api_id):
    """Generate sample AI predictions for the timeline."""
    if db is None:
        return
    
    try:
        # Check if ai_predictions collection exists, if not create sample data
        if "ai_predictions" not in db.list_collection_names():
            ai_predictions = db.ai_predictions
        else:
            ai_predictions = db.ai_predictions
            predictions = list(ai_predictions.find({"api_id": api_id}).limit(5))
            
            if len(predictions) >= 3:  # Already have enough predictions
                return
        
        # Generate some sample predictions
        import random
        from datetime import datetime, timedelta
        
        for i in range(3):
            pred_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))
            prediction = {
                "api_id": api_id,
                "failure_probability": random.uniform(0.3, 0.85),
                "confidence": random.uniform(0.6, 0.9),
                "timestamp": pred_time,
                "risk_level": random.choice(["LOW", "MEDIUM", "HIGH"]),
                "predicted_failure_time": pred_time + timedelta(hours=random.randint(6, 48))
            }
            ai_predictions.insert_one(prediction)
                
    except Exception as e:
        print(f"Error generating AI predictions: {e}")


@app.route("/api/test-alert", methods=["POST"])
def test_alert():
    """Test endpoint to simulate API failure and trigger email alerts."""
    data = request.json or {}
    api_url = data.get("api_url")
    if not api_url:
        return jsonify({"error": "API URL is required"}), 400
    
    # Simulate API failure
    send_api_down_alert(
        api_url=api_url,
        api_name=data.get("api_name"),
        status="down",
        error_message="Test alert - simulated API failure"
    )
    
    return jsonify({"success": True, "message": f"Test alert sent for {api_url}"})


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
        # Send alert to contacts monitoring this API
        send_api_down_alert(
            api_url=api_url,
            api_name=data.get("api_name"),
            status="down",
            error_message=str(e)
        )
        return jsonify(error_payload), 500

    res.update({"api_url": api_url, "header_name": h_name or "", "header_value": h_val or ""})
    
    # Check if API is down and send alert
    if not res.get("up", True):
        send_api_down_alert(
            api_url=api_url,
            api_name=data.get("api_name"),
            status="down",
            error_message=res.get("error", "API check failed")
        )
    
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

# --- HEALTHCARE API CATEGORIES AND IMPACT SCORING ---

HEALTHCARE_CATEGORIES = {
    'emergency_dispatch': {
        'priority': 'critical',
        'impact_score': 95,
        'icon': '🚨',
        'description': 'Emergency Dispatch Services',
        'check_interval': 10  # seconds
    },
    'life_support': {
        'priority': 'critical',
        'impact_score': 98,
        'icon': '❤️',
        'description': 'Life Support Systems',
        'check_interval': 15
    },
    'emergency_alerts': {
        'priority': 'critical',
        'impact_score': 92,
        'icon': '📢',
        'description': 'Emergency Alert Broadcasting',
        'check_interval': 20
    },
    'hospital_operations': {
        'priority': 'high',
        'impact_score': 80,
        'icon': '🏥',
        'description': 'Hospital Operations',
        'check_interval': 30
    },
    'telemedicine': {
        'priority': 'high',
        'impact_score': 75,
        'icon': '💻',
        'description': 'Telemedicine Services',
        'check_interval': 45
    },
    'vaccination': {
        'priority': 'high',
        'impact_score': 70,
        'icon': '💉',
        'description': 'Vaccination Services',
        'check_interval': 60
    },
    'health_records': {
        'priority': 'medium',
        'impact_score': 60,
        'icon': '📋',
        'description': 'Health Records Access',
        'check_interval': 90
    },
    'supply_chain': {
        'priority': 'medium',
        'impact_score': 55,
        'icon': '🚚',
        'description': 'Medical Supply Chain',
        'check_interval': 120
    },
    'public_health': {
        'priority': 'medium',
        'impact_score': 50,
        'icon': '📊',
        'description': 'Public Health Data',
        'check_interval': 180
    }
}

def get_healthcare_impact_score(category, custom_score=None):
    """Get impact score for healthcare category"""
    if custom_score is not None:
        return custom_score
    return HEALTHCARE_CATEGORIES.get(category, {}).get('impact_score', 50)

def get_healthcare_priority(category):
    """Get priority level for healthcare category"""
    return HEALTHCARE_CATEGORIES.get(category, {}).get('priority', 'medium')

def get_healthcare_check_interval(category, custom_interval=None):
    """Get recommended check interval for healthcare category"""
    if custom_interval is not None:
        return custom_interval
    return HEALTHCARE_CATEGORIES.get(category, {}).get('check_interval', 60)

# --- HEALTHCARE-SPECIFIC ENDPOINTS ---

@app.route("/api/healthcare/categories")
def get_healthcare_categories():
    """Get available healthcare API categories with metadata"""
    return jsonify({
        "categories": HEALTHCARE_CATEGORIES,
        "priorities": ["critical", "high", "medium", "low"],
        "impact_range": {"min": 0, "max": 100}
    })

@app.route("/api/healthcare/impact", methods=["POST"])
def calculate_healthcare_impact():
    """Calculate impact score for healthcare API"""
    try:
        data = request.get_json()
        category = data.get('category')
        custom_score = data.get('impact_score')
        
        if not category:
            return jsonify({"error": "Category is required"}), 400
        
        impact_score = get_healthcare_impact_score(category, custom_score)
        priority = get_healthcare_priority(category)
        recommended_interval = get_healthcare_check_interval(category)
        
        return jsonify({
            "impact_score": impact_score,
            "priority": priority,
            "recommended_check_interval": recommended_interval,
            "category_info": HEALTHCARE_CATEGORIES.get(category, {})
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/healthcare/stats")
def get_healthcare_stats():
    """Get healthcare-specific monitoring statistics"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        monitored_apis = db.monitored_apis
        
        # Get all monitors
        monitors = list(monitored_apis.find())
        
        # Calculate stats by priority
        stats = {
            "total_apis": len(monitors),
            "by_priority": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "by_status": {
                "up": 0,
                "down": 0,
                "unknown": 0
            },
            "by_category": {},
            "average_uptime": 0,
            "active_incidents": 0
        }
        
        total_uptime = 0
        uptime_count = 0
        
        for monitor in monitors:
            # Count by priority
            priority = monitor.get('priority', 'medium')
            if priority in stats["by_priority"]:
                stats["by_priority"][priority] += 1
            
            # Count by status
            status = monitor.get('status', 'unknown')
            if status in stats["by_status"]:
                stats["by_status"][status] += 1
            
            # Count by category
            category = monitor.get('category', 'unknown')
            if category not in stats["by_category"]:
                stats["by_category"][category] = 0
            stats["by_category"][category] += 1
            
            # Calculate uptime
            uptime = monitor.get('uptime_percentage', 0)
            if uptime > 0:
                total_uptime += uptime
                uptime_count += 1
            
            # Count active incidents (down critical/high priority APIs)
            if status == 'down' and priority in ['critical', 'high']:
                stats["active_incidents"] += 1
        
        # Calculate average uptime
        if uptime_count > 0:
            stats["average_uptime"] = round(total_uptime / uptime_count, 2)
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/healthcare/war-room/incidents")
def get_active_incidents():
    """Get active incidents for war room"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        monitored_apis = db.monitored_apis
        
        # Get critical and high priority APIs that are down
        incidents = list(monitored_apis.find({
            "status": "down",
            "priority": {"$in": ["critical", "high"]}
        }))
        
        # Format incidents for war room
        formatted_incidents = []
        for incident in incidents:
            category_info = HEALTHCARE_CATEGORIES.get(incident.get('category'), {})
            formatted_incidents.append({
                "id": str(incident.get('_id')),
                "title": f"🚨 {incident.get('name', 'Unknown API')} Critical Failure",
                "description": f"{category_info.get('icon', '⚠️')} {category_info.get('description', incident.get('category', 'API'))} is down",
                "impact": incident.get('impact_score', category_info.get('impact_score', 50)),
                "priority": incident.get('priority', 'medium'),
                "category": incident.get('category', 'unknown'),
                "contact": incident.get('contact', 'No contact'),
                "start_time": incident.get('last_check', datetime.utcnow().isoformat()),
                "duration_minutes": int((datetime.utcnow() - incident.get('last_check', datetime.utcnow())).total_seconds() / 60)
            })
        
        return jsonify({
            "incidents": formatted_incidents,
            "total_count": len(formatted_incidents),
            "critical_count": len([i for i in formatted_incidents if i.get('priority') == 'critical']),
            "high_count": len([i for i in formatted_incidents if i.get('priority') == 'high'])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ADVANCED MONITOR API ---
@app.route("/api/advanced/monitors")
def get_monitors():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        monitored_apis = db.monitored_apis
        monitoring_logs = db.monitoring_logs
        
        monitors = list(monitored_apis.find().sort([("category", ASCENDING), ("url", ASCENDING)]))
        
        twenty_four_hours_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"

        for monitor in monitors:
            monitor = serialize_objectid(monitor)
            api_id = monitor["id"]
            
            # Stats
            pipeline = [
                {"$match": {"api_id": api_id, "timestamp": {"$gte": twenty_four_hours_ago}}},
                {"$group": {
                    "_id": None,
                    "avg_latency": {"$avg": "$total_latency_ms"},
                    "total_checks": {"$sum": 1},
                    "up_checks": {"$sum": {"$cond": ["$is_up", 1, 0]}}
                }}
            ]
            
            stats = list(monitoring_logs.aggregate(pipeline))
            
            if stats and stats[0].get("avg_latency") is not None:
                monitor['avg_latency_24h'] = round(stats[0]['avg_latency'], 2)
                monitor['uptime_pct_24h'] = round((stats[0]['up_checks'] / stats[0]['total_checks']) * 100, 2)
            else:
                monitor['avg_latency_24h'] = 0
                monitor['uptime_pct_24h'] = 100.0

            # Recent checks
            recent = list(monitoring_logs.find({"api_id": api_id}).sort("timestamp", DESCENDING).limit(15))
            monitor['recent_checks'] = [
                {'is_up': r['is_up'], 'timestamp': r['timestamp']} 
                for r in reversed(recent)
            ]

        return jsonify(monitors)

    except Exception as e:
        print(f"[DB ERROR] Failed to fetch dashboard monitors: {e}")
        return jsonify({"error": "Failed to retrieve monitor data from server."}), 500

@app.route("/api/advanced/add_monitor", methods=["POST"])
def add_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
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
    
    monitored_apis = db.monitored_apis
    
    # Check if URL already exists
    if monitored_apis.find_one({"url": url}):
        return jsonify({"error": "This URL is already monitored."}), 409
    
    monitor_doc = {
        "url": url,
        "api_name": data.get("api_name") or data.get("name"),
        "category": data.get("category"),
        "priority": data.get("priority", "medium"),
        "impact_score": data.get("impact_score", 50),
        "emergency_contact": data.get("emergency_contact"),
        "fallback_url": data.get("fallback_url"),
        "header_name": data.get("header_name"),
        "header_value": data.get("header_value"),
        "check_interval": data.get("check_interval"),
        "check_frequency_minutes": freq,
        "notification_email": data.get("notification_email"),
        "is_active": True,
        "last_checked_at": None,
        "last_status": "Pending"
    }
    
    monitored_apis.insert_one(monitor_doc)
    return jsonify({"success": True, "message": "Monitor added successfully."})

@app.route("/api/advanced/update_monitor", methods=["POST"])
def update_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
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
    
    monitored_apis = db.monitored_apis
    monitored_apis.update_one(
        {"_id": ObjectId(data["id"])},
        {"$set": {
            "url": url,
            "category": data.get("category"),
            "header_name": data.get("header_name"),
            "header_value": data.get("header_value"),
            "check_frequency_minutes": freq,
            "notification_email": data.get("notification_email")
        }}
    )
    
    return jsonify({"success": True, "message": "Monitor updated successfully."})

@app.route("/api/advanced/delete_monitor", methods=["POST"])
def delete_monitor():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    if "id" not in data: 
        return jsonify({"error": "'id' is required"}), 400
    
    monitored_apis = db.monitored_apis
    monitoring_logs = db.monitoring_logs
    
    api_id = data["id"]
    monitored_apis.delete_one({"_id": ObjectId(api_id)})
    monitoring_logs.delete_many({"api_id": api_id})
    
    return jsonify({"success": True})

@app.route("/api/advanced/history")
def get_history():
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    api_id = request.args.get("id")
    if not api_id: 
        return jsonify({"error": "'id' (api_id) is required"}), 400
    
    page = request.args.get("page", 1, type=int)
    per_page = 15
    
    monitoring_logs = db.monitoring_logs
    total_items = monitoring_logs.count_documents({"api_id": api_id})
    skip = (page - 1) * per_page
    
    logs = list(monitoring_logs.find({"api_id": api_id}).sort("timestamp", DESCENDING).skip(skip).limit(per_page))
    
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
def get_last_checks(api_id):
    if db is None:
        return jsonify([])
    
    monitoring_logs = db.monitoring_logs
    logs = list(monitoring_logs.find({"api_id": api_id}).sort("timestamp", DESCENDING).limit(15))
    
    result = [{"is_up": bool(log.get("is_up"))} for log in logs]
    return jsonify(result)

@app.route("/api/advanced/log_details/<log_id>")
def get_log_details(log_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    monitoring_logs = db.monitoring_logs
    log = monitoring_logs.find_one({"_id": ObjectId(log_id)})
    
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
def get_uptime_history(api_id):
    """Calculates daily uptime percentage for the last 90 days."""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    monitoring_logs = db.monitoring_logs
    ninety_days_ago = (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
    
    try:
        pipeline = [
            {"$match": {"api_id": api_id, "timestamp": {"$gte": ninety_days_ago}}},
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

# --- DEVELOPER DATA INTEGRATION APIs ---

@app.route("/api/sync/github", methods=["POST"])
def sync_github():
    """Sync commits and PRs from GitHub using stored settings"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    repo_owner = data.get("repo_owner")
    repo_name = data.get("repo_name")
    since_days = data.get("since_days", 7)
    
    # If not provided in request, get from stored settings
    if not repo_owner or not repo_name:
        settings = db.github_settings.find_one({"user_id": "default_user"})
        if settings:
            repo_owner = settings.get("repo_owner")
            repo_name = settings.get("repo_name")
    
    if not repo_owner or not repo_name:
        return jsonify({"error": "repo_owner and repo_name required. Please save settings first."}), 400
    
    # Try to get token from stored settings first, then fall back to env variable
    github_token = None
    settings = db.github_settings.find_one({"user_id": "default_user"})
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
def sync_issues():
    """Sync issues from GitHub using stored settings"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    repo_owner = data.get("repo_owner")
    repo_name = data.get("repo_name")
    
    # If not provided in request, get from stored settings
    if not repo_owner or not repo_name:
        settings = db.github_settings.find_one({"user_id": "default_user"})
        if settings:
            repo_owner = settings.get("repo_owner")
            repo_name = settings.get("repo_name")
    
    if not repo_owner or not repo_name:
        return jsonify({"error": "repo_owner and repo_name required. Please save settings first."}), 400
    
    # Try to get token from stored settings first, then fall back to env variable
    github_token = None
    settings = db.github_settings.find_one({"user_id": "default_user"})
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
def get_alert_status(api_id):
    """Get current alert status for an API (downtime alerts + AI predictions)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        result = {
            "downtime_alert": None,
            "ai_prediction": None
        }
        
        # Check for open downtime alert
        downtime_alert = db.alert_history.find_one({
            "api_id": api_id,
            "status": "open",
            "alert_type": "downtime"
        })
        
        if downtime_alert:
            result["downtime_alert"] = {
                "created_at": downtime_alert.get("created_at"),
                "github_issue_number": downtime_alert.get("github_issue_number"),
                "github_issue_url": downtime_alert.get("github_issue_url"),
                "reason": downtime_alert.get("reason")
            }
        
        # Check for AI prediction alert
        ai_alert = db.alert_history.find_one({
            "api_id": api_id,
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

        result["worker_responses"] = fetch_worker_responses(api_id, limit=5)
        # Don't try to predict on-demand, just show if alert exists
        # AI predictions happen in background every 15 mins

        return jsonify(result)
        
    except Exception as e:
        print(f"[Alert Status] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/worker-responses/<api_id>")
def get_worker_responses(api_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    limit = request.args.get("limit", 20, type=int)
    limit = min(max(limit, 1), 100)
    try:
        responses = fetch_worker_responses(api_id, limit=limit)
        return jsonify(responses)
    except Exception as e:
        print(f"[Worker Responses] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/github/create-downtime-alert", methods=["POST"])
def create_downtime_alert():
    """Create a GitHub issue for API downtime"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    api_id = data.get("api_id")
    
    if not api_id:
        return jsonify({"error": "api_id required"}), 400
    
    # Get GitHub settings
    settings = db.github_settings.find_one({"user_id": "default_user"})
    if not settings:
        return jsonify({"error": "GitHub settings not configured"}), 400
    
    repo_owner = settings.get("repo_owner")
    repo_name = settings.get("repo_name")
    github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        return jsonify({"error": "GitHub token not configured"}), 500
    
    try:
        # Get API details
        api = db.monitored_apis.find_one({"_id": ObjectId(api_id)})
        if not api:
            return jsonify({"error": "API not found"}), 404
        
        # Get latest downtime log
        latest_log = db.monitoring_logs.find_one(
            {"api_id": api_id, "is_up": False},
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
def create_incident():
    """Create a new incident report"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    
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
        "created_at": now_isoutc()
    }
    
    db.incident_reports.insert_one(incident_doc)
    serialize_objectid(incident_doc)
    
    return jsonify({"success": True, "incident": incident_doc})

@app.route("/api/incidents", methods=["GET"])
def get_incidents():
    """Get all incident reports"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    incidents = list(db.incident_reports.find().sort("created_at", -1).limit(50))
    
    for incident in incidents:
        serialize_objectid(incident)
    
    return jsonify(incidents)


# --- Phase 2 Demo Endpoints ---
@app.route("/demo/incident", methods=["GET"])
def demo_incident():
    """Return mock incident war-room payload"""
    payload = deepcopy(DEMO_INCIDENT)
    payload["chat"] = DEMO_CHAT
    payload["timeline"] = DEMO_TIMELINE
    return jsonify(payload)


@app.route("/demo/incident/chat", methods=["POST"])
def demo_incident_chat_send():
    data = request.json or {}
    message = data.get("message")
    author = data.get("author") or "Guest"
    role = data.get("role") or _get_request_role()
    if not message:
        return jsonify({"error": "message required"}), 400
    chat_entry = {
        "id": f"msg{len(DEMO_CHAT)+1}",
        "author": author,
        "role": role,
        "message": message,
        "timestamp": now_isoutc()
    }
    DEMO_CHAT.append(chat_entry)
    DEMO_TIMELINE.append({
        "type": "note",
        "label": f"{role} update",
        "detail": message,
        "timestamp": chat_entry["timestamp"]
    })
    return jsonify({"success": True, "message": chat_entry})


@app.route("/demo/incident/assign", methods=["POST"])
@require_roles(ROLE_PERMISSIONS["assign_incident"])
def demo_incident_assign():
    data = request.json or {}
    assignee = data.get("assignee") or {}
    DEMO_INCIDENT["assigned_to"] = assignee
    DEMO_TIMELINE.append({
        "type": "assign",
        "label": "Assignment Updated",
        "detail": f"Assigned to {assignee.get('name', 'Unknown')} ({assignee.get('role', 'N/A')})",
        "timestamp": now_isoutc()
    })
    return jsonify({"success": True, "incident": DEMO_INCIDENT})


@app.route("/demo/incident/status", methods=["POST"])
@require_roles(ROLE_PERMISSIONS["update_status"])
def demo_incident_status():
    data = request.json or {}
    status = data.get("status") or "Open"
    DEMO_INCIDENT["status"] = status
    DEMO_TIMELINE.append({
        "type": "status",
        "label": f"Status → {status}",
        "detail": request.demo_role,
        "timestamp": now_isoutc()
    })
    return jsonify({"success": True, "incident": DEMO_INCIDENT})


@app.route("/demo/incident/causal_graph", methods=["GET"])
def demo_causal_graph():
    graph = deepcopy(DEMO_CAUSAL_GRAPH)
    # randomize node statuses for liveliness
    for node in graph["nodes"]:
        if node["id"] == graph["root_cause"]:
            node["status"] = "critical"
        else:
            node["status"] = random.choice(["normal", "warning"])
    return jsonify(graph)


@app.route("/demo/simulation/run", methods=["POST"])
@require_roles(ROLE_PERMISSIONS["run_simulation"])
def demo_simulation_run():
    data = request.json or {}
    action_type = data.get("action_type") or "RESTART_SERVICE"
    params = data.get("params") or {}
    base_risk = 0.82
    adjustments = {
        "RESTART_SERVICE": -0.20,
        "INCREASE_TIMEOUT": -0.10,
        "ADD_DB_INDEX": -0.25,
        "REDUCE_LOAD": -0.18,
        "SWITCH_TO_BACKUP_API": -0.30,
        "CLEAN_CACHE": -0.12,
    }
    delta = adjustments.get(action_type, -0.05)
    new_risk = max(0.05, base_risk + delta + random.uniform(-0.03, 0.03))
    latency = random.randint(280, 420)
    confidence = random.uniform(0.7, 0.9)
    result = {
        "action_type": action_type,
        "params": params,
        "new_risk": round(new_risk, 2),
        "latency_ms": latency,
        "confidence": round(confidence, 2),
        "recommendation": "Scenario suggests risk drops after action; monitor DB metrics and cache hit rate.",
        "timestamp": now_isoutc()
    }
    DEMO_SIM_HISTORY.append(result)
    return jsonify(result)


@app.route("/demo/simulation/history", methods=["GET"])
def demo_simulation_history():
    return jsonify(list(reversed(DEMO_SIM_HISTORY[-10:])))


@app.route("/demo/incident/summarize", methods=["POST"])
def demo_incident_summarize():
    summary = {
        "incident_id": DEMO_INCIDENT["incident_id"],
        "summary": "DB saturation (92% CPU) triggered stale bed data. Actions: restarted replica, increased cache TTL.",
        "started_at": DEMO_INCIDENT.get("started_at"),
        "status": DEMO_INCIDENT.get("status"),
        "affected_api": DEMO_INCIDENT["api"].get("name"),
        "actions_taken": [evt for evt in DEMO_TIMELINE if evt.get("type") in {"action", "note"}],
    }
    DEMO_TIMELINE.append({
        "type": "summary",
        "label": "AI Summary Generated",
        "detail": summary["summary"],
        "timestamp": now_isoutc()
    })
    return jsonify(summary)

# --- GITHUB SETTINGS APIs ---

@app.route("/api/github/settings", methods=["POST"])
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
        settings_doc = {
            "user_id": "default_user",  # Can be extended for multi-user
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "updated_at": now_isoutc()
        }
        
        # Only update token if provided (for security, don't overwrite with empty)
        if github_token:
            settings_doc["github_token"] = github_token
        
        # Upsert: update if exists, insert if not
        db.github_settings.update_one(
            {"user_id": "default_user"},
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
def get_github_settings():
    """Get saved GitHub repository settings (token masked for security)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        settings = db.github_settings.find_one({"user_id": "default_user"})
        
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
def export_monitoring_dataset():
    """Export monitoring data as CSV and push to GitHub repository"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        # Get GitHub settings
        settings = db.github_settings.find_one({"user_id": "default_user"})
        if not settings:
            return jsonify({"error": "GitHub settings not configured. Please save settings first."}), 400
        
        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            return jsonify({"error": "GITHUB_TOKEN not configured in environment"}), 500
        
        # Get monitoring data from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        logs = list(db.monitoring_logs.find({
            "timestamp": {"$gte": thirty_days_ago.isoformat()}
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
def get_developer_context(api_id):
    """Get all developer context for an API"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        # Get latest monitoring log
        latest_log = db.monitoring_logs.find_one(
            {"api_id": api_id},
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
            {"_id": ObjectId(api_id)},
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
def predict_failure(api_id):
    """Predict if API will fail in next hour"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        ai = AIPredictor(db)
        prediction = ai.predict_failure(api_id)
        return jsonify(prediction)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/anomalies/<api_id>")
def detect_anomalies(api_id):
    """Detect anomalies in API performance"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    hours = request.args.get("hours", 24, type=int)
    
    try:
        ai = AIPredictor(db)
        anomalies = ai.detect_anomalies(api_id, hours)
        return jsonify(anomalies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/insights/<api_id>")
def get_ai_insights(api_id):
    """Get AI-generated insights and recommendations.

    This endpoint now also stores a richer, LLM-style summary in MongoDB
    (ai_insights collection) while preserving the existing card-style
    insights array used by the frontend.
    """
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    try:
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
def get_ai_insights_history(api_id):
    """Return stored AI insight history for an API from MongoDB."""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500

    try:
        history = get_ai_insights_from_db(api_id, limit=20)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/similar_incidents", methods=["POST"])
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
        app.run(port=5000, debug=True, use_reloader=False)
    except Exception as e:
        print(f"[Flask ERROR] Could not start Flask app: {e}")
