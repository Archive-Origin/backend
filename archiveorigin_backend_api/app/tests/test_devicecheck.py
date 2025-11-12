"""
Tests for DeviceCheck client module

Tests JWT creation, token validation, and API communication.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import httpx

from app.devicecheck import (
    DeviceCheckClient,
    DeviceCheckResponse,
    DeviceCheckError,
    InvalidTokenError,
    JWTAuthenticationError,
    APIError,
    DeviceCheckEventType
)


@pytest.fixture
def devicecheck_config():
    """DeviceCheck configuration for testing"""
    return {
        "private_key_path": "/tmp/test_key.p8",
        "key_id": "ABC1234567",
        "team_id": "ABCD123456",
        "api_url": "https://api.devicecheck.apple.com/v1"
    }


@pytest.fixture
def mock_private_key():
    """Mock private key content"""
    return """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgZJQnHrHmKVlT
-----END PRIVATE KEY-----"""


@pytest.fixture
def devicecheck_client(devicecheck_config, mock_private_key):
    """Create DeviceCheck client with mocked private key"""
    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = mock_private_key
        client = DeviceCheckClient(**devicecheck_config)
    return client


class TestDeviceCheckClientInitialization:
    """Test DeviceCheck client initialization"""
    
    def test_client_initialization(self, devicecheck_client):
        """Test client initializes with correct configuration"""
        assert devicecheck_client.key_id == "ABC1234567"
        assert devicecheck_client.team_id == "ABCD123456"
        assert devicecheck_client.jwt_expiry_minutes == 5
        assert devicecheck_client.max_retries == 3
    
    def test_private_key_not_found(self, devicecheck_config):
        """Test error when private key file not found"""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with pytest.raises(JWTAuthenticationError):
                DeviceCheckClient(**devicecheck_config)


class TestJWTCreation:
    """Test JWT creation for API authentication"""
    
    def test_jwt_creation(self, devicecheck_client):
        """Test JWT is created successfully"""
        with patch("jwt.encode") as mock_encode:
            mock_encode.return_value = "test.jwt.token"
            
            token = devicecheck_client._create_jwt()
            
            assert token == "test.jwt.token"
            mock_encode.assert_called_once()


class TestDeviceCheckResponse:
    """Test DeviceCheckResponse model"""
    
    def test_response_with_all_fields(self):
        """Test response with all fields"""
        response = DeviceCheckResponse(
            is_valid=True,
            bit0=True,
            bit1=False,
            last_update_time=1234567890
        )
        assert response.is_valid is True
        assert response.bit0 is True


class TestExceptionHandling:
    """Test exception handling"""
    
    def test_devicecheck_error_inheritance(self):
        """Test DeviceCheckError is base exception"""
        assert issubclass(InvalidTokenError, DeviceCheckError)
        assert issubclass(JWTAuthenticationError, DeviceCheckError)
        assert issubclass(APIError, DeviceCheckError)
