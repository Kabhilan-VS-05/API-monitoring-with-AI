import os
import pytest
import requests

BASE_URL = os.getenv("API_MONITOR_BASE_URL", "http://localhost:5000")


def _require_server():
    try:
        requests.get(f"{BASE_URL}/monitored_urls", timeout=3)
    except requests.RequestException:
        pytest.skip(f"API monitor server not reachable at {BASE_URL}")


def _get_first_monitor():
    response = requests.get(f"{BASE_URL}/api/advanced/monitors", timeout=10)
    assert response.status_code == 200
    monitors = response.json()
    if not monitors:
        pytest.skip("No monitors found. Add at least one monitor to run AI endpoint tests.")
    return monitors[0]["id"]


def test_ai_prediction():
    _require_server()
    api_id = _get_first_monitor()

    response = requests.get(f"{BASE_URL}/api/ai/predict/{api_id}", timeout=20)
    assert response.status_code == 200

    prediction = response.json()
    assert "will_fail" in prediction
    assert "confidence" in prediction
    assert "risk_score" in prediction


def test_anomaly_detection():
    _require_server()
    api_id = _get_first_monitor()

    response = requests.get(f"{BASE_URL}/api/ai/anomalies/{api_id}?hours=24", timeout=20)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_ai_insights():
    _require_server()
    api_id = _get_first_monitor()

    response = requests.get(f"{BASE_URL}/api/ai/insights/{api_id}", timeout=20)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_similar_incidents():
    _require_server()

    response = requests.post(
        f"{BASE_URL}/api/ai/similar_incidents",
        json={"issue": "API timeout database connection"},
        timeout=20,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
