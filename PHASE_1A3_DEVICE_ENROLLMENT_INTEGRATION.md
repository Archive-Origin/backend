# Phase 1A.3: Device Enrollment Integration - Task 1.3

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** November 14, 2025  
**Depends On:** Phase 1A.2 (Complete)

---

## Overview

Integrate DeviceCheck client into the device enrollment endpoint to validate device authenticity and store attestation data. This ensures only legitimate Apple devices can enroll in the system.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API with `/device/enroll` endpoint
- **PostgreSQL Database** - Device storage
- **DeviceCheck Client** - Mock implementation (from Phase 1A.2)
- **Ed25519 Service** - Signature verification

### What's Missing
- DeviceCheck integration in `/device/enroll` endpoint
- Attestation data storage
- Attestation status tracking
- Device validation flow
- Error handling for failed attestations

---

## Task 1.3: Implement Device Enrollment Integration

### Objectives
1. Integrate DeviceCheck client into enrollment endpoint
2. Validate device attestation
3. Store attestation data
4. Track attestation status
5. Handle attestation failures

### Implementation Steps

#### Step 1: Update Device Model

**File:** `archiveorigin_backend_api/app/models.py`

```python
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Device(Base):
    """Device enrollment record"""
    __tablename__ = "devices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(255), nullable=False, unique=True)
    device_token = Column(String(500), nullable=False)
    token_created_at = Column(DateTime, default=datetime.utcnow)
    token_expires_at = Column(DateTime, nullable=False)
    
    # Attestation fields
    attestation_status = Column(String(20), default='pending')  # pending, valid, invalid, expired
    attestation_data = Column(JSON, nullable=True)
    attestation_timestamp = Column(DateTime, nullable=True)
    attestation_expires_at = Column(DateTime, nullable=True)
    
    # Device info
    device_model = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)
    
    # Status tracking
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime, nullable=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Device {self.device_id}>"

class AttestationLog(Base):
    """Attestation validation log"""
    __tablename__ = "attestation_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), nullable=False)
    validation_status = Column(String(20), nullable=False)  # success, failure
    validation_timestamp = Column(DateTime, default=datetime.utcnow)
    error_message = Column(String(500), nullable=True)
    attestation_data = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<AttestationLog {self.device_id}>"
```

#### Step 2: Update Enrollment Service

**File:** `archiveorigin_backend_api/app/services/enrollment_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Device, AttestationLog
from devicecheck import DeviceCheckClient, DeviceCheckError
from typing import Dict, Optional
import uuid

class EnrollmentService:
    """Service for device enrollment"""
    
    def __init__(self, devicecheck_client: DeviceCheckClient):
        self.devicecheck_client = devicecheck_client
    
    async def enroll_device(
        self,
        db: Session,
        device_id: str,
        device_token: str,
        device_model: str = None,
        os_version: str = None,
        app_version: str = None,
        metadata: Dict = None
    ) -> Device:
        """Enroll a device with DeviceCheck validation"""
        
        # Check if device already enrolled
        existing_device = db.query(Device).filter(
            Device.device_id == device_id
        ).first()
        
        if existing_device:
            # Update existing device
            return await self._update_device_enrollment(
                db, existing_device, device_token, device_model, 
                os_version, app_version, metadata
            )
        
        # Create new device
        device = Device(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_token=device_token,
            token_created_at=datetime.utcnow(),
            token_expires_at=datetime.utcnow() + timedelta(days=30),
            device_model=device_model,
            os_version=os_version,
            app_version=app_version,
            metadata=metadata or {},
            attestation_status='pending'
        )
        
        # Validate with DeviceCheck
        try:
            attestation_result = await self.devicecheck_client.validate_device(
                device_token
            )
            
            device.attestation_status = 'valid'
            device.attestation_data = attestation_result.dict()
            device.attestation_timestamp = datetime.utcnow()
            device.attestation_expires_at = datetime.utcnow() + timedelta(days=365)
            
            # Log successful attestation
            self._log_attestation(
                db, device.id, 'success', attestation_result.dict()
            )
        
        except DeviceCheckError as e:
            device.attestation_status = 'invalid'
            device.is_active = False
            
            # Log failed attestation
            self._log_attestation(
                db, device.id, 'failure', error_message=str(e)
            )
            
            raise
        
        db.add(device)
        db.commit()
        db.refresh(device)
        
        return device
    
    async def _update_device_enrollment(
        self,
        db: Session,
        device: Device,
        device_token: str,
        device_model: str = None,
        os_version: str = None,
        app_version: str = None,
        metadata: Dict = None
    ) -> Device:
        """Update existing device enrollment"""
        
        device.device_token = device_token
        device.token_created_at = datetime.utcnow()
        device.token_expires_at = datetime.utcnow() + timedelta(days=30)
        device.attestation_status = 'pending'
        device.last_activity = datetime.utcnow()
        
        if device_model:
            device.device_model = device_model
        if os_version:
            device.os_version = os_version
        if app_version:
            device.app_version = app_version
        if metadata:
            device.metadata = metadata
        
        # Re-validate with DeviceCheck
        try:
            attestation_result = await self.devicecheck_client.validate_device(
                device_token
            )
            
            device.attestation_status = 'valid'
            device.attestation_data = attestation_result.dict()
            device.attestation_timestamp = datetime.utcnow()
            device.attestation_expires_at = datetime.utcnow() + timedelta(days=365)
            device.is_active = True
            
            self._log_attestation(
                db, device.id, 'success', attestation_result.dict()
            )
        
        except DeviceCheckError as e:
            device.attestation_status = 'invalid'
            device.is_active = False
            
            self._log_attestation(
                db, device.id, 'failure', error_message=str(e)
            )
            
            raise
        
        db.commit()
        db.refresh(device)
        
        return device
    
    def _log_attestation(
        self,
        db: Session,
        device_id: str,
        status: str,
        attestation_data: Dict = None,
        error_message: str = None
    ):
        """Log attestation validation"""
        log = AttestationLog(
            id=str(uuid.uuid4()),
            device_id=device_id,
            validation_status=status,
            attestation_data=attestation_data,
            error_message=error_message
        )
        db.add(log)
        db.commit()
    
    def get_device(self, db: Session, device_id: str) -> Optional[Device]:
        """Get device by ID"""
        return db.query(Device).filter(Device.device_id == device_id).first()
    
    def get_device_by_token(self, db: Session, device_token: str) -> Optional[Device]:
        """Get device by token"""
        return db.query(Device).filter(Device.device_token == device_token).first()
```

#### Step 3: Update Enrollment Endpoint

**File:** `archiveorigin_backend_api/app/routes/enrollment.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from services.enrollment_service import EnrollmentService
from devicecheck import DeviceCheckClient, DeviceCheckError

router = APIRouter(prefix="/device", tags=["device"])

class EnrollmentRequest(BaseModel):
    device_id: str
    device_token: str
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    metadata: Optional[dict] = None

class EnrollmentResponse(BaseModel):
    device_id: str
    attestation_status: str
    token_expires_at: str
    message: str

@router.post("/enroll")
async def enroll_device(
    request: EnrollmentRequest,
    db: Session = Depends(get_db)
):
    """Enroll a device with DeviceCheck validation"""
    try:
        # Initialize DeviceCheck client
        devicecheck_client = DeviceCheckClient()
        enrollment_service = EnrollmentService(devicecheck_client)
        
        # Enroll device
        device = await enrollment_service.enroll_device(
            db,
            request.device_id,
            request.device_token,
            request.device_model,
            request.os_version,
            request.app_version,
            request.metadata
        )
        
        return EnrollmentResponse(
            device_id=device.device_id,
            attestation_status=device.attestation_status,
            token_expires_at=device.token_expires_at.isoformat(),
            message="Device enrolled successfully"
        )
    
    except DeviceCheckError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Device attestation failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enrollment failed: {str(e)}"
        )

@router.get("/status/{device_id}")
async def get_device_status(
    device_id: str,
    db: Session = Depends(get_db)
):
    """Get device enrollment status"""
    try:
        devicecheck_client = DeviceCheckClient()
        enrollment_service = EnrollmentService(devicecheck_client)
        
        device = enrollment_service.get_device(db, device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        return {
            'device_id': device.device_id,
            'attestation_status': device.attestation_status,
            'is_active': device.is_active,
            'enrollment_date': device.enrollment_date.isoformat(),
            'last_activity': device.last_activity.isoformat() if device.last_activity else None,
            'token_expires_at': device.token_expires_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

---

## Success Criteria

- ✅ Device model updated with attestation fields
- ✅ Enrollment service created
- ✅ DeviceCheck integration working
- ✅ Attestation data stored
- ✅ Attestation logging implemented
- ✅ Enrollment endpoint updated
- ✅ Device status endpoint working
- ✅ Error handling implemented
- ✅ Tests passing

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add Device and AttestationLog models
2. **NEW:** `archiveorigin_backend_api/app/services/enrollment_service.py` - Enrollment service
3. **NEW:** `archiveorigin_backend_api/app/routes/enrollment.py` - Enrollment endpoints

---

## Dependencies

- `sqlalchemy` - ORM
- `fastapi` - Web framework
- `pydantic` - Data validation

---

## Resources

- [DeviceCheck API](https://developer.apple.com/documentation/devicecheck)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
