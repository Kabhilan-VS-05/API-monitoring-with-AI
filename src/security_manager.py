import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

"""security_manager.py

Provides AES-256-GCM encryption/decryption helpers for secure storage
and convenience methods to encrypt/decrypt API keys and other secrets.

Environment:
- SECURITY_MASTER_KEY : base64-encoded 32-byte key (preferred)
  or a passphrase (will be hashed to 32 bytes).
"""


def _get_master_key():
    key_env = os.getenv("SECURITY_MASTER_KEY")
    if not key_env:
        raise RuntimeError("SECURITY_MASTER_KEY environment variable is required")

    # Accept a base64-encoded key or derive from passphrase
    try:
        key = base64.b64decode(key_env)
        if len(key) == 32:
            return key
    except Exception:
        pass

    # Fallback: derive 32-byte key from passphrase
    from hashlib import sha256
    return sha256(key_env.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext and return token string (base64 of nonce+ciphertext+tag)."""
    if plaintext is None:
        return None
    key = _get_master_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    token = base64.b64encode(nonce + ct).decode("utf-8")
    return f"enc:{token}"


def decrypt_secret(token: str) -> str:
    """Decrypt token produced by encrypt_secret. If token is plain return as-is."""
    if token is None:
        return None
    if not isinstance(token, str):
        return token
    if not token.startswith("enc:"):
        return token

    try:
        key = _get_master_key()
        b = base64.b64decode(token.split(":", 1)[1])
        nonce = b[:12]
        ct = b[12:]
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Decryption failed: {e}")


def decrypt_if_needed(value):
    """Utility: decrypts only if value looks encrypted (starts with 'enc:')"""
    try:
        return decrypt_secret(value) if isinstance(value, str) and value.startswith("enc:") else value
    except Exception:
        return value


def secure_store_fields(doc: dict, fields: list):
    """Encrypt selected fields in a dict in-place using encrypt_secret.
    Returns the modified dict."""
    for f in fields:
        if f in doc and doc[f]:
            try:
                doc[f] = encrypt_secret(str(doc[f]))
            except Exception:
                pass
    return doc
