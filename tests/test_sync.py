"""
Quick test script to sync GitHub data
"""
import requests
import json

# Sync GitHub data
print("Syncing GitHub data...")
response = requests.post(
    "http://localhost:5000/api/sync/github",
    json={
        "repo_owner": "Kabhilan-VS-05",
        "repo_name": "API-Monitoring",
        "since_days": 90
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Sync issues
print("\nSyncing issues...")
response = requests.post(
    "http://localhost:5000/api/sync/issues",
    json={
        "repo_owner": "Kabhilan-VS-05",
        "repo_name": "API-Monitoring"
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# View commits
print("\nFetching commits...")
response = requests.get("http://localhost:5000/api/commits?hours=720")
commits = response.json()
print(f"Found {len(commits)} commits")
if commits:
    for commit in commits[:3]:
        print(f"  - {commit['message'][:50]}... by {commit['author']}")

# View issues
print("\nFetching issues...")
response = requests.get("http://localhost:5000/api/issues")
issues = response.json()
print(f"Found {len(issues)} issues")
if issues:
    for issue in issues[:3]:
        print(f"  - #{issue['number']}: {issue['title'][:50]}...")
