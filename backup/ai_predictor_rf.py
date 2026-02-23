"""
AI Prediction Engine with Random Forest Classifier
Advanced ML-based failure prediction with continuous learning
"""

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pickle
import os

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARNING] scikit-learn not installed. Using fallback statistical methods.")

class AIPredictor:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self.model_path = "models/rf_model.pkl"
        self.scaler_path = "models/scaler.pkl"
        
        # Create models directory
        os.makedirs("models", exist_ok=True)
        
        # Load or initialize model
        if SKLEARN_AVAILABLE:
            self.model = self._load_or_create_model()
            self.scaler = self._load_or_create_scaler()
            self.use_ml = True
        else:
            self.model = None
            self.scaler = None
            self.use_ml = False
    
    def _load_or_create_model(self):
        """Load existing model or create new one"""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    model = pickle.load(f)
                print("[AI] Loaded existing Random Forest model")
                return model
            except Exception as e:
                print(f"[AI] Error loading model: {e}")
        
        # Create new model
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        print("[AI] Created new Random Forest model")
        return model
    
    def _load_or_create_scaler(self):
        """Load existing scaler or create new one"""
        if os.path.exists(self.scaler_path):
            try:
                with open(self.scaler_path, 'rb') as f:
                    scaler = pickle.load(f)
                print("[AI] Loaded existing scaler")
                return scaler
            except Exception as e:
                print(f"[AI] Error loading scaler: {e}")
        
        scaler = StandardScaler()
        print("[AI] Created new scaler")
        return scaler
    
    def _save_model(self):
        """Save trained model and scaler"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            print("[AI] Model and scaler saved")
        except Exception as e:
            print(f"[AI] Error saving model: {e}")
    
    def _extract_features(self, api_id, hours=24):
        """
        Extract features for ML model
        Returns: numpy array of features
        """
        time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        # Get monitoring logs
        recent_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", -1).limit(100))
        
        if len(recent_logs) < 5:
            return None, None
        
        # Feature 1: Failure rate
        failure_rate = sum(1 for log in recent_logs if not log.get("is_up", True)) / len(recent_logs)
        
        # Feature 2: Average latency
        latencies = [log.get("total_latency_ms", 0) for log in recent_logs if log.get("total_latency_ms")]
        avg_latency = np.mean(latencies) if latencies else 0
        
        # Feature 3: Latency standard deviation (volatility)
        latency_std = np.std(latencies) if len(latencies) > 1 else 0
        
        # Feature 4: Latency trend (slope)
        latency_trend = self._calculate_trend(latencies[:20]) if len(latencies) >= 5 else 0
        
        # Feature 5: Error count
        error_count = sum(1 for log in recent_logs if log.get("error_message"))
        
        # Feature 6: Error rate
        error_rate = error_count / len(recent_logs)
        
        # Feature 7: Recent commits (deployment risk)
        recent_commits = list(self.db.git_commits.find({
            "timestamp": {"$gte": time_threshold}
        }).limit(10))
        commit_count = len(recent_commits)
        
        # Feature 8: Recent issues
        recent_issues = list(self.db.issues.find({
            "created_at": {"$gte": time_threshold},
            "state": "open"
        }).limit(10))
        issue_count = len(recent_issues)
        
        # Feature 9: Max latency spike
        max_latency = max(latencies) if latencies else 0
        
        # Feature 10: Min latency
        min_latency = min(latencies) if latencies else 0
        
        # Feature 11: Latency range
        latency_range = max_latency - min_latency
        
        # Feature 12: Recent failure streak
        failure_streak = 0
        for log in recent_logs:
            if not log.get("is_up", True):
                failure_streak += 1
            else:
                break
        
        # Feature 13: Time since last failure (hours)
        time_since_failure = 24  # default
        for log in recent_logs:
            if not log.get("is_up", True):
                log_time = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
                time_since_failure = (datetime.now(log_time.tzinfo) - log_time).total_seconds() / 3600
                break
        
        # Feature 14: Average DNS latency
        dns_latencies = [log.get("dns_latency_ms", 0) for log in recent_logs if log.get("dns_latency_ms")]
        avg_dns = np.mean(dns_latencies) if dns_latencies else 0
        
        # Feature 15: Average server processing time
        server_times = [log.get("server_processing_latency_ms", 0) for log in recent_logs if log.get("server_processing_latency_ms")]
        avg_server = np.mean(server_times) if server_times else 0
        
        features = np.array([
            failure_rate,
            avg_latency,
            latency_std,
            latency_trend,
            error_count,
            error_rate,
            commit_count,
            issue_count,
            max_latency,
            min_latency,
            latency_range,
            failure_streak,
            time_since_failure,
            avg_dns,
            avg_server
        ])
        
        # Determine label (for training)
        # Label = 1 if failure rate > 20% or recent failure streak > 2
        label = 1 if (failure_rate > 0.2 or failure_streak > 2) else 0
        
        return features, label
    
    def train_model(self, api_ids=None):
        """
        Train the Random Forest model on historical data
        """
        if not self.use_ml:
            print("[AI] scikit-learn not available, skipping training")
            return False
        
        print("[AI] Starting model training...")
        
        # Get all API IDs if not specified
        if api_ids is None:
            api_ids = [doc["_id"] for doc in self.db.monitored_apis.find({}, {"_id": 1})]
            api_ids = [str(id) for id in api_ids]
        
        if not api_ids:
            print("[AI] No APIs to train on")
            return False
        
        # Collect training data
        X_train = []
        y_train = []
        
        for api_id in api_ids:
            features, label = self._extract_features(api_id)
            if features is not None:
                X_train.append(features)
                y_train.append(label)
        
        if len(X_train) < 10:
            print(f"[AI] Insufficient training data: {len(X_train)} samples")
            return False
        
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Save model
        self._save_model()
        
        # Calculate accuracy
        train_score = self.model.score(X_train_scaled, y_train)
        print(f"[AI] Model trained on {len(X_train)} samples")
        print(f"[AI] Training accuracy: {train_score*100:.2f}%")
        
        # Feature importance
        feature_names = [
            "failure_rate", "avg_latency", "latency_std", "latency_trend",
            "error_count", "error_rate", "commit_count", "issue_count",
            "max_latency", "min_latency", "latency_range", "failure_streak",
            "time_since_failure", "avg_dns", "avg_server"
        ]
        importances = self.model.feature_importances_
        top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:5]
        print("[AI] Top 5 important features:")
        for name, importance in top_features:
            print(f"  - {name}: {importance*100:.2f}%")
        
        return True
    
    def predict_failure(self, api_id, hours_ahead=1):
        """
        Predict if API will fail in the next N hours using Random Forest
        """
        try:
            features, _ = self._extract_features(api_id)
            
            if features is None:
                return {
                    "will_fail": False,
                    "confidence": 0.0,
                    "reason": "Insufficient data for prediction",
                    "risk_score": 0,
                    "method": "none"
                }
            
            if self.use_ml and hasattr(self.model, 'predict_proba'):
                # Use Random Forest prediction
                features_scaled = self.scaler.transform(features.reshape(1, -1))
                prediction = self.model.predict(features_scaled)[0]
                probabilities = self.model.predict_proba(features_scaled)[0]
                
                will_fail = bool(prediction == 1)
                confidence = float(probabilities[1])  # Probability of failure
                risk_score = int(confidence * 100)
                
                # Get feature contributions
                reason = self._explain_prediction(features, confidence)
                
                return {
                    "will_fail": will_fail,
                    "confidence": confidence,
                    "reason": reason,
                    "risk_score": risk_score,
                    "method": "random_forest",
                    "model_accuracy": "trained" if hasattr(self.model, 'n_estimators') else "untrained"
                }
            else:
                # Fallback to statistical method
                return self._statistical_prediction(features)
        
        except Exception as e:
            print(f"[AI] Prediction error: {e}")
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": f"Prediction error: {str(e)}",
                "risk_score": 0,
                "method": "error"
            }
    
    def _statistical_prediction(self, features):
        """Fallback statistical prediction method"""
        failure_rate = features[0]
        avg_latency = features[1]
        latency_trend = features[3]
        error_count = features[4]
        commit_count = features[6]
        failure_streak = features[11]
        
        # Calculate risk score
        risk_score = 0
        risk_score += min(failure_rate * 100, 30)
        risk_score += min(latency_trend * 25, 25)
        risk_score += min(avg_latency / 100, 20)
        risk_score += min(error_count * 3, 15)
        risk_score += min(commit_count * 2, 10)
        
        risk_score = int(min(risk_score, 100))
        will_fail = risk_score > 70
        confidence = risk_score / 100
        
        reasons = []
        if failure_rate > 0.2:
            reasons.append(f"High failure rate: {failure_rate*100:.1f}%")
        if avg_latency > 1000:
            reasons.append(f"High latency: {avg_latency:.0f}ms")
        if latency_trend > 0.1:
            reasons.append("Latency increasing")
        if error_count > 5:
            reasons.append(f"{error_count} errors detected")
        if commit_count > 0:
            reasons.append(f"Recent code changes: {commit_count} commits")
        if failure_streak > 0:
            reasons.append(f"Failure streak: {failure_streak}")
        
        reason = " | ".join(reasons) if reasons else "Normal operation"
        
        return {
            "will_fail": will_fail,
            "confidence": confidence,
            "reason": reason,
            "risk_score": risk_score,
            "method": "statistical"
        }
    
    def _explain_prediction(self, features, confidence):
        """Generate human-readable explanation"""
        feature_names = [
            "failure_rate", "avg_latency", "latency_std", "latency_trend",
            "error_count", "error_rate", "commit_count", "issue_count",
            "max_latency", "min_latency", "latency_range", "failure_streak",
            "time_since_failure", "avg_dns", "avg_server"
        ]
        
        reasons = []
        
        if features[0] > 0.2:  # failure_rate
            reasons.append(f"High failure rate: {features[0]*100:.1f}%")
        if features[1] > 1000:  # avg_latency
            reasons.append(f"High latency: {features[1]:.0f}ms")
        if features[3] > 0.1:  # latency_trend
            reasons.append("Latency increasing")
        if features[4] > 5:  # error_count
            reasons.append(f"{int(features[4])} errors detected")
        if features[6] > 0:  # commit_count
            reasons.append(f"Recent code changes: {int(features[6])} commits")
        if features[11] > 2:  # failure_streak
            reasons.append(f"Failure streak: {int(features[11])}")
        if features[7] > 0:  # issue_count
            reasons.append(f"{int(features[7])} open issues")
        
        if not reasons:
            reasons.append("Normal operation")
        
        return " | ".join(reasons)
    
    def _calculate_trend(self, values):
        """Calculate linear trend (slope)"""
        if len(values) < 2:
            return 0
        x = np.arange(len(values))
        y = np.array(values)
        if len(x) > 0 and len(y) > 0:
            slope = np.polyfit(x, y, 1)[0]
            return float(slope)
        return 0
    
    def detect_anomalies(self, api_id, hours=24):
        """Detect anomalies in API performance"""
        try:
            time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
            
            logs = list(self.db.monitoring_logs.find({
                "api_id": api_id,
                "timestamp": {"$gte": time_threshold}
            }).sort("timestamp", 1))
            
            if len(logs) < 10:
                return []
            
            anomalies = []
            
            # Calculate baseline metrics
            latencies = [log.get("total_latency_ms", 0) for log in logs if log.get("total_latency_ms")]
            if not latencies:
                return []
            
            mean_latency = np.mean(latencies)
            std_latency = np.std(latencies)
            threshold = mean_latency + (2 * std_latency)
            
            # Detect latency spikes
            for log in logs:
                latency = log.get("total_latency_ms", 0)
                if latency > threshold and latency > 1000:
                    anomalies.append({
                        "type": "latency_spike",
                        "timestamp": log.get("timestamp"),
                        "severity": "high" if latency > threshold * 1.5 else "medium",
                        "description": f"Latency spike: {latency:.0f}ms (normal: {mean_latency:.0f}ms)",
                        "value": latency,
                        "expected": mean_latency
                    })
            
            # Detect sudden failures
            for i in range(1, len(logs)):
                prev_up = logs[i-1].get("is_up", True)
                curr_up = logs[i].get("is_up", True)
                
                if prev_up and not curr_up:
                    anomalies.append({
                        "type": "sudden_failure",
                        "timestamp": logs[i].get("timestamp"),
                        "severity": "critical",
                        "description": "API went down unexpectedly",
                        "error": logs[i].get("error_message", "Unknown error")
                    })
            
            # Detect error bursts
            error_logs = [log for log in logs if log.get("error_message")]
            if len(error_logs) > 3:
                anomalies.append({
                    "type": "error_burst",
                    "timestamp": error_logs[-1].get("timestamp"),
                    "severity": "high",
                    "description": f"Multiple errors detected: {len(error_logs)} in {hours}h",
                    "count": len(error_logs)
                })
            
            return anomalies[-10:]
            
        except Exception as e:
            print(f"[Anomaly Detection] Error: {e}")
            return []
    
    def generate_insights(self, api_id):
        """Generate AI insights and recommendations"""
        try:
            prediction = self.predict_failure(api_id)
            anomalies = self.detect_anomalies(api_id)
            
            insights = []
            
            # Insight 1: Failure prediction
            if prediction["will_fail"]:
                insights.append({
                    "type": "warning",
                    "title": "⚠️ Failure Predicted (ML)",
                    "message": f"Random Forest predicts failure (confidence: {prediction['confidence']*100:.0f}%)",
                    "details": prediction["reason"],
                    "action": "Review recent changes and monitor closely"
                })
            elif prediction["risk_score"] > 30:
                insights.append({
                    "type": "info",
                    "title": "ℹ️ Elevated Risk",
                    "message": f"Risk score: {prediction['risk_score']}/100",
                    "details": prediction["reason"],
                    "action": "Monitor performance metrics"
                })
            
            # Insight 2: Anomalies
            if anomalies:
                critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
                if critical_anomalies:
                    insights.append({
                        "type": "error",
                        "title": "🚨 Critical Anomalies Detected",
                        "message": f"{len(critical_anomalies)} critical issues found",
                        "details": "; ".join([a["description"] for a in critical_anomalies[:3]]),
                        "action": "Investigate immediately"
                    })
            
            # Insight 3: ML model status
            if self.use_ml:
                insights.append({
                    "type": "info",
                    "title": "🤖 ML Model Active",
                    "message": f"Using Random Forest Classifier",
                    "details": f"Method: {prediction.get('method', 'unknown')}",
                    "action": "Model continuously learning from data"
                })
            
            return insights
            
        except Exception as e:
            print(f"[Insights] Error: {e}")
            return []
    
    def find_similar_incidents(self, current_issue, limit=5):
        """Find similar past incidents"""
        try:
            incidents = list(self.db.incident_reports.find().sort("created_at", -1).limit(50))
            
            if not incidents:
                return []
            
            current_keywords = self._extract_keywords(current_issue)
            
            similar = []
            for incident in incidents:
                incident_text = f"{incident.get('title', '')} {incident.get('summary', '')} {incident.get('root_cause', '')}"
                incident_keywords = self._extract_keywords(incident_text)
                
                similarity = self._jaccard_similarity(current_keywords, incident_keywords)
                
                if similarity > 0.1:
                    similar.append({
                        "incident": incident,
                        "similarity": similarity,
                        "matching_keywords": list(current_keywords & incident_keywords)
                    })
            
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar[:limit]
            
        except Exception as e:
            print(f"[Similar Incidents] Error: {e}")
            return []
    
    def _extract_keywords(self, text):
        """Extract keywords from text"""
        if not text:
            return set()
        
        words = text.lower().split()
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were'}
        keywords = {word for word in words if len(word) > 3 and word not in stopwords}
        return keywords
    
    def _jaccard_similarity(self, set1, set2):
        """Calculate Jaccard similarity"""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
