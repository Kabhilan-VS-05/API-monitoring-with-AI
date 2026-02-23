"""
Intelligent Alert Manager
Automatically creates GitHub alerts based on smart conditions:
- Continuous downtime detection
- Root-cause aware incident grouping
- Recovery notifications
- Cooldown suppression to avoid alert spam
"""

from datetime import datetime, timedelta
import os
import time

from issue_integration import IssueIntegration


class AlertManager:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self.alert_cooldown_minutes = 15
        self.max_downtime_alerts = 2
        self.suppression_cooldown_minutes = int(os.getenv("ALERT_SUPPRESSION_COOLDOWN_MINUTES", "30"))
        self.failure_threshold = max(2, int(os.getenv("ALERT_FAILURE_THRESHOLD", "3")))

    def _api_owner_id(self, api_id):
        try:
            from bson import ObjectId
            api_doc = self.db.monitored_apis.find_one({"_id": ObjectId(api_id)}, {"user_id": 1})
            if api_doc and api_doc.get("user_id"):
                return api_doc.get("user_id")
        except Exception:
            pass
        return "default_user"

    def _get_open_incident(self, api_id, user_id=None):
        user_id = user_id or self._api_owner_id(api_id)
        return self.db.alert_incidents.find_one(
            {"api_id": api_id, "user_id": user_id, "status": "open"},
            sort=[("created_at", -1)],
        )

    def _open_or_update_incident(self, api_id, api_url, root_cause_hint=None, reason=None, user_id=None):
        now = datetime.utcnow().isoformat() + "Z"
        user_id = user_id or self._api_owner_id(api_id)
        incident = self._get_open_incident(api_id, user_id=user_id)
        if incident:
            self.db.alert_incidents.update_one(
                {"_id": incident["_id"]},
                {
                    "$set": {
                        "last_seen_at": now,
                        "root_cause_hint": root_cause_hint or incident.get("root_cause_hint"),
                        "latest_reason": reason or incident.get("latest_reason"),
                    },
                    "$inc": {"failure_events": 1},
                },
            )
            incident["last_seen_at"] = now
            incident["failure_events"] = int(incident.get("failure_events", 0)) + 1
            return incident

        incident_id = f"INC-{int(datetime.utcnow().timestamp())}"
        incident_doc = {
            "incident_id": incident_id,
            "api_id": api_id,
            "user_id": user_id,
            "api_url": api_url,
            "status": "open",
            "created_at": now,
            "last_seen_at": now,
            "failure_events": 1,
            "suppressed_alerts": 0,
            "root_cause_hint": root_cause_hint,
            "latest_reason": reason,
        }
        self.db.alert_incidents.insert_one(incident_doc)
        return incident_doc

    def _mark_incident_suppressed(self, api_id, user_id=None):
        incident = self._get_open_incident(api_id, user_id=user_id)
        if not incident:
            return
        self.db.alert_incidents.update_one(
            {"_id": incident["_id"]},
            {
                "$inc": {"suppressed_alerts": 1},
                "$set": {"last_suppressed_at": datetime.utcnow().isoformat() + "Z"},
            },
        )

    def _close_open_incident(self, api_id, resolution=None, downtime_duration=None, user_id=None):
        incident = self._get_open_incident(api_id, user_id=user_id)
        if not incident:
            return
        self.db.alert_incidents.update_one(
            {"_id": incident["_id"]},
            {
                "$set": {
                    "status": "resolved",
                    "resolved_at": datetime.utcnow().isoformat() + "Z",
                    "resolution": resolution or "Recovered",
                    "downtime_duration": downtime_duration,
                }
            },
        )

    def should_create_alert(self, api_id, current_status, api_url=None):
        """
        Send alert only when sustained failures occur.
        Group repeated failures into one incident and suppress duplicates.
        """
        if current_status not in ["Down", "Error"]:
            return False, "No alert needed"

        user_id = self._api_owner_id(api_id)
        recent_logs = list(
            self.db.monitoring_logs.find(
                {
                    "api_id": api_id,
                    "user_id": user_id,
                    "check_skipped": {"$ne": True},
                }
            )
            .sort("timestamp", -1)
            .limit(8)
        )

        consecutive_failures = self._count_consecutive_failures(recent_logs)
        latest_failure = next((log for log in recent_logs if not log.get("is_up", True)), {})
        root_cause_hint = latest_failure.get("root_cause_hint") or "unknown"
        reason = f"API {current_status}: Downtime detected (root cause hint: {root_cause_hint})"

        print(f"[Alert] API {api_id} status: {current_status}, consecutive failures: {consecutive_failures}")

        if consecutive_failures < self.failure_threshold:
            return False, "Insufficient consecutive failures"

        self._open_or_update_incident(api_id, api_url or "Unknown API", root_cause_hint=root_cause_hint, reason=reason, user_id=user_id)

        open_alert = self.db.alert_history.find_one(
            {
                "api_id": api_id,
                "user_id": user_id,
                "status": "open",
                "alert_type": "downtime",
            }
        )
        if open_alert:
            self._mark_incident_suppressed(api_id, user_id=user_id)
            print(f"[Alert] API {api_id} already has open alert #{open_alert.get('github_issue_number')}")
            return False, "Grouped into existing open incident"

        suppression_cutoff = datetime.utcnow() - timedelta(minutes=self.suppression_cooldown_minutes)
        recent_alert = self.db.alert_history.find_one(
            {
                "api_id": api_id,
                "user_id": user_id,
                "alert_type": "downtime",
                "created_at": {"$gte": suppression_cutoff.isoformat() + "Z"},
            }
        )
        if recent_alert:
            self._mark_incident_suppressed(api_id, user_id=user_id)
            return False, f"Suppressed by cooldown ({self.suppression_cooldown_minutes}m)"

        return True, reason

    def should_create_recovery_alert(self, api_id):
        """
        Should we create a recovery notification?
        Only if there was a previous downtime alert.
        Returns: (should_recover, list_of_open_alerts)
        """
        user_id = self._api_owner_id(api_id)
        open_alerts = list(
            self.db.alert_history.find(
                {
                    "api_id": api_id,
                    "user_id": user_id,
                    "status": "open",
                    "alert_type": "downtime",
                }
            )
        )

        if not open_alerts:
            return False, None

        print(f"[Alert] API {api_id} has {len(open_alerts)} open downtime alert(s)")

        recent_logs = list(
            self.db.monitoring_logs.find(
                {
                    "api_id": api_id,
                    "user_id": user_id,
                    "check_skipped": {"$ne": True},
                }
            )
            .sort("timestamp", -1)
            .limit(5)
        )

        consecutive_successes = self._count_consecutive_successes(recent_logs)
        print(f"[Alert] API {api_id} consecutive successes: {consecutive_successes}/3")

        if recent_logs:
            statuses = [("Up" if log.get("is_up", False) else "Down") for log in recent_logs]
            print(f"[Alert] Recent statuses: {statuses}")

        if consecutive_successes >= 3:
            print(f"[Alert] Creating recovery alert for API {api_id}")
            return True, open_alerts

        print(f"[Alert] Not enough successes yet ({consecutive_successes}/3)")
        return False, None

    def _is_in_cooldown(self, api_id):
        cooldown_time = datetime.utcnow() - timedelta(minutes=self.alert_cooldown_minutes)
        recent_alert = self.db.alert_history.find_one(
            {
                "api_id": api_id,
                "created_at": {"$gte": cooldown_time.isoformat()},
            }
        )
        return recent_alert is not None

    def _count_consecutive_failures(self, logs):
        count = 0
        for log in logs:
            if not log.get("is_up", True):
                count += 1
            else:
                break
        return count

    def _count_consecutive_successes(self, logs):
        count = 0
        for log in logs:
            if log.get("is_up", False):
                count += 1
            else:
                break
        return count

    def _is_outlier(self, api_id, recent_logs):
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        historical_logs = list(
            self.db.monitoring_logs.find(
                {
                    "api_id": api_id,
                    "check_skipped": {"$ne": True},
                    "timestamp": {
                        "$gte": twenty_four_hours_ago.isoformat(),
                        "$lte": one_hour_ago.isoformat(),
                    },
                }
            ).limit(100)
        )

        if len(historical_logs) < 10:
            return False

        baseline_latency = sum(log.get("total_latency_ms", 0) for log in historical_logs) / len(historical_logs)
        baseline_error_rate = sum(1 for log in historical_logs if not log.get("is_up", True)) / len(historical_logs)

        current_latency = sum(log.get("total_latency_ms", 0) for log in recent_logs[:5]) / min(5, len(recent_logs))
        current_error_rate = sum(1 for log in recent_logs[:5] if not log.get("is_up", True)) / min(5, len(recent_logs))

        latency_spike = current_latency > baseline_latency * 2
        error_spike = current_error_rate > baseline_error_rate + 0.3
        return latency_spike or error_spike

    def _has_latency_spike(self, logs):
        if len(logs) < 5:
            return False

        recent_latencies = [log.get("total_latency_ms", 0) for log in logs[:3]]
        older_latencies = [log.get("total_latency_ms", 0) for log in logs[3:6]]

        if not older_latencies:
            return False

        avg_recent = sum(recent_latencies) / len(recent_latencies)
        avg_older = sum(older_latencies) / len(older_latencies)

        return avg_recent > avg_older * 3 and avg_recent > 1000

    def create_downtime_alert(self, api_id, api_url, reason):
        print(f"[Alert] Attempting to create downtime alert for {api_url}")
        print(f"[Alert] Reason: {reason}")

        user_id = self._api_owner_id(api_id)
        settings = self.db.github_settings.find_one({"user_id": user_id})
        if not settings:
            print("[Alert] GitHub settings not configured. Please configure in Settings panel.")
            return {"success": False, "error": "GitHub settings not configured"}

        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")

        if not repo_owner or not repo_name:
            print(f"[Alert] Missing repo info: owner={repo_owner}, name={repo_name}")
            return {"success": False, "error": "Repository owner/name not configured"}

        if not github_token:
            print("[Alert] GitHub token not configured")
            return {"success": False, "error": "GitHub token not configured"}

        latest_log = self.db.monitoring_logs.find_one(
            {"api_id": api_id, "user_id": user_id, "is_up": False, "check_skipped": {"$ne": True}},
            sort=[("timestamp", -1)],
        )

        if not latest_log:
            return None

        incident = self._open_or_update_incident(
            api_id,
            api_url,
            root_cause_hint=latest_log.get("root_cause_hint"),
            reason=reason,
            user_id=user_id,
        )
        incident_id = incident.get("incident_id") if incident else f"INC-{int(time.time())}"

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
            "incident_id": incident_id,
            "history_summary": f"{reason}\n\nAPI has been down since {latest_log.get('timestamp')}",
        }

        issue_integration = IssueIntegration(github_token, self.db)
        result = issue_integration.create_downtime_alert(repo_owner, repo_name, api_url, downtime_data)

        if result.get("success"):
            self.db.alert_history.insert_one(
                {
                    "api_id": api_id,
                    "user_id": user_id,
                    "alert_type": "downtime",
                    "status": "open",
                    "github_issue_number": result.get("issue_number"),
                    "github_issue_url": result.get("issue_url"),
                    "reason": reason,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "incident_id": incident_id,
                    "root_cause_hint": latest_log.get("root_cause_hint"),
                }
            )
            if incident:
                self.db.alert_incidents.update_one(
                    {"api_id": api_id, "user_id": user_id, "status": "open"},
                    {
                        "$set": {
                            "last_alert_at": datetime.utcnow().isoformat() + "Z",
                            "github_issue_number": result.get("issue_number"),
                            "github_issue_url": result.get("issue_url"),
                        }
                    },
                )

            print(f"[Alert] Created downtime alert for {api_url}: {result.get('issue_url')}")

        return result

    def create_recovery_alert(self, api_id, api_url, open_alerts):
        user_id = self._api_owner_id(api_id)
        settings = self.db.github_settings.find_one({"user_id": user_id})
        if not settings:
            return None

        repo_owner = settings.get("repo_owner")
        repo_name = settings.get("repo_name")
        github_token = settings.get("github_token") or os.getenv("GITHUB_TOKEN")

        if not github_token:
            return None

        latest_log = self.db.monitoring_logs.find_one(
            {"api_id": api_id, "user_id": user_id, "is_up": True, "check_skipped": {"$ne": True}},
            sort=[("timestamp", -1)],
        )

        first_alert = min(open_alerts, key=lambda x: x.get("created_at", ""))
        downtime_duration = "Unknown"
        if first_alert.get("created_at") and latest_log:
            try:
                start_str = first_alert["created_at"].replace("Z", "")
                end_str = latest_log.get("timestamp").replace("Z", "")
                start = datetime.fromisoformat(start_str)
                end = datetime.fromisoformat(end_str)
                duration = end - start
                hours = duration.total_seconds() / 3600
                if hours < 1:
                    downtime_duration = f"{int(duration.total_seconds() / 60)} minutes"
                else:
                    downtime_duration = f"{hours:.1f} hours"
            except Exception as exc:
                print(f"[Alert] Error calculating duration: {exc}")
                downtime_duration = "Unknown"

        alert_numbers = [str(alert.get("github_issue_number")) for alert in open_alerts]
        resolution_message = (
            "**API Recovered Successfully**\n\n"
            f"**Total Alerts Closed:** {len(open_alerts)} (Issues: #{', #'.join(alert_numbers)})\n"
            f"**Downtime Duration:** {downtime_duration}\n"
            f"**Recovered At:** {latest_log.get('timestamp') if latest_log else 'Unknown'}\n"
            "**Current Status:** Operational\n\n"
            "The API is now responding normally and has been stable for the last 3 checks."
        )

        issue_integration = IssueIntegration(github_token, self.db)
        closed_count = 0

        for alert in open_alerts:
            result = issue_integration.close_downtime_alert(
                repo_owner,
                repo_name,
                alert.get("github_issue_number"),
                resolution_message,
            )

            if result.get("success"):
                self.db.alert_history.update_one(
                    {"_id": alert["_id"]},
                    {
                        "$set": {
                            "status": "closed",
                            "resolved_at": datetime.utcnow().isoformat() + "Z",
                            "downtime_duration": downtime_duration,
                        }
                    },
                )
                closed_count += 1

        self._close_open_incident(
            api_id,
            resolution="Recovery detected after sustained healthy checks",
            downtime_duration=downtime_duration,
            user_id=user_id,
        )

        print(f"[Alert] Closed {closed_count} recovery alerts for {api_url}")

        return {
            "success": True,
            "message": f"Closed {closed_count} alerts",
            "alerts_closed": closed_count,
        }

    def check_and_alert(self, api_id, api_url, current_status):
        """
        Main method: check for recovery first, then downtime.
        """
        should_recover, open_alerts = self.should_create_recovery_alert(api_id)
        if should_recover and open_alerts:
            return self.create_recovery_alert(api_id, api_url, open_alerts)

        should_alert, reason = self.should_create_alert(api_id, current_status, api_url=api_url)
        if should_alert:
            return self.create_downtime_alert(api_id, api_url, reason)

        return None
