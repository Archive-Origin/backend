from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from config import settings

AUTH_WINDOW_SECONDS = 300

@dataclass
class ClientIdentity:
    api_key: Optional[str]
    name: str
    authenticated: bool
    rate_limit: int
    allow_manifest_summary: bool

def _now_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())

def authenticate_request(headers, payload_content_hash: Optional[str]) -> ClientIdentity:
    api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    if not api_key:
        return ClientIdentity(
            api_key=None,
            name="anonymous",
            authenticated=False,
            rate_limit=settings.anonymous_rate_limit_per_minute,
            allow_manifest_summary=settings.allow_manifest_summary,
        )

    key_record = settings.verifier_api_keys.get(api_key)
    if not key_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    timestamp_header = headers.get("X-Api-Timestamp")
    signature_header = headers.get("X-Api-Signature")
    if not timestamp_header or not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_hmac_headers")

    try:
        timestamp = int(timestamp_header)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_timestamp") from None

    if abs(_now_epoch() - timestamp) > AUTH_WINDOW_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="timestamp_out_of_window")

    message = f"{timestamp}:{payload_content_hash or ''}"
    secret = key_record["hmac_secret"].encode("utf-8")
    expected = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    rate_limit = key_record.get("rate_limit_per_minute") or settings.authenticated_rate_limit_per_minute
    allow_manifest_summary = bool(key_record.get("allow_manifest_summary"))

    return ClientIdentity(
        api_key=api_key,
        name=key_record.get("name", "trusted"),
        authenticated=True,
        rate_limit=rate_limit,
        allow_manifest_summary=allow_manifest_summary,
    )
