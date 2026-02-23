"""
GitHub Integration Module
Fetches commits, pull requests, and related data from GitHub API
"""

import requests
from datetime import datetime, timedelta
import os

class GitHubIntegration:
    def __init__(self, token, mongo_db):
        self.token = token
        self.db = mongo_db
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
    
    def fetch_commits(self, repo_owner, repo_name, since_days=7):
        """Fetch commits from the last N days"""
        since_date = (datetime.utcnow() - timedelta(days=since_days)).isoformat() + "Z"
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/commits"
        params = {"since": since_date, "per_page": 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            commits = response.json()
            
            print(f"[GitHub] Fetched {len(commits)} commits from {repo_owner}/{repo_name}")
            
            for commit in commits:
                self.store_commit(commit, repo_owner, repo_name)
            
            return {"success": True, "count": len(commits)}
        except requests.exceptions.RequestException as e:
            print(f"[GitHub] Error fetching commits: {e}")
            return {"success": False, "error": str(e)}
    
    def store_commit(self, commit_data, repo_owner, repo_name):
        """Store commit in MongoDB"""
        try:
            commit_doc = {
                "commit_id": commit_data["sha"],
                "repository": f"{repo_owner}/{repo_name}",
                "author": commit_data["commit"]["author"]["name"],
                "author_email": commit_data["commit"]["author"]["email"],
                "message": commit_data["commit"]["message"],
                "timestamp": commit_data["commit"]["author"]["date"],
                "url": commit_data["html_url"],
                "branch": "main",  # Default, can be enhanced
                "files_changed": [],  # Will be populated if needed
                "additions": 0,
                "deletions": 0
            }
            
            # Get detailed commit info (files changed)
            if "url" in commit_data:
                try:
                    detail_response = requests.get(commit_data["url"], headers=self.headers, timeout=10)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        if "files" in detail_data:
                            commit_doc["files_changed"] = [f["filename"] for f in detail_data["files"]]
                            commit_doc["additions"] = detail_data.get("stats", {}).get("additions", 0)
                            commit_doc["deletions"] = detail_data.get("stats", {}).get("deletions", 0)
                except:
                    pass  # Skip if details fetch fails
            
            # Upsert to avoid duplicates
            self.db.git_commits.update_one(
                {"commit_id": commit_doc["commit_id"]},
                {"$set": commit_doc},
                upsert=True
            )
            
        except Exception as e:
            print(f"[GitHub] Error storing commit: {e}")
    
    def fetch_pull_requests(self, repo_owner, repo_name, state="all"):
        """Fetch pull requests"""
        url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls"
        params = {"state": state, "per_page": 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            prs = response.json()
            
            print(f"[GitHub] Fetched {len(prs)} pull requests")
            
            for pr in prs:
                self.store_pull_request(pr, repo_owner, repo_name)
            
            return {"success": True, "count": len(prs)}
        except requests.exceptions.RequestException as e:
            print(f"[GitHub] Error fetching PRs: {e}")
            return {"success": False, "error": str(e)}
    
    def store_pull_request(self, pr_data, repo_owner, repo_name):
        """Store pull request in MongoDB"""
        try:
            pr_doc = {
                "pr_id": f"{repo_owner}/{repo_name}/pr/{pr_data['number']}",
                "number": pr_data["number"],
                "repository": f"{repo_owner}/{repo_name}",
                "title": pr_data["title"],
                "state": pr_data["state"],
                "author": pr_data["user"]["login"],
                "created_at": pr_data["created_at"],
                "updated_at": pr_data["updated_at"],
                "merged_at": pr_data.get("merged_at"),
                "url": pr_data["html_url"],
                "commits": pr_data.get("commits", 0),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0)
            }
            
            self.db.pull_requests.update_one(
                {"pr_id": pr_doc["pr_id"]},
                {"$set": pr_doc},
                upsert=True
            )
            
        except Exception as e:
            print(f"[GitHub] Error storing PR: {e}")
    
    def get_recent_commits(self, hours=24):
        """Get commits from last N hours"""
        time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        commits = list(self.db.git_commits.find({
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", -1).limit(50))
        return commits
