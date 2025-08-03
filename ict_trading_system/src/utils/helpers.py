import hashlib
import hmac
import os
from config import settings

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
