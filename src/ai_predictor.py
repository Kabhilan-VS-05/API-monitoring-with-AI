"""
Category-Aware LSTM + Autoencoder AI Predictor
Trains separate models for different API categories (REST API, Website, Database, etc.)
"""

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pickle
import os
import json
from bson import ObjectId

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from sklearn.preprocessing import StandardScaler
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("[WARNING] TensorFlow not installed. Using fallback statistical methods.")

# Define API categories and their characteristics
API_CATEGORIES = {
    "REST API": {
        "expected_latency": 200,  # ms
        "failure_threshold": 0.05,  # 5% failure rate
        "latency_threshold": 2000,  # 2 seconds
        "status_codes": [200, 201, 204, 400, 401, 403, 404, 500, 502, 503]
    },
    "Website": {
        "expected_latency": 500,
        "failure_threshold": 0.02,  # 2% failure rate
        "latency_threshold": 3000,
        "status_codes": [200, 301, 302, 400, 403, 404, 500, 502, 503]
    },
    "Database": {
        "expected_latency": 50,
        "failure_threshold": 0.01,  # 1% failure rate
        "latency_threshold": 1000,
        "status_codes": [200, 408, 500, 503, 504]
    },
    "Microservice": {
        "expected_latency": 100,
        "failure_threshold": 0.03,
        "latency_threshold": 1500,
        "status_codes": [200, 201, 400, 404, 429, 500, 502, 503]
    },
    "Third-Party API": {
        "expected_latency": 1000,
        "failure_threshold": 0.10,  # 10% failure rate (more tolerant)
        "latency_threshold": 5000,
        "status_codes": [200, 400, 401, 403, 429, 500, 502, 503]
    },
    "Internal Service": {
        "expected_latency": 150,
        "failure_threshold": 0.02,
        "latency_threshold": 1000,
        "status_codes": [200, 201, 400, 404, 500, 503]
    }
}

class CategoryAwareAIPredictor:
    def __init__(self, mongo_db):
        self.db = mongo_db
        # Models directory is in project root, not in src/
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)
        self.models_dir = os.path.join(project_root, "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Model parameters
        self.sequence_length = 20
        self.n_features = 10
        self.min_training_sequences = 25
        self.min_prediction_observations = 5
        
        # Category-specific models
        self.category_models = {}  # {category: {"lstm": model, "autoencoder": model, "scaler": scaler}}
        
        if TENSORFLOW_AVAILABLE:
            self.use_ml = True
            print("[AI] Category-Aware LSTM + Autoencoder initialized")
            # Load existing models on startup
            self._load_all_models()
        else:
            self.use_ml = False
            print("[AI] TensorFlow not available, using statistical methods")

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _load_all_models(self):
        """Load all pre-trained models on startup to avoid retraining"""
        for category in API_CATEGORIES.keys():
            try:
                if self._load_category_model(category):
                    print(f"[AI] Loaded pre-trained model for {category}")
            except Exception as e:
                print(f"[AI] No pre-trained model for {category}: {e}")
    
    def _get_category_path(self, category):
        """Get file paths for category-specific models"""
        safe_category = category.replace(" ", "_").lower()
        return {
            "lstm": os.path.join(self.models_dir, f"lstm_{safe_category}.h5"),
            "autoencoder": os.path.join(self.models_dir, f"autoencoder_{safe_category}.h5"),
            "scaler": os.path.join(self.models_dir, f"scaler_{safe_category}.pkl"),
            "config": os.path.join(self.models_dir, f"config_{safe_category}.json")
        }
    
    def _save_category_model(self, category, lstm_model, autoencoder_model, scaler):
        """Save trained models for a category"""
        if not self.use_ml:
            return False
        
        try:
            paths = self._get_category_path(category)
            
            # Save models
            lstm_model.save(paths["lstm"])
            autoencoder_model.save(paths["autoencoder"])
            
            # Save scaler
            with open(paths["scaler"], 'wb') as f:
                pickle.dump(scaler, f)
            
            # Save config
            config = {
                "category": category,
                "sequence_length": self.sequence_length,
                "n_features": self.n_features,
                "saved_at": datetime.utcnow().isoformat()
            }
            with open(paths["config"], 'w') as f:
                json.dump(config, f)
            
            print(f"[AI] Saved model for {category}")
            return True
        except Exception as e:
            print(f"[AI] Error saving model for {category}: {e}")
            return False
    
    def _load_category_model(self, category):
        """Load pre-trained models for a category"""
        if not self.use_ml:
            return False
        
        try:
            paths = self._get_category_path(category)
            config = {}
            if os.path.exists(paths["config"]):
                try:
                    with open(paths["config"], "r") as f:
                        config = json.load(f)
                except Exception:
                    config = {}
            
            # Check if all files exist
            if not all(os.path.exists(p) for p in [paths["lstm"], paths["autoencoder"], paths["scaler"]]):
                return False
            
            # Load models
            lstm_model = keras.models.load_model(paths["lstm"])
            autoencoder_model = keras.models.load_model(paths["autoencoder"])
            
            # Load scaler
            with open(paths["scaler"], 'rb') as f:
                scaler = pickle.load(f)
            
            # Store in memory
            self.category_models[category] = {
                "lstm": lstm_model,
                "autoencoder": autoencoder_model,
                "scaler": scaler,
                "ml_ready": bool(config.get("ml_ready", True))
            }
            if "anomaly_threshold" in config:
                try:
                    self.category_models[category]["anomaly_threshold"] = float(config["anomaly_threshold"])
                except (TypeError, ValueError):
                    pass
            
            return True
        except Exception as e:
            print(f"[AI] Error loading model for {category}: {e}")
            return False
    
    def _create_lstm_model(self):
        """Create LSTM model for failure prediction"""
        model = keras.Sequential([
            layers.LSTM(64, return_sequences=True, input_shape=(self.sequence_length, self.n_features)),
            layers.Dropout(0.2),
            layers.LSTM(32, return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(1, activation='sigmoid')
        ])
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy', 'AUC'])
        return model
    
    def _create_autoencoder_model(self):
        """Create Autoencoder for anomaly detection"""
        input_layer = layers.Input(shape=(self.sequence_length, self.n_features))
        encoded = layers.LSTM(32, return_sequences=True)(input_layer)
        encoded = layers.LSTM(16, return_sequences=False)(encoded)
        decoded = layers.RepeatVector(self.sequence_length)(encoded)
        decoded = layers.LSTM(16, return_sequences=True)(decoded)
        decoded = layers.LSTM(32, return_sequences=True)(decoded)
        decoded = layers.TimeDistributed(layers.Dense(self.n_features))(decoded)
        autoencoder = keras.Model(input_layer, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        return autoencoder
    
    def _load_or_create_category_models(self, category):
        """Load or create models for specific category"""
        if category in self.category_models:
            return self.category_models[category]
        
        paths = self._get_category_path(category)
        models = {}
        
        # Load or create LSTM
        if os.path.exists(paths["lstm"]):
            try:
                models["lstm"] = keras.models.load_model(paths["lstm"])
                print(f"[AI] Loaded LSTM for category: {category}")
            except:
                models["lstm"] = self._create_lstm_model()
        else:
            models["lstm"] = self._create_lstm_model()
        
        # Load or create Autoencoder
        if os.path.exists(paths["autoencoder"]):
            try:
                models["autoencoder"] = keras.models.load_model(paths["autoencoder"])
                print(f"[AI] Loaded Autoencoder for category: {category}")
            except:
                models["autoencoder"] = self._create_autoencoder_model()
        else:
            models["autoencoder"] = self._create_autoencoder_model()
        
        # Load or create Scaler
        if os.path.exists(paths["scaler"]):
            try:
                with open(paths["scaler"], 'rb') as f:
                    models["scaler"] = pickle.load(f)
                print(f"[AI] Loaded scaler for category: {category}")
            except Exception as e:
                print(f"[AI] Error loading scaler for {category}: {e}")
                from sklearn.preprocessing import StandardScaler
                models["scaler"] = StandardScaler()
                print(f"[AI] Created new unfitted scaler for {category}")
        else:
            print(f"[AI] Scaler file not found for {category}: {paths['scaler']}")
            from sklearn.preprocessing import StandardScaler
            models["scaler"] = StandardScaler()
            print(f"[AI] Created new unfitted scaler for {category}")

        config = {}
        if os.path.exists(paths["config"]):
            try:
                with open(paths["config"], "r") as f:
                    config = json.load(f)
            except Exception:
                config = {}
        models["ml_ready"] = bool(config.get("ml_ready", True))
        if "anomaly_threshold" in config:
            try:
                models["anomaly_threshold"] = float(config["anomaly_threshold"])
            except (TypeError, ValueError):
                pass
        
        self.category_models[category] = models
        return models
    
    def _get_api_category(self, api_id):
        """Get category for an API"""
        try:
            api = self.db.monitored_apis.find_one({"_id": ObjectId(api_id)})
        except Exception:
            api = self.db.monitored_apis.find_one({"_id": api_id})
        if api and api.get("category"):
            return api["category"]
        return "REST API"  # Default category
    
    def _extract_time_series(self, api_id, hours=48, allow_padding=False):
        """Extract time-series data for LSTM"""
        category = self._get_api_category(api_id)
        time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "check_skipped": {"$ne": True},
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", 1))

        if len(logs) < 2:
            return None, None, category

        category_config = API_CATEGORIES.get(category, API_CATEGORIES["REST API"])
        
        features_list = []
        labels_list = []
        recent_failure_window = []

        for log in logs:
            # Normalize latency based on category expectations
            expected_latency = category_config.get("expected_latency", 200)
            if not expected_latency or expected_latency == 0:
                expected_latency = 200  # Default fallback
            
            total_latency = max(0.0, self._safe_float(log.get("total_latency_ms")))
            normalized_latency = total_latency / expected_latency

            dns_latency = max(0.0, self._safe_float(log.get("dns_latency_ms")))
            dns_latency_normalized = dns_latency / 100.0

            tcp_latency = max(0.0, self._safe_float(log.get("tcp_latency_ms")))
            tcp_latency_normalized = tcp_latency / 100.0

            tls_latency = max(0.0, self._safe_float(log.get("tls_latency_ms")))
            tls_latency_normalized = tls_latency / 100.0

            server_latency = max(0.0, self._safe_float(log.get("server_processing_latency_ms")))
            server_latency_normalized = server_latency / expected_latency

            download_latency = max(0.0, self._safe_float(log.get("content_download_latency_ms")))
            download_latency_normalized = download_latency / expected_latency

            is_up = bool(log.get("is_up", True))
            recent_failure_window.append(0 if is_up else 1)
            if len(recent_failure_window) > 5:
                recent_failure_window.pop(0)
            failure_ratio_recent = sum(recent_failure_window) / max(len(recent_failure_window), 1)

            features = [
                1.0 if is_up else 0.0,
                min(normalized_latency, 10.0),  # Cap at 10x expected
                dns_latency_normalized,
                tcp_latency_normalized,
                tls_latency_normalized,
                server_latency_normalized,
                download_latency_normalized,
                self._safe_int(log.get("status_code"), 200) / 500.0,
                1.0 if log.get("error_message") else 0.0,
                failure_ratio_recent
            ]
            features_list.append(features)
            label = 0.0 if is_up else 1.0
            labels_list.append(label)
        
        # Create sequences
        sequences = []
        labels = []

        if len(features_list) <= self.sequence_length:
            if allow_padding and len(features_list) >= self.min_prediction_observations:
                pad_count = self.sequence_length - len(features_list)
                first = features_list[0]
                padded_seq = ([first] * pad_count) + features_list
                sequences.append(padded_seq)
                labels.append(labels_list[-1])
                return np.array(sequences, dtype=np.float32), np.array(labels, dtype=np.float32), category
            return None, None, category

        for i in range(len(features_list) - self.sequence_length):
            seq = features_list[i:i + self.sequence_length]
            label = labels_list[i + self.sequence_length]
            sequences.append(seq)
            labels.append(label)

        if not sequences:
            return None, None, category

        return np.array(sequences, dtype=np.float32), np.array(labels, dtype=np.float32), category
    
    def _train_category_model(self, category, api_ids, epochs=50, batch_size=32, progress_callback=None):
        """Trains models for a specific category"""
        print("\n" + '='*70)
        print(f"Training models for category: {category}")
        print('='*70)
        
        # Collect data for this category
        all_sequences = []
        all_labels = []
        
        for api_id in api_ids:
            sequences, labels, _ = self._extract_time_series(api_id, hours=48, allow_padding=False)
            if sequences is not None and len(sequences) > 0:
                all_sequences.append(sequences)
                all_labels.append(labels)
        
        if not all_sequences:
            print(f"[AI] No data for category: {category}")
            return None
        
        X = np.vstack(all_sequences)
        y = np.concatenate(all_labels)
        unique_labels = np.unique(y)
        
        print(f"Training on {len(X)} sequences from {len(api_ids)} APIs")
        if progress_callback:
            progress_callback(
                stage="preparing_data",
                progress=10.0,
                message="Preparing training dataset..."
            )

        if len(X) < self.min_training_sequences or len(unique_labels) < 2:
            paths = self._get_category_path(category)
            from sklearn.preprocessing import StandardScaler

            n_samples, n_steps, n_features = X.shape
            scaler = StandardScaler()
            scaler.fit(X.reshape(-1, n_features))
            with open(paths["scaler"], "wb") as f:
                pickle.dump(scaler, f)

            baseline_reason = (
                f"Insufficient balanced data for neural training (samples={len(X)}, "
                f"classes={len(unique_labels)}). Falling back to statistical prediction."
            )
            config = {
                "category": category,
                "sequence_length": self.sequence_length,
                "n_features": self.n_features,
                "trained": False,
                "ml_ready": False,
                "fallback": "statistical",
                "reason": baseline_reason,
                "last_trained": datetime.utcnow().isoformat(),
                "samples": int(len(X)),
                "class_distribution": {
                    "up": int(np.sum(y == 0)),
                    "down": int(np.sum(y == 1))
                }
            }
            with open(paths["config"], "w") as f:
                json.dump(config, f)

            if category in self.category_models:
                self.category_models[category]["scaler"] = scaler
                self.category_models[category]["ml_ready"] = False
            else:
                self.category_models[category] = {"scaler": scaler, "ml_ready": False}

            print(f"[AI] {baseline_reason}")
            return {"accuracy": None, "auc": None, "samples": len(X), "trained": False, "reason": baseline_reason}
        
        # Load or create models for this category
        models = self._load_or_create_category_models(category)
        
        # Scale data
        n_samples, n_steps, n_features = X.shape
        X_reshaped = X.reshape(-1, n_features)
        X_scaled = models["scaler"].fit_transform(X_reshaped)
        X_scaled = X_scaled.reshape(n_samples, n_steps, n_features)
        
        # Split data
        split_idx = max(1, min(len(X_scaled) - 1, int(len(X_scaled) * 0.8)))
        X_train, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Train LSTM
        print(f"\n{'='*70}")
        print(f"TRAINING LSTM MODEL FOR {category.upper()}")
        print(f"Total Epochs: {epochs}")
        print(f"Training Samples: {len(X_train)}")
        print(f"Validation Samples: {len(X_val)}")
        print(f"{'='*70}\n")
        
        if progress_callback:
            progress_callback(
                stage="lstm_start",
                progress=20.0,
                message="Training LSTM neural network..."
            )

        class _LSTMProgressCallback(keras.callbacks.Callback):
            def __init__(self, total_epochs, progress_cb, start=20.0, end=75.0):
                super().__init__()
                self.total_epochs = max(total_epochs, 1)
                self.progress_cb = progress_cb
                self.start = start
                self.end = end

            def on_epoch_end(self, epoch, logs=None):
                fraction = (epoch + 1) / self.total_epochs
                progress = self.start + fraction * (self.end - self.start)
                self.progress_cb(
                    stage="lstm_epoch",
                    progress=min(progress, self.end),
                    message=f"LSTM training ({epoch + 1}/{self.total_epochs})..."
                )

        lstm_callbacks = [
            keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(patience=5, factor=0.5)
        ]
        if progress_callback:
            lstm_callbacks.append(_LSTMProgressCallback(epochs, progress_callback))

        history = models["lstm"].fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            verbose=1,
            callbacks=lstm_callbacks,
            class_weight=(
                {
                    0: float(max(1, np.sum(y_train == 1))) / float(max(1, np.sum(y_train == 0))),
                    1: float(max(1, np.sum(y_train == 0))) / float(max(1, np.sum(y_train == 1)))
                }
                if len(np.unique(y_train)) == 2 else None
            )
        )

        actual_epochs = len(history.history['loss'])
        print(f"\n{'='*70}")
        print(f"LSTM TRAINING COMPLETED")
        print(f"Epochs Completed: {actual_epochs}/{epochs}")
        if actual_epochs < epochs:
            print(f"Early stopping triggered at epoch {actual_epochs}")
        print(f"{'='*70}\n")

        if progress_callback:
            progress_callback(
                stage="lstm_completed",
                progress=75.0,
                message="LSTM training complete. Validating performance..."
            )

        # Evaluate
        loss, acc, auc = models["lstm"].evaluate(X_val, y_val, verbose=0)
        models["ml_ready"] = True
        print(f"\n[{category}] LSTM Accuracy: {acc*100:.2f}%")
        print(f"[{category}] LSTM AUC: {auc:.3f}")

        # Train Autoencoder
        X_normal = X_scaled[y == 0]
        if len(X_normal) > 10:
            print(f"\nTraining Autoencoder for {category}...")
            if progress_callback:
                progress_callback(
                    stage="autoencoder_start",
                    progress=78.0,
                    message="Training autoencoder anomaly detector..."
                )

            class _AutoencoderProgressCallback(keras.callbacks.Callback):
                def __init__(self, total_epochs, progress_cb, start=78.0, end=90.0):
                    super().__init__()
                    self.total_epochs = max(total_epochs, 1)
                    self.progress_cb = progress_cb
                    self.start = start
                    self.end = end

                def on_epoch_end(self, epoch, logs=None):
                    fraction = (epoch + 1) / self.total_epochs
                    progress = self.start + fraction * (self.end - self.start)
                    self.progress_cb(
                        stage="autoencoder_epoch",
                        progress=min(progress, self.end),
                        message=f"Autoencoder training ({epoch + 1}/{self.total_epochs})..."
                    )

            auto_callbacks = [keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)]
            if progress_callback:
                auto_callbacks.append(_AutoencoderProgressCallback(epochs, progress_callback))

            models["autoencoder"].fit(
                X_normal, X_normal,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=0.2,
                verbose=1,
                callbacks=auto_callbacks
            )

            # Calculate threshold
            reconstructions = models["autoencoder"].predict(X_normal, verbose=0)
            mse = np.mean(np.square(X_normal - reconstructions), axis=(1, 2))
            models["anomaly_threshold"] = np.percentile(mse, 95)
            print(f"[{category}] Anomaly threshold: {models['anomaly_threshold']:.4f}")
            if progress_callback:
                progress_callback(
                    stage="autoencoder_completed",
                    progress=90.0,
                    message="Autoencoder training complete. Calibrating anomaly thresholds..."
                )
        else:
            if progress_callback:
                progress_callback(
                    stage="autoencoder_skipped",
                    progress=82.0,
                    message="Insufficient normal data for autoencoder. Skipping anomaly training."
                )

        # Save models
        paths = self._get_category_path(category)
        models["lstm"].save(paths["lstm"])
        models["autoencoder"].save(paths["autoencoder"])
        with open(paths["scaler"], 'wb') as f:
            pickle.dump(models["scaler"], f)

        if progress_callback:
            progress_callback(
                stage="finalizing",
                progress=95.0,
                message="Finalizing models and saving artifacts..."
            )
        
        # Save config
        config = {
            "category": category,
            "sequence_length": self.sequence_length,
            "n_features": self.n_features,
            "accuracy": float(acc),
            "auc": float(auc),
            "trained": True,
            "ml_ready": True,
            "last_trained": datetime.utcnow().isoformat()
        }
        if models.get("anomaly_threshold") is not None:
            try:
                config["anomaly_threshold"] = float(models.get("anomaly_threshold"))
            except (TypeError, ValueError):
                pass
        with open(paths["config"], 'w') as f:
            json.dump(config, f)
        
        return {"accuracy": acc, "auc": auc, "samples": len(X)}

    def train_models_by_category(self, epochs=50, batch_size=32):
        """Train separate models for each category"""
        if not self.use_ml:
            print("[AI] TensorFlow not available")
            return False
        
        print("=" * 70)
        print("Category-Aware Model Training")
        print("=" * 70)
        
        # Group APIs by category
        apis = list(self.db.monitored_apis.find())
        category_apis = defaultdict(list)
        
        for api in apis:
            category = api.get("category", "REST API")
            category_apis[category].append(str(api["_id"]))
        
        print(f"\nFound {len(category_apis)} categories:")
        for cat, api_list in category_apis.items():
            print(f"  - {cat}: {len(api_list)} APIs")
        
        results = {}
        
        # Train models for each category
        for category, api_ids in category_apis.items():
            result = self._train_category_model(category, api_ids, epochs, batch_size)
            if result:
                results[category] = result
        
        # Print summary
        print("\n" + "=" * 70)
        print("Training Summary")
        print("=" * 70)
        for category, metrics in results.items():
            print(f"{category:20s} | Acc: {metrics['accuracy']*100:5.2f}% | AUC: {metrics['auc']:.3f} | Samples: {metrics['samples']}")
        
        return True

    def train_model_for_api_category(self, api_id, epochs=50, batch_size=32, force_retrain=False, progress_callback=None):
        """Trains the model for the category associated with a specific API"""
        if not self.use_ml:
            print("[AI] TensorFlow not available")
            return False
        
        category = self._get_api_category(api_id)
        
        # Check if model already exists and is loaded (skip only if not forcing retrain)
        if force_retrain:
            print(f"[AI] 🔄 FORCE RETRAIN requested for '{category}'")
            # Clear cached model to ensure fresh training
            if category in self.category_models:
                print(f"[AI] Clearing cached model for '{category}'")
                del self.category_models[category]
        else:
            # Only skip if not forcing retrain
            if category in self.category_models and self.category_models[category].get("ml_ready", False):
                print(f"[AI] Model for '{category}' already trained and loaded. Skipping training.")
                return True
            
            # Try to load existing model
            if self._load_category_model(category) and self.category_models.get(category, {}).get("ml_ready", False):
                print(f"[AI] Loaded existing model for '{category}'. Skipping training.")
                return True
        
        # Find all APIs in this category
        apis_in_category = list(self.db.monitored_apis.find({"category": category}))
        api_ids_in_category = [str(api["_id"]) for api in apis_in_category]
        
        if not api_ids_in_category:
            print(f"[AI] No APIs found for category: {category}")
            return False
        
        print(f"[AI] Training model for category '{category}' (triggered by API '{api_id}')")
        result = self._train_category_model(
            category,
            api_ids_in_category,
            epochs,
            batch_size,
            progress_callback=progress_callback
        )
        
        # Store last training time in MongoDB for all APIs in this category
        if result is not None:
            from datetime import datetime
            training_time = datetime.utcnow()
            for api_id_in_cat in api_ids_in_category:
                self.db.monitored_apis.update_one(
                    {"_id": ObjectId(api_id_in_cat)},
                    {"$set": {"last_ai_training": training_time}}
                )
            print(f"[AI] Updated last_ai_training timestamp for {len(api_ids_in_category)} APIs in category '{category}'")
        
        return result is not None
    
    def train_model(self, api_id, epochs=50, batch_size=32, progress_callback=None):
        """Alias for train_model_for_api_category for backward compatibility"""
        return self.train_model_for_api_category(api_id, epochs, batch_size, progress_callback=progress_callback)

    def predict_failure(self, api_id, hours_ahead=1):
        """Predict failure using category-specific model"""
        try:
            print(f"[AI] predict_failure called for api_id: {api_id}")
            category = self._get_api_category(api_id)
            sequences, _, category = self._extract_time_series(api_id, hours=48, allow_padding=True)
            
            if sequences is None:
                print(f"[AI] No sequences returned - insufficient data")
                return self._statistical_prediction(
                    api_id,
                    category,
                    reason_override="Insufficient sequence data for neural model; using statistical fallback."
                )
            
            print(f"[AI] Got {len(sequences)} sequences, category: {category}")

            # Load training metadata for this category if available
            training_meta = {}
            try:
                paths = self._get_category_path(category)
                config_path = paths.get("config")
                if config_path and os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        training_meta = json.load(f)
            except Exception as meta_err:
                print(f"[AI] Could not load training metadata for {category}: {meta_err}")

            if self.use_ml:
                # Load category-specific models
                if training_meta and training_meta.get("ml_ready") is False:
                    return self._statistical_prediction(
                        api_id,
                        category,
                        reason_override=training_meta.get("reason") or "Model not ML-ready; using statistical fallback."
                    )

                models = self._load_or_create_category_models(category)
                if models.get("ml_ready") is False:
                    return self._statistical_prediction(
                        api_id,
                        category,
                        reason_override="Model metadata indicates fallback mode; using statistical prediction."
                    )
                
                # Use last sequence
                last_seq = sequences[-1:]
                n_samples, n_steps, n_features = last_seq.shape
                
                # Validate sequence shape
                print(f"[AI] Validating shape: got ({n_samples}, {n_steps}, {n_features}), need ({n_samples}, {self.sequence_length}, {self.n_features})")
                
                if n_steps != self.sequence_length or n_features != self.n_features:
                    print(f"[AI] Shape mismatch detected - returning insufficient data message")
                    return self._statistical_prediction(
                        api_id,
                        category,
                        reason_override=(
                            f"Shape mismatch for neural input (need {self.sequence_length}, got {n_steps}); "
                            "using statistical fallback."
                        )
                    )
                
                seq_reshaped = last_seq.reshape(-1, n_features)
                
                # Check if scaler is fitted
                try:
                    seq_scaled = models["scaler"].transform(seq_reshaped)
                except Exception as scaler_error:
                    print(f"[AI] Scaler not fitted for category {category}: {scaler_error}")
                    return self._statistical_prediction(
                        api_id,
                        category,
                        reason_override=f"Scaler/model not ready for category {category}; using statistical fallback."
                    )
                
                seq_scaled = seq_scaled.reshape(n_samples, n_steps, n_features)
                
                # LSTM Prediction (failure probability)
                lstm_prediction = models["lstm"].predict(seq_scaled, verbose=0)[0][0]
                
                # Autoencoder Anomaly Score
                reconstructions = models["autoencoder"].predict(seq_scaled, verbose=0)
                reconstruction_error = np.mean(np.square(seq_scaled - reconstructions))
                
                # Normalize reconstruction error (0-1 scale)
                # Higher error = more anomalous = higher risk
                anomaly_score = min(reconstruction_error / 0.1, 1.0)  # 0.1 is threshold
                
                # Combine LSTM and Autoencoder scores (weighted average)
                # LSTM: 70%, Autoencoder: 30%
                combined_score = (lstm_prediction * 0.7) + (anomaly_score * 0.3)
                
                # Get recent data for context
                recent_logs = list(self.db.monitoring_logs.find({
                    "api_id": api_id,
                    "check_skipped": {"$ne": True}
                }).sort("timestamp", -1).limit(50))
                
                # Calculate actual failure rate for calibration
                actual_failure_rate = 0.0
                if recent_logs:
                    failures = sum(1 for log in recent_logs if not log.get("is_up", True))
                    actual_failure_rate = failures / len(recent_logs)
                
                # Calibrate prediction with actual data
                # If model says high risk but actual failures are low, reduce confidence
                calibration_factor = 1.0
                if combined_score > 0.7 and actual_failure_rate < 0.1:
                    calibration_factor = 0.7  # Reduce confidence
                elif combined_score < 0.3 and actual_failure_rate > 0.3:
                    calibration_factor = 1.3  # Increase confidence
                
                calibrated_score = min(combined_score * calibration_factor, 1.0)
                
                # Calculate confidence (how sure the model is)
                # High confidence when LSTM and Autoencoder agree
                agreement = 1.0 - abs(lstm_prediction - anomaly_score)
                
                # Confidence also depends on data quality
                data_quality = min(len(recent_logs) / 50.0, 1.0)  # Need 50 samples for full confidence
                
                # Final confidence (0.5 to 0.95 range - never 100%)
                confidence = 0.5 + (agreement * data_quality * 0.45)
                
                # Determine risk level based on calibrated score
                if calibrated_score >= 0.70:
                    risk_level = "high"
                    will_fail = True
                elif calibrated_score >= 0.40:
                    risk_level = "medium"
                    will_fail = True
                else:
                    risk_level = "low"
                    will_fail = False
                
                # Risk score (0-100)
                risk_score = int(calibrated_score * 100)
                
                # Generate explanation
                reason = self._explain_prediction(recent_logs, calibrated_score, category)
                
                print(f"[AI] ========== PREDICTION BREAKDOWN ==========")
                print(f"[AI] LSTM Score: {lstm_prediction:.3f} (70% weight)")
                print(f"[AI] Anomaly Score: {anomaly_score:.3f} (30% weight)")
                print(f"[AI] Combined Score: {combined_score:.3f}")
                print(f"[AI] Actual Failure Rate: {actual_failure_rate:.3f}")
                print(f"[AI] Calibration Factor: {calibration_factor:.2f}")
                print(f"[AI] Calibrated Score: {calibrated_score:.3f}")
                print(f"[AI] Model Agreement: {agreement:.3f}")
                print(f"[AI] Data Quality: {data_quality:.3f} ({len(recent_logs)} samples)")
                print(f"[AI] Final Confidence: {confidence:.3f} ({confidence*100:.1f}%)")
                print(f"[AI] Risk Level: {risk_level.upper()}")
                print(f"[AI] ==========================================")

                # Extract training metadata fields for UI
                model_accuracy = None
                model_auc = None
                last_trained = None
                if training_meta:
                    try:
                        if "accuracy" in training_meta:
                            model_accuracy = float(training_meta["accuracy"])
                    except (TypeError, ValueError):
                        model_accuracy = None
                    try:
                        if "auc" in training_meta:
                            model_auc = float(training_meta["auc"])
                    except (TypeError, ValueError):
                        model_auc = None
                    last_trained = training_meta.get("last_trained") or training_meta.get("saved_at")

                return {
                    "will_fail": will_fail,
                    "failure_probability": float(calibrated_score),
                    "confidence": float(confidence),
                    "reason": reason,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "method": "lstm_autoencoder",
                    "category": category,
                    "model": f"LSTM + Autoencoder ({category})",
                    "lstm_score": float(lstm_prediction),
                    "anomaly_score": float(anomaly_score),
                    "combined_score": float(combined_score),
                    "calibrated_score": float(calibrated_score),
                    "actual_failure_rate": float(actual_failure_rate),
                    "calibration_factor": float(calibration_factor),
                    "agreement": float(agreement),
                    "data_quality": float(data_quality),
                    "sample_size": len(recent_logs),
                    "risk_factors": self._extract_risk_factors(recent_logs, category, calibrated_score),
                    "last_trained": last_trained,
                    "model_accuracy": model_accuracy,
                    "model_auc": model_auc,
                    "model_version": training_meta.get("saved_at") if training_meta else None
                }
            else:
                return self._statistical_prediction(api_id, category)
        
        except Exception as e:
            print(f"[AI] Prediction error: {e}")
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": f"Error: {str(e)}",
                "risk_score": 0,
                "risk_level": "low",
                "method": "error",
                "category": None,
                "model": "error",
                "lstm_score": 0.0,
                "anomaly_score": 0.0,
                "combined_score": 0.0,
                "calibrated_score": 0.0,
                "actual_failure_rate": 0.0,
                "calibration_factor": 1.0,
                "agreement": 0.0,
                "data_quality": 0.0,
                "sample_size": 0,
                "risk_factors": [],
                "last_trained": None,
                "model_accuracy": None,
                "model_auc": None,
                "model_version": None
            }
    
    def _explain_prediction(self, recent_logs, calibrated_score, category):
        """Generate natural-language summary for UI"""
        if not recent_logs:
            return f"Category-aware model detected a {int(calibrated_score * 100)}% risk for {category}, but recent monitoring data is limited."

        total_logs = len(recent_logs)
        failure_count = sum(1 for log in recent_logs if not log.get("is_up", True))
        failure_rate = failure_count / total_logs if total_logs else 0.0
        reasons = []

        if failure_count:
            reasons.append(f"{failure_count} of the last {total_logs} checks failed ({failure_rate*100:.1f}% failure rate)")

        latencies = [self._safe_float(log.get("total_latency_ms")) for log in recent_logs if log.get("total_latency_ms") is not None]
        if latencies:
            avg_latency = float(np.mean(latencies))
            p95_latency = float(np.percentile(latencies, 95))
            category_config = API_CATEGORIES.get(category, API_CATEGORIES["REST API"])
            latency_threshold = category_config.get("latency_threshold", 2000)
            if avg_latency > latency_threshold:
                reasons.append(f"average latency {avg_latency:.0f}ms exceeds {latency_threshold}ms threshold")
            elif p95_latency > latency_threshold * 0.9:
                reasons.append(f"95th percentile latency {p95_latency:.0f}ms nearing {latency_threshold}ms limit")

        if not reasons and calibrated_score >= 0.4:
            reasons.append("Model detected anomalous behaviour in recent patterns")

        if not reasons:
            reasons.append(f"Recent performance metrics look stable; monitoring continues")

        return "; ".join(reasons[:3])

    def _extract_risk_factors(self, recent_logs, category, calibrated_score):
        """Build machine-readable risk factors for downstream consumers"""
        risk_factors = []

        if not recent_logs:
            risk_factors.append("Insufficient recent monitoring data for detailed analysis")
            return risk_factors

        total_logs = len(recent_logs)
        failures = sum(1 for log in recent_logs if not log.get("is_up", True))
        failure_rate = failures / total_logs if total_logs else 0.0
        if failures:
            risk_factors.append(f"Failure rate {failure_rate*100:.1f}% ({failures}/{total_logs} checks)")

        # Latency analysis
        latencies = [self._safe_float(log.get("total_latency_ms"), None) for log in recent_logs if log.get("total_latency_ms") is not None]
        latencies = [lat for lat in latencies if lat is not None]
        if latencies:
            avg_latency = float(np.mean(latencies))
            max_latency = float(np.max(latencies))
            std_latency = float(np.std(latencies))
            p95_latency = float(np.percentile(latencies, 95))
            category_config = API_CATEGORIES.get(category, API_CATEGORIES["REST API"])
            expected_latency = category_config.get("expected_latency", 200)

            if avg_latency > expected_latency * 2:
                risk_factors.append(f"Latency spike: {avg_latency:.0f}ms avg (expected {expected_latency}ms)")
            elif avg_latency > expected_latency * 1.5:
                risk_factors.append(f"Sustained latency increase: {avg_latency:.0f}ms avg")

            if std_latency > expected_latency:
                risk_factors.append(f"Unstable response variability: σ {std_latency:.0f}ms")

            if max_latency > expected_latency * 3:
                risk_factors.append(f"Peak latency reached {max_latency:.0f}ms")

            if p95_latency > expected_latency * 2.5:
                risk_factors.append(f"Latency tail risk: 95th percentile at {p95_latency:.0f}ms")

        # Error codes
        error_codes = []
        for log in recent_logs:
            status_code = log.get("status_code")
            if status_code is None:
                continue
            status_code = self._safe_int(status_code)
            if status_code >= 400:
                error_codes.append(status_code)

        if error_codes:
            from collections import Counter
            for code, count in Counter(error_codes).most_common(3):
                risk_factors.append(f"HTTP {code} observed {count} times in last {total_logs} checks")

        # Temporal pattern
        if total_logs >= 10:
            recent_slice = recent_logs[:10]
            older_slice = recent_logs[10:20] if total_logs >= 20 else []
            recent_failures = sum(1 for log in recent_slice if not log.get("is_up", True))
            older_failures = sum(1 for log in older_slice if not log.get("is_up", True))
            if recent_failures >= max(3, older_failures * 1.5):
                risk_factors.append("Failure trend accelerating in latest checks")

        risk_score = int(calibrated_score * 100)
        if risk_score >= 70:
            risk_factors.append("Neural model indicates high-risk anomaly pattern")
        elif risk_score >= 40:
            risk_factors.append("Model detected concerning behavioural shift")

        if not risk_factors:
            risk_factors.append("Model flagged elevated risk without obvious metric spikes")

        return risk_factors[:5]
    
    def _statistical_prediction(self, api_id, category, reason_override=None):
        """Fallback statistical prediction"""
        time_threshold = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
        recent_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "check_skipped": {"$ne": True},
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", -1).limit(50))
        
        if len(recent_logs) < 5:
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": reason_override or "Insufficient data",
                "risk_score": 0,
                "risk_level": "low",
                "method": "statistical",
                "category": category,
                "failure_probability": 0.0,
                "lstm_score": 0.0,
                "anomaly_score": 0.0,
                "combined_score": 0.0,
                "calibrated_score": 0.0,
                "actual_failure_rate": 0.0,
                "calibration_factor": 1.0,
                "agreement": 0.0,
                "data_quality": 0.0,
                "sample_size": len(recent_logs),
                "risk_factors": [],
                "last_trained": None,
                "model_accuracy": None,
                "model_auc": None,
                "model_version": None
            }
        
        failure_rate = sum(1 for log in recent_logs if not log.get("is_up", True)) / len(recent_logs)
        category_config = API_CATEGORIES.get(category, API_CATEGORIES["REST API"])
        
        # Adjust risk based on category expectations
        expected_failure_rate = category_config.get("failure_threshold", 0.05)
        if not expected_failure_rate or expected_failure_rate == 0:
            expected_failure_rate = 0.05
        
        risk_score = int(min((failure_rate / expected_failure_rate) * 100, 100))
        failure_probability = min(max(risk_score / 100.0, 0.0), 1.0)
        confidence = min(0.95, max(0.35, 0.45 + (len(recent_logs) / 100.0)))
        
        return {
            "will_fail": risk_score >= 70,
            "failure_probability": failure_probability,
            "confidence": confidence,
            "reason": reason_override or f"Failure rate: {failure_rate*100:.1f}% ({category})",
            "risk_score": risk_score,
            "risk_level": "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low",
            "method": "statistical",
            "category": category,
            "lstm_score": None,
            "anomaly_score": None,
            "combined_score": None,
            "calibrated_score": None,
            "actual_failure_rate": failure_rate,
            "calibration_factor": None,
            "agreement": None,
            "data_quality": None,
            "sample_size": len(recent_logs),
            "risk_factors": [],
            "last_trained": None,
            "model_accuracy": None,
            "model_auc": None,
            "model_version": None
        }
    
    def detect_anomalies(self, api_id, hours=24):
        """Detect anomalies using category-specific autoencoder"""
        if not self.use_ml:
            return []
        
        try:
            sequences, _, category = self._extract_time_series(api_id, hours=hours)
            if sequences is None:
                return []

            models = self._load_or_create_category_models(category)
            if "autoencoder" not in models or "scaler" not in models:
                return []
            if models.get("ml_ready") is False:
                return []

            # Scale the data
            n_samples, n_steps, n_features = sequences.shape
            sequences_reshaped = sequences.reshape(-1, n_features)
            
            try:
                sequences_scaled = models["scaler"].transform(sequences_reshaped)
            except Exception:
                return [] # Scaler not fitted
                
            sequences_scaled = sequences_scaled.reshape(n_samples, n_steps, n_features)

            # Get reconstruction loss
            reconstructions = models["autoencoder"].predict(sequences_scaled, verbose=0)
            mse = np.mean(np.square(sequences_scaled - reconstructions), axis=(1, 2))

            # Use pre-calculated threshold
            threshold = models.get("anomaly_threshold")
            if threshold is None:
                # Fallback: calculate threshold on the fly if not present
                threshold = np.percentile(mse, 95)

            # Find anomalies
            anomalous_indices = np.where(mse > threshold)[0]
            
            if len(anomalous_indices) == 0:
                return []

            # Get original logs for anomalous sequences
            time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
            logs = list(self.db.monitoring_logs.find({
                "api_id": api_id,
                "check_skipped": {"$ne": True},
                "timestamp": {"$gte": time_threshold}
            }).sort("timestamp", 1))

            anomalies = []
            for i in anomalous_indices:
                # The anomaly is at the end of the sequence
                log_index = i + self.sequence_length
                if log_index < len(logs):
                    anomaly_log = logs[log_index]
                    anomaly_log["_id"] = str(anomaly_log["_id"])
                    anomaly_log["reconstruction_error"] = float(mse[i])
                    anomaly_log["type"] = "Reconstruction Error" # Add type for frontend
                    anomaly_log["description"] = f"High reconstruction error ({anomaly_log['reconstruction_error']:.2f}). "
                    if anomaly_log.get("error_message"):
                        anomaly_log["description"] += f"Original error: {anomaly_log['error_message']}"
                    anomalies.append(anomaly_log)
            
            return anomalies
        except Exception as e:
            print(f"[AI] Anomaly detection error: {e}")
            return []
    
    def generate_insights(self, api_id):
        """Generate insights"""
        try:
            print("[AI] Generating insights...")
            prediction = self.predict_failure(api_id)
            print(f"[AI] Prediction result: {prediction}")
            insights = []
            
            if prediction["will_fail"]:
                insights.append({
                    "type": "warning",
                    "title": f"Failure Predicted ({prediction.get('category', 'Unknown')})",
                    "message": f"Category-aware model predicts failure (confidence: {prediction['confidence']*100:.0f}%)",
                    "details": prediction["reason"],
                    "action": "Review recent changes"
                })
            
            if self.use_ml:
                insights.append({
                    "type": "info",
                    "title": "Category-Aware AI Active",
                    "message": f"Using specialized model for {prediction.get('category', 'Unknown')}",
                    "details": f"Method: {prediction.get('method', 'unknown')}",
                    "action": "Model trained for this API category"
                })
            
            print(f"[AI] Generated insights list: {insights}")
            return insights
        except Exception as e:
            print(f"[AI] Insight generation error: {e}")
            return []
    
    def find_similar_incidents(self, current_issue, limit=5):
        """Find similar incidents using TF-IDF"""
        try:
            incidents = list(self.db.incident_reports.find())
            if not incidents:
                return []

            # Create corpus
            corpus = []
            for inc in incidents:
                text = f"{inc.get('title', '')} {inc.get('summary', '')} {inc.get('root_cause', '')}"
                corpus.append(text)

            # Vectorize
            vectorizer = TfidfVectorizer(stop_words='english', max_df=0.85, min_df=1)
            tfidf_matrix = vectorizer.fit_transform(corpus)
            current_issue_vector = vectorizer.transform([current_issue])

            # Calculate similarity
            cosine_similarities = cosine_similarity(current_issue_vector, tfidf_matrix).flatten()

            # Get top N similar incidents
            similar_indices = cosine_similarities.argsort()[::-1][:limit]

            results = []
            for i in similar_indices:
                if cosine_similarities[i] > 0.1:  # Similarity threshold
                    results.append({
                        "incident": incidents[i],
                        "similarity": float(cosine_similarities[i])
                    })
            
            return results
        except Exception as e:
            print(f"[AI] Similar incidents error: {e}")
            return []
