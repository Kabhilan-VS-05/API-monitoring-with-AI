import os
import time
import jwt
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

"""auth_manager.py

Simple JWT-based authentication and RBAC helpers.

Environment:
- JWT_SECRET_KEY : secret for signing tokens (required)
"""

JWT_SECRET = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "dev-secret"
JWT_ALGORITHM = "HS256"


def create_user(db, username: str, password: str, role: str = "field_worker"):
    users = db.users
    hashed = generate_password_hash(password)
    user = {
        "username": username,
        "password_hash": hashed,
        "role": role,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    users.update_one({"username": username}, {"$set": user}, upsert=True)
    return True


def authenticate(db, username: str, password: str):
    user = db.users.find_one({"username": username})
    if not user:
        return None
    if check_password_hash(user.get("password_hash", ""), password):
        return {"id": str(user.get("_id")), "username": user.get("username"), "role": user.get("role")}
    return None


def create_access_token(identity: dict, expires_in: int = 3600):
    now = int(time.time())
    payload = {
        "sub": identity.get("id"),
        "username": identity.get("username"),
        "role": identity.get("role"),
        "iat": now,
        "exp": now + int(expires_in)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT returns bytes in some versions
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def role_required(required_role):
    """Decorator for Flask endpoints: checks Authorization header for Bearer token and role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify, g
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth.split(" ", 1)[1]
            payload = decode_token(token)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401
            role = payload.get("role")
            # allow if user role is equal or higher in role hierarchy
            hierarchy = ["field_worker", "ngo_leader", "hospital_admin", "developer"]
            try:
                if hierarchy.index(role) < hierarchy.index(required_role):
                    return jsonify({"error": "Insufficient role permissions"}), 403
            except ValueError:
                return jsonify({"error": "Unknown role"}), 403
            # Attach identity to flask.g for convenience (avoids assigning to Request)
            try:
                g.jwt_payload = payload
            except Exception:
                # best-effort only; don't fail if g isn't available
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator
