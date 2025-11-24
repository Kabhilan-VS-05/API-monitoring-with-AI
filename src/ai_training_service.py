"""
Separate AI Training Service
Runs on a different port (5001) to handle AI training without blocking main app
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import os
import sys
from datetime import datetime, timedelta
import requests
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_predictor import CategoryAwareAIPredictor as AIPredictor
from ai_alert_manager import AIAlertManager

app = Flask(__name__)
CORS(app)

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "api_monitoring")

# Global MongoDB client
mongo_client = None
db = None

# Store training status for each API
training_status = {}
MAIN_APP_URL = os.getenv("MAIN_APP_URL", "http://localhost:5000")


def fetch_worker_feedback(api_id, lookback_hours=24, limit=20):
    if db is None or not api_id:
        return []
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    cursor = db.worker_responses.find({
        "api_id": api_id,
        "timestamp": {"$gte": cutoff.isoformat() + "Z"}
    }).sort("timestamp", DESCENDING).limit(limit)
    return list(cursor)


def apply_worker_feedback_calibration(failure_prob, responses):
    if not responses:
        return failure_prob, "no_feedback"

    latest = responses[0]
    response_type = latest.get("response")
    if response_type == "FIXED":
        return max(failure_prob * 0.8, 0.0), "feedback_fixed"
    if response_type == "NEED_HELP":
        return min(failure_prob * 1.2, 1.0), "feedback_need_help"
    if response_type == "RETRY":
        return min(failure_prob * 1.05, 1.0), "feedback_retry"
    return failure_prob, "feedback_unknown"


def publish_training_run(payload):
    try:
        resp = requests.post(f"{MAIN_APP_URL}/api/ai/training_runs", json=payload, timeout=5)
        if not resp.ok:
            print(f"[AI Training Service] Warning: main app rejected training run ({resp.status_code}) {resp.text}")
    except Exception as exc:
        print(f"[AI Training Service] Could not publish training run: {exc}")

def init_mongodb():
    """Initialize MongoDB connection"""
    global mongo_client, db
    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client.server_info()
        db = mongo_client[MONGODB_DB]
        print(f"[AI Training Service] Connected to MongoDB: {MONGODB_DB}")
        return True
    except Exception as e:
        print(f"[AI Training Service] MongoDB connection failed: {e}")
        return False

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "service": "AI Training Service",
        "port": 5001,
        "mongodb_connected": db is not None
    })

@app.route("/training/status/<api_id>", methods=["GET"])
def get_training_status(api_id):
    """Get current training status for an API"""
    status = training_status.get(api_id, {
        "status": "idle",
        "message": "No training in progress"
    })
    return jsonify(status)

@app.route("/train/full", methods=["POST"])
def train_full():
    """
    Full training mode - Always uses complete 50 epochs
    - Full epochs (50)
    - Complete training process
    - Sends alerts if high risk detected
    - Returns comprehensive results
    """
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    data = request.json or {}
    api_id = data.get("api_id")
    force_retrain = data.get("force_retrain", True)
    
    if not api_id:
        return jsonify({"error": "api_id required"}), 400
    
    try:
        print("=" * 60)
        print(f"[AI Training Service] FULL TRAINING STARTED")
        print(f"[AI Training Service] API ID: {api_id}")
        print(f"[AI Training Service] Epochs: 50 (Full Training)")
        print(f"[AI Training Service] Force Retrain: {force_retrain}")
        print("=" * 60)
        
        start_time = datetime.utcnow()
        training_session_id = str(uuid.uuid4())

        def _update_status(status, message, progress, stage=None, extra=None):
            payload = {
                "status": status,
                "message": message,
                "progress": float(max(0.0, min(progress, 100.0))),
                "stage": stage,
                "started_at": start_time.isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            if extra:
                payload.update(extra)
            training_status[api_id] = payload

        _update_status(
            "starting",
            "Initializing AI training environment...",
            progress=2.0,
            stage="starting"
        )

        def progress_callback(stage, progress, message):
            _update_status(
                "training",
                message,
                progress,
                stage=stage
            )

        ai = AIPredictor(db)
        result = ai.train_model_for_api_category(
            api_id,
            force_retrain=force_retrain,
            progress_callback=progress_callback
        )

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        if result:
            _update_status(
                "analyzing",
                "Generating AI predictions...",
                progress=92.0,
                stage="analyzing"
            )
            
            print("=" * 60)
            print(f"[AI Training Service] ✅ TRAINING COMPLETED")
            print(f"[AI Training Service] Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            print("=" * 60)
            
            # Get comprehensive prediction results
            prediction_result = None
            alert_sent = False
            risk_level = "unknown"
            
            try:
                prediction = ai.predict_failure(api_id)
                
                if prediction:
                    failure_prob = prediction.get('failure_probability')
                    confidence = prediction.get('confidence')

                    try:
                        failure_prob = float(failure_prob)
                    except (TypeError, ValueError):
                        failure_prob = 0.0

                    try:
                        confidence = float(confidence)
                    except (TypeError, ValueError):
                        confidence = 0.0
                    risk_factors = prediction.get('risk_factors', [])
                    
                    worker_feedback = fetch_worker_feedback(api_id)
                    failure_prob, feedback_tag = apply_worker_feedback_calibration(failure_prob, worker_feedback)
                    feedback_summary = {
                        "tag": feedback_tag,
                        "count": len(worker_feedback),
                        "latest": worker_feedback[0] if worker_feedback else None
                    }
                    print(f"[AI Training Service] Worker feedback tag: {feedback_tag}, samples: {len(worker_feedback)}")
                    
                    # Determine risk level
                    if failure_prob >= 0.70:
                        risk_level = "high"
                    elif failure_prob >= 0.40:
                        risk_level = "medium"
                    else:
                        risk_level = "low"
                    
                    print(f"[AI Training Service] PREDICTION RESULTS:")
                    print(f"[AI Training Service]   - Failure Probability: {failure_prob*100:.1f}%")
                    print(f"[AI Training Service]   - Confidence: {confidence*100:.1f}%")
                    print(f"[AI Training Service]   - Risk Level: {risk_level.upper()}")
                    print(f"[AI Training Service]   - Risk Factors: {len(risk_factors)}")
                    
                    # Send alert if high or moderate risk
                    if failure_prob >= 0.40:  
                        if failure_prob >= 0.70:
                            print(f"[AI Training Service] HIGH RISK DETECTED!")
                        else:
                            print(f"[AI Training Service] MODERATE RISK DETECTED!")
                        
                        # Check if alert already exists
                        existing_alert = db.alert_history.find_one({
                            "api_id": api_id,
                            "alert_type": "ai_prediction",
                            "status": "open"
                        })
                        
                        if not existing_alert:
                            print(f"[AI Training Service] Sending AI prediction alert...")
                            ai_alert_mgr = AIAlertManager(db)
                            ai_alert_mgr.check_and_alert_single_api(api_id)
                            alert_sent = True
                            print(f"[AI Training Service] Alert sent successfully")
                            
                            # Create GitHub issue for high/moderate risk
                            try:
                                print(f"[AI Training Service] Creating GitHub issue...")
                                from github_integration import GitHubIntegration
                                
                                # Get API details
                                api_doc = db.monitored_apis.find_one({"_id": ObjectId(api_id)})
                                if api_doc:
                                    api_url = api_doc.get('url', 'Unknown API')
                                    api_category = api_doc.get('category', 'Uncategorized')
                                    
                                    # Create detailed GitHub issue
                                    github = GitHubIntegration(db)
                                    
                                    # Build issue title
                                    risk_emoji = "" if failure_prob >= 0.70 else ""
                                    title = f"{risk_emoji} AI Alert: {risk_level.upper()} Risk - {api_category} API"
                                    
                                    # Build issue body
                                    body = f"""## AI-Powered Failure Prediction Alert

### Prediction Details
- **API Endpoint:** `{api_url}`
- **Category:** {api_category}
- **Risk Level:** {risk_level.upper()}
- **Failure Probability:** {failure_prob*100:.1f}%
- **Confidence:** {confidence*100:.1f}%
- **Risk Score:** {int(failure_prob*100)}/100

### Analysis
LSTM neural network detected concerning patterns in API behavior.

**Status:** {"HIGH ALERT - Immediate action required" if failure_prob >= 0.70 else "MODERATE RISK - Monitor closely"}

### Risk Factors
"""
                                    if risk_factors:
                                        for factor in risk_factors[:5]:  
                                            body += f"- {factor}\n"
                                    else:
                                        body += "- Pattern anomalies detected\n- Historical trend analysis indicates increased failure risk\n"
                                    
                                    body += f"""
### Recommended Actions
1. **Review Recent Changes:** Check recent deployments and code changes
2. **Monitor Metrics:** Watch latency, error rates, and resource usage
3. **Check Dependencies:** Verify all external services are healthy
4. **Review Logs:** Look for error patterns or warnings
5. **Consider Rollback:** If issues persist, consider rolling back recent changes

### Detection Time
{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

---
*This issue was automatically created by the AI Co-Pilot monitoring system.*
*Training completed in {duration:.1f} seconds with {confidence*100:.1f}% confidence.*
"""
                                    
                                    # Create the issue
                                    issue_result = github.create_issue_for_api_failure(
                                        api_id=api_id,
                                        title=title,
                                        description=body,
                                        labels=["ai-prediction", risk_level + "-risk", "automated-alert"]
                                    )
                                    
                                    if issue_result and issue_result.get('success'):
                                        issue_url = issue_result.get('issue_url')
                                        issue_number = issue_result.get('issue_number')
                                        print(f"[AI Training Service] GitHub issue created: #{issue_number}")
                                        print(f"[AI Training Service] URL: {issue_url}")
                                        
                                        # Update alert with GitHub info
                                        db.alert_history.update_one(
                                            {"api_id": api_id, "alert_type": "ai_prediction", "status": "open"},
                                            {"$set": {
                                                "github_issue_url": issue_url,
                                                "github_issue_number": issue_number
                                            }}
                                        )
                                    else:
                                        print(f"[AI Training Service] GitHub issue creation failed")
                                        
                            except Exception as github_error:
                                print(f"[AI Training Service] GitHub error: {github_error}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"[AI Training Service] Alert already exists (not sending duplicate)")
                    else:
                        print(f"[AI Training Service] Risk is {risk_level.upper()}, no alert needed")
                    
                    prediction_result = {
                        "failure_probability": failure_prob,
                        "failure_probability_percent": round(failure_prob * 100, 1),
                        "confidence": confidence,
                        "confidence_percent": round(confidence * 100, 1),
                        "risk_level": risk_level,
                        "risk_factors": risk_factors,
                        "worker_feedback": feedback_summary,
                        "alert_sent": alert_sent
                    }
                    
            except Exception as alert_error:
                print(f"[AI Training Service] Error with prediction/alert: {alert_error}")
                import traceback
                traceback.print_exc()
            
            print("=" * 60)
            
            # Update status: Completed
            _update_status(
                "completed",
                "Training completed successfully!",
                progress=100.0,
                stage="completed",
                extra={
                    "completed_at": end_time.isoformat(),
                    "duration_seconds": round(duration, 1),
                    "prediction": prediction_result
                }
            )
            
            if prediction_result:
                failure_prob = prediction_result.get("failure_probability", 0.0)
                confidence = prediction_result.get("confidence", 0.0)
                risk_level_str = (prediction_result.get("risk_level") or "unknown").upper()
                summary_text = (
                    f"Failure probability {failure_prob*100:.1f}% · Confidence {confidence*100:.1f}% · Risk level {risk_level_str}"
                )

                log_lines = [
                    "[AI] ========== PREDICTION BREAKDOWN ==========" ,
                    f"[AI] Failure Probability: {failure_prob*100:.1f}%",
                    f"[AI] Confidence: {confidence*100:.1f}%",
                    f"[AI] Risk Level: {risk_level_str}",
                    f"[AI Training Service] Duration: {round(duration, 1)}s",
                    f"[AI Training Service] Risk Factors: {len(risk_factors)}",
                    f"[AI Training Service] {'✅ Risk is LOW, no alert needed' if risk_level == 'low' else '🚨 Alert evaluated'}"
                ]

                training_payload = {
                    "api_id": api_id,
                    "training_session_id": training_session_id,
                    "mode": "full",
                    "status": "completed",
                    "started_at": start_time.isoformat(),
                    "completed_at": end_time.isoformat(),
                    "duration_seconds": round(duration, 1),
                    "duration_minutes": round(duration / 60, 1),
                    "failure_probability": failure_prob,
                    "confidence": confidence,
                    "risk_level": risk_level,
                    "risk_score": prediction.get("risk_score"),
                    "sample_size": prediction.get("sample_size"),
                    "model_metadata": {
                        "model_name": prediction.get("model"),
                        "model_version": prediction.get("model_version"),
                        "last_trained": prediction.get("last_trained"),
                        "accuracy": prediction.get("model_accuracy"),
                        "auc": prediction.get("model_auc")
                    },
                    "prediction": prediction,
                    "metrics": {
                        "lstm_score": prediction.get("lstm_score"),
                        "anomaly_score": prediction.get("anomaly_score"),
                        "combined_score": prediction.get("combined_score"),
                        "calibrated_score": prediction.get("calibrated_score"),
                        "actual_failure_rate": prediction.get("actual_failure_rate"),
                        "calibration_factor": prediction.get("calibration_factor"),
                        "agreement": prediction.get("agreement"),
                        "data_quality": prediction.get("data_quality"),
                        "sample_size": prediction.get("sample_size")
                    },
                    "risk_factors": risk_factors,
                    "log_lines": log_lines,
                    "summary": summary_text,
                    "actions": [
                        "Review recent deployments and code changes.",
                        "Monitor latency, error, and status metrics closely.",
                        "Inspect logs and tracing data for anomalies."
                    ],
                    "alert_sent": alert_sent,
                    "created_at": end_time.isoformat()
                }

                publish_training_run(training_payload)
            
            return jsonify({
                "success": True,
                "mode": "full",
                "epochs": 50,
                "message": "Full training completed successfully",
                "duration_seconds": round(duration, 1),
                "duration_minutes": round(duration / 60, 1),
                "prediction": prediction_result,
                "timestamp": end_time.isoformat()
            })
        else:
            print("=" * 60)
            print(f"[AI Training Service] ⚠️  TRAINING SKIPPED")
            print(f"[AI Training Service] Reason: Insufficient data")
            print("=" * 60)
            
            # Update status: Skipped
            _update_status(
                "skipped",
                "Training skipped (insufficient data)",
                progress=0.0,
                stage="skipped"
            )
            
            return jsonify({
                "success": False,
                "mode": "full",
                "message": "Training skipped (insufficient data)",
                "duration_seconds": round(duration, 1)
            })
            
    except Exception as e:
        print("=" * 60)
        print(f"[AI Training Service] ❌ TRAINING ERROR")
        print(f"[AI Training Service] Error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        
        # Update status: Error
        training_status[api_id] = {
            "status": "error",
            "message": f"Training error: {str(e)}",
            "progress": 0,
            "error": str(e),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/training_runs/<api_id>", methods=["GET"])
def get_training_runs(api_id):
    """Get AI training runs for a specific API."""
    print(f"[AI Training Service] Received request for training runs of API: {api_id}")
    
    try:
        limit = int(request.args.get("limit", 15))
        print(f"[AI Training Service] Query limit: {limit}")
        
        # Check if database is available
        if db is None:
            print("[AI Training Service] Database not available")
            return jsonify([]), 500
        
        # Check if collection exists
        if "ai_training_runs" not in db.list_collection_names():
            print("[AI Training Service] ai_training_runs collection not found")
            return jsonify([])
        
        # Query training runs from database
        runs = list(db.ai_training_runs.find(
            {"api_id": api_id},
            {"_id": 0}
        ).sort("started_at", -1).limit(limit))
        
        print(f"[AI Training Service] Found {len(runs)} training runs")
        
        if not runs:
            print("[AI Training Service] No training runs found for this API")
            return jsonify([])
        
        return jsonify(runs)
        
    except Exception as e:
        print(f"[AI Training Service] Error fetching training runs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 500

@app.route("/debug/routes", methods=["GET"])
def debug_routes():
    """Debug endpoint to list all registered routes."""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "rule": str(rule)
        })
    return jsonify({"routes": routes})

if __name__ == "__main__":
    print("=" * 60)
    print("AI TRAINING SERVICE - Separate Port (5001)")
    print("=" * 60)
    print("This service handles AI model training independently")
    print("Main app runs on port 5000 and stays responsive")
    print("=" * 60)
    
    # Initialize MongoDB
    if init_mongodb():
        print("[AI Training Service] Ready to accept training requests")
        print("[AI Training Service] Training Mode: FULL (50 epochs)")
        print("[AI Training Service] Endpoints:")
        print("  - POST /train/full")
        print("  - GET /api/ai/training_runs/<api_id>")
        print("  - GET /health")
        print("=" * 60)
        
        # Run on port 5001
        app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
    else:
        print("[AI Training Service] Failed to start - MongoDB not available")
        sys.exit(1)
