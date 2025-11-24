"""
Issue Integration Module
Fetches issues from GitHub or Jira
"""

import requests
from datetime import datetime
try:
    from security_manager import decrypt_if_needed
except Exception:
    from typing import Any
    def decrypt_if_needed(value: Any) -> Any:
        return value

class IssueIntegration:
    def __init__(self, token, mongo_db):
        # Allow encrypted token storage; decrypt if necessary
        self.token = decrypt_if_needed(token)
        self.db = mongo_db
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
    
    def fetch_github_issues(self, repo_owner, repo_name, state="all"):
        """Fetch issues from GitHub"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues"
        params = {"state": state, "per_page": 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            issues = response.json()
            
            # Filter out pull requests (GitHub API returns PRs as issues)
            issues = [issue for issue in issues if "pull_request" not in issue]
            
            print(f"[Issues] Fetched {len(issues)} issues from {repo_owner}/{repo_name}")
            
            for issue in issues:
                self.store_issue(issue, "github", repo_owner, repo_name)
            
            return {"success": True, "count": len(issues)}
        except requests.exceptions.RequestException as e:
            print(f"[Issues] Error fetching issues: {e}")
            return {"success": False, "error": str(e)}
    
    def store_issue(self, issue_data, source, repo_owner, repo_name):
        """Store issue in MongoDB"""
        try:
            issue_doc = {
                "issue_id": f"{source}_{repo_owner}_{repo_name}_{issue_data['number']}",
                "source": source,
                "repository": f"{repo_owner}/{repo_name}",
                "number": issue_data["number"],
                "title": issue_data["title"],
                "description": issue_data.get("body", ""),
                "state": issue_data["state"],
                "labels": [label["name"] for label in issue_data.get("labels", [])],
                "created_at": issue_data["created_at"],
                "updated_at": issue_data["updated_at"],
                "closed_at": issue_data.get("closed_at"),
                "url": issue_data["html_url"],
                "assigned_to": issue_data["assignee"]["login"] if issue_data.get("assignee") else None,
                "priority": self.extract_priority(issue_data.get("labels", [])),
                "related_apis": []  # Can be populated based on labels or description
            }
            
            # Upsert to avoid duplicates
            self.db.issues.update_one(
                {"issue_id": issue_doc["issue_id"]},
                {"$set": issue_doc},
                upsert=True
            )
            
        except Exception as e:
            print(f"[Issues] Error storing issue: {e}")
    
    def extract_priority(self, labels):
        """Extract priority from labels"""
        priority_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "priority: critical": "critical",
            "priority: high": "high",
            "priority: medium": "medium",
            "priority: low": "low"
        }
        
        for label in labels:
            label_name = label["name"].lower()
            if label_name in priority_map:
                return priority_map[label_name]
        
        return "medium"  # Default
    
    def get_open_issues(self):
        """Get all open issues"""
        issues = list(self.db.issues.find({
            "state": "open"
        }).sort("created_at", -1).limit(50))
        return issues
    
    def get_issues_by_api(self, api_id):
        """Get issues related to a specific API"""
        issues = list(self.db.issues.find({
            "related_apis": api_id
        }).sort("created_at", -1).limit(20))
        return issues
    
    def create_downtime_alert(self, repo_owner, repo_name, api_url, downtime_data):
        """Create a GitHub issue for API downtime alert"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues"
        
        # Build issue title
        title = f"API Downtime Alert: {api_url}"
        
        # Build detailed issue body
        body = f"""## API Downtime Detected

**API URL:** `{api_url}`  
**Status:** DOWN  
**Detected At:** {downtime_data.get('timestamp', datetime.utcnow().isoformat())}  

### Details

- **Status Code:** {downtime_data.get('status_code', 'N/A')}
- **Error Message:** {downtime_data.get('error_message', 'Connection failed')}
- **Response Time:** {downtime_data.get('total_latency_ms', 'N/A')} ms
- **URL Type:** {downtime_data.get('url_type', 'Unknown')}

### Latency Breakdown

- **DNS Latency:** {downtime_data.get('dns_latency_ms', 0)} ms
- **TCP Latency:** {downtime_data.get('tcp_latency_ms', 0)} ms
- **TLS Latency:** {downtime_data.get('tls_latency_ms', 0)} ms
- **Server Processing:** {downtime_data.get('server_processing_latency_ms', 0)} ms

### Recent History

{downtime_data.get('history_summary', 'No recent history available')}

### Recommended Actions

1. Check server logs for errors
2. Verify API endpoint configuration
3. Test network connectivity
4. Review recent code deployments
5. Check database connections

---
*This issue was automatically created by API Monitoring System*  
*Incident ID: {downtime_data.get('incident_id', 'N/A')}*
"""
        
        # Prepare issue payload
        issue_payload = {
            "title": title,
            "body": body,
            "labels": ["api-downtime", "automated", "critical"],
            "assignees": downtime_data.get('assignees', [])
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=issue_payload, timeout=10)
            response.raise_for_status()
            issue = response.json()
            
            print(f"[Issues] Created downtime alert issue #{issue['number']}: {issue['html_url']}")
            
            # Store in MongoDB
            self.store_issue(issue, "github", repo_owner, repo_name)
            
            return {
                "success": True,
                "issue_number": issue["number"],
                "issue_url": issue["html_url"],
                "message": f"GitHub issue #{issue['number']} created successfully"
            }
            
        except requests.exceptions.RequestException as e:
            print(f"[Issues] Error creating downtime alert: {e}")
            return {"success": False, "error": str(e)}
    
    def close_downtime_alert(self, repo_owner, repo_name, issue_number, resolution_message):
        """Close a downtime alert issue when API is back up"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/issues/{issue_number}"
        
        # Add comment about resolution
        comment_url = f"{url}/comments"
        comment_body = f"""## ✅ API Restored

{resolution_message}

**Resolved At:** {datetime.utcnow().isoformat()}

---
*This issue was automatically closed by API Monitoring System*
"""
        
        try:
            # Add comment
            requests.post(comment_url, headers=self.headers, json={"body": comment_body}, timeout=10)
            
            # Close issue
            response = requests.patch(url, headers=self.headers, json={"state": "closed"}, timeout=10)
            response.raise_for_status()
            
            print(f"[Issues] Closed downtime alert issue #{issue_number}")
            
            return {
                "success": True,
                "message": f"Issue #{issue_number} closed successfully"
            }
            
        except requests.exceptions.RequestException as e:
            print(f"[Issues] Error closing issue: {e}")
            return {"success": False, "error": str(e)}
