"""
Intelligent Alert Manager
Automatically creates GitHub alerts based on smart conditions:
- Outlier detection (sudden changes)
- Continuous downtime (not just single failures)
- Recovery notifications
- AI-based anomaly detection
- Prevents alert spam
"""

from datetime import datetime, timedelta
from issue_integration import IssueIntegration
import os

class AlertManager:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self.alert_cooldown_minutes = 15  # Minimum time between alerts for same API
        self.max_downtime_alerts = 2  # Maximum downtime alerts before waiting for recovery
        
    def should_create_alert(self, api_id, current_status):
        """
        Simple decision: Send alert when API goes down
        Only one alert per downtime incident
        """
        
        # Check if there's already an open downtime alert
        open_alert = self.db.alert_history.find_one({
            "api_id": api_id,
            "status": "open",
            "alert_type": "downtime"
        })
        
        if open_alert:
            print(f"[Alert] API {api_id} already has open alert #{open_alert.get('github_issue_number')}")
            return False, "Alert already exists"
        
        # If API is down or error and no open alert exists, create one
        if current_status in ["Down", "Error"]:
            # Send alert immediately on first failure (changed from 3 to 1)
            recent_logs = list(self.db.monitoring_logs.find({
                "api_id": api_id
            }).sort("timestamp", -1).limit(5))
            
            consecutive_failures = self._count_consecutive_failures(recent_logs)
            print(f"[Alert] API {api_id} status: {current_status}, consecutive failures: {consecutive_failures}")
            
            if consecutive_failures >= 1:  # Changed from 3 to 1
                print(f"[Alert] 🚨 Creating downtime alert for API {api_id} (immediate alert)")
                return True, f"API {current_status}: Downtime detected"
            else:
                print(f"[Alert] No failures detected")
        
        return False, "No alert needed"
    
    def should_create_recovery_alert(self, api_id):
        """
        Should we create a recovery notification?
        Only if there was a previous downtime alert
        Returns: (should_recover, list_of_open_alerts)
        """
        
        # Check if there are ANY open GitHub issues for this API
        open_alerts = list(self.db.alert_history.find({
            "api_id": api_id,
            "status": "open",
            "alert_type": "downtime"
        }))
        
        if not open_alerts:
            # No open alerts, so no recovery needed
            return False, None
        
        print(f"[Alert] API {api_id} has {len(open_alerts)} open downtime alert(s)")
        
        # Check if API is now stable (3+ consecutive successes)
        recent_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id
        }).sort("timestamp", -1).limit(5))
        
        consecutive_successes = sum(1 for log in recent_logs if log.get("is_up", False))
        print(f"[Alert] API {api_id} consecutive successes: {consecutive_successes}/3")
        
        # Debug: Show recent log statuses
        if recent_logs:
            statuses = [("Up" if log.get("is_up", False) else "Down") for log in recent_logs]
            print(f"[Alert] Recent statuses: {statuses}")
        
        if consecutive_successes >= 3:
            print(f"[Alert] ✅ Creating recovery alert for API {api_id}")
            return True, open_alerts  # Return ALL open alerts
        else:
            print(f"[Alert] ⏸️ Not enough successes yet ({consecutive_successes}/3)")
        
        return False, None
    
    def _is_in_cooldown(self, api_id):
        """Check if we're in cooldown period (prevent alert spam)"""
        cooldown_time = datetime.utcnow() - timedelta(minutes=self.alert_cooldown_minutes)
        
        recent_alert = self.db.alert_history.find_one({
            "api_id": api_id,
            "created_at": {"$gte": cooldown_time.isoformat()}
        })
        
        return recent_alert is not None
    
    def _count_consecutive_failures(self, logs):
        """Count consecutive failures from most recent logs"""
        count = 0
        for log in logs:
            if not log.get("is_up", True):
                count += 1
            else:
                break
        return count
    
    def _is_outlier(self, api_id, recent_logs):
        """
        Detect outliers using statistical analysis
        Compare current performance with historical baseline
        """
        
        # Get historical baseline (last 24 hours, excluding recent)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        historical_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "timestamp": {
                "$gte": twenty_four_hours_ago.isoformat(),
                "$lte": one_hour_ago.isoformat()
            }
        }).limit(100))
        
        if len(historical_logs) < 10:
            return False
        
        # Calculate baseline metrics
        baseline_latency = sum(log.get("total_latency_ms", 0) for log in historical_logs) / len(historical_logs)
        baseline_error_rate = sum(1 for log in historical_logs if not log.get("is_up", True)) / len(historical_logs)
        
        # Calculate current metrics
        current_latency = sum(log.get("total_latency_ms", 0) for log in recent_logs[:5]) / min(5, len(recent_logs))
        current_error_rate = sum(1 for log in recent_logs[:5] if not log.get("is_up", True)) / min(5, len(recent_logs))
        
        # Outlier conditions
        latency_spike = current_latency > baseline_latency * 2  # 2x increase
        error_spike = current_error_rate > baseline_error_rate + 0.3  # 30% increase in errors
        
        return latency_spike or error_spike
    
    def _has_latency_spike(self, logs):
        """Detect sudden latency spikes"""
        if len(logs) < 5:
            return False
        
        recent_latencies = [log.get("total_latency_ms", 0) for log in logs[:3]]
        older_latencies = [log.get("total_latency_ms", 0) for log in logs[3:6]]
        
        if not older_latencies:
            return False
        
        avg_recent = sum(recent_latencies) / len(recent_latencies)
        avg_older = sum(older_latencies) / len(older_latencies)
        
        # Spike if recent latency is 3x older latency
        return avg_recent > avg_older * 3 and avg_recent > 1000  # and > 1 second
    
    def create_downtime_alert(self, api_id, api_url, reason):
        """Create GitHub alert for downtime"""
        
        print(f"[Alert] Attempting to create downtime alert for {api_url}")
        print(f"[Alert] Reason: {reason}")
        
        # Get GitHub settings
        settings = self.db.github_settings.find_one({"user_id": "default_user"})
        if not settings:
            print("[Alert] ❌ GitHub settings not configured. Please configure in Settings panel.")
            return {"success": False, "error": "GitHub settings not configured"}
        
        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
        
        if not repo_owner or not repo_name:
            print(f"[Alert] ❌ Missing repo info: owner={repo_owner}, name={repo_name}")
            return {"success": False, "error": "Repository owner/name not configured"}
        
        if not github_token:
            print("[Alert] ❌ GitHub token not configured")
            return {"success": False, "error": "GitHub token not configured"}
        
        # Get latest downtime log
        latest_log = self.db.monitoring_logs.find_one(
            {"api_id": api_id, "is_up": False},
            sort=[("timestamp", -1)]
        )
        
        if not latest_log:
            return None
        
        # Prepare downtime data
        import time
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
            "history_summary": f"{reason}\n\nAPI has been down since {latest_log.get('timestamp')}"
        }
        
        # Create GitHub issue
        issue_integration = IssueIntegration(github_token, self.db)
        result = issue_integration.create_downtime_alert(
            repo_owner, repo_name, api_url, downtime_data
        )
        
        if result.get("success"):
            # Record alert in history
            self.db.alert_history.insert_one({
                "api_id": api_id,
                "alert_type": "downtime",
                "status": "open",
                "github_issue_number": result.get("issue_number"),
                "github_issue_url": result.get("issue_url"),
                "reason": reason,
                "created_at": datetime.utcnow().isoformat() + 'Z',
                "incident_id": downtime_data["incident_id"]
            })
            
            print(f"[Alert] Created downtime alert for {api_url}: {result.get('issue_url')}")
        
        return result
    
    def create_recovery_alert(self, api_id, api_url, open_alerts):
        """Create ONE recovery notification and close ALL previous alerts"""
        
        settings = self.db.github_settings.find_one({"user_id": "default_user"})
        if not settings:
            return None
        
        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")
        
        if not github_token:
            return None
        
        # Get recovery time
        latest_log = self.db.monitoring_logs.find_one(
            {"api_id": api_id, "is_up": True},
            sort=[("timestamp", -1)]
        )
        
        # Calculate downtime from FIRST alert
        first_alert = min(open_alerts, key=lambda x: x.get("created_at", ""))
        downtime_duration = "Unknown"
        if first_alert.get("created_at") and latest_log:
            try:
                # Remove 'Z' suffix and parse as naive datetime
                start_str = first_alert["created_at"].replace('Z', '')
                end_str = latest_log.get("timestamp").replace('Z', '')
                start = datetime.fromisoformat(start_str)
                end = datetime.fromisoformat(end_str)
                duration = end - start
                hours = duration.total_seconds() / 3600
                if hours < 1:
                    downtime_duration = f"{int(duration.total_seconds() / 60)} minutes"
                else:
                    downtime_duration = f"{hours:.1f} hours"
            except Exception as e:
                print(f"[Alert] Error calculating duration: {e}")
                downtime_duration = "Unknown"
        
        # Build resolution message with all alert references
        alert_numbers = [str(alert.get("github_issue_number")) for alert in open_alerts]
        resolution_message = f"""**✅ API Recovered Successfully!**

**Total Alerts Closed:** {len(open_alerts)} (Issues: #{', #'.join(alert_numbers)})
**Downtime Duration:** {downtime_duration}
**Recovered At:** {latest_log.get('timestamp') if latest_log else 'Unknown'}
**Current Status:** ✅ Operational

The API is now responding normally and has been stable for the last 3 checks.

---
*All related downtime alerts have been automatically closed.*
"""
        
        # Close ALL GitHub issues
        issue_integration = IssueIntegration(github_token, self.db)
        closed_count = 0
        
        for alert in open_alerts:
            result = issue_integration.close_downtime_alert(
                repo_owner, 
                repo_name, 
                alert.get("github_issue_number"),
                resolution_message
            )
            
            if result.get("success"):
                # Update alert history
                self.db.alert_history.update_one(
                    {"_id": alert["_id"]},
                    {
                        "$set": {
                            "status": "closed",
                            "resolved_at": datetime.utcnow().isoformat() + 'Z',
                            "downtime_duration": downtime_duration
                        }
                    }
                )
                closed_count += 1
        
        print(f"[Alert] Closed {closed_count} recovery alerts for {api_url}")
        
        return {
            "success": True,
            "message": f"Closed {closed_count} alerts",
            "alerts_closed": closed_count
        }
    
    def check_and_alert(self, api_id, api_url, current_status):
        """
        Main method: Check if alert should be created and create it
        Called by monitoring system every check
        """
        
        # Check for recovery first
        should_recover, open_alerts = self.should_create_recovery_alert(api_id)
        if should_recover and open_alerts:
            return self.create_recovery_alert(api_id, api_url, open_alerts)
        
        # Check for downtime alert
        should_alert, reason = self.should_create_alert(api_id, current_status)
        if should_alert:
            return self.create_downtime_alert(api_id, api_url, reason)
        
        return None
