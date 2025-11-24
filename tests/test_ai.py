"""
Test AI/ML Prediction Features
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_ai_prediction():
    """Test failure prediction"""
    print("\n=== Testing AI Failure Prediction ===")
    
    # Get first monitored API
    monitors = requests.get(f"{BASE_URL}/api/advanced/monitors").json()
    if not monitors:
        print("❌ No monitors found. Add a monitor first.")
        return
    
    api_id = monitors[0]["id"]
    print(f"Testing with API ID: {api_id}")
    
    # Get prediction
    response = requests.get(f"{BASE_URL}/api/ai/predict/{api_id}")
    prediction = response.json()
    
    print(f"\nPrediction Results:")
    print(f"  Will Fail: {prediction.get('will_fail')}")
    print(f"  Confidence: {prediction.get('confidence', 0)*100:.1f}%")
    print(f"  Risk Score: {prediction.get('risk_score')}/100")
    print(f"  Reason: {prediction.get('reason')}")
    
    if prediction.get('metrics'):
        print(f"\n  Metrics:")
        for key, value in prediction['metrics'].items():
            print(f"    - {key}: {value}")

def test_anomaly_detection():
    """Test anomaly detection"""
    print("\n=== Testing Anomaly Detection ===")
    
    monitors = requests.get(f"{BASE_URL}/api/advanced/monitors").json()
    if not monitors:
        print("❌ No monitors found.")
        return
    
    api_id = monitors[0]["id"]
    
    response = requests.get(f"{BASE_URL}/api/ai/anomalies/{api_id}?hours=24")
    anomalies = response.json()
    
    print(f"Found {len(anomalies)} anomalies:")
    for anomaly in anomalies:
        print(f"\n  Type: {anomaly.get('type')}")
        print(f"  Severity: {anomaly.get('severity')}")
        print(f"  Description: {anomaly.get('description')}")
        print(f"  Time: {anomaly.get('timestamp')}")

def test_ai_insights():
    """Test AI insights generation"""
    print("\n=== Testing AI Insights ===")
    
    monitors = requests.get(f"{BASE_URL}/api/advanced/monitors").json()
    if not monitors:
        print("❌ No monitors found.")
        return
    
    api_id = monitors[0]["id"]
    
    response = requests.get(f"{BASE_URL}/api/ai/insights/{api_id}")
    insights = response.json()
    
    print(f"Generated {len(insights)} insights:")
    for insight in insights:
        print(f"\n  {insight.get('title')}")
        print(f"  Type: {insight.get('type')}")
        print(f"  Message: {insight.get('message')}")
        print(f"  Details: {insight.get('details')}")
        print(f"  Action: {insight.get('action')}")

def test_similar_incidents():
    """Test finding similar incidents"""
    print("\n=== Testing Similar Incidents ===")
    
    response = requests.post(
        f"{BASE_URL}/api/ai/similar_incidents",
        json={"issue": "API timeout database connection"}
    )
    
    similar = response.json()
    
    print(f"Found {len(similar)} similar incidents:")
    for item in similar:
        incident = item.get('incident', {})
        print(f"\n  Similarity: {item.get('similarity', 0)*100:.1f}%")
        print(f"  Title: {incident.get('title')}")
        print(f"  Root Cause: {incident.get('root_cause')}")
        print(f"  Fix: {incident.get('fix_applied')}")
        print(f"  Matching Keywords: {', '.join(item.get('matching_keywords', []))}")

def main():
    print("=" * 60)
    print("AI/ML Prediction System - Test Suite")
    print("=" * 60)
    
    try:
        test_ai_prediction()
        test_anomaly_detection()
        test_ai_insights()
        test_similar_incidents()
        
        print("\n" + "=" * 60)
        print("✅ All AI tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
