import os
import pytest
import requests

BASE_URL = os.getenv("API_MONITOR_BASE_URL", "http://localhost:5000")
REPO_OWNER = os.getenv("TEST_GITHUB_REPO_OWNER")
REPO_NAME = os.getenv("TEST_GITHUB_REPO_NAME")


def _require_server():
    try:
        requests.get(f"{BASE_URL}/monitored_urls", timeout=3)
    except requests.RequestException:
        pytest.skip(f"API monitor server not reachable at {BASE_URL}")


def _require_sync_config():
    if not REPO_OWNER or not REPO_NAME:
        pytest.skip("Set TEST_GITHUB_REPO_OWNER and TEST_GITHUB_REPO_NAME for sync tests")


def test_sync_github_and_issues():
    _require_server()
    _require_sync_config()

    response = requests.post(
        f"{BASE_URL}/api/sync/github",
        json={"repo_owner": REPO_OWNER, "repo_name": REPO_NAME, "since_days": 30},
        timeout=30,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True

    response = requests.post(
        f"{BASE_URL}/api/sync/issues",
        json={"repo_owner": REPO_OWNER, "repo_name": REPO_NAME},
        timeout=30,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("success") is True


def test_get_commits_and_issues():
    _require_server()

    commits_resp = requests.get(f"{BASE_URL}/api/commits?hours=720", timeout=10)
    issues_resp = requests.get(f"{BASE_URL}/api/issues", timeout=10)

    assert commits_resp.status_code == 200
    assert issues_resp.status_code == 200
    assert isinstance(commits_resp.json(), list)
    assert isinstance(issues_resp.json(), list)
