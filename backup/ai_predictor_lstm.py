"""
AI Prediction Engine with LSTM + Autoencoder Hybrid Model
Advanced deep learning for time-series prediction and anomaly detection
"""

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pickle
import os
import json

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from sklearn.preprocessing import StandardScaler
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("[WARNING] TensorFlow not installed. Using fallback statistical methods.")

class AIPredictor:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self.model_path = "models/lstm_model.h5"
        self.autoencoder_path = "models/autoencoder_model.h5"
        self.scaler_path = "models/scaler.pkl"
        self.config_path = "models/model_config.json"
        
        # Create models directory
        os.makedirs("models", exist_ok=True)
        
        # Model parameters
        self.sequence_length = 20  # Use last 20 time steps
        self.n_features = 10  # Number of features per time step
        
        # Load or initialize models
        if TENSORFLOW_AVAILABLE:
            self.lstm_model = self._load_or_create_lstm()
            self.autoencoder = self._load_or_create_autoencoder()
            self.scaler = self._load_or_create_scaler()
            self.use_ml = True
            print("[AI] LSTM + Autoencoder initialized")
        else:
            self.lstm_model = None
            self.autoencoder = None
            self.scaler = None
            self.use_ml = False
    
    def _load_or_create_lstm(self):
        """Load existing LSTM model or create new one"""
        if os.path.exists(self.model_path):
            try:
                model = keras.models.load_model(self.model_path)
                print("[AI] Loaded existing LSTM model")
                return model
            except Exception as e:
                print(f"[AI] Error loading LSTM model: {e}")
        
        # Create new LSTM model for failure prediction
        model = keras.Sequential([
            layers.LSTM(64, return_sequences=True, input_shape=(self.sequence_length, self.n_features)),
            layers.Dropout(0.2),
            layers.LSTM(32, return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(16, activation='relu'),
            layers.Dense(1, activation='sigmoid')  # Binary classification
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy', 'AUC']
        )
        
        print("[AI] Created new LSTM model")
        return model
    
    def _load_or_create_autoencoder(self):
        """Load existing Autoencoder or create new one"""
        if os.path.exists(self.autoencoder_path):
            try:
                model = keras.models.load_model(self.autoencoder_path)
                print("[AI] Loaded existing Autoencoder")
                return model
            except Exception as e:
                print(f"[AI] Error loading Autoencoder: {e}")
        
        # Create new Autoencoder for anomaly detection
        input_layer = layers.Input(shape=(self.sequence_length, self.n_features))
        
        # Encoder
        encoded = layers.LSTM(32, return_sequences=True)(input_layer)
        encoded = layers.LSTM(16, return_sequences=False)(encoded)
        
        # Decoder
        decoded = layers.RepeatVector(self.sequence_length)(encoded)
        decoded = layers.LSTM(16, return_sequences=True)(decoded)
        decoded = layers.LSTM(32, return_sequences=True)(decoded)
        decoded = layers.TimeDistributed(layers.Dense(self.n_features))(decoded)
        
        autoencoder = keras.Model(input_layer, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        
        print("[AI] Created new Autoencoder")
        return autoencoder
    
    def _load_or_create_scaler(self):
        """Load existing scaler or create new one"""
        if os.path.exists(self.scaler_path):
            try:
                with open(self.scaler_path, 'rb') as f:
                    scaler = pickle.load(f)
                print("[AI] Loaded existing scaler")
                return scaler
            except Exception as e:
                print(f"[AI] Error loading scaler: {e}")
        
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        print("[AI] Created new scaler")
        return scaler
    
    def _save_models(self):
        """Save trained models"""
        try:
            if self.lstm_model:
                self.lstm_model.save(self.model_path)
            if self.autoencoder:
                self.autoencoder.save(self.autoencoder_path)
            if self.scaler:
                with open(self.scaler_path, 'wb') as f:
                    pickle.dump(self.scaler, f)
            
            # Save config
            config = {
                "sequence_length": self.sequence_length,
                "n_features": self.n_features,
                "trained": True,
                "last_trained": datetime.utcnow().isoformat()
            }
            with open(self.config_path, 'w') as f:
                json.dump(config, f)
            
            print("[AI] Models saved successfully")
        except Exception as e:
            print(f"[AI] Error saving models: {e}")
    
    def _extract_time_series(self, api_id, hours=48):
        """
        Extract time-series data for LSTM
        Returns: (sequences, labels)
        """
        time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        
        # Get monitoring logs
        logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", 1))
        
        if len(logs) < self.sequence_length + 1:
            return None, None
        
        # Extract features for each time step
        features_list = []
        labels_list = []
        
        for log in logs:
            features = [
                1.0 if log.get("is_up", True) else 0.0,  # Status
                log.get("total_latency_ms", 0) / 1000.0,  # Latency (seconds)
                log.get("dns_latency_ms", 0) / 1000.0,
                log.get("tcp_latency_ms", 0) / 1000.0,
                log.get("tls_latency_ms", 0) / 1000.0,
                log.get("server_processing_latency_ms", 0) / 1000.0,
                log.get("content_download_latency_ms", 0) / 1000.0,
                log.get("status_code", 200) / 500.0,  # Normalize status code
                1.0 if log.get("error_message") else 0.0,  # Has error
                0.0  # Placeholder for additional features
            ]
            features_list.append(features)
            
            # Label: 1 if next check fails, 0 if succeeds
            label = 0.0 if log.get("is_up", True) else 1.0
            labels_list.append(label)
        
        # Create sequences
        sequences = []
        labels = []
        
        for i in range(len(features_list) - self.sequence_length):
            seq = features_list[i:i + self.sequence_length]
            label = labels_list[i + self.sequence_length]
            sequences.append(seq)
            labels.append(label)
        
        return np.array(sequences), np.array(labels)
    
    def train_models(self, api_ids=None, epochs=50, batch_size=32):
        """
        Train LSTM and Autoencoder models
        """
        if not self.use_ml:
            print("[AI] TensorFlow not available, skipping training")
            return False
        
        print("[AI] Starting model training...")
        print(f"[AI] Epochs: {epochs}, Batch size: {batch_size}")
        
        # Get all API IDs if not specified
        if api_ids is None:
            api_ids = [doc["_id"] for doc in self.db.monitored_apis.find({}, {"_id": 1})]
            api_ids = [str(id) for id in api_ids]
        
        if not api_ids:
            print("[AI] No APIs to train on")
            return False
        
        # Collect training data
        all_sequences = []
        all_labels = []
        
        for api_id in api_ids:
            sequences, labels = self._extract_time_series(api_id)
            if sequences is not None and len(sequences) > 0:
                all_sequences.append(sequences)
                all_labels.append(labels)
        
        if not all_sequences:
            print("[AI] Insufficient training data")
            return False
        
        # Combine all data
        X = np.vstack(all_sequences)
        y = np.concatenate(all_labels)
        
        print(f"[AI] Training on {len(X)} sequences from {len(api_ids)} APIs")
        
        # Reshape for scaling
        n_samples, n_steps, n_features = X.shape
        X_reshaped = X.reshape(-1, n_features)
        
        # Fit scaler
        X_scaled = self.scaler.fit_transform(X_reshaped)
        X_scaled = X_scaled.reshape(n_samples, n_steps, n_features)
        
        # Split train/validation
        split_idx = int(len(X_scaled) * 0.8)
        X_train, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        print("\n[AI] Training LSTM for failure prediction...")
        
        # Train LSTM
        history_lstm = self.lstm_model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            verbose=1,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(patience=5, factor=0.5)
            ]
        )
        
        # Evaluate LSTM
        lstm_loss, lstm_acc, lstm_auc = self.lstm_model.evaluate(X_val, y_val, verbose=0)
        print(f"\n[AI] LSTM Validation Accuracy: {lstm_acc*100:.2f}%")
        print(f"[AI] LSTM AUC Score: {lstm_auc:.3f}")
        
        print("\n[AI] Training Autoencoder for anomaly detection...")
        
        # Train Autoencoder (only on normal data)
        X_normal = X_scaled[y == 0]
        
        if len(X_normal) > 10:
            history_ae = self.autoencoder.fit(
                X_normal, X_normal,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=0.2,
                verbose=1,
                callbacks=[
                    keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)
                ]
            )
            
            # Calculate reconstruction error threshold
            reconstructions = self.autoencoder.predict(X_normal, verbose=0)
            mse = np.mean(np.square(X_normal - reconstructions), axis=(1, 2))
            self.anomaly_threshold = np.percentile(mse, 95)  # 95th percentile
            
            print(f"[AI] Autoencoder trained. Anomaly threshold: {self.anomaly_threshold:.4f}")
        else:
            print("[AI] Not enough normal data for Autoencoder training")
        
        # Save models
        self._save_models()
        
        print("\n" + "=" * 60)
        print("✅ Training Complete!")
        print("=" * 60)
        print(f"LSTM Accuracy: {lstm_acc*100:.2f}%")
        print(f"LSTM AUC: {lstm_auc:.3f}")
        print(f"Total Sequences: {len(X)}")
        print(f"Models saved to: models/")
        
        return True
    
    def predict_failure(self, api_id, hours_ahead=1):
        """
        Predict if API will fail using LSTM
        """
        try:
            sequences, _ = self._extract_time_series(api_id, hours=48)
            
            if sequences is None or len(sequences) == 0:
                return {
                    "will_fail": False,
                    "confidence": 0.0,
                    "reason": "Insufficient data for prediction",
                    "risk_score": 0,
                    "method": "none"
                }
            
            if self.use_ml and self.lstm_model:
                # Use last sequence for prediction
                last_sequence = sequences[-1:]
                
                # Scale
                n_samples, n_steps, n_features = last_sequence.shape
                seq_reshaped = last_sequence.reshape(-1, n_features)
                seq_scaled = self.scaler.transform(seq_reshaped)
                seq_scaled = seq_scaled.reshape(n_samples, n_steps, n_features)
                
                # Predict
                prediction = self.lstm_model.predict(seq_scaled, verbose=0)[0][0]
                
                will_fail = bool(prediction > 0.5)
                confidence = float(prediction)
                risk_score = int(confidence * 100)
                
                # Get recent metrics for explanation
                recent_logs = list(self.db.monitoring_logs.find({
                    "api_id": api_id
                }).sort("timestamp", -1).limit(10))
                
                reason = self._explain_lstm_prediction(recent_logs, confidence)
                
                return {
                    "will_fail": will_fail,
                    "confidence": confidence,
                    "reason": reason,
                    "risk_score": risk_score,
                    "method": "lstm",
                    "model": "LSTM + Autoencoder Hybrid"
                }
            else:
                # Fallback to statistical method
                return self._statistical_prediction(api_id)
        
        except Exception as e:
            print(f"[AI] Prediction error: {e}")
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": f"Prediction error: {str(e)}",
                "risk_score": 0,
                "method": "error"
            }
    
    def detect_anomalies_ml(self, api_id, hours=24):
        """
        Detect anomalies using Autoencoder
        """
        if not self.use_ml or not self.autoencoder:
            return self.detect_anomalies_statistical(api_id, hours)
        
        try:
            sequences, _ = self._extract_time_series(api_id, hours=hours)
            
            if sequences is None or len(sequences) == 0:
                return []
            
            # Scale sequences
            n_samples, n_steps, n_features = sequences.shape
            seq_reshaped = sequences.reshape(-1, n_features)
            seq_scaled = self.scaler.transform(seq_reshaped)
            seq_scaled = seq_scaled.reshape(n_samples, n_steps, n_features)
            
            # Get reconstructions
            reconstructions = self.autoencoder.predict(seq_scaled, verbose=0)
            
            # Calculate reconstruction errors
            mse = np.mean(np.square(seq_scaled - reconstructions), axis=(1, 2))
            
            # Detect anomalies
            anomalies = []
            threshold = getattr(self, 'anomaly_threshold', np.percentile(mse, 95))
            
            # Get timestamps
            logs = list(self.db.monitoring_logs.find({
                "api_id": api_id
            }).sort("timestamp", 1).limit(len(sequences) + self.sequence_length))
            
            for i, error in enumerate(mse):
                if error > threshold:
                    log_idx = i + self.sequence_length
                    if log_idx < len(logs):
                        log = logs[log_idx]
                        anomalies.append({
                            "type": "autoencoder_anomaly",
                            "timestamp": log.get("timestamp"),
                            "severity": "high" if error > threshold * 1.5 else "medium",
                            "description": f"Unusual pattern detected (error: {error:.4f})",
                            "reconstruction_error": float(error),
                            "threshold": float(threshold)
                        })
            
            return anomalies[-10:]  # Return last 10
            
        except Exception as e:
            print(f"[AI] Anomaly detection error: {e}")
            return self.detect_anomalies_statistical(api_id, hours)
    
    def _explain_lstm_prediction(self, recent_logs, confidence):
        """Generate explanation for LSTM prediction"""
        if not recent_logs:
            return "LSTM neural network prediction"
        
        reasons = []
        
        # Analyze recent patterns
        failure_count = sum(1 for log in recent_logs if not log.get("is_up", True))
        if failure_count > 0:
            reasons.append(f"{failure_count} recent failures")
        
        latencies = [log.get("total_latency_ms", 0) for log in recent_logs if log.get("total_latency_ms")]
        if latencies:
            avg_latency = np.mean(latencies)
            if avg_latency > 1000:
                reasons.append(f"High latency: {avg_latency:.0f}ms")
        
        error_count = sum(1 for log in recent_logs if log.get("error_message"))
        if error_count > 0:
            reasons.append(f"{error_count} errors detected")
        
        if not reasons:
            if confidence > 0.7:
                reasons.append("LSTM detected failure pattern")
            else:
                reasons.append("Normal operation pattern")
        
        return " | ".join(reasons)
    
    def _statistical_prediction(self, api_id):
        """Fallback statistical prediction"""
        # Simple statistical method (copy from original)
        time_threshold = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
        
        recent_logs = list(self.db.monitoring_logs.find({
            "api_id": api_id,
            "timestamp": {"$gte": time_threshold}
        }).sort("timestamp", -1).limit(50))
        
        if len(recent_logs) < 5:
            return {
                "will_fail": False,
                "confidence": 0.0,
                "reason": "Insufficient data",
                "risk_score": 0,
                "method": "statistical"
            }
        
        failure_rate = sum(1 for log in recent_logs if not log.get("is_up", True)) / len(recent_logs)
        risk_score = int(min(failure_rate * 200, 100))
        
        return {
            "will_fail": risk_score > 70,
            "confidence": risk_score / 100,
            "reason": f"Failure rate: {failure_rate*100:.1f}%",
            "risk_score": risk_score,
            "method": "statistical"
        }
    
    def detect_anomalies_statistical(self, api_id, hours=24):
        """Statistical anomaly detection (fallback)"""
        # Copy from original ai_predictor.py
        try:
            time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
            
            logs = list(self.db.monitoring_logs.find({
                "api_id": api_id,
                "timestamp": {"$gte": time_threshold}
            }).sort("timestamp", 1))
            
            if len(logs) < 10:
                return []
            
            anomalies = []
            latencies = [log.get("total_latency_ms", 0) for log in logs if log.get("total_latency_ms")]
            
            if latencies:
                mean_latency = np.mean(latencies)
                std_latency = np.std(latencies)
                threshold = mean_latency + (2 * std_latency)
                
                for log in logs:
                    latency = log.get("total_latency_ms", 0)
                    if latency > threshold and latency > 1000:
                        anomalies.append({
                            "type": "latency_spike",
                            "timestamp": log.get("timestamp"),
                            "severity": "high",
                            "description": f"Latency spike: {latency:.0f}ms (normal: {mean_latency:.0f}ms)"
                        })
            
            return anomalies[-10:]
        except:
            return []
    
    # Wrapper methods
    def detect_anomalies(self, api_id, hours=24):
        """Detect anomalies (uses ML if available)"""
        if self.use_ml:
            return self.detect_anomalies_ml(api_id, hours)
        return self.detect_anomalies_statistical(api_id, hours)
    
    def generate_insights(self, api_id):
        """Generate AI insights"""
        try:
            prediction = self.predict_failure(api_id)
            anomalies = self.detect_anomalies(api_id)
            
            insights = []
            
            if prediction["will_fail"]:
                insights.append({
                    "type": "warning",
                    "title": "⚠️ Failure Predicted (LSTM)",
                    "message": f"Deep learning predicts failure (confidence: {prediction['confidence']*100:.0f}%)",
                    "details": prediction["reason"],
                    "action": "Review recent changes and monitor closely"
                })
            elif prediction["risk_score"] > 30:
                insights.append({
                    "type": "info",
                    "title": "ℹ️ Elevated Risk",
                    "message": f"Risk score: {prediction['risk_score']}/100",
                    "details": prediction["reason"],
                    "action": "Monitor performance metrics"
                })
            
            if anomalies:
                critical = [a for a in anomalies if a.get("severity") == "high"]
                if critical:
                    insights.append({
                        "type": "error",
                        "title": "🚨 Anomalies Detected",
                        "message": f"{len(critical)} anomalies found",
                        "details": "; ".join([a["description"] for a in critical[:3]]),
                        "action": "Investigate immediately"
                    })
            
            if self.use_ml:
                insights.append({
                    "type": "info",
                    "title": "🧠 Deep Learning Active",
                    "message": "Using LSTM + Autoencoder Hybrid",
                    "details": f"Method: {prediction.get('method', 'unknown')}",
                    "action": "Neural network continuously learning"
                })
            
            return insights
        except Exception as e:
            print(f"[Insights] Error: {e}")
            return []
    
    def find_similar_incidents(self, current_issue, limit=5):
        """Find similar past incidents"""
        # Same as before
        try:
            incidents = list(self.db.incident_reports.find().sort("created_at", -1).limit(50))
            if not incidents:
                return []
            
            current_keywords = self._extract_keywords(current_issue)
            similar = []
            
            for incident in incidents:
                incident_text = f"{incident.get('title', '')} {incident.get('summary', '')} {incident.get('root_cause', '')}"
                incident_keywords = self._extract_keywords(incident_text)
                similarity = self._jaccard_similarity(current_keywords, incident_keywords)
                
                if similarity > 0.1:
                    similar.append({
                        "incident": incident,
                        "similarity": similarity,
                        "matching_keywords": list(current_keywords & incident_keywords)
                    })
            
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar[:limit]
        except:
            return []
    
    def _extract_keywords(self, text):
        """Extract keywords"""
        if not text:
            return set()
        words = text.lower().split()
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were'}
        return {word for word in words if len(word) > 3 and word not in stopwords}
    
    def _jaccard_similarity(self, set1, set2):
        """Calculate Jaccard similarity"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
