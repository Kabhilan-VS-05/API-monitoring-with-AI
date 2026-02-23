"""
Process-Based Task Manager for AI Model Training
Runs AI training in completely separate processes for full isolation
"""

import multiprocessing
import time
import sys
import os
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def train_model_worker(api_id, force_retrain, mongodb_uri, mongodb_db, result_queue):
    """
    Worker function that runs in a separate process
    Completely isolated from the main Flask application
    """
    try:
        print(f"[Process Worker {os.getpid()}] Starting AI training for API {api_id}")
        
        # Create new MongoDB connection in this process
        mongo_client = MongoClient(mongodb_uri)
        db = mongo_client[mongodb_db]
        
        # Import AI predictor in this process
        from ai_predictor import CategoryAwareAIPredictor as AIPredictor
        
        # Create AI predictor instance
        ai = AIPredictor(db)
        
        # Train the model
        result = ai.train_model_for_api_category(api_id, force_retrain=force_retrain)
        
        if result:
            print(f"[Process Worker {os.getpid()}] Training completed for API {api_id}")
            
            # Check prediction and send alert if needed
            try:
                prediction = ai.predict_failure(api_id)
                failure_prob = prediction.get('failure_probability', 0) if prediction else 0
                
                print(f"[Process Worker {os.getpid()}] Prediction: {failure_prob*100:.0f}% risk")
                
                if failure_prob >= 0.70:
                    print(f"[Process Worker {os.getpid()}] HIGH RISK detected!")
                    
                    # Check if alert already exists
                    existing_alert = db.alert_history.find_one({
                        "api_id": api_id,
                        "alert_type": "ai_prediction",
                        "status": "open"
                    })
                    
                    if not existing_alert:
                        print(f"[Process Worker {os.getpid()}] Sending AI prediction alert...")
                        from ai_alert_manager import AIAlertManager
                        ai_alert_mgr = AIAlertManager(db)
                        api_url = "Unknown API"
                        try:
                            api_doc = db.monitored_apis.find_one({"_id": ObjectId(api_id)})
                            if api_doc:
                                api_url = api_doc.get("url", "Unknown API")
                        except Exception:
                            # Keep fallback URL if ObjectId conversion or lookup fails
                            pass

                        alert_result = ai_alert_mgr.create_ai_prediction_alert(
                            api_id,
                            api_url,
                            prediction
                        )
                        if alert_result and alert_result.get("success"):
                            print(f"[Process Worker {os.getpid()}] Alert sent successfully")
                        else:
                            print(f"[Process Worker {os.getpid()}] Alert send failed: {alert_result}")
                    else:
                        print(f"[Process Worker {os.getpid()}] Alert already exists")
                else:
                    print(f"[Process Worker {os.getpid()}] Risk is low, no alert needed")
                    
            except Exception as alert_error:
                print(f"[Process Worker {os.getpid()}] Error with alert: {alert_error}")
            
            # Send success result back
            result_queue.put({
                'status': 'success',
                'api_id': api_id,
                'message': 'Training completed successfully',
                'prediction': prediction if 'prediction' in locals() else None
            })
        else:
            # Send skip result back
            result_queue.put({
                'status': 'skipped',
                'api_id': api_id,
                'message': 'Training skipped (insufficient data)'
            })
        
        # Close MongoDB connection
        mongo_client.close()
        print(f"[Process Worker {os.getpid()}] Process completed successfully")
        
    except Exception as e:
        print(f"[Process Worker {os.getpid()}] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Send error result back
        result_queue.put({
            'status': 'error',
            'api_id': api_id,
            'error': str(e)
        })


class ProcessTaskManager:
    """
    Manages AI training tasks in separate processes
    Each training runs in complete isolation from the main app
    """
    
    def __init__(self, mongodb_uri, mongodb_db):
        self.mongodb_uri = mongodb_uri
        self.mongodb_db = mongodb_db
        self.active_processes = {}
        self.result_queue = multiprocessing.Queue()
        self.task_results = {}
        self.monitor_thread = None
        self.running = False
        
        # Set multiprocessing start method
        try:
            multiprocessing.set_start_method('spawn')
        except RuntimeError:
            # Already set
            pass
    
    def start(self):
        """Start the result monitor thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_results, daemon=True)
            self.monitor_thread.start()
            print("[Process Task Manager] Monitor thread started")
    
    def stop(self):
        """Stop the monitor thread and terminate all processes"""
        self.running = False
        
        # Terminate all active processes
        for task_id, process in list(self.active_processes.items()):
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        print("[Process Task Manager] Stopped")
    
    def _monitor_results(self):
        """Monitor thread that collects results from worker processes"""
        import threading
        
        while self.running:
            try:
                # Check for results with timeout
                if not self.result_queue.empty():
                    result = self.result_queue.get(timeout=1)
                    
                    api_id = result.get('api_id')
                    task_id = f"train_{api_id}"
                    
                    # Store result
                    self.task_results[task_id] = {
                        'status': result.get('status'),
                        'result': result,
                        'completed_at': datetime.utcnow().isoformat()
                    }
                    
                    print(f"[Process Task Manager] Task {task_id} completed with status: {result.get('status')}")
                    
                    # Clean up process reference
                    if task_id in self.active_processes:
                        process = self.active_processes[task_id]
                        if not process.is_alive():
                            del self.active_processes[task_id]
                
                # Clean up finished processes
                for task_id, process in list(self.active_processes.items()):
                    if not process.is_alive():
                        del self.active_processes[task_id]
                
                time.sleep(0.5)
                
            except Exception as e:
                if self.running:
                    print(f"[Process Task Manager] Monitor error: {e}")
                time.sleep(1)
    
    def submit_training_task(self, api_id, force_retrain=False):
        """
        Submit AI training task to run in a separate process
        
        Args:
            api_id: API ID to train model for
            force_retrain: Whether to force retraining
        
        Returns:
            task_id: Unique task identifier
        """
        task_id = f"train_{api_id}_{int(time.time())}"
        
        # Create new process for this training task
        process = multiprocessing.Process(
            target=train_model_worker,
            args=(api_id, force_retrain, self.mongodb_uri, self.mongodb_db, self.result_queue),
            name=f"AITraining-{api_id}"
        )
        
        # Start the process
        process.start()
        
        # Store process reference
        self.active_processes[task_id] = process
        
        print(f"[Process Task Manager] Started process {process.pid} for task {task_id}")
        
        return task_id
    
    def get_task_status(self, task_id):
        """Get the status of a training task"""
        # Check if process is still running
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            if process.is_alive():
                return {
                    'status': 'running',
                    'pid': process.pid
                }
        
        # Check if task has completed
        if task_id in self.task_results:
            return self.task_results[task_id]
        
        return {'status': 'not_found'}
    
    def clear_old_results(self, max_age_seconds=3600):
        """Clear task results older than max_age_seconds"""
        current_time = datetime.utcnow()
        to_delete = []
        
        for task_id, result in self.task_results.items():
            completed_at = datetime.fromisoformat(result['completed_at'])
            age = (current_time - completed_at).total_seconds()
            
            if age > max_age_seconds:
                to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.task_results[task_id]
        
        if to_delete:
            print(f"[Process Task Manager] Cleared {len(to_delete)} old results")


# Import threading for monitor thread
import threading
