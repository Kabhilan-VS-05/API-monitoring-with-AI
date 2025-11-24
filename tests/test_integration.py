"""
Test script for developer data integration
Run this after setting GITHUB_TOKEN environment variable
"""

import requests
import json
import os

BASE_URL = "http://localhost:5000"

def test_github_sync():
    """Test GitHub sync"""
    print("\n=== Testing GitHub Sync ===")
    url = f"{BASE_URL}/api/sync/github"
    data = {
        "repo_owner": "Kabhilan-VS-05",
        "repo_name": "API-Monitoring",
        "since_days": 30
    }
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_issue_sync():
    """Test issue sync"""
    print("\n=== Testing Issue Sync ===")
    url = f"{BASE_URL}/api/sync/issues"
    data = {
        "repo_owner": "Kabhilan-VS-05",
        "repo_name": "API-Monitoring"
    }
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_get_commits():
    """Test get commits"""
    print("\n=== Testing Get Commits ===")
    url = f"{BASE_URL}/api/commits?hours=168"  # Last week
    
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    commits = response.json()
    print(f"Found {len(commits)} commits")
    if commits:
        print(f"Latest commit: {commits[0].get('message', 'N/A')[:50]}...")
    return response.status_code == 200

def test_get_issues():
    """Test get issues"""
    print("\n=== Testing Get Issues ===")
    url = f"{BASE_URL}/api/issues"
    
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    issues = response.json()
    print(f"Found {len(issues)} issues")
    if issues:
        print(f"Latest issue: {issues[0].get('title', 'N/A')[:50]}...")
    return response.status_code == 200

def test_create_incident():
    """Test create incident"""
    print("\n=== Testing Create Incident ===")
    url = f"{BASE_URL}/api/incidents"
    data = {
        "title": "Test Incident - API Timeout",
        "summary": "Payment API experienced timeout issues",
        "severity": "high",
        "start_time": "2025-10-31T10:00:00Z",
        "end_time": "2025-10-31T10:30:00Z",
        "duration_minutes": 30,
        "affected_apis": [],
        "root_cause": "Database connection pool exhausted",
        "fix_applied": "Increased connection pool size",
        "prevention_steps": "Monitor connection pool usage",
        "created_by": "Kabhilan"
    }
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_get_context():
    """Test get developer context for an API"""
    print("\n=== Testing Get Context ===")
    
    # First, get a monitored API
    monitors_url = f"{BASE_URL}/api/advanced/monitors"
    response = requests.get(monitors_url)
    
    if response.status_code == 200:
        monitors = response.json()
        if monitors:
            api_id = monitors[0].get("id")
            print(f"Testing with API ID: {api_id}")
            
            context_url = f"{BASE_URL}/api/context/{api_id}"
            context_response = requests.get(context_url)
            print(f"Status: {context_response.status_code}")
            
            if context_response.status_code == 200:
                context = context_response.json()
                print(f"Commits: {len(context.get('commits', []))}")
                print(f"Issues: {len(context.get('issues', []))}")
                print(f"Logs: {len(context.get('logs', []))}")
                print(f"Incidents: {len(context.get('incidents', []))}")
                print(f"Correlation Score: {context.get('correlation_score', 0)}")
                return True
        else:
            print("No monitors found. Add a monitor first.")
    
    return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Developer Data Integration - Test Suite")
    print("=" * 60)
    
    # Check if GitHub token is set
    if not os.getenv("GITHUB_TOKEN"):
        print("\n⚠️  WARNING: GITHUB_TOKEN environment variable not set!")
        print("Set it with: set GITHUB_TOKEN=your_token_here")
        return
    
    print(f"\n✅ GitHub token found")
    print(f"Testing with: Kabhilan-VS-05/API-Monitoring")
    
    results = []
    
    # Run tests
    results.append(("GitHub Sync", test_github_sync()))
    results.append(("Issue Sync", test_issue_sync()))
    results.append(("Get Commits", test_get_commits()))
    results.append(("Get Issues", test_get_issues()))
    results.append(("Create Incident", test_create_incident()))
    results.append(("Get Context", test_get_context()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s} {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! Developer data integration is working!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
