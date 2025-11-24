"""
Quick test to verify the GitHub alert endpoint exists
"""
import requests

# Test if endpoint is registered
try:
    response = requests.post(
        'http://localhost:5000/api/github/create-downtime-alert',
        json={'api_id': 'test123'},
        timeout=5
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Response: {response.text[:200]}")
    
    if 'application/json' in response.headers.get('content-type', ''):
        print(f"JSON: {response.json()}")
    else:
        print("ERROR: Response is not JSON!")
        print(f"Full response:\n{response.text}")
        
except requests.exceptions.ConnectionError:
    print("ERROR: Cannot connect to Flask server. Is it running on port 5000?")
except Exception as e:
    print(f"ERROR: {e}")
