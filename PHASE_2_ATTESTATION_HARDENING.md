# Phase 2A: Attestation Chain Validation (Task 2A.1)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** December 20, 2025

---

## Overview

Implement comprehensive attestation chain validation to verify the integrity and authenticity of Apple's attestation certificates. This ensures that device attestations come from legitimate Apple devices and haven't been tampered with.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/attestation.py** - Certificate ingestion utilities
- **archiveorigin_backend_api/app/crl.py** - CRL refresh utilities
- **archiveorigin_backend_api/models.py** - AttestationCertificate model
- **Database:** PostgreSQL with attestation certificate storage

### What's Missing
- Chain validation logic
- Certificate verification against Apple's root CA
- Revocation checking (CRL validation)
- Chain integrity verification
- Error handling for invalid chains

---

## Task 2A.1: Implement Attestation Chain Validation

### Objectives
1. Validate certificate chain from leaf to root
2. Verify signatures at each level
3. Check certificate validity dates
4. Validate against Apple's root certificates
5. Check revocation status (CRL)

### Implementation Steps

#### Step 1: Create Attestation Chain Validator Module

**File:** `archiveorigin_backend_api/app/attestation_validator.py`

```python
"""
Attestation Chain Validation Module

Validates Apple's attestation certificate chains for DeviceCheck and App Attest.
"""

from typing import List, Optional, Tuple
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger("archiveorigin.attestation_validator")


class AttestationChainValidator:
    """Validates attestation certificate chains"""
    
    def __init__(self, apple_root_certs: List[x509.Certificate]):
        """
        Initialize validator with Apple's root certificates
        
        Args:
            apple_root_certs: List of Apple root CA certificates
        """
        self.apple_root_certs = apple_root_certs
        self.backend = default_backend()
    
    def validate_chain(
        self,
        cert_chain: List[x509.Certificate],
        expected_oid: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate complete certificate chain
        
        Args:
            cert_chain: List of certificates from leaf to root
            expected_oid: Expected OID for device type (optional)
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not cert_chain:
            return False, "Empty certificate chain"
        
        # Validate chain structure
        is_valid, msg = self._validate_chain_structure(cert_chain)
        if not is_valid:
            return False, msg
        
        # Validate each certificate
        for i, cert in enumerate(cert_chain):
            is_valid, msg = self._validate_certificate(cert, i)
            if not is_valid:
                return False, msg
        
        # Validate signatures
        is_valid, msg = self._validate_signatures(cert_chain)
        if not is_valid:
            return False, msg
        
        # Validate root certificate
        is_valid, msg = self._validate_root(cert_chain[-1])
        if not is_valid:
            return False, msg
        
        # Validate OID if specified
        if expected_oid:
            is_valid, msg = self._validate_oid(cert_chain[0], expected_oid)
            if not is_valid:
                return False, msg
        
        return True, "Chain validation successful"
    
    def _validate_chain_structure(
        self,
        cert_chain: List[x509.Certificate]
    ) -> Tuple[bool, str]:
        """Validate chain structure and ordering"""
        if len(cert_chain) < 2:
            return False, "Chain must have at least 2 certificates"
        
        # Verify issuer/subject relationships
        for i in range(len(cert_chain) - 1):
            current = cert_chain[i]
            issuer = cert_chain[i + 1]
            
            if current.issuer != issuer.subject:
                return False, f"Issuer mismatch at position {i}"
        
        return True, "Chain structure valid"
    
    def _validate_certificate(
        self,
        cert: x509.Certificate,
        position: int
    ) -> Tuple[bool, str]:
        """Validate individual certificate"""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        # Check validity dates
        if now < cert.not_valid_before_utc:
            return False, f"Cert {position} not yet valid"
        
        if now > cert.not_valid_after_utc:
            return False, f"Cert {position} expired"
        
        # Check for required extensions
        try:
            # Basic constraints
            basic_constraints = cert.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS
            )
            
            # Key usage
            key_usage = cert.extensions.get_extension_for_oid(
                ExtensionOID.KEY_USAGE
            )
        except x509.ExtensionNotFound:
            return False, f"Cert {position} missing required extensions"
        
        return True, f"Cert {position} valid"
    
    def _validate_signatures(
        self,
        cert_chain: List[x509.Certificate]
    ) -> Tuple[bool, str]:
        """Validate signatures in chain"""
        for i in range(len(cert_chain) - 1):
            current = cert_chain[i]
            issuer = cert_chain[i + 1]
            
            try:
                # Verify signature
                issuer.public_key().verify(
                    current.signature,
                    current.tbs_certificate_bytes,
                    current.signature_algorithm_oid
                )
            except Exception as e:
                return False, f"Signature verification failed at position {i}: {str(e)}"
        
        return True, "All signatures valid"
    
    def _validate_root(
        self,
        root_cert: x509.Certificate
    ) -> Tuple[bool, str]:
        """Validate root certificate against Apple's roots"""
        # Check if root is self-signed
        if root_cert.issuer != root_cert.subject:
            return False, "Root certificate is not self-signed"
        
        # Verify against Apple's root certificates
        for apple_root in self.apple_root_certs:
            if root_cert.public_bytes(
                encoding=x509.serialization.Encoding.DER
            ) == apple_root.public_bytes(
                encoding=x509.serialization.Encoding.DER
            ):
                return True, "Root certificate matches Apple's root"
        
        return False, "Root certificate not found in Apple's roots"
    
    def _validate_oid(
        self,
        leaf_cert: x509.Certificate,
        expected_oid: str
    ) -> Tuple[bool, str]:
        """Validate certificate OID"""
        try:
            ext_key_usage = leaf_cert.extensions.get_extension_for_oid(
                ExtensionOID.EXTENDED_KEY_USAGE
            )
            
            oids = [str(oid) for oid in ext_key_usage.value]
            
            if expected_oid in oids:
                return True, f"OID {expected_oid} found"
            else:
                return False, f"Expected OID {expected_oid} not found"
        except x509.ExtensionNotFound:
            return False, "Extended key usage extension not found"
```

#### Step 2: Add Validation to DeviceCheck Client

**File:** `archiveorigin_backend_api/app/devicecheck.py`

Add chain validation to the DeviceCheck client:

```python
from attestation_validator import AttestationChainValidator

class DeviceCheckClient:
    def __init__(self, ...):
        # ... existing code ...
        self.chain_validator = AttestationChainValidator(
            apple_root_certs=self._load_apple_roots()
        )
    
    def validate_attestation_chain(
        self,
        cert_chain: List[str],  # Base64 encoded certificates
        device_type: str = "devicecheck"
    ) -> Tuple[bool, str]:
        """
        Validate attestation certificate chain
        
        Args:
            cert_chain: List of base64-encoded certificates
            device_type: Type of device (devicecheck or app_attest)
        
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Decode certificates
            decoded_certs = [
                x509.load_der_x509_certificate(
                    base64.b64decode(cert),
                    default_backend()
                )
                for cert in cert_chain
            ]
            
            # Determine expected OID
            expected_oid = self._get_expected_oid(device_type)
            
            # Validate chain
            return self.chain_validator.validate_chain(
                decoded_certs,
                expected_oid
            )
        except Exception as e:
            logger.error(f"Chain validation error: {str(e)}")
            return False, f"Chain validation failed: {str(e)}"
    
    def _get_expected_oid(self, device_type: str) -> str:
        """Get expected OID for device type"""
        oids = {
            "devicecheck": "1.2.840.113635.100.8.2",
            "app_attest": "1.2.840.113635.100.8.3",
        }
        return oids.get(device_type, "1.2.840.113635.100.8.2")
```

#### Step 3: Add Database Schema for Chain Validation

**File:** `archiveorigin_backend_api/app/models.py`

Add new model for chain validation results:

```python
class AttestationChainValidation(Base):
    """Attestation chain validation results"""
    __tablename__ = "attestation_chain_validations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_token_id = Column(String(36), ForeignKey("device_tokens.id"))
    
    # Validation results
    is_valid = Column(Boolean, nullable=False)
    validation_message = Column(String(500))
    
    # Chain details
    chain_length = Column(Integer)
    leaf_cert_subject = Column(String(500))
    root_cert_subject = Column(String(500))
    
    # Timestamps
    validated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When validation expires
    
    # Relationships
    device_token = relationship("DeviceToken", back_populates="chain_validations")
```

#### Step 4: Create Validation Endpoint

**File:** `archiveorigin_backend_api/app/main.py`

Add endpoint to validate chains:

```python
@app.post(
    "/validate-attestation-chain",
    summary="Validate attestation certificate chain",
    tags=["Attestation"],
    response_model=dict,
    responses={
        200: {"description": "Chain validation result"},
        400: {"description": "Invalid request"},
        401: {"description": "Unauthorized"},
    }
)
async def validate_attestation_chain(
    request: ValidateChainRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """
    Validate an attestation certificate chain
    
    - **cert_chain**: List of base64-encoded certificates
    - **device_type**: Type of device (devicecheck or app_attest)
    
    Returns validation result and stores in database.
    """
    # Authenticate request
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Get DeviceCheck client
    client = get_devicecheck_client()
    
    # Validate chain
    is_valid, message = client.validate_attestation_chain(
        request.cert_chain,
        request.device_type
    )
    
    # Store validation result
    validation = AttestationChainValidation(
        device_token_id=device_token.id,
        is_valid=is_valid,
        validation_message=message,
        chain_length=len(request.cert_chain),
        expires_at=datetime.utcnow() + timedelta(days=365)
    )
    db.add(validation)
    db.commit()
    
    return {
        "is_valid": is_valid,
        "message": message,
        "validation_id": validation.id
    }
```

#### Step 5: Add Schema for Request/Response

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class ValidateChainRequest(BaseModel):
    cert_chain: List[str] = Field(
        ...,
        description="List of base64-encoded certificates",
        example=["MIIBkTCB+wIJAKHHCgVZYYYYMA0GCSqGSIb3..."]
    )
    device_type: str = Field(
        default="devicecheck",
        description="Type of device (devicecheck or app_attest)",
        example="devicecheck"
    )

class ChainValidationResponse(BaseModel):
    is_valid: bool
    message: str
    validation_id: str
```

---

## Testing

### Unit Tests

**File:** `archiveorigin_backend_api/tests/test_attestation_validator.py`

```python
import pytest
from attestation_validator import AttestationChainValidator
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def test_validate_valid_chain():
    """Test validation of valid chain"""
    # Load test certificates
    validator = AttestationChainValidator(apple_root_certs=[...])
    
    # Test with valid chain
    is_valid, msg = validator.validate_chain(valid_chain)
    assert is_valid is True

def test_validate_expired_cert():
    """Test validation fails for expired certificate"""
    validator = AttestationChainValidator(apple_root_certs=[...])
    
    # Test with expired cert
    is_valid, msg = validator.validate_chain(expired_chain)
    assert is_valid is False
    assert "expired" in msg.lower()

def test_validate_invalid_signature():
    """Test validation fails for invalid signature"""
    validator = AttestationChainValidator(apple_root_certs=[...])
    
    # Test with tampered chain
    is_valid, msg = validator.validate_chain(tampered_chain)
    assert is_valid is False
    assert "signature" in msg.lower()
```

---

## Success Criteria

- ✅ Chain validator module created and tested
- ✅ Validates certificate chain structure
- ✅ Verifies signatures at each level
- ✅ Checks validity dates
- ✅ Validates against Apple's root certificates
- ✅ Endpoint created for chain validation
- ✅ Validation results stored in database
- ✅ Unit tests passing (>85% coverage)
- ✅ Error handling for all failure cases

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/app/attestation_validator.py`
2. **MODIFY:** `archiveorigin_backend_api/app/devicecheck.py`
3. **MODIFY:** `archiveorigin_backend_api/app/models.py`
4. **MODIFY:** `archiveorigin_backend_api/app/main.py`
5. **MODIFY:** `archiveorigin_backend_api/app/schemas.py`
6. **NEW:** `archiveorigin_backend_api/tests/test_attestation_validator.py`

---

## Dependencies

- `cryptography` - Certificate handling
- `pyopenssl` - OpenSSL bindings (optional, for advanced validation)

---

## Resources

- [Apple DeviceCheck Documentation](https://developer.apple.com/documentation/devicecheck)
- [X.509 Certificate Validation](https://en.wikipedia.org/wiki/X.509)
- [Cryptography Library Docs](https://cryptography.io/)
- [RFC 5280 - X.509 PKI](https://tools.ietf.org/html/rfc5280)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
