# DeviceCheck Integration - Research & Implementation Guide

## Overview

DeviceCheck is Apple's service for validating that requests to your server are coming from legitimate, unmodified Apple devices. It provides device attestation and allows you to store and retrieve per-device data.

**Documentation:** https://developer.apple.com/documentation/devicecheck

---

## Key Concepts

### 1. DeviceCheck Token
- Generated on the iOS device using `DCDevice.current.generateToken(completionHandler:)`
- Contains device attestation data
- Valid for a limited time (typically 1 hour)
- Must be validated on the server

### 2. Server-to-Server API
- Endpoint: `https://api.devicecheck.apple.com/v1/validate_device_token`
- Requires JWT authentication with Apple's private key
- Validates tokens and retrieves device data

### 3. Device Data
- Apple stores 2 bits of data per device per app
- Can be used to track device state
- Persists across app reinstalls (on same device)

---

## Implementation Flow

### Client Side (iOS App)
```
1. App calls DCDevice.current.generateToken()
2. Token is generated with device attestation
3. Token is sent to backend with request
4. Token is valid for ~1 hour
```

### Server Side (Backend)
```
1. Receive token from client
2. Create JWT signed with Apple private key
3. Call Apple's validation endpoint
4. Verify response and extract device data
5. Store attestation in database
6. Allow/deny request based on validation
```

---

## Required Setup

### 1. Apple Developer Account
- Enroll in Apple Developer Program
- Create App ID for your application
- Enable DeviceCheck capability

### 2. Private Key
- Download private key from Apple Developer portal
- Format: `.p8` file (PKCS#8)
- Keep secure - never commit to repository
- Store in environment variable or secure vault

### 3. Key Identifier
- Provided by Apple when you download the key
- Used in JWT header
- Format: 10-character alphanumeric string

### 4. Team ID
- Your Apple Developer Team ID
- 10-character alphanumeric string
- Used in JWT claims

---

## JWT Authentication

### JWT Structure
```
Header:
{
  "alg": "ES256",
  "kid": "KEY_IDENTIFIER",
  "typ": "JWT"
}

Payload:
{
  "iss": "TEAM_ID",
  "iat": 1234567890,
  "exp": 1234571490
}

Signature: ES256 signed with private key
```

### Python Implementation
```python
import jwt
import time
from datetime import datetime, timedelta

def create_devicecheck_jwt(private_key_path, key_id, team_id):
    """Create JWT for DeviceCheck API authentication"""
    
    with open(private_key_path, 'r') as f:
        private_key = f.read()
    
    now = datetime.utcnow()
    exp = now + timedelta(minutes=5)
    
    payload = {
        'iss': team_id,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }
    
    headers = {
        'kid': key_id,
        'typ': 'JWT'
    }
    
    token = jwt.encode(
        payload,
        private_key,
        algorithm='ES256',
        headers=headers
    )
    
    return token
```

---

## API Endpoints

### Validate Device Token
```
POST https://api.devicecheck.apple.com/v1/validate_device_token

Headers:
  Authorization: Bearer {JWT}
  Content-Type: application/json

Body:
{
  "device_token": "base64-encoded-token-from-client",
  "transaction_id": "unique-transaction-id",
  "timestamp": 1234567890
}

Response (Success):
{
  "is_valid": true
}

Response (Failure):
{
  "is_valid": false
}
```

### Query Device Data
```
POST https://api.devicecheck.apple.com/v1/query_device_data

Headers:
  Authorization: Bearer {JWT}
  Content-Type: application/json

Body:
{
  "device_token": "base64-encoded-token",
  "transaction_id": "unique-transaction-id",
  "timestamp": 1234567890
}

Response:
{
  "is_valid": true,
  "bit0": true/false,
  "bit1": true/false,
  "last_update_time": 1234567890
}
```

### Update Device Data
```
POST https://api.devicecheck.apple.com/v1/update_device_data

Headers:
  Authorization: Bearer {JWT}
  Content-Type: application/json

Body:
{
  "device_token": "base64-encoded-token",
  "transaction_id": "unique-transaction-id",
  "timestamp": 1234567890,
  "bit0": true/false,
  "bit1": true/false
}

Response:
{
  "is_valid": true
}
```

---

## Error Handling

### Common Errors
- `invalid_token` - Token is invalid or expired
- `invalid_jwt` - JWT authentication failed
- `invalid_transaction_id` - Transaction ID format invalid
- `invalid_timestamp` - Timestamp is too old or in future
- `rate_limited` - Too many requests

### Retry Strategy
- Implement exponential backoff
- Max 3 retries for transient errors
- Log all failures for debugging

---

## Security Considerations

### 1. Token Validation
- Always validate tokens on server
- Never trust client-side validation
- Check token expiration
- Verify device attestation

### 2. Private Key Management
- Store in environment variable
- Never commit to repository
- Rotate periodically
- Use secure key management service

### 3. Rate Limiting
- Apple enforces rate limits
- Implement client-side rate limiting
- Cache validation results when possible
- Monitor for abuse

### 4. Transaction IDs
- Must be unique per request
- Use UUID v4
- Include in logs for debugging
- Prevents replay attacks

---

## Integration Points

### 1. Device Enrollment (`/device/enroll`)
- Client sends DeviceCheck token
- Server validates token
- Store device attestation in database
- Return device token for future requests

### 2. Proof Locking (`/lock-proof`)
- Validate device attestation before accepting proof
- Check attestation freshness
- Update device data if needed
- Log all attestation events

### 3. Database Schema
```sql
CREATE TABLE device_attestations (
    id UUID PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,
    device_token VARCHAR(255) NOT NULL,
    is_valid BOOLEAN NOT NULL,
    last_validated_at TIMESTAMP NOT NULL,
    attestation_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attestation_logs (
    id UUID PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    is_valid BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES device_attestations(device_id)
);
```

---

## Implementation Checklist

### Phase 1.1: Research (Current)
- [x] Understand DeviceCheck concepts
- [x] Review API endpoints
- [x] Document JWT authentication
- [x] Identify security requirements
- [x] Plan database schema

### Phase 1.2: Implementation
- [ ] Create DeviceCheck client class
- [ ] Implement JWT generation
- [ ] Implement token validation
- [ ] Add error handling
- [ ] Add retry logic

### Phase 1.3: Integration
- [ ] Modify `/device/enroll` endpoint
- [ ] Add attestation validation
- [ ] Store attestation data
- [ ] Add attestation status tracking

### Phase 1.4: Proof Locking
- [ ] Add attestation check to `/lock-proof`
- [ ] Implement freshness validation
- [ ] Add attestation failure handling

### Phase 1.5: Testing
- [ ] Unit tests for DeviceCheck client
- [ ] Integration tests with mock API
- [ ] End-to-end device enrollment tests
- [ ] Error scenario tests

---

## Environment Variables

```bash
# DeviceCheck Configuration
DEVICECHECK_PRIVATE_KEY_PATH=/path/to/private/key.p8
DEVICECHECK_KEY_ID=ABC1234567
DEVICECHECK_TEAM_ID=ABCD123456
DEVICECHECK_API_URL=https://api.devicecheck.apple.com/v1

# Attestation Configuration
ATTESTATION_VALIDATION_ENABLED=true
ATTESTATION_FRESHNESS_SECONDS=3600
ATTESTATION_RETRY_MAX_ATTEMPTS=3
ATTESTATION_RETRY_BACKOFF_SECONDS=1
```

---

## References

- Apple DeviceCheck Documentation: https://developer.apple.com/documentation/devicecheck
- Apple Security Overview: https://developer.apple.com/security/
- JWT Specification: https://tools.ietf.org/html/rfc7519
- ES256 Algorithm: https://tools.ietf.org/html/rfc7518#section-3.4

---

## Next Steps

1. **Task 1.2**: Implement DeviceCheck client
   - Create `app/devicecheck.py` module
   - Implement JWT generation
   - Implement token validation
   - Add error handling

2. **Task 1.3**: Integrate with device enrollment
   - Modify `/device/enroll` endpoint
   - Add attestation validation
   - Update database schema

3. **Task 1.4**: Add verification to proof locking
   - Modify `/lock-proof` endpoint
   - Add attestation freshness checks

4. **Task 1.5**: Write comprehensive tests
   - Unit tests for DeviceCheck client
   - Integration tests with mock API
   - End-to-end tests

---

**Research Completed:** November 12, 2025
**Status:** READY FOR IMPLEMENTATION
**Next Task:** 1.2 - Implement DeviceCheck Client
