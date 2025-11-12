from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt

from config import settings

logger = logging.getLogger("archiveorigin.devicecheck")

BASE_URLS = {
    "production": "https://api.devicecheck.apple.com/v1",
    "development": "https://api.development.devicecheck.apple.com/v1",
}


class DeviceCheckError(Exception):
    def __init__(self, reason: str, status_code: Optional[int] = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


@dataclass
class DeviceCheckResult:
    transaction_id: str
    timestamp: int


class DeviceCheckClient:
    def __init__(
        self,
        team_id: str,
        key_id: str,
        private_key: str,
        environment: str = "production",
        timeout_seconds: float = 5.0,
    ):
        self.team_id = team_id
        self.key_id = key_id
        self.private_key = private_key
        self.base_url = BASE_URLS.get(environment, BASE_URLS["production"])
        self.http = httpx.Client(timeout=timeout_seconds)

    def _jwt(self) -> str:
        headers = {"alg": "ES256", "kid": self.key_id}
        payload = {"iss": self.team_id, "iat": int(time.time())}
        return jwt.encode(payload, self.private_key, algorithm="ES256", headers=headers)

    def validate(self, device_token: str, device_id: Optional[str] = None, bundle_id: Optional[str] = None) -> DeviceCheckResult:
        if not device_token:
            raise DeviceCheckError("missing_device_token")
        token = self._jwt()
        transaction_id = str(uuid.uuid4())
        body = {
            "device_token": device_token,
            "transaction_id": transaction_id,
            "timestamp": int(time.time()),
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = self.http.post(f"{self.base_url}/validate_device_token", json=body, headers=headers)
        if response.status_code == 200:
            logger.debug("DeviceCheck validation success for device_id=%s bundle_id=%s", device_id, bundle_id)
            return DeviceCheckResult(transaction_id=transaction_id, timestamp=body["timestamp"])

        reason = response.text or "devicecheck_error"
        logger.warning(
            "DeviceCheck validation failed status=%s device_id=%s bundle_id=%s response=%s",
            response.status_code,
            device_id,
            bundle_id,
            reason,
        )
        if response.status_code == 400:
            raise DeviceCheckError("invalid_device_token", response.status_code)
        if response.status_code == 401:
            raise DeviceCheckError("unauthorized", response.status_code)
        if response.status_code == 429:
            raise DeviceCheckError("rate_limited", response.status_code)
        raise DeviceCheckError("devicecheck_service_error", response.status_code)

    def close(self):
        self.http.close()


_client: Optional[DeviceCheckClient] = None


def get_devicecheck_client() -> DeviceCheckClient:
    global _client
    if _client is None:
        if not settings.devicecheck_enabled:
            raise DeviceCheckError("devicecheck_disabled")
        _client = DeviceCheckClient(
            team_id=settings.devicecheck_team_id,
            key_id=settings.devicecheck_key_id,
            private_key=settings.devicecheck_private_key,
            environment=settings.devicecheck_environment,
        )
    return _client
