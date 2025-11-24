import os
import subprocess
import requests
import time
from datetime import datetime

"""self_healing.py

Provides a SelfHealingManager that can attempt restarts, switch to fallback
endpoints and adjust monitoring frequency to reduce load during incidents.

This module is intentionally pragmatic: restart commands are executed via
`restart_command` fields stored in monitored_apis documents (if present).
"""


class SelfHealingManager:
    def __init__(self, db=None, mongodb_uri=None, mongodb_db=None):
        self.db = db
        # Lazy connect if db not provided
        if self.db is None and mongodb_uri and mongodb_db:
            from pymongo import MongoClient
            client = MongoClient(mongodb_uri)
            self.db = client[mongodb_db]

    def check_health(self, url, timeout=6):
        try:
            r = requests.get(url, timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    def attempt_restart(self, api_doc: dict) -> dict:
        """If `restart_command` present in api_doc, execute it and record outcome."""
        result = {"attempted": False, "success": False, "output": None}
        cmd = api_doc.get("restart_command")
        if not cmd:
            return result

        result["attempted"] = True
        try:
            # Use shell for Windows compatibility; caller must ensure safety of command
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            result["success"] = (completed.returncode == 0)
            result["output"] = (completed.stdout or "") + (completed.stderr or "")

            # Log to DB if available
            if self.db is not None:
                self.db.incident_reports.insert_one({
                    "api_id": api_doc.get("_id"),
                    "action": "restart_attempt",
                    "command": cmd,
                    "success": result["success"],
                    "output": result["output"],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })

        except Exception as e:
            result["success"] = False
            result["output"] = str(e)

        return result

    def switch_to_fallback(self, api_doc: dict) -> dict:
        """Switch monitored API to a configured fallback URL (if provided)."""
        fallback = api_doc.get("fallback_url")
        if not fallback or self.db is None:
            return {"switched": False, "reason": "no_fallback_or_db"}

        try:
            self.db.monitored_apis.update_one(
                {"_id": api_doc.get("_id")},
                {"$set": {"active_url": fallback, "is_fallback": True, "fallback_switched_at": datetime.utcnow().isoformat() + "Z"}}
            )
            return {"switched": True, "fallback": fallback}
        except Exception as e:
            return {"switched": False, "reason": str(e)}

    def adjust_monitoring_frequency(self, api_doc: dict, up=True) -> dict:
        """Adjust monitoring frequency to reduce load during incidents.
        If `up` is True, increase interval (less frequent checks);
        otherwise restore to default if available.
        """
        if self.db is None:
            return {"changed": False}

        try:
            current = api_doc.get("monitor_interval", 60)
            if up:
                new_interval = min(900, int(current * 2))
            else:
                # restore toward a default if available
                new_interval = api_doc.get("default_monitor_interval", 60)

            self.db.monitored_apis.update_one(
                {"_id": api_doc.get("_id")},
                {"$set": {"monitor_interval": new_interval, "monitor_adjusted_at": datetime.utcnow().isoformat() + "Z"}}
            )
            return {"changed": True, "monitor_interval": new_interval}
        except Exception as e:
            return {"changed": False, "error": str(e)}

    def evaluate_and_heal(self, api_doc: dict) -> dict:
        """High-level evaluation: check health, attempt restart, switch fallback and adjust frequency."""
        url = api_doc.get("active_url") or api_doc.get("url")
        if not url:
            return {"evaluated": False, "reason": "no_url"}

        healthy = self.check_health(url)
        if healthy:
            return {"evaluated": True, "healthy": True}

        # Not healthy -> attempt restart
        restart_res = self.attempt_restart(api_doc)

        # If restart unsuccessful, switch to fallback
        fallback_res = {}
        if not restart_res.get("success"):
            fallback_res = self.switch_to_fallback(api_doc)

        # Reduce monitoring frequency to reduce load
        freq_res = self.adjust_monitoring_frequency(api_doc, up=True)

        return {
            "evaluated": True,
            "healthy": False,
            "restart": restart_res,
            "fallback": fallback_res,
            "frequency": freq_res
        }
