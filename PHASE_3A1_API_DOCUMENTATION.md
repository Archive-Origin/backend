# Phase 3A.1: API Documentation (OpenAPI/Swagger) - Task 3.1

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 10, 2026  
**Depends On:** Phase 2 (Complete)

---

## Overview

Implement comprehensive API documentation using OpenAPI 3.0 specification with automatic Swagger UI generation. This provides interactive API documentation, client SDK generation capabilities, and clear endpoint specifications.

---

## Current State

### Existing Components
- **FastAPI Framework** - Automatic OpenAPI support
- **Pydantic Models** - Type definitions for request/response
- **Endpoints** - `/device/enroll`, `/lock-proof`, `/health`, etc.
- **Database Models** - SQLAlchemy ORM models

### What's Missing
- OpenAPI metadata and descriptions
- Endpoint documentation
- Request/response examples
- Error response documentation
- Security scheme documentation
- Tag organization
- Swagger UI customization

---

## Task 3.1: Implement API Documentation

### Objectives
1. Generate comprehensive OpenAPI specification
2. Create interactive Swagger UI
3. Document all endpoints with examples
4. Define error responses
5. Enable client SDK generation

### Implementation Steps

#### Step 1: Configure FastAPI with OpenAPI Metadata

**File:** `archiveorigin_backend_api/app/main.py`

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Archive Origin Backend API",
    description="""
    Archive Origin Backend provides secure device enrollment, 
    capture proof locking, and Merkle ledger sealing for 
    cryptographic proof of authenticity.
    
    ## Features
    - Device enrollment with DeviceCheck attestation
    - Immutable capture proof storage
    - Merkle ledger with cryptographic sealing
    - Comprehensive audit trails
    - Compliance reporting
    
    ## Authentication
    All endpoints require Bearer token authentication using Ed25519 signatures.
    """,
    version="1.0.0",
    contact={
        "name": "Archive Origin Support",
        "url": "https://archiveorigin.com",
        "email": "support@archiveorigin.com"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://archiveorigin.com/license"
    },
    servers=[
        {
            "url": "https://api.archiveorigin.com",
            "description": "Production server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Archive Origin Backend API",
        version="1.0.0",
        description="Secure device enrollment and proof locking API",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Ed25519 signed JWT token"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    # Add tags
    openapi_schema["tags"] = [
        {
            "name": "Device Management",
            "description": "Device enrollment and token management"
        },
        {
            "name": "Proof Management",
            "description": "Capture proof locking and verification"
        },
        {
            "name": "Ledger Management",
            "description": "Merkle ledger operations"
        },
        {
            "name": "Health & Status",
            "description": "System health and status endpoints"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

#### Step 2: Document Endpoints with Descriptions and Examples

**File:** `archiveorigin_backend_api/app/main.py`

```python
from fastapi import HTTPException, Header, Depends
from pydantic import BaseModel, Field

class DeviceEnrollmentRequest(BaseModel):
    """Device enrollment request"""
    device_id: str = Field(..., description="Unique device identifier")
    device_token: str = Field(..., description="Apple DeviceCheck token")
    device_name: str = Field(..., description="Human-readable device name")
    os_version: str = Field(..., description="Device OS version")
    
    class Config:
        schema_extra = {
            "example": {
                "device_id": "device-uuid-12345",
                "device_token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...",
                "device_name": "iPhone 14 Pro",
                "os_version": "17.1"
            }
        }

class DeviceEnrollmentResponse(BaseModel):
    """Device enrollment response"""
    device_id: str = Field(..., description="Enrolled device ID")
    enrollment_token: str = Field(..., description="Bearer token for API requests")
    token_expires_at: str = Field(..., description="Token expiration timestamp")
    attestation_status: str = Field(..., description="Device attestation status")
    
    class Config:
        schema_extra = {
            "example": {
                "device_id": "device-uuid-12345",
                "enrollment_token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_expires_at": "2025-11-19T22:55:00Z",
                "attestation_status": "verified"
            }
        }

@app.post(
    "/device/enroll",
    response_model=DeviceEnrollmentResponse,
    tags=["Device Management"],
    summary="Enroll a new device",
    description="""
    Enroll a new device with DeviceCheck attestation.
    
    This endpoint:
    1. Validates the device token with Apple DeviceCheck
    2. Verifies device authenticity
    3. Creates enrollment record
    4. Issues bearer token for API access
    
    The returned token should be used in the Authorization header
    for all subsequent API requests.
    """,
    responses={
        200: {
            "description": "Device successfully enrolled",
            "content": {
                "application/json": {
                    "example": {
                        "device_id": "device-uuid-12345",
                        "enrollment_token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_expires_at": "2025-11-19T22:55:00Z",
                        "attestation_status": "verified"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid device token format"
                    }
                }
            }
        },
        401: {
            "description": "Device attestation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Device attestation verification failed"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too many enrollment requests"
                    }
                }
            }
        }
    }
)
async def enroll_device(
    request: DeviceEnrollmentRequest,
    db: Session = Depends(get_db)
) -> DeviceEnrollmentResponse:
    """
    Enroll a new device with DeviceCheck attestation.
    
    Args:
        request: Device enrollment request
        db: Database session
    
    Returns:
        DeviceEnrollmentResponse with enrollment token
    
    Raises:
        HTTPException: If enrollment fails
    """
    # Implementation
    pass

class LockProofRequest(BaseModel):
    """Lock proof request"""
    capture_id: str = Field(..., description="Unique capture identifier")
    proof_data: str = Field(..., description="Base64-encoded proof data")
    metadata: dict = Field(default={}, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "capture_id": "capture-uuid-12345",
                "proof_data": "base64encodedproofdata...",
                "metadata": {
                    "timestamp": "2025-11-12T22:55:00Z",
                    "location": "San Francisco, CA"
                }
            }
        }

class LockProofResponse(BaseModel):
    """Lock proof response"""
    proof_id: str = Field(..., description="Locked proof ID")
    merkle_root: str = Field(..., description="Merkle root hash")
    ledger_entry: int = Field(..., description="Ledger entry index")
    locked_at: str = Field(..., description="Lock timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "proof_id": "proof-uuid-12345",
                "merkle_root": "a1b2c3d4e5f6...",
                "ledger_entry": 42,
                "locked_at": "2025-11-12T22:55:00Z"
            }
        }

@app.post(
    "/lock-proof",
    response_model=LockProofResponse,
    tags=["Proof Management"],
    summary="Lock a capture proof",
    description="""
    Lock a capture proof in the Merkle ledger.
    
    This endpoint:
    1. Validates the proof data
    2. Stores proof in database
    3. Adds to Merkle tree
    4. Computes new Merkle root
    5. Returns proof ID and ledger entry
    
    Locked proofs are immutable and cryptographically sealed.
    """,
    responses={
        200: {"description": "Proof successfully locked"},
        400: {"description": "Invalid proof data"},
        401: {"description": "Unauthorized - invalid token"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def lock_proof(
    request: LockProofRequest,
    auth_header: str = Header(None),
    db: Session = Depends(get_db)
) -> LockProofResponse:
    """Lock a capture proof in the Merkle ledger"""
    pass

@app.get(
    "/health",
    tags=["Health & Status"],
    summary="Health check",
    description="Check API and database health status",
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": "connected",
                        "timestamp": "2025-11-12T22:55:00Z"
                    }
                }
            }
        },
        503: {
            "description": "Service unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "database": "disconnected"
                    }
                }
            }
        }
    }
)
async def health_check(db: Session = Depends(get_db)):
    """Check API and database health"""
    pass
```

#### Step 3: Configure Swagger UI

**File:** `archiveorigin_backend_api/app/main.py`

```python
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
    get_redoc_html
)

@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Archive Origin API - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css",
        swagger_favicon_url="https://archiveorigin.com/favicon.ico"
    )

@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Archive Origin API - ReDoc"
    )
```

#### Step 4: Add Request/Response Examples

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Optional

class ErrorResponse(BaseModel):
    """Error response"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: str = Field(..., description="Error timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Device attestation failed",
                "error_code": "ATTESTATION_FAILED",
                "timestamp": "2025-11-12T22:55:00Z"
            }
        }

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="System status")
    database: str = Field(..., description="Database status")
    timestamp: str = Field(..., description="Check timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "database": "connected",
                "timestamp": "2025-11-12T22:55:00Z"
            }
        }
```

#### Step 5: Generate OpenAPI Schema File

**File:** `archiveorigin_backend_api/scripts/generate_openapi.py`

```python
"""Generate OpenAPI schema file"""

import json
from app.main import app

def generate_openapi_schema():
    """Generate and save OpenAPI schema"""
    openapi_schema = app.openapi()
    
    with open("openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print("✅ OpenAPI schema generated: openapi.json")

if __name__ == "__main__":
    generate_openapi_schema()
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_api_documentation.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_openapi_schema_exists():
    """Test OpenAPI schema is available"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"] == "3.0.2"
    assert schema["info"]["title"] == "Archive Origin Backend API"

def test_swagger_ui_available():
    """Test Swagger UI is available"""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text

def test_redoc_available():
    """Test ReDoc is available"""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text

def test_endpoints_documented():
    """Test all endpoints are documented"""
    response = client.get("/openapi.json")
    schema = response.json()
    
    # Check required endpoints
    paths = schema["paths"]
    assert "/device/enroll" in paths
    assert "/lock-proof" in paths
    assert "/health" in paths

def test_security_scheme_defined():
    """Test security scheme is defined"""
    response = client.get("/openapi.json")
    schema = response.json()
    
    assert "securitySchemes" in schema["components"]
    assert "bearerAuth" in schema["components"]["securitySchemes"]
```

---

## Success Criteria

- ✅ OpenAPI 3.0 specification generated
- ✅ All endpoints documented with descriptions
- ✅ Request/response examples provided
- ✅ Error responses documented
- ✅ Security schemes defined
- ✅ Swagger UI accessible at /docs
- ✅ ReDoc accessible at /redoc
- ✅ OpenAPI schema downloadable
- ✅ Unit tests passing (>85% coverage)
- ✅ Schema validation working

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add OpenAPI config
2. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add examples
3. **NEW:** `archiveorigin_backend_api/scripts/generate_openapi.py` - Schema generation
4. **NEW:** `archiveorigin_backend_api/tests/test_api_documentation.py` - Tests

---

## Dependencies

- `fastapi` - Already installed
- `pydantic` - Already installed
- `swagger-ui` - CDN-based (no install needed)

---

## Resources

- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [FastAPI OpenAPI Documentation](https://fastapi.tiangolo.com/how-to/extending-openapi/)
- [Swagger UI Documentation](https://swagger.io/tools/swagger-ui/)
- [ReDoc Documentation](https://redoc.ly/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
