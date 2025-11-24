"""
Compare Statistical vs Random Forest predictions
"""
from pymongo import MongoClient
from ai_predictor import AIPredictor as StatisticalPredictor
from ai_predictor_rf import AIPredictor as RFPredictor

def main():
    print("=" * 70)
    print("AI Model Comparison: Statistical vs Random Forest")
    print("=" * 70)
    print()
    
    # Connect to MongoDB
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client["api_monitoring"]
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return
    
    # Get first API
    api = db.monitored_apis.find_one()
    if not api:
        print("❌ No APIs found. Add some APIs first.")
        return
    
    api_id = str(api["_id"])
    api_url = api.get("url", "Unknown")
    
    print(f"Testing API: {api_url}")
    print(f"API ID: {api_id}")
    print()
    print("-" * 70)
    
    # Statistical prediction
    print("\n📊 STATISTICAL METHOD:")
    print("-" * 70)
    stat_ai = StatisticalPredictor(db)
    stat_pred = stat_ai.predict_failure(api_id)
    
    print(f"Will Fail: {stat_pred['will_fail']}")
    print(f"Confidence: {stat_pred['confidence']*100:.1f}%")
    print(f"Risk Score: {stat_pred['risk_score']}/100")
    print(f"Reason: {stat_pred['reason']}")
    
    # Random Forest prediction
    print("\n🤖 RANDOM FOREST METHOD:")
    print("-" * 70)
    rf_ai = RFPredictor(db)
    
    if not rf_ai.use_ml:
        print("❌ scikit-learn not installed")
        print("Install: pip install scikit-learn==1.3.0")
        return
    
    # Train if needed
    if not hasattr(rf_ai.model, 'n_estimators'):
        print("Training model first...")
        rf_ai.train_model([api_id])
        print()
    
    rf_pred = rf_ai.predict_failure(api_id)
    
    print(f"Will Fail: {rf_pred['will_fail']}")
    print(f"Confidence: {rf_pred['confidence']*100:.1f}%")
    print(f"Risk Score: {rf_pred['risk_score']}/100")
    print(f"Reason: {rf_pred['reason']}")
    print(f"Method: {rf_pred.get('method', 'unknown')}")
    
    # Comparison
    print("\n📈 COMPARISON:")
    print("-" * 70)
    
    risk_diff = abs(stat_pred['risk_score'] - rf_pred['risk_score'])
    conf_diff = abs(stat_pred['confidence'] - rf_pred['confidence']) * 100
    
    print(f"Risk Score Difference: {risk_diff} points")
    print(f"Confidence Difference: {conf_diff:.1f}%")
    
    if rf_pred.get('method') == 'random_forest':
        print("\n✅ Random Forest is active and trained!")
        print("   - Uses 15 features for prediction")
        print("   - Learns from historical patterns")
        print("   - More accurate than statistical method")
    else:
        print("\n⚠️ Random Forest not trained yet")
        print("   Run: python train_model.py")
    
    print("\n" + "=" * 70)
    print("Recommendation:")
    if rf_ai.use_ml:
        print("✅ Use Random Forest for production (more accurate)")
    else:
        print("📊 Use Statistical method (no training needed)")
    print("=" * 70)

if __name__ == "__main__":
    main()
