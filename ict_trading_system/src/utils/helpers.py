
import hashlib
import hmac
import os
from ict_trading_system.config import settings
from cryptography.fernet import Fernet, InvalidToken

# --- API Key Encryption Helpers ---
def get_fernet():
    key = getattr(settings, "API_KEY_ENCRYPTION_KEY", None)
    if not key:
        raise RuntimeError("API_KEY_ENCRYPTION_KEY not set in config.")
    return Fernet(key.encode())

def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage at rest."""
    f = get_fernet()
    return f.encrypt(api_key.encode()).decode()

def decrypt_api_key(token: str) -> str:
    """Decrypt an API key for use."""
    f = get_fernet()
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid encrypted API key token.")

def verify_webhook_secret(secret: str) -> bool:
    return hmac.compare_digest(secret, settings.WEBHOOK_SECRET)


def hash_api_key(key: str) -> str:
    """Hash an API key for storage/verification."""
    return hashlib.sha256(key.encode()).hexdigest()

def sanitize_string(s: str) -> str:
    """Basic input sanitization: remove dangerous characters."""
    import re
    return re.sub(r'[^\w\-\.@:, ]', '', s)

def sanitize_payload(payload: dict) -> dict:
    """Sanitize all string fields in a dict payload."""
    for k, v in payload.items():
        if isinstance(v, str):
            payload[k] = sanitize_string(v)
        elif isinstance(v, dict):
            payload[k] = sanitize_payload(v)
    return payload
