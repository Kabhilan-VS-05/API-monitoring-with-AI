"""
AI-Based Predictive Alert Manager
Trains model every 15 minutes and creates alerts for high failure predictions
"""

from datetime import datetime, timedelta
from ai_predictor import CategoryAwareAIPredictor as AIPredictor
from issue_integration import IssueIntegration
import os
import time

class AIAlertManager:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self.ai_predictor = AIPredictor(mongo_db)
        self.prediction_threshold = 0.7  # 70% probability of failure triggers alert
        self.last_training_time = {}  # Track last training time per API
        self.training_interval_minutes = 20  # Changed from 15 to 20 minutes
        
    def should_train_model(self, api_id):
        """Check if it's time to train the model for this API"""
        if api_id not in self.last_training_time:
            return True
        
        last_train = self.last_training_time[api_id]
        time_since_train = (datetime.utcnow() - last_train).total_seconds() / 60
        
        return time_since_train >= self.training_interval_minutes
    
    def train_and_predict(self, api_id):
        """
        Train model and make prediction for API
        Returns: (should_alert, prediction_data)
        """
        
        # Check if we need to train
        if not self.should_train_model(api_id):
            return False, None
        
        # Get historical data for training
        historical_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id
        }).sort("timestamp", -1).limit(1000))
        
        if len(historical_logs) < 50:
            print(f"[AI Alert] Not enough data for {api_id} (need 50, have {len(historical_logs)})")
            return False, None
        
        # Train the model
        print(f"[AI Alert] Training model for API {api_id}...")
        self.ai_predictor.train_model_for_api_category(api_id)
        self.last_training_time[api_id] = datetime.utcnow()
        
        # Make prediction
        prediction = self.ai_predictor.predict_failure(api_id)
        
        if not prediction:
            return False, None
        
        failure_probability = prediction.get("failure_probability")
        try:
            failure_probability = float(failure_probability)
        except (TypeError, ValueError):
            failure_probability = 0.0
        
        # Check if prediction is high enough to alert
        if failure_probability >= self.prediction_threshold:
            # Check if we already have an open AI prediction alert
            existing_alert = self.db.alert_history.find_one({
                "api_id": api_id,
                "status": "open",
                "alert_type": "ai_prediction"
            })
            
            if existing_alert:
                # Update existing alert with new prediction
                self.db.alert_history.update_one(
                    {"_id": existing_alert["_id"]},
                    {
                        "$set": {
                            "failure_probability": failure_probability,
                            "prediction_data": prediction,
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    }
                )
                print(f"[AI Alert] Updated existing prediction alert for {api_id}: {failure_probability:.1%}")
                return False, prediction  # Don't create new alert
            else:
                # Create new alert
                return True, prediction
        
        return False, None
    
    def create_ai_prediction_alert(self, api_id, api_url, prediction_data):
        """Create GitHub issue for AI prediction of high failure probability"""
        
        # Get GitHub settings
        settings = self.db.github_settings.find_one({"user_id": "default_user"})
        if not settings:
            print("[AI Alert] GitHub settings not configured")
            return None
        
        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
        
        if not github_token:
            print("[AI Alert] GitHub token not configured")
            return None
        
        # Build alert data
        failure_prob = prediction_data.get("failure_probability", 0)
        risk_factors = prediction_data.get("risk_factors", [])
        recommendations = prediction_data.get("recommendations", [])
        
        # Create detailed issue body
        title = f"🤖 AI Prediction: High Failure Risk for {api_url}"
        
        risk_factors_text = "\n".join([f"- {factor}" for factor in risk_factors]) if risk_factors else "- No specific risk factors identified"
        recommendations_text = "\n".join([f"{i+1}. {rec}" for i, rec in enumerate(recommendations)]) if recommendations else "1. Monitor API closely\n2. Review recent changes"
        
        body = f"""## 🤖 AI Prediction Alert

**API URL:** `{api_url}`  
**Failure Probability:** {failure_prob:.1%}  
**Prediction Time:** {datetime.utcnow().isoformat()}  
**Alert Type:** Predictive (AI-based)

### 📊 AI Analysis

The AI model has detected a **high probability of failure** for this API based on recent patterns and historical data.

**Confidence Level:** {failure_prob:.1%}

### ⚠️ Risk Factors

{risk_factors_text}

### 🔧 Recommended Actions

{recommendations_text}

### 📈 Prediction Details

- **Model Type:** Category-Aware AI Predictor
- **Training Data:** Last 1000 monitoring logs
- **Last Trained:** {datetime.utcnow().isoformat()}
- **Prediction Threshold:** 70%

### 💡 What This Means

This is a **predictive alert** - the API may not be down yet, but the AI model predicts a high likelihood of failure based on:
- Recent performance trends
- Historical failure patterns
- Latency degradation
- Error rate increases

**Action Required:** Monitor this API closely and consider proactive measures to prevent downtime.

---
*This issue was automatically created by AI Monitoring System*  
*Prediction ID: PRED-{int(time.time())}*
"""
        
        # Create GitHub issue
        issue_integration = IssueIntegration(github_token, self.db)
        
        try:
            import requests
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            issue_payload = {
                "title": title,
                "body": body,
                "labels": ["ai-prediction", "automated", "warning"]
            }
            
            response = requests.post(url, headers=headers, json=issue_payload, timeout=10)
            response.raise_for_status()
            issue = response.json()
            
            # Store in alert history
            self.db.alert_history.insert_one({
                "api_id": api_id,
                "alert_type": "ai_prediction",
                "status": "open",
                "github_issue_number": issue["number"],
                "github_issue_url": issue["html_url"],
                "failure_probability": failure_prob,
                "prediction_data": prediction_data,
                "created_at": datetime.utcnow().isoformat(),
                "prediction_id": f"PRED-{int(time.time())}"
            })
            
            print(f"[AI Alert] Created prediction alert for {api_url}: {issue['html_url']}")
            
            return {
                "success": True,
                "issue_number": issue["number"],
                "issue_url": issue["html_url"],
                "message": f"AI prediction alert created: {failure_prob:.1%} failure probability"
            }
            
        except Exception as e:
            print(f"[AI Alert] Error creating prediction alert: {e}")
            return {"success": False, "error": str(e)}
    
    def close_prediction_alert_if_stable(self, api_id):
        """Close AI prediction alert if API is now stable"""
        
        # Check for open AI prediction alert
        open_alert = self.db.alert_history.find_one({
            "api_id": api_id,
            "status": "open",
            "alert_type": "ai_prediction"
        })
        
        if not open_alert:
            return None
        
        # Check if API is stable (last 10 checks all successful)
        recent_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id
        }).sort("timestamp", -1).limit(10))
        
        all_up = all(log.get("is_up", False) for log in recent_logs)
        
        if all_up and len(recent_logs) >= 10:
            # Close the prediction alert
            settings = self.db.github_settings.find_one({"user_id": "default_user"})
            if not settings:
                return None
            
            repo_owner = settings.get("repo_owner")
            repo_name = settings.get("repo_name")
            github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
            
            if not github_token:
                return None
            
            issue_integration = IssueIntegration(github_token, self.db)
            
            resolution_message = f"""## ✅ API Stabilized

The API has been stable for the last 10 checks. The predicted failure did not occur.

**Status:** ✅ Stable  
**Resolved At:** {datetime.utcnow().isoformat()}

The AI prediction alert is being closed as the API is performing normally.

---
*This issue was automatically closed by AI Monitoring System*
"""
            
            result = issue_integration.close_downtime_alert(
                repo_owner,
                repo_name,
                open_alert.get("github_issue_number"),
                resolution_message
            )
            
            if result.get("success"):
                self.db.alert_history.update_one(
                    {"_id": open_alert["_id"]},
                    {
                        "$set": {
                            "status": "closed",
                            "resolved_at": datetime.utcnow().isoformat(),
                            "resolution": "API stabilized, prediction did not materialize"
                        }
                    }
                )
                
                print(f"[AI Alert] Closed prediction alert - API stable")
            
            return result
        
        return None
    
    def check_and_alert(self, api_id, api_url):
        """
        Main method: Train model, predict, and alert if needed
        Called every monitoring cycle
        """
        
        # First check if we should close any existing prediction alerts
        self.close_prediction_alert_if_stable(api_id)
        
        # Train and predict
        should_alert, prediction_data = self.train_and_predict(api_id)
        
        if should_alert:
            return self.create_ai_prediction_alert(api_id, api_url, prediction_data)
        
        return None
