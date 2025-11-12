"""
DeviceCheck Integration Module

Handles Apple DeviceCheck token validation and device attestation.
Provides JWT authentication and API communication with Apple's DeviceCheck service.
"""

import jwt
import uuid
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceCheckError(Exception):
    """Base exception for DeviceCheck errors"""
    pass


class InvalidTokenError(DeviceCheckError):
    """Raised when token validation fails"""
    pass


class JWTAuthenticationError(DeviceCheckError):
    """Raised when JWT creation or validation fails"""
    pass


class APIError(DeviceCheckError):
    """Raised when API communication fails"""
    pass


class DeviceCheckEventType(str, Enum):
    """Types of DeviceCheck events"""
    TOKEN_VALIDATED = "token_validated"
    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    API_ERROR = "api_error"
    VALIDATION_SUCCESS = "validation_success"
    VALIDATION_FAILURE = "validation_failure"


class DeviceCheckResponse(BaseModel):
    """Response from DeviceCheck API"""
    is_valid: bool
    bit0: Optional[bool] = None
    bit1: Optional[bool] = None
    last_update_time: Optional[int] = None


class DeviceCheckClient:
    """
    Client for Apple DeviceCheck API
    
    Handles JWT creation, token validation, and device data management.
    """
    
    def __init__(
        self,
        private_key_path: str,
        key_id: str,
        team_id: str,
        api_url: str = "https://api.devicecheck.apple.com/v1",
        jwt_expiry_minutes: int = 5,
        max_retries: int = 3,
        retry_backoff_seconds: int = 1
    ):
        """Initialize DeviceCheck client"""
        self.private_key_path = private_key_path
        self.key_id = key_id
        self.team_id = team_id
        self.api_url = api_url
        self.jwt_expiry_minutes = jwt_expiry_minutes
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        
        self._private_key = self._load_private_key()
    
    def _load_private_key(self) -> str:
        """Load private key from file"""
        try:
            with open(self.private_key_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise JWTAuthenticationError(
                f"Private key not found at {self.private_key_path}"
            )
        except Exception as e:
            raise JWTAuthenticationError(f"Failed to load private key: {str(e)}")
    
    def _create_jwt(self) -> str:
        """Create JWT for API authentication"""
        try:
            now = datetime.utcnow()
            exp = now + timedelta(minutes=self.jwt_expiry_minutes)
            
            payload = {
                'iss': self.team_id,
                'iat': int(now.timestamp()),
                'exp': int(exp.timestamp())
            }
            
            headers = {
                'kid': self.key_id,
                'typ': 'JWT'
            }
            
            token = jwt.encode(
                payload,
                self._private_key,
                algorithm='ES256',
                headers=headers
            )
            
            return token
        except Exception as e:
            raise JWTAuthenticationError(f"Failed to create JWT: {str(e)}")
    
    async def validate_device_token(
        self,
        device_token: str,
        transaction_id: Optional[str] = None
    ) -> DeviceCheckResponse:
        """Validate device token with Apple"""
        if not transaction_id:
            transaction_id = str(uuid.uuid4())
        
        jwt_token = self._create_jwt()
        
        payload = {
            "device_token": device_token,
            "transaction_id": transaction_id,
            "timestamp": int(datetime.utcnow().timestamp())
        }
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_url}/validate_device_token"
        
        return await self._make_request(url, payload, headers)
    
    async def query_device_data(
        self,
        device_token: str,
        transaction_id: Optional[str] = None
    ) -> DeviceCheckResponse:
        """Query device data from Apple"""
        if not transaction_id:
            transaction_id = str(uuid.uuid4())
        
        jwt_token = self._create_jwt()
        
        payload = {
            "device_token": device_token,
            "transaction_id": transaction_id,
            "timestamp": int(datetime.utcnow().timestamp())
        }
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_url}/query_device_data"
        
        return await self._make_request(url, payload, headers)
    
    async def update_device_data(
        self,
        device_token: str,
        bit0: bool,
        bit1: bool,
        transaction_id: Optional[str] = None
    ) -> DeviceCheckResponse:
        """Update device data on Apple"""
        if not transaction_id:
            transaction_id = str(uuid.uuid4())
        
        jwt_token = self._create_jwt()
        
        payload = {
            "device_token": device_token,
            "transaction_id": transaction_id,
            "timestamp": int(datetime.utcnow().timestamp()),
            "bit0": bit0,
            "bit1": bit1
        }
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_url}/update_device_data"
        
        return await self._make_request(url, payload, headers)
    
    async def _make_request(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> DeviceCheckResponse:
        """Make HTTP request to DeviceCheck API with retry logic"""
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    data = response.json()
                    return DeviceCheckResponse(**data)
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                        backoff = self.retry_backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"DeviceCheck API error (attempt {attempt + 1}), "
                            f"retrying in {backoff}s: {e}"
                        )
                        await asyncio.sleep(backoff)
                    else:
                        raise APIError(f"DeviceCheck API error: {e}")
                        
                except Exception as e:
                    raise APIError(f"Failed to communicate with DeviceCheck API: {str(e)}")
        
        raise APIError("Max retries exceeded")
