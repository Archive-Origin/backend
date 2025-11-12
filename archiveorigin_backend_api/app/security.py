import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

def new_token_urlsafe(n_bytes: int = 64) -> str:
    return secrets.token_urlsafe(n_bytes)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def calc_expiry(ttl_seconds: int) -> datetime:
    return now_utc() + timedelta(seconds=ttl_seconds)

def is_expired(expires_at: datetime) -> bool:
    return expires_at <= now_utc()

def near_expiry(expires_at: datetime, buffer_seconds: int) -> bool:
    return (expires_at - now_utc()).total_seconds() <= buffer_seconds

def validate_pubkey_format(public_key: str) -> bool:
    # Expected format ed25519:base64
    if not public_key.startswith("ed25519:"):
        return False
    b64 = public_key.split("ed25519:", 1)[1]
    try:
        base64.b64decode(b64, validate=True)
        return True
    except Exception:
        return False

def validate_signature(pubkey: str, message: bytes, signature_b64: str) -> bool:
    try:
        import nacl.signing, nacl.encoding
    except Exception:
        return False
    if not pubkey.startswith("ed25519:"):
        return False
    pub_b64 = pubkey.split("ed25519:", 1)[1]
    try:
        verify_key = nacl.signing.VerifyKey(base64.b64decode(pub_b64), encoder=nacl.encoding.RawEncoder)
        sig = base64.b64decode(signature_b64.split("ed25519_sig:", 1)[1])
        verify_key.verify(message, sig)
        return True
    except Exception:
        return False
