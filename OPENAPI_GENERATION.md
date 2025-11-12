# OpenAPI Generation - Archive Origin Backend

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Assigned To:** Codex

---

## Overview

Generate comprehensive OpenAPI 3.0 specification for the Archive Origin Backend API using FastAPI's built-in OpenAPI support.

---

## Current FastAPI Setup

**App Location:** `archiveorigin_backend_api/app/main.py`

**Existing Configuration:**
```python
app = FastAPI(
    title="Archive Origin Proof API",
    default_response_class=JSONResponse
)
```

**Current Endpoints:**
- `POST /device/enroll` - Device enrollment & token renewal
- `POST /lock-proof` - Immutable capture proof storage
- `POST /verify` - Proof verification
- `GET /ledger-lookup` - Ledger lookup
- `GET /certificate/{cert_id}` - Certificate retrieval
- `GET /health` - Health check

---

## Tasks

### Task 1: Enhance FastAPI Configuration
- [ ] Add OpenAPI metadata to FastAPI app:
  - `description` - API description
  - `version` - API version (e.g., "1.0.0")
  - `terms_of_service` - Link to ToS
  - `contact` - Contact information
  - `license_info` - License details

**Example:**
```python
app = FastAPI(
    title="Archive Origin Proof API",
    description="Device attestation and proof locking API",
    version="1.0.0",
    terms_of_service="https://example.com/terms",
    contact={
        "name": "Archive Origin",
        "url": "https://example.com",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)
```

### Task 2: Add Endpoint Documentation
- [ ] Add docstrings to all endpoint functions
- [ ] Add `summary` and `description` to route decorators
- [ ] Add `tags` for endpoint grouping
- [ ] Add `responses` with status codes and descriptions

**Example:**
```python
@app.post(
    "/device/enroll",
    summary="Enroll a new device",
    description="Register a new device and receive a device token",
    tags=["Device Management"],
    response_model=EnrollResponse,
    responses={
        200: {"description": "Device enrolled successfully"},
        400: {"description": "Invalid request"},
        429: {"description": "Rate limited"},
    }
)
async def enroll_device(request: EnrollRequest, db: Session = Depends(get_db)):
    """
    Enroll a new device in the Archive Origin system.
    
    - **device_id**: Unique device identifier
    - **public_key**: Device's public key for signature verification
    
    Returns a device token valid for 24 hours.
    """
    ...
```

### Task 3: Enhance Schema Documentation
- [ ] Add field descriptions to all Pydantic models
- [ ] Add examples to schemas
- [ ] Add field constraints (min/max, patterns, etc.)

**Example:**
```python
class EnrollRequest(BaseModel):
    device_id: str = Field(
        ...,
        description="Unique device identifier",
        example="device-12345",
        min_length=1,
        max_length=255
    )
    public_key: str = Field(
        ...,
        description="Device's Ed25519 public key in base64 format",
        example="MCowBQYDK2VwAyEA..."
    )
```

### Task 4: Generate OpenAPI Spec
- [ ] Access OpenAPI spec at `/openapi.json`
- [ ] Validate OpenAPI 3.0 compliance
- [ ] Save spec to file: `openapi.json`

**Command:**
```bash
curl http://localhost:8000/openapi.json > openapi.json
```

### Task 5: Generate Swagger UI
- [ ] Swagger UI automatically available at `/docs`
- [ ] ReDoc available at `/redoc`
- [ ] Test all endpoints in Swagger UI

**URLs:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Task 6: Export OpenAPI Spec
- [ ] Generate `openapi.json` file
- [ ] Generate `openapi.yaml` file
- [ ] Commit to repository

**Tools:**
```bash
# Using FastAPI CLI (if available)
fastapi openapi-json > openapi.json

# Or using curl
curl http://localhost:8000/openapi.json > openapi.json

# Convert to YAML
pip install pyyaml
python -c "import json, yaml; print(yaml.dump(json.load(open('openapi.json'))))" > openapi.yaml
```

---

## Implementation Steps

1. **Start the backend server:**
   ```bash
   cd /Users/midnight/Desktop/backend
   docker-compose up -d
   # or
   python -m uvicorn archiveorigin_backend_api.app.main:app --reload
   ```

2. **Access Swagger UI:**
   - Open browser to `http://localhost:8000/docs`

3. **Enhance documentation:**
   - Add docstrings to endpoints
   - Add field descriptions to schemas
   - Add examples and constraints

4. **Generate OpenAPI spec:**
   ```bash
   curl http://localhost:8000/openapi.json > openapi.json
   ```

5. **Commit to repository:**
   ```bash
   git add openapi.json openapi.yaml
   git commit -m "Add OpenAPI specification"
   git push origin main
   ```

---

## Files to Modify

1. **archiveorigin_backend_api/app/main.py**
   - Enhance FastAPI app configuration
   - Add endpoint documentation
   - Add response descriptions

2. **archiveorigin_backend_api/app/schemas.py**
   - Add field descriptions
   - Add examples
   - Add constraints

3. **New Files to Create:**
   - `openapi.json` - OpenAPI 3.0 specification
   - `openapi.yaml` - OpenAPI in YAML format
   - `OPENAPI_SPEC.md` - OpenAPI documentation

---

## Success Criteria

- ✅ All endpoints documented with summaries and descriptions
- ✅ All schemas have field descriptions and examples
- ✅ OpenAPI spec generated and valid
- ✅ Swagger UI accessible and functional
- ✅ ReDoc accessible and functional
- ✅ OpenAPI files committed to repository
- ✅ Documentation updated in roadmap

---

## Resources

- [FastAPI OpenAPI Documentation](https://fastapi.tiangolo.com/features/#automatic-docs)
- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [Pydantic Field Documentation](https://docs.pydantic.dev/latest/concepts/fields/)
- [Swagger UI](https://swagger.io/tools/swagger-ui/)
- [ReDoc](https://redoc.ly/)

---

**Created:** November 12, 2025  
**For:** Codex Agent  
**Status:** Ready for Implementation
