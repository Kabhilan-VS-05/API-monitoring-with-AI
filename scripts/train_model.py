"""
Train Random Forest Model on Historical Data
"""
from pymongo import MongoClient
from ai_predictor_rf import AIPredictor

def main():
    print("=" * 60)
    print("Random Forest Model Training")
    print("=" * 60)
    print()
    
    # Connect to MongoDB
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client["api_monitoring"]
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("Make sure MongoDB is running!")
        return
    
    # Initialize AI Predictor
    ai = AIPredictor(db)
    
    if not ai.use_ml:
        print("❌ scikit-learn not available")
        print("Install it with: pip install scikit-learn==1.3.0")
        return
    
    print("✅ Random Forest AI initialized")
    print()
    
    # Get all monitored APIs
    apis = list(db.monitored_apis.find({}, {"_id": 1}))
    api_ids = [str(api["_id"]) for api in apis]
    
    if not api_ids:
        print("❌ No APIs found in database")
        print("Add some APIs first and let them collect data")
        return
    
    print(f"Found {len(api_ids)} monitored APIs")
    print()
    
    # Train model
    print("Training Random Forest model...")
    print("This may take a few seconds...")
    print()
    
    success = ai.train_model(api_ids)
    
    if success:
        print()
        print("=" * 60)
        print("✅ Training Complete!")
        print("=" * 60)
        print()
        print("Model saved to: models/rf_model.pkl")
        print("Scaler saved to: models/scaler.pkl")
        print()
        print("The AI will now use Random Forest for predictions!")
        print()
        print("Next steps:")
        print("1. Restart application: START_HERE.bat")
        print("2. Test predictions: python tests\\test_ai.py")
        print("3. Check AI insights in dashboard")
    else:
        print()
        print("❌ Training failed")
        print("Possible reasons:")
        print("- Not enough data (need at least 10 samples)")
        print("- APIs haven't been monitored long enough")
        print("- Database connection issues")
        print()
        print("Solution: Let the system collect more data and try again")

if __name__ == "__main__":
    main()
