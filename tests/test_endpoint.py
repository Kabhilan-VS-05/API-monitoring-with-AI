import os
import pytest
import requests

BASE_URL = os.getenv("API_MONITOR_BASE_URL", "http://localhost:5000")


def _require_server():
    try:
        requests.get(f"{BASE_URL}/monitored_urls", timeout=3)
    except requests.RequestException:
        pytest.skip(f"API monitor server not reachable at {BASE_URL}")


def test_downtime_alert_endpoint_returns_json():
    _require_server()

    response = requests.post(
        f"{BASE_URL}/api/github/create-downtime-alert",
        json={"api_id": "test123"},
        timeout=10,
    )

    assert "application/json" in response.headers.get("content-type", "")
    assert response.status_code in (200, 400, 404, 500)
