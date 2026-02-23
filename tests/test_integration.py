import os
import pytest
import requests

BASE_URL = os.getenv("API_MONITOR_BASE_URL", "http://localhost:5000")
TEST_REPO_OWNER = os.getenv("TEST_GITHUB_REPO_OWNER", "example-owner")
TEST_REPO_NAME = os.getenv("TEST_GITHUB_REPO_NAME", "example-repo")


def _require_server():
    try:
        requests.get(f"{BASE_URL}/monitored_urls", timeout=3)
    except requests.RequestException:
        pytest.skip(f"API monitor server not reachable at {BASE_URL}")


def _get_first_monitor_id_or_skip():
    response = requests.get(f"{BASE_URL}/api/advanced/monitors", timeout=10)
    assert response.status_code == 200
    monitors = response.json()
    if not monitors:
        pytest.skip("No monitors found. Add at least one monitor to run context test.")
    return monitors[0]["id"]


def test_save_and_get_github_settings():
    _require_server()

    payload = {
        "repo_owner": TEST_REPO_OWNER,
        "repo_name": TEST_REPO_NAME,
    }
    save_response = requests.post(
        f"{BASE_URL}/api/github/settings",
        json=payload,
        timeout=10,
    )
    assert save_response.status_code == 200
    assert save_response.json().get("success") is True

    get_response = requests.get(f"{BASE_URL}/api/github/settings", timeout=10)
    assert get_response.status_code == 200
    settings = get_response.json()
    assert settings.get("repo_owner") == TEST_REPO_OWNER
    assert settings.get("repo_name") == TEST_REPO_NAME


def test_create_and_list_incident():
    _require_server()

    incident_payload = {
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
        "created_by": "Automated Test",
    }

    create_response = requests.post(
        f"{BASE_URL}/api/incidents",
        json=incident_payload,
        timeout=10,
    )
    assert create_response.status_code == 200
    assert create_response.json().get("success") is True

    list_response = requests.get(f"{BASE_URL}/api/incidents", timeout=10)
    assert list_response.status_code == 200
    assert isinstance(list_response.json(), list)


def test_get_context_for_existing_monitor():
    _require_server()
    api_id = _get_first_monitor_id_or_skip()

    response = requests.get(f"{BASE_URL}/api/context/{api_id}", timeout=15)
    assert response.status_code == 200

    payload = response.json()
    assert "commits" in payload
    assert "issues" in payload
    assert "logs" in payload
    assert "incidents" in payload
    assert "correlation_score" in payload
