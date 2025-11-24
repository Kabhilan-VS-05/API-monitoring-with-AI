"""
Correlation Engine
Links monitoring events with developer data (commits, issues, logs, incidents)
"""

from datetime import datetime, timedelta
from bson import ObjectId

class CorrelationEngine:
    def __init__(self, mongo_db):
        self.db = mongo_db
    
    def correlate_monitoring_event(self, monitoring_log):
        """Find related developer data for a monitoring event"""
        try:
            timestamp = monitoring_log.get("timestamp")
            api_id = monitoring_log.get("api_id")
            
            if not timestamp or not api_id:
                return None
            
            # Parse timestamp
            event_time = datetime.fromisoformat(timestamp.replace("Z", ""))
            
            # Time window: 24 hours before the event
            time_window_start = (event_time - timedelta(hours=24)).isoformat() + "Z"
            
            # Find related commits
            related_commits = list(self.db.git_commits.find({
                "timestamp": {"$gte": time_window_start, "$lte": timestamp}
            }).sort("timestamp", -1).limit(10))
            
            # Find related issues
            related_issues = list(self.db.issues.find({
                "$or": [
                    {"related_apis": api_id},
                    {"state": "open"}  # All open issues might be relevant
                ]
            }).sort("created_at", -1).limit(5))
            
            # Find related error logs
            related_logs = list(self.db.application_logs.find({
                "timestamp": {"$gte": time_window_start, "$lte": timestamp},
                "level": {"$in": ["ERROR", "CRITICAL", "error", "critical"]}
            }).sort("timestamp", -1).limit(10))
            
            # Find similar past incidents
            related_incidents = list(self.db.incident_reports.find({
                "affected_apis": api_id
            }).sort("created_at", -1).limit(3))
            
            # Calculate correlation score
            correlation_score = self.calculate_correlation_score(
                related_commits, related_issues, related_logs, related_incidents
            )
            
            # Store correlation
            correlation_doc = {
                "timestamp": timestamp,
                "api_id": api_id,
                "monitoring_log_id": str(monitoring_log.get("_id", "")),
                "commit_ids": [c["commit_id"] for c in related_commits],
                "issue_ids": [i["issue_id"] for i in related_issues],
                "log_ids": [str(l["_id"]) for l in related_logs],
                "incident_ids": [i["incident_id"] for i in related_incidents],
                "correlation_score": correlation_score,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            result = self.db.data_correlations.insert_one(correlation_doc)
            correlation_doc["_id"] = str(result.inserted_id)
            
            print(f"[Correlation] Created correlation with score {correlation_score:.2f}")
            
            return correlation_doc
            
        except Exception as e:
            print(f"[Correlation] Error creating correlation: {e}")
            return None
    
    def calculate_correlation_score(self, commits, issues, logs, incidents):
        """Calculate how strongly events are correlated (0-1)"""
        score = 0.0
        
        # Weight factors
        score += min(len(commits) * 0.15, 0.3)      # Max 0.3 for commits
        score += min(len(issues) * 0.20, 0.3)       # Max 0.3 for issues
        score += min(len(logs) * 0.10, 0.2)         # Max 0.2 for logs
        score += min(len(incidents) * 0.10, 0.2)    # Max 0.2 for incidents
        
        return min(score, 1.0)  # Normalize to 0-1
    
    def get_correlation_by_api(self, api_id, limit=10):
        """Get correlations for a specific API"""
        correlations = list(self.db.data_correlations.find({
            "api_id": api_id
        }).sort("timestamp", -1).limit(limit))
        return correlations
    
    def get_correlation_details(self, correlation_id):
        """Get full details of a correlation with all related data"""
        try:
            correlation = self.db.data_correlations.find_one({"_id": ObjectId(correlation_id)})
            if not correlation:
                return None
            
            # Fetch related data
            commits = list(self.db.git_commits.find({
                "commit_id": {"$in": correlation.get("commit_ids", [])}
            }))
            
            issues = list(self.db.issues.find({
                "issue_id": {"$in": correlation.get("issue_ids", [])}
            }))
            
            logs = []
            for log_id in correlation.get("log_ids", []):
                try:
                    log = self.db.application_logs.find_one({"_id": ObjectId(log_id)})
                    if log:
                        logs.append(log)
                except:
                    pass
            
            incidents = list(self.db.incident_reports.find({
                "incident_id": {"$in": correlation.get("incident_ids", [])}
            }))
            
            return {
                "correlation": correlation,
                "commits": commits,
                "issues": issues,
                "logs": logs,
                "incidents": incidents
            }
            
        except Exception as e:
            print(f"[Correlation] Error getting details: {e}")
            return None
