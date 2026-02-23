"""
Quick test to verify AI predictor shape validation
"""
from pymongo import MongoClient
from ai_predictor import CategoryAwareAIPredictor as AIPredictor

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["api_monitoring"]

# Initialize AI
ai = AIPredictor(db)

# Get first API
api = db.monitored_apis.find_one()
if api:
    api_id = str(api["_id"])
    print(f"Testing API: {api.get('url', 'Unknown')}")
    print(f"Category: {api.get('category', 'None')}")
    print()
    
    # Try prediction
    result = ai.predict_failure(api_id)
    
    print("Prediction Result:")
    print(f"  Risk Score: {result['risk_score']}/100")
    print(f"  Confidence: {result['confidence']*100:.0f}%")
    print(f"  Analysis: {result['reason']}")
    print(f"  Method: {result['method']}")
    print(f"  Category: {result.get('category', 'Unknown')}")
else:
    print("No APIs found in database")
