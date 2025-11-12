# Phase 2A.2: Attestation Metadata (Task 2A.2)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** December 20, 2025  
**Depends On:** Task 2A.1 (Chain Validation)

---

## Overview

Implement comprehensive attestation metadata collection and storage. This captures detailed information about each attestation including device characteristics, certificate details, validation timestamps, and audit trails for compliance and security analysis.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/attestation_validator.py** - Chain validation (from 2A.1)
- **archiveorigin_backend_api/models.py** - AttestationCertificate model
- **Database:** PostgreSQL with attestation storage

### What's Missing
- Metadata extraction from certificates
- Device characteristic tracking
- Attestation audit trail
- Metadata versioning
- Metadata query/retrieval endpoints

---

## Task 2A.2: Implement Attestation Metadata

### Objectives
1. Extract metadata from attestation certificates
2. Store device characteristics and identifiers
3. Track attestation lifecycle events
4. Enable metadata queries and filtering
5. Support compliance reporting

### Implementation Steps

#### Step 1: Create Attestation Metadata Models

**File:** `archiveorigin_backend_api/app/models.py`

Add new models for metadata:

```python
class AttestationMetadata(Base):
    """Attestation metadata and device characteristics"""
    __tablename__ = "attestation_metadata"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_token_id = Column(String(36), ForeignKey("device_tokens.id"), nullable=False)
    chain_validation_id = Column(String(36), ForeignKey("attestation_chain_validations.id"))
    
    # Device Information
    device_id = Column(String(255), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)  # devicecheck, app_attest
    device_model = Column(String(255))
    device_os_version = Column(String(50))
    
    # Certificate Metadata
    cert_subject = Column(String(500))
    cert_issuer = Column(String(500))
    cert_serial_number = Column(String(255))
    cert_not_before = Column(DateTime)
    cert_not_after = Column(DateTime)
    cert_fingerprint_sha256 = Column(String(64), index=True)
    
    # Attestation Details
    attestation_type = Column(String(50))  # basic, full
    attestation_format = Column(String(50))  # apple, google, etc
    attestation_challenge = Column(String(500))
    
    # Security Indicators
    is_emulator = Column(Boolean, default=False)
    is_rooted = Column(Boolean, default=False)
    is_debuggable = Column(Boolean, default=False)
    security_level = Column(String(50))  # basic, hardware, unknown
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, index=True)
    
    # Relationships
    device_token = relationship("DeviceToken", back_populates="attestation_metadata")
    chain_validation = relationship("AttestationChainValidation")
    audit_events = relationship("AttestationAuditEvent", back_populates="metadata")


class AttestationAuditEvent(Base):
    """Audit trail for attestation lifecycle events"""
    __tablename__ = "attestation_audit_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metadata_id = Column(String(36), ForeignKey("attestation_metadata.id"), nullable=False)
    
    # Event Details
    event_type = Column(String(50), nullable=False, index=True)  # created, validated, renewed, revoked
    event_status = Column(String(50), nullable=False)  # success, failure, warning
    event_message = Column(String(500))
    
    # Context
    actor = Column(String(255))  # who triggered the event
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    metadata = relationship("AttestationMetadata", back_populates="audit_events")


class AttestationMetadataVersion(Base):
    """Version history for attestation metadata changes"""
    __tablename__ = "attestation_metadata_versions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metadata_id = Column(String(36), ForeignKey("attestation_metadata.id"), nullable=False)
    
    # Version Info
    version_number = Column(Integer, nullable=False)
    change_type = Column(String(50))  # created, updated, renewed
    
    # Previous Values (JSON)
    previous_values = Column(JSON)
    new_values = Column(JSON)
    
    # Metadata
    changed_by = Column(String(255))
    change_reason = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

#### Step 2: Create Metadata Extraction Module

**File:** `archiveorigin_backend_api/app/metadata_extractor.py`

```python
"""
Attestation Metadata Extraction Module

Extracts and processes metadata from attestation certificates.
"""

from typing import Dict, Optional, Any
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger("archiveorigin.metadata_extractor")


class AttestationMetadataExtractor:
    """Extracts metadata from attestation certificates"""
    
    def extract_metadata(
        self,
        cert: x509.Certificate,
        device_id: str,
        device_type: str = "devicecheck"
    ) -> Dict[str, Any]:
        """
        Extract metadata from certificate
        
        Args:
            cert: X.509 certificate
            device_id: Device identifier
            device_type: Type of device (devicecheck or app_attest)
        
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {
            "device_id": device_id,
            "device_type": device_type,
            "cert_subject": self._extract_subject(cert),
            "cert_issuer": self._extract_issuer(cert),
            "cert_serial_number": str(cert.serial_number),
            "cert_not_before": cert.not_valid_before_utc,
            "cert_not_after": cert.not_valid_after_utc,
            "cert_fingerprint_sha256": self._calculate_fingerprint(cert),
            "attestation_type": self._extract_attestation_type(cert),
            "attestation_format": self._extract_attestation_format(cert),
            "security_level": self._extract_security_level(cert),
            "is_emulator": self._check_emulator(cert),
            "is_rooted": self._check_rooted(cert),
            "is_debuggable": self._check_debuggable(cert),
        }
        
        return metadata
    
    def _extract_subject(self, cert: x509.Certificate) -> str:
        """Extract certificate subject"""
        try:
            return cert.subject.rfc4514_string()
        except Exception as e:
            logger.error(f"Error extracting subject: {str(e)}")
            return ""
    
    def _extract_issuer(self, cert: x509.Certificate) -> str:
        """Extract certificate issuer"""
        try:
            return cert.issuer.rfc4514_string()
        except Exception as e:
            logger.error(f"Error extracting issuer: {str(e)}")
            return ""
    
    def _calculate_fingerprint(self, cert: x509.Certificate) -> str:
        """Calculate SHA256 fingerprint"""
        try:
            cert_der = cert.public_bytes(
                encoding=x509.serialization.Encoding.DER
            )
            return hashlib.sha256(cert_der).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating fingerprint: {str(e)}")
            return ""
    
    def _extract_attestation_type(self, cert: x509.Certificate) -> str:
        """Extract attestation type (basic or full)"""
        try:
            # Check for attestation type extension
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.EXTENDED_KEY_USAGE
            )
            
            oids = [str(oid) for oid in ext.value]
            
            # Apple attestation OIDs
            if "1.2.840.113635.100.8.2" in oids:
                return "full"  # DeviceCheck full attestation
            elif "1.2.840.113635.100.8.3" in oids:
                return "full"  # App Attest full attestation
            else:
                return "basic"
        except Exception:
            return "basic"
    
    def _extract_attestation_format(self, cert: x509.Certificate) -> str:
        """Extract attestation format"""
        try:
            issuer = cert.issuer.rfc4514_string()
            
            if "Apple" in issuer:
                return "apple"
            elif "Google" in issuer:
                return "google"
            else:
                return "unknown"
        except Exception:
            return "unknown"
    
    def _extract_security_level(self, cert: x509.Certificate) -> str:
        """Extract security level"""
        try:
            # Check for hardware-backed key usage
            key_usage = cert.extensions.get_extension_for_oid(
                ExtensionOID.KEY_USAGE
            )
            
            if key_usage.value.digital_signature:
                return "hardware"
            else:
                return "basic"
        except Exception:
            return "unknown"
    
    def _check_emulator(self, cert: x509.Certificate) -> bool:
        """Check if device is emulator"""
        try:
            subject = cert.subject.rfc4514_string()
            return "emulator" in subject.lower()
        except Exception:
            return False
    
    def _check_rooted(self, cert: x509.Certificate) -> bool:
        """Check if device is rooted/jailbroken"""
        try:
            # Check for jailbreak indicators in certificate
            subject = cert.subject.rfc4514_string()
            return "jailbreak" in subject.lower() or "rooted" in subject.lower()
        except Exception:
            return False
    
    def _check_debuggable(self, cert: x509.Certificate) -> bool:
        """Check if device is debuggable"""
        try:
            subject = cert.subject.rfc4514_string()
            return "debug" in subject.lower()
        except Exception:
            return False
```

#### Step 3: Create Metadata Service

**File:** `archiveorigin_backend_api/app/metadata_service.py`

```python
"""
Attestation Metadata Service

Manages metadata storage, retrieval, and audit trail.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging
import uuid

from models import (
    AttestationMetadata,
    AttestationAuditEvent,
    AttestationMetadataVersion
)
from metadata_extractor import AttestationMetadataExtractor

logger = logging.getLogger("archiveorigin.metadata_service")


class AttestationMetadataService:
    """Service for managing attestation metadata"""
    
    def __init__(self, db: Session):
        self.db = db
        self.extractor = AttestationMetadataExtractor()
    
    def create_metadata(
        self,
        device_token_id: str,
        device_id: str,
        device_type: str,
        cert_metadata: Dict[str, Any],
        chain_validation_id: Optional[str] = None
    ) -> AttestationMetadata:
        """
        Create new attestation metadata
        
        Args:
            device_token_id: Associated device token ID
            device_id: Device identifier
            device_type: Type of device
            cert_metadata: Extracted certificate metadata
            chain_validation_id: Associated chain validation ID
        
        Returns:
            Created AttestationMetadata object
        """
        metadata = AttestationMetadata(
            id=str(uuid.uuid4()),
            device_token_id=device_token_id,
            chain_validation_id=chain_validation_id,
            device_id=device_id,
            device_type=device_type,
            cert_subject=cert_metadata.get("cert_subject"),
            cert_issuer=cert_metadata.get("cert_issuer"),
            cert_serial_number=cert_metadata.get("cert_serial_number"),
            cert_not_before=cert_metadata.get("cert_not_before"),
            cert_not_after=cert_metadata.get("cert_not_after"),
            cert_fingerprint_sha256=cert_metadata.get("cert_fingerprint_sha256"),
            attestation_type=cert_metadata.get("attestation_type"),
            attestation_format=cert_metadata.get("attestation_format"),
            security_level=cert_metadata.get("security_level"),
            is_emulator=cert_metadata.get("is_emulator", False),
            is_rooted=cert_metadata.get("is_rooted", False),
            is_debuggable=cert_metadata.get("is_debuggable", False),
            expires_at=cert_metadata.get("cert_not_after")
        )
        
        self.db.add(metadata)
        self.db.commit()
        
        # Log creation event
        self._log_audit_event(
            metadata.id,
            "created",
            "success",
            "Attestation metadata created"
        )
        
        return metadata
    
    def get_metadata(self, metadata_id: str) -> Optional[AttestationMetadata]:
        """Get metadata by ID"""
        return self.db.query(AttestationMetadata).filter(
            AttestationMetadata.id == metadata_id
        ).first()
    
    def get_metadata_by_device(
        self,
        device_id: str,
        limit: int = 10
    ) -> List[AttestationMetadata]:
        """Get metadata for device"""
        return self.db.query(AttestationMetadata).filter(
            AttestationMetadata.device_id == device_id
        ).order_by(
            AttestationMetadata.created_at.desc()
        ).limit(limit).all()
    
    def get_metadata_by_fingerprint(
        self,
        fingerprint: str
    ) -> Optional[AttestationMetadata]:
        """Get metadata by certificate fingerprint"""
        return self.db.query(AttestationMetadata).filter(
            AttestationMetadata.cert_fingerprint_sha256 == fingerprint
        ).first()
    
    def update_metadata(
        self,
        metadata_id: str,
        updates: Dict[str, Any],
        change_reason: str = "Manual update"
    ) -> Optional[AttestationMetadata]:
        """
        Update metadata and track changes
        
        Args:
            metadata_id: Metadata ID to update
            updates: Dictionary of updates
            change_reason: Reason for change
        
        Returns:
            Updated AttestationMetadata object
        """
        metadata = self.get_metadata(metadata_id)
        if not metadata:
            return None
        
        # Store previous values
        previous_values = {
            "security_level": metadata.security_level,
            "is_emulator": metadata.is_emulator,
            "is_rooted": metadata.is_rooted,
            "is_debuggable": metadata.is_debuggable,
        }
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(metadata, key):
                setattr(metadata, key, value)
        
        metadata.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        
        # Create version record
        self._create_version(
            metadata_id,
            "updated",
            previous_values,
            updates,
            change_reason
        )
        
        # Log audit event
        self._log_audit_event(
            metadata_id,
            "updated",
            "success",
            f"Metadata updated: {change_reason}"
        )
        
        return metadata
    
    def _log_audit_event(
        self,
        metadata_id: str,
        event_type: str,
        status: str,
        message: str,
        actor: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AttestationAuditEvent:
        """Log audit event"""
        event = AttestationAuditEvent(
            id=str(uuid.uuid4()),
            metadata_id=metadata_id,
            event_type=event_type,
            event_status=status,
            event_message=message,
            actor=actor or "system",
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(event)
        self.db.commit()
        
        return event
    
    def _create_version(
        self,
        metadata_id: str,
        change_type: str,
        previous_values: Dict[str, Any],
        new_values: Dict[str, Any],
        change_reason: str
    ) -> AttestationMetadataVersion:
        """Create version record"""
        # Get current version number
        last_version = self.db.query(AttestationMetadataVersion).filter(
            AttestationMetadataVersion.metadata_id == metadata_id
        ).order_by(
            AttestationMetadataVersion.version_number.desc()
        ).first()
        
        version_number = (last_version.version_number + 1) if last_version else 1
        
        version = AttestationMetadataVersion(
            id=str(uuid.uuid4()),
            metadata_id=metadata_id,
            version_number=version_number,
            change_type=change_type,
            previous_values=previous_values,
            new_values=new_values,
            changed_by="system",
            change_reason=change_reason,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(version)
        self.db.commit()
        
        return version
    
    def get_audit_trail(
        self,
        metadata_id: str,
        limit: int = 50
    ) -> List[AttestationAuditEvent]:
        """Get audit trail for metadata"""
        return self.db.query(AttestationAuditEvent).filter(
            AttestationAuditEvent.metadata_id == metadata_id
        ).order_by(
            AttestationAuditEvent.created_at.desc()
        ).limit(limit).all()
    
    def get_version_history(
        self,
        metadata_id: str
    ) -> List[AttestationMetadataVersion]:
        """Get version history for metadata"""
        return self.db.query(AttestationMetadataVersion).filter(
            AttestationMetadataVersion.metadata_id == metadata_id
        ).order_by(
            AttestationMetadataVersion.version_number.asc()
        ).all()
```

#### Step 4: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

Add endpoints for metadata:

```python
from metadata_service import AttestationMetadataService

@app.post(
    "/attestation/metadata",
    summary="Create attestation metadata",
    tags=["Attestation"],
    response_model=dict,
    responses={
        201: {"description": "Metadata created"},
        400: {"description": "Invalid request"},
        401: {"description": "Unauthorized"},
    }
)
async def create_attestation_metadata(
    request: CreateMetadataRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Create attestation metadata from certificate"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = AttestationMetadataService(db)
    metadata = service.create_metadata(
        device_token_id=device_token.id,
        device_id=request.device_id,
        device_type=request.device_type,
        cert_metadata=request.cert_metadata,
        chain_validation_id=request.chain_validation_id
    )
    
    return {
        "metadata_id": metadata.id,
        "device_id": metadata.device_id,
        "created_at": metadata.created_at.isoformat()
    }


@app.get(
    "/attestation/metadata/{metadata_id}",
    summary="Get attestation metadata",
    tags=["Attestation"],
    response_model=dict
)
async def get_attestation_metadata(
    metadata_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get attestation metadata by ID"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = AttestationMetadataService(db)
    metadata = service.get_metadata(metadata_id)
    
    if not metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    return {
        "id": metadata.id,
        "device_id": metadata.device_id,
        "device_type": metadata.device_type,
        "cert_fingerprint": metadata.cert_fingerprint_sha256,
        "security_level": metadata.security_level,
        "is_emulator": metadata.is_emulator,
        "is_rooted": metadata.is_rooted,
        "created_at": metadata.created_at.isoformat()
    }


@app.get(
    "/attestation/metadata/device/{device_id}",
    summary="Get metadata for device",
    tags=["Attestation"],
    response_model=list
)
async def get_device_metadata(
    device_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get all metadata for a device"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = AttestationMetadataService(db)
    metadata_list = service.get_metadata_by_device(device_id, limit)
    
    return [
        {
            "id": m.id,
            "device_id": m.device_id,
            "security_level": m.security_level,
            "created_at": m.created_at.isoformat()
        }
        for m in metadata_list
    ]


@app.get(
    "/attestation/metadata/{metadata_id}/audit-trail",
    summary="Get audit trail",
    tags=["Attestation"],
    response_model=list
)
async def get_audit_trail(
    metadata_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get audit trail for metadata"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = AttestationMetadataService(db)
    events = service.get_audit_trail(metadata_id, limit)
    
    return [
        {
            "event_type": e.event_type,
            "event_status": e.event_status,
            "message": e.event_message,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]
```

#### Step 5: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class CreateMetadataRequest(BaseModel):
    device_id: str = Field(..., description="Device identifier")
    device_type: str = Field(default="devicecheck", description="Device type")
    cert_metadata: Dict[str, Any] = Field(..., description="Certificate metadata")
    chain_validation_id: Optional[str] = Field(None, description="Chain validation ID")

class MetadataResponse(BaseModel):
    id: str
    device_id: str
    device_type: str
    cert_fingerprint: str
    security_level: str
    is_emulator: bool
    is_rooted: bool
    created_at: str
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_metadata_service.py`

```python
import pytest
from metadata_service import AttestationMetadataService
from metadata_extractor import AttestationMetadataExtractor

def test_extract_metadata():
    """Test metadata extraction"""
    extractor = AttestationMetadataExtractor()
    # Load test certificate
    metadata = extractor.extract_metadata(test_cert, "device-123")
    
    assert metadata["device_id"] == "device-123"
    assert "cert_fingerprint_sha256" in metadata
    assert metadata["security_level"] in ["basic", "hardware", "unknown"]

def test_create_metadata(db):
    """Test metadata creation"""
    service = AttestationMetadataService(db)
    metadata = service.create_metadata(
        device_token_id="token-123",
        device_id="device-123",
        device_type="devicecheck",
        cert_metadata={"cert_subject": "CN=test"}
    )
    
    assert metadata.id is not None
    assert metadata.device_id == "device-123"

def test_audit_trail(db):
    """Test audit trail logging"""
    service = AttestationMetadataService(db)
    metadata = service.create_metadata(...)
    
    trail = service.get_audit_trail(metadata.id)
    assert len(trail) > 0
    assert trail[0].event_type == "created"
```

---

## Success Criteria

- ✅ Metadata models created with all fields
- ✅ Metadata extraction from certificates
- ✅ Metadata service with CRUD operations
- ✅ Audit trail logging for all events
- ✅ Version history tracking
- ✅ API endpoints for metadata operations
- ✅ Query endpoints for device/fingerprint lookup
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add metadata models
2. **NEW:** `archiveorigin_backend_api/app/metadata_extractor.py` - Extraction logic
3. **NEW:** `archiveorigin_backend_api/app/metadata_service.py` - Service layer
4. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
5. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
6. **NEW:** `archiveorigin_backend_api/tests/test_metadata_service.py` - Tests

---

## Dependencies

- `cryptography` - Certificate handling
- `sqlalchemy` - ORM (already installed)

---

## Resources

- [X.509 Certificate Fields](https://en.wikipedia.org/wiki/X.509)
- [Apple Attestation Documentation](https://developer.apple.com/documentation/devicecheck)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/14/orm/relationships.html)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
