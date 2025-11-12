"""
DeviceCheck Integration Module - MOCK IMPLEMENTATION

⚠️ THIS IS MOCK CODE FOR DEVELOPMENT
Replace with real implementation when ready for production.
See DEVELOPMENT_ROADMAP.md for details.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("archiveorigin.devicecheck")


class DeviceCheckError(Exception):
    """DeviceCheck API error"""
    def __init__(self, reason: str, status_code: Optional[int] = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


@dataclass
class DeviceCheckResult:
    """Mock DeviceCheck validation result"""
    transaction_id: str
    timestamp: int


class DeviceCheckClient:
    """
    MOCK DeviceCheck Client
    
    This is a mock implementation for development.
    Replace with real httpx/jwt implementation for production.
    """
    
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
        self.environment = environment
        self.timeout_seconds = timeout_seconds
        logger.info("MOCK DeviceCheckClient initialized (environment=%s)", environment)

    def _jwt(self) -> str:
        """MOCK: Generate JWT token"""
        # TODO: Replace with real jwt.encode() using ES256
        return f"mock_jwt_token_{int(time.time())}"

    def validate(
        self, 
        device_token: str, 
        device_id: Optional[str] = None, 
        bundle_id: Optional[str] = None
    ) -> DeviceCheckResult:
        """
        MOCK: Validate device token
        
        TODO: Replace with real httpx POST to Apple's DeviceCheck API
        """
        if not device_token:
            raise DeviceCheckError("missing_device_token")
        
        # MOCK: Always return success
        transaction_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        logger.debug(
            "MOCK DeviceCheck validation for device_id=%s bundle_id=%s",
            device_id,
            bundle_id
        )
        
        return DeviceCheckResult(transaction_id=transaction_id, timestamp=timestamp)

    def close(self):
        """Close HTTP client"""
        logger.debug("MOCK DeviceCheckClient closed")


_client: Optional[DeviceCheckClient] = None


def get_devicecheck_client() -> DeviceCheckClient:
    """Get or create singleton DeviceCheck client"""
    global _client
    if _client is None:
        # TODO: Load from settings when ready for production
        _client = DeviceCheckClient(
            team_id="MOCK_TEAM_ID",
            key_id="MOCK_KEY_ID",
            private_key="MOCK_PRIVATE_KEY",
            environment="development",
        )
    return _client
