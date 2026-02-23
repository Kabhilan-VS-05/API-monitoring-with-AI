"""
Train LSTM + Autoencoder Hybrid Model
"""
from pymongo import MongoClient
from ai_predictor_lstm import AIPredictor
import sys

def main():
    print("=" * 70)
    print("LSTM + Autoencoder Hybrid Model Training")
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
        print("Make sure MongoDB is running!")
        return
    
    # Initialize AI Predictor
    ai = AIPredictor(db)
    
    if not ai.use_ml:
        print("❌ TensorFlow not available")
        print("Install it with: pip install tensorflow==2.15.0")
        return
    
    print("✅ LSTM + Autoencoder initialized")
    print()
    
    # Get all monitored APIs
    apis = list(db.monitored_apis.find({}, {"_id": 1, "url": 1}))
    api_ids = [str(api["_id"]) for api in apis]
    
    if not api_ids:
        print("❌ No APIs found in database")
        print("Add some APIs first and let them collect data")
        return
    
    print(f"Found {len(api_ids)} monitored APIs:")
    for api in apis[:5]:
        print(f"  - {api.get('url', 'Unknown')}")
    if len(apis) > 5:
        print(f"  ... and {len(apis)-5} more")
    print()
    
    # Training parameters
    epochs = 50
    batch_size = 32
    
    print("Training Parameters:")
    print(f"  - Epochs: {epochs}")
    print(f"  - Batch Size: {batch_size}")
    print(f"  - Sequence Length: {ai.sequence_length}")
    print(f"  - Features per Step: {ai.n_features}")
    print()
    
    print("=" * 70)
    print("Starting Training... This may take 5-10 minutes")
    print("=" * 70)
    print()
    
    # Train models
    success = ai.train_models(api_ids, epochs=epochs, batch_size=batch_size)
    
    if success:
        print()
        print("=" * 70)
        print("✅ Training Complete!")
        print("=" * 70)
        print()
        print("Models saved:")
        print("  - models/lstm_model.h5 (Failure Prediction)")
        print("  - models/autoencoder_model.h5 (Anomaly Detection)")
        print("  - models/scaler.pkl (Feature Scaler)")
        print("  - models/model_config.json (Configuration)")
        print()
        print("The AI will now use deep learning for predictions!")
        print()
        print("Next steps:")
        print("  1. Restart application: START_HERE.bat")
        print("  2. Test predictions: python tests\\test_ai.py")
        print("  3. Check AI insights in dashboard")
        print()
        print("Model Architecture:")
        print("  🧠 LSTM: 2 layers (64→32 units) + Dense layers")
        print("  🔄 Autoencoder: Encoder-Decoder with LSTM layers")
        print("  📊 Total Parameters: ~50K-100K")
    else:
        print()
        print("❌ Training failed")
        print()
        print("Possible reasons:")
        print("  - Not enough data (need 20+ time steps per API)")
        print("  - APIs haven't been monitored long enough")
        print("  - Database connection issues")
        print("  - TensorFlow installation issues")
        print()
        print("Solution:")
        print("  1. Let the system collect more data (wait 1-2 hours)")
        print("  2. Add more APIs to monitor")
        print("  3. Check MongoDB has monitoring_logs data")
        print("  4. Try again: python train_lstm.py")

if __name__ == "__main__":
    main()
