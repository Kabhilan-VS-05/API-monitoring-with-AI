"""
Train Category-Aware LSTM Models
Trains separate models for each API category
"""
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from pymongo import MongoClient
from ai_predictor import CategoryAwareAIPredictor

def main():
    print("=" * 70)
    print("CATEGORY-AWARE LSTM TRAINING")
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
    
    # Initialize AI
    ai = CategoryAwareAIPredictor(db)
    
    if not ai.use_ml:
        print("❌ TensorFlow not available")
        print("Install: pip install tensorflow==2.15.0")
        return
    
    print("✅ Category-Aware AI initialized")
    print()
    
    # Show API categories
    apis = list(db.monitored_apis.find())
    if not apis:
        print("❌ No APIs found")
        print("Add some APIs first with different categories:")
        print("  - REST API")
        print("  - Website")
        print("  - Database")
        print("  - Microservice")
        print("  - Third-Party API")
        print("  - Internal Service")
        return
    
    print(f"Found {len(apis)} APIs")
    
    # Group by category
    from collections import defaultdict
    category_count = defaultdict(int)
    for api in apis:
        category = api.get("category", "REST API")
        category_count[category] += 1
    
    print("\nAPI Categories:")
    for cat, count in category_count.items():
        print(f"  - {cat}: {count} APIs")
    
    print()
    print("=" * 70)
    print("Starting Training...")
    print("=" * 70)
    print()
    print("This will train separate models for each category.")
    print("Training time: 5-15 minutes per category")
    print()
    
    # Train models
    success = ai.train_models_by_category(epochs=50, batch_size=32)
    
    if success:
        print()
        print("=" * 70)
        print("✅ TRAINING COMPLETE!")
        print("=" * 70)
        print()
        print("Category-specific models saved:")
        for category in category_count.keys():
            safe_cat = category.replace(" ", "_").lower()
            print(f"  - models/lstm_{safe_cat}.h5")
            print(f"  - models/autoencoder_{safe_cat}.h5")
            print(f"  - models/scaler_{safe_cat}.pkl")
        print()
        print("Benefits:")
        print("  ✅ Each category has optimized thresholds")
        print("  ✅ Better accuracy for specific API types")
        print("  ✅ Reduced false positives")
        print("  ✅ Category-aware predictions")
        print()
        print("Next steps:")
        print("  1. Restart: START_HERE.bat")
        print("  2. Test predictions")
        print("  3. Check dashboard AI insights")
    else:
        print()
        print("❌ Training failed")
        print("Possible reasons:")
        print("  - Not enough data per category")
        print("  - Need 20+ time steps per API")
        print("  - Wait for more monitoring data")

if __name__ == "__main__":
    main()
