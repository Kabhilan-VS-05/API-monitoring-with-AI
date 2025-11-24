"""
Log Collection Module
Custom MongoDB log handler for application logs
"""

import logging
from datetime import datetime

class MongoDBLogHandler(logging.Handler):
    """Custom log handler that writes to MongoDB"""
    
    def __init__(self, mongo_db):
        super().__init__()
        self.db = mongo_db
    
    def emit(self, record):
        """Store log entry in MongoDB"""
        try:
            log_doc = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "source": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line_number": record.lineno,
                "api_endpoint": getattr(record, 'api_endpoint', None),
                "error_code": getattr(record, 'error_code', None),
                "request_id": getattr(record, 'request_id', None),
                "user_id": getattr(record, 'user_id', None)
            }
            
            # Add stack trace if exception
            if record.exc_info:
                log_doc["stack_trace"] = self.format(record)
            
            # Store in MongoDB
            self.db.application_logs.insert_one(log_doc)
            
        except Exception as e:
            # Fallback to console if MongoDB fails
            print(f"[LogHandler] Error storing log: {e}")


def log_api_error(db, api_url, error_message, status_code=None, request_data=None):
    """Helper function to log API errors with context"""
    log_doc = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "error",
        "source": "api_monitor",
        "api_endpoint": api_url,
        "message": error_message,
        "error_code": status_code,
        "request_data": request_data
    }
    
    try:
        db.application_logs.insert_one(log_doc)
    except Exception as e:
        print(f"[LogCollector] Error storing API error: {e}")


def get_recent_logs(db, hours=24, level=None):
    """Get recent logs from MongoDB"""
    from datetime import timedelta
    time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    
    query = {"timestamp": {"$gte": time_threshold}}
    if level:
        query["level"] = level.upper()
    
    logs = list(db.application_logs.find(query).sort("timestamp", -1).limit(100))
    return logs


def get_logs_by_api(db, api_endpoint, hours=24):
    """Get logs for a specific API endpoint"""
    from datetime import timedelta
    time_threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    
    logs = list(db.application_logs.find({
        "api_endpoint": api_endpoint,
        "timestamp": {"$gte": time_threshold}
    }).sort("timestamp", -1).limit(50))
    return logs
