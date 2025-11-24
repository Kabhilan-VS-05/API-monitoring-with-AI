"""
Background Task Manager for AI Model Training
Runs AI training in separate processes to avoid blocking the main application
Uses multiprocessing for complete isolation from the main Flask app
"""

import multiprocessing
import threading
import queue
import time
from datetime import datetime
from typing import Dict, Any, Callable
import os

class BackgroundTaskManager:
    """Manages background tasks in separate threads"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.active_tasks = {}
        self.task_results = {}
        self.worker_thread = None
        self.running = False
        
    def start(self):
        """Start the background worker thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            print("[Background Tasks] Worker thread started")
    
    def stop(self):
        """Stop the background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            print("[Background Tasks] Worker thread stopped")
    
    def _worker(self):
        """Worker thread that processes tasks from the queue"""
        while self.running:
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1)
                
                task_id = task['id']
                func = task['func']
                args = task.get('args', ())
                kwargs = task.get('kwargs', {})
                
                print(f"[Background Tasks] Processing task {task_id}")
                self.active_tasks[task_id] = {
                    'status': 'running',
                    'started_at': datetime.utcnow().isoformat()
                }
                
                try:
                    # Execute the task
                    result = func(*args, **kwargs)
                    
                    # Store result
                    self.task_results[task_id] = {
                        'status': 'completed',
                        'result': result,
                        'completed_at': datetime.utcnow().isoformat()
                    }
                    print(f"[Background Tasks] Task {task_id} completed successfully")
                    
                except Exception as e:
                    # Store error
                    self.task_results[task_id] = {
                        'status': 'failed',
                        'error': str(e),
                        'completed_at': datetime.utcnow().isoformat()
                    }
                    print(f"[Background Tasks] Task {task_id} failed: {e}")
                
                finally:
                    # Remove from active tasks
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]
                    
                    self.task_queue.task_done()
                    
            except queue.Empty:
                # No tasks in queue, continue
                continue
            except Exception as e:
                print(f"[Background Tasks] Worker error: {e}")
    
    def submit_task(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """
        Submit a task to be executed in the background
        
        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            task_id: The ID of the submitted task
        """
        task = {
            'id': task_id,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'submitted_at': datetime.utcnow().isoformat()
        }
        
        self.task_queue.put(task)
        print(f"[Background Tasks] Task {task_id} submitted to queue")
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task"""
        # Check if task is still active
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        
        # Check if task has completed
        if task_id in self.task_results:
            return self.task_results[task_id]
        
        # Task not found
        return {'status': 'not_found'}
    
    def clear_old_results(self, max_age_seconds: int = 3600):
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
            print(f"[Background Tasks] Cleared {len(to_delete)} old task results")


# Global task manager instance
task_manager = BackgroundTaskManager()
