"""
AI Prediction Engine
Simple ML-based failure prediction and anomaly detection
"""

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

class AIPredictor:
    def __init__(self, mongo_db):
        self.db = mongo_db
    
    def predict_failure(self, api_id, hours_ahead=1):
        """
        Predict if API will fail in the next N hours
        Returns: {
            "will_fail": bool,
            "confidence": float (0-1),
            "reason": str,
            "risk_score": float (0-100)
        }
        """
        try:
            # Get recent monitoring data (last 24 hours)
            time_threshold = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
            
            recent_logs = list(self.db.monitoring_logs.find({
                "api_id": api_id,
                "timestamp": {"$gte": time_threshold}
            }).sort("timestamp", -1).limit(100))
            
            if len(recent_logs) < 5:
                return {
                    "will_fail": False,
                    "confidence": 0.0,
                    "reason": "Insufficient data for prediction",
                    "risk_score": 0
                }
            
            # Calculate features
            failure_rate = sum(1 for log in recent_logs if not log.get("is_up", True)) / len(recent_logs)
            avg_latency = np.mean([log.get("total_latency_ms", 0) for log in recent_logs if log.get("total_latency_ms")])
            latency_trend = self._calculate_trend([log.get("total_latency_ms", 0) for log in recent_logs[:20]])
            error_count = sum(1 for log in recent_logs if log.get("error_message"))
            
            # Get recent commits (might indicate risky changes)
            recent_commits = list(self.db.git_commits.find({
                "timestamp": {"$gte": time_threshold}
            }).limit(10))
            
            # Calculate risk score (0-100)
            risk_score = 0
            reasons = []
            
            # Factor 1: Recent failure rate (0-30 points)
            if failure_rate > 0.3:
                risk_score += 30
                reasons.append(f"High failure rate: {failure_rate*100:.1f}%")
            elif failure_rate > 0.1:
                risk_score += 15
                reasons.append(f"Elevated failure rate: {failure_rate*100:.1f}%")
            
            # Factor 2: Latency trend (0-25 points)
            if latency_trend > 0.2:  # Increasing trend
                risk_score += 25
                reasons.append(f"Latency increasing rapidly")
            elif latency_trend > 0.1:
                risk_score += 12
                reasons.append(f"Latency trending upward")
            
            # Factor 3: High latency (0-20 points)
            if avg_latency > 5000:  # > 5 seconds
                risk_score += 20
                reasons.append(f"Very high latency: {avg_latency:.0f}ms")
            elif avg_latency > 2000:  # > 2 seconds
                risk_score += 10
                reasons.append(f"High latency: {avg_latency:.0f}ms")
            
            # Factor 4: Recent errors (0-15 points)
            if error_count > 5:
                risk_score += 15
                reasons.append(f"Multiple errors: {error_count} in 24h")
            elif error_count > 0:
                risk_score += 7
                reasons.append(f"Recent errors detected: {error_count}")
            
            # Factor 5: Recent code changes (0-10 points)
            if len(recent_commits) > 5:
                risk_score += 10
                reasons.append(f"High code change activity: {len(recent_commits)} commits")
            elif len(recent_commits) > 0:
                risk_score += 5
                reasons.append(f"Recent code changes: {len(recent_commits)} commits")
            
            # Determine prediction
            will_fail = risk_score > 50
            confidence = min(risk_score / 100, 0.95)  # Cap at 95%
            
            reason = " | ".join(reasons) if reasons else "All metrics normal"
            
            return {
                "will_fail": will_fail,
                "confidence": confidence,
                "reason": reason,
                "risk_score": min(risk_score, 100),
                "metrics": {
                    "failure_rate": failure_rate,
                    "avg_latency": avg_latency,
                    "latency_trend": latency_trend,
                    "error_count": error_count,
                    "recent_commits": len(recent_commits)
                }
            }
            
        except Exception as e:
            print(f"[AI Predictor] Error: {e}")
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": f"Prediction error: {str(e)}",
                "risk_score": 0
            }
    
    def detect_anomalies(self, api_id, hours=24):
        """
        Detect anomalous behavior in API performance
        Returns list of anomalies with timestamps and descriptions
        """
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
            threshold = mean_latency + (2 * std_latency)  # 2 standard deviations
            
            # Detect latency spikes
            for log in logs:
                latency = log.get("total_latency_ms", 0)
                if latency > threshold and latency > 1000:  # Also must be > 1 second
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
            
            # Detect error bursts (multiple errors in short time)
            error_logs = [log for log in logs if log.get("error_message")]
            if len(error_logs) > 3:
                anomalies.append({
                    "type": "error_burst",
                    "timestamp": error_logs[-1].get("timestamp"),
                    "severity": "high",
                    "description": f"Multiple errors detected: {len(error_logs)} in {hours}h",
                    "count": len(error_logs)
                })
            
            return anomalies[-10:]  # Return last 10 anomalies
            
        except Exception as e:
            print(f"[Anomaly Detection] Error: {e}")
            return []
    
    def find_similar_incidents(self, current_issue, limit=5):
        """
        Find similar past incidents using simple text matching
        Returns list of similar incidents with similarity scores
        """
        try:
            # Get all past incidents
            incidents = list(self.db.incident_reports.find().sort("created_at", -1).limit(50))
            
            if not incidents:
                return []
            
            # Simple similarity scoring based on keywords
            current_keywords = self._extract_keywords(current_issue)
            
            similar = []
            for incident in incidents:
                incident_text = f"{incident.get('title', '')} {incident.get('summary', '')} {incident.get('root_cause', '')}"
                incident_keywords = self._extract_keywords(incident_text)
                
                # Calculate similarity (Jaccard similarity)
                similarity = self._jaccard_similarity(current_keywords, incident_keywords)
                
                if similarity > 0.1:  # At least 10% similar
                    similar.append({
                        "incident": incident,
                        "similarity": similarity,
                        "matching_keywords": list(current_keywords & incident_keywords)
                    })
            
            # Sort by similarity
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar[:limit]
            
        except Exception as e:
            print(f"[Similar Incidents] Error: {e}")
            return []
    
    def generate_insights(self, api_id):
        """
        Generate AI insights and recommendations
        """
        try:
            prediction = self.predict_failure(api_id)
            anomalies = self.detect_anomalies(api_id)
            
            insights = []
            
            # Insight 1: Failure prediction
            if prediction["will_fail"]:
                insights.append({
                    "type": "warning",
                    "title": "⚠️ Failure Predicted",
                    "message": f"API likely to fail in next hour (confidence: {prediction['confidence']*100:.0f}%)",
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
            
            # Insight 3: Performance trend
            metrics = prediction.get("metrics", {})
            if metrics.get("latency_trend", 0) > 0.15:
                insights.append({
                    "type": "warning",
                    "title": "📈 Performance Degrading",
                    "message": "Latency is increasing over time",
                    "details": f"Average latency: {metrics.get('avg_latency', 0):.0f}ms",
                    "action": "Consider scaling or optimization"
                })
            
            # Insight 4: Recent changes
            if metrics.get("recent_commits", 0) > 3:
                insights.append({
                    "type": "info",
                    "title": "🔄 High Change Activity",
                    "message": f"{metrics['recent_commits']} commits in last 24h",
                    "details": "Increased risk due to code changes",
                    "action": "Verify recent deployments"
                })
            
            return insights
            
        except Exception as e:
            print(f"[Insights] Error: {e}")
            return []
    
    # Helper methods
    def _calculate_trend(self, values):
        """Calculate trend using simple linear regression slope"""
        if len(values) < 2:
            return 0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Remove zeros
        mask = y > 0
        if not mask.any():
            return 0
        
        x = x[mask]
        y = y[mask]
        
        if len(x) < 2:
            return 0
        
        # Calculate slope
        slope = np.polyfit(x, y, 1)[0]
        
        # Normalize by mean
        mean_y = np.mean(y)
        if mean_y == 0:
            return 0
        
        return slope / mean_y
    
    def _extract_keywords(self, text):
        """Extract keywords from text (simple word splitting)"""
        if not text:
            return set()
        
        # Simple keyword extraction
        words = text.lower().split()
        # Filter out common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were'}
        keywords = {word for word in words if len(word) > 3 and word not in stopwords}
        return keywords
    
    def _jaccard_similarity(self, set1, set2):
        """Calculate Jaccard similarity between two sets"""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
