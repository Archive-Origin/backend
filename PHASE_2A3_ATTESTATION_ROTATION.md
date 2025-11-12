# Phase 2A.3: Attestation Rotation (Task 2A.3)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** December 27, 2025  
**Depends On:** Task 2A.2 (Attestation Metadata)

---

## Overview

Implement attestation certificate rotation mechanism to ensure continuous security by regularly refreshing attestation certificates. This prevents certificate expiration, manages certificate lifecycle, and maintains compliance with security policies.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/metadata_service.py** - Metadata management (from 2A.2)
- **archiveorigin_backend_api/app/attestation_validator.py** - Chain validation (from 2A.1)
- **Database:** PostgreSQL with attestation storage

### What's Missing
- Rotation scheduling logic
- Certificate renewal workflow
- Rotation event tracking
- Expiration monitoring
- Rotation policy enforcement

---

## Task 2A.3: Implement Attestation Rotation

### Objectives
1. Implement certificate rotation scheduling
2. Manage certificate lifecycle transitions
3. Track rotation events and history
4. Monitor certificate expiration
5. Enforce rotation policies

### Implementation Steps

#### Step 1: Create Rotation Models

**File:** `archiveorigin_backend_api/app/models.py`

Add rotation models:

```python
class AttestationRotationPolicy(Base):
    """Attestation rotation policy configuration"""
    __tablename__ = "attestation_rotation_policies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Policy Configuration
    device_type = Column(String(50), nullable=False, unique=True)  # devicecheck, app_attest
    rotation_interval_days = Column(Integer, default=90)  # Rotate every 90 days
    expiration_warning_days = Column(Integer, default=14)  # Warn 14 days before expiry
    max_certificate_age_days = Column(Integer, default=365)  # Max age before forced rotation
    
    # Policy Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rotation_schedules = relationship("AttestationRotationSchedule", back_populates="policy")


class AttestationRotationSchedule(Base):
    """Attestation rotation schedule for devices"""
    __tablename__ = "attestation_rotation_schedules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_token_id = Column(String(36), ForeignKey("device_tokens.id"), nullable=False)
    policy_id = Column(String(36), ForeignKey("attestation_rotation_policies.id"), nullable=False)
    
    # Schedule Information
    device_id = Column(String(255), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    
    # Rotation Timing
    last_rotation_at = Column(DateTime)
    next_rotation_at = Column(DateTime, nullable=False, index=True)
    scheduled_rotation_at = Column(DateTime)
    
    # Current Certificate
    current_cert_id = Column(String(36), ForeignKey("attestation_metadata.id"))
    current_cert_expires_at = Column(DateTime)
    
    # Status
    rotation_status = Column(String(50), default="pending")  # pending, in_progress, completed, failed
    rotation_attempts = Column(Integer, default=0)
    last_rotation_error = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    policy = relationship("AttestationRotationPolicy", back_populates="rotation_schedules")
    device_token = relationship("DeviceToken")
    current_cert = relationship("AttestationMetadata")
    rotation_events = relationship("AttestationRotationEvent", back_populates="schedule")


class AttestationRotationEvent(Base):
    """Attestation rotation event history"""
    __tablename__ = "attestation_rotation_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(String(36), ForeignKey("attestation_rotation_schedules.id"), nullable=False)
    
    # Event Details
    event_type = Column(String(50), nullable=False)  # initiated, in_progress, completed, failed
    event_status = Column(String(50), nullable=False)  # success, failure, warning
    event_message = Column(String(500))
    
    # Certificate Information
    old_cert_id = Column(String(36), ForeignKey("attestation_metadata.id"))
    new_cert_id = Column(String(36), ForeignKey("attestation_metadata.id"))
    
    # Rotation Details
    rotation_reason = Column(String(255))  # scheduled, expiration_warning, manual, policy_change
    rotation_duration_ms = Column(Integer)  # How long rotation took
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    schedule = relationship("AttestationRotationSchedule", back_populates="rotation_events")
    old_cert = relationship("AttestationMetadata", foreign_keys=[old_cert_id])
    new_cert = relationship("AttestationMetadata", foreign_keys=[new_cert_id])
```

#### Step 2: Create Rotation Service

**File:** `archiveorigin_backend_api/app/rotation_service.py`

```python
"""
Attestation Rotation Service

Manages certificate rotation scheduling and lifecycle.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import logging
import uuid
import time

from models import (
    AttestationRotationPolicy,
    AttestationRotationSchedule,
    AttestationRotationEvent,
    AttestationMetadata
)

logger = logging.getLogger("archiveorigin.rotation_service")


class AttestationRotationService:
    """Service for managing attestation rotation"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_rotation_policy(
        self,
        device_type: str,
        rotation_interval_days: int = 90,
        expiration_warning_days: int = 14,
        max_certificate_age_days: int = 365
    ) -> AttestationRotationPolicy:
        """
        Create rotation policy
        
        Args:
            device_type: Type of device (devicecheck, app_attest)
            rotation_interval_days: Days between rotations
            expiration_warning_days: Days before expiry to warn
            max_certificate_age_days: Maximum certificate age
        
        Returns:
            Created AttestationRotationPolicy
        """
        policy = AttestationRotationPolicy(
            id=str(uuid.uuid4()),
            device_type=device_type,
            rotation_interval_days=rotation_interval_days,
            expiration_warning_days=expiration_warning_days,
            max_certificate_age_days=max_certificate_age_days
        )
        
        self.db.add(policy)
        self.db.commit()
        
        logger.info(f"Created rotation policy for {device_type}")
        return policy
    
    def create_rotation_schedule(
        self,
        device_token_id: str,
        device_id: str,
        device_type: str,
        current_cert_id: str,
        current_cert_expires_at: datetime
    ) -> AttestationRotationSchedule:
        """
        Create rotation schedule for device
        
        Args:
            device_token_id: Device token ID
            device_id: Device identifier
            device_type: Type of device
            current_cert_id: Current certificate ID
            current_cert_expires_at: Certificate expiration date
        
        Returns:
            Created AttestationRotationSchedule
        """
        # Get or create policy
        policy = self.db.query(AttestationRotationPolicy).filter(
            AttestationRotationPolicy.device_type == device_type
        ).first()
        
        if not policy:
            policy = self.create_rotation_policy(device_type)
        
        # Calculate next rotation
        now = datetime.now(timezone.utc)
        next_rotation = now + timedelta(days=policy.rotation_interval_days)
        
        # Check if certificate expires before next rotation
        if current_cert_expires_at < next_rotation:
            next_rotation = current_cert_expires_at - timedelta(
                days=policy.expiration_warning_days
            )
        
        schedule = AttestationRotationSchedule(
            id=str(uuid.uuid4()),
            device_token_id=device_token_id,
            policy_id=policy.id,
            device_id=device_id,
            device_type=device_type,
            current_cert_id=current_cert_id,
            current_cert_expires_at=current_cert_expires_at,
            next_rotation_at=next_rotation,
            rotation_status="pending"
        )
        
        self.db.add(schedule)
        self.db.commit()
        
        logger.info(f"Created rotation schedule for device {device_id}")
        return schedule
    
    def get_schedules_due_for_rotation(self) -> List[AttestationRotationSchedule]:
        """Get all schedules due for rotation"""
        now = datetime.now(timezone.utc)
        
        return self.db.query(AttestationRotationSchedule).filter(
            AttestationRotationSchedule.next_rotation_at <= now,
            AttestationRotationSchedule.rotation_status.in_(["pending", "failed"])
        ).all()
    
    def get_expiration_warnings(
        self,
        warning_days: int = 14
    ) -> List[AttestationRotationSchedule]:
        """Get schedules with certificates expiring soon"""
        now = datetime.now(timezone.utc)
        warning_threshold = now + timedelta(days=warning_days)
        
        return self.db.query(AttestationRotationSchedule).filter(
            AttestationRotationSchedule.current_cert_expires_at <= warning_threshold,
            AttestationRotationSchedule.current_cert_expires_at > now,
            AttestationRotationSchedule.rotation_status != "completed"
        ).all()
    
    def initiate_rotation(
        self,
        schedule_id: str,
        reason: str = "scheduled"
    ) -> Tuple[bool, str]:
        """
        Initiate rotation for schedule
        
        Args:
            schedule_id: Schedule ID
            reason: Reason for rotation
        
        Returns:
            Tuple of (success, message)
        """
        schedule = self.db.query(AttestationRotationSchedule).filter(
            AttestationRotationSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            return False, "Schedule not found"
        
        if schedule.rotation_status == "in_progress":
            return False, "Rotation already in progress"
        
        # Update schedule status
        schedule.rotation_status = "in_progress"
        schedule.rotation_attempts += 1
        schedule.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        # Log rotation event
        event = AttestationRotationEvent(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            event_type="initiated",
            event_status="success",
            event_message=f"Rotation initiated: {reason}",
            old_cert_id=schedule.current_cert_id,
            rotation_reason=reason,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.info(f"Initiated rotation for schedule {schedule_id}")
        return True, "Rotation initiated"
    
    def complete_rotation(
        self,
        schedule_id: str,
        new_cert_id: str,
        new_cert_expires_at: datetime
    ) -> Tuple[bool, str]:
        """
        Complete rotation for schedule
        
        Args:
            schedule_id: Schedule ID
            new_cert_id: New certificate ID
            new_cert_expires_at: New certificate expiration
        
        Returns:
            Tuple of (success, message)
        """
        schedule = self.db.query(AttestationRotationSchedule).filter(
            AttestationRotationSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            return False, "Schedule not found"
        
        # Get policy for next rotation calculation
        policy = schedule.policy
        
        # Update schedule
        old_cert_id = schedule.current_cert_id
        schedule.last_rotation_at = datetime.now(timezone.utc)
        schedule.current_cert_id = new_cert_id
        schedule.current_cert_expires_at = new_cert_expires_at
        schedule.next_rotation_at = datetime.now(timezone.utc) + timedelta(
            days=policy.rotation_interval_days
        )
        schedule.rotation_status = "completed"
        schedule.rotation_attempts = 0
        schedule.last_rotation_error = None
        schedule.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        # Log rotation event
        event = AttestationRotationEvent(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            event_type="completed",
            event_status="success",
            event_message="Rotation completed successfully",
            old_cert_id=old_cert_id,
            new_cert_id=new_cert_id,
            rotation_reason="scheduled",
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.info(f"Completed rotation for schedule {schedule_id}")
        return True, "Rotation completed"
    
    def fail_rotation(
        self,
        schedule_id: str,
        error_message: str
    ) -> Tuple[bool, str]:
        """
        Mark rotation as failed
        
        Args:
            schedule_id: Schedule ID
            error_message: Error message
        
        Returns:
            Tuple of (success, message)
        """
        schedule = self.db.query(AttestationRotationSchedule).filter(
            AttestationRotationSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            return False, "Schedule not found"
        
        # Update schedule
        schedule.rotation_status = "failed"
        schedule.last_rotation_error = error_message
        schedule.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        # Log rotation event
        event = AttestationRotationEvent(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            event_type="failed",
            event_status="failure",
            event_message=f"Rotation failed: {error_message}",
            old_cert_id=schedule.current_cert_id,
            rotation_reason="scheduled",
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.error(f"Rotation failed for schedule {schedule_id}: {error_message}")
        return False, f"Rotation failed: {error_message}"
    
    def get_rotation_history(
        self,
        schedule_id: str,
        limit: int = 50
    ) -> List[AttestationRotationEvent]:
        """Get rotation history for schedule"""
        return self.db.query(AttestationRotationEvent).filter(
            AttestationRotationEvent.schedule_id == schedule_id
        ).order_by(
            AttestationRotationEvent.created_at.desc()
        ).limit(limit).all()
```

#### Step 3: Create Rotation Scheduler (Background Task)

**File:** `archiveorigin_backend_api/app/rotation_scheduler.py`

```python
"""
Attestation Rotation Scheduler

Background task for managing certificate rotations.
"""

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from rotation_service import AttestationRotationService

logger = logging.getLogger("archiveorigin.rotation_scheduler")


class AttestationRotationScheduler:
    """Background scheduler for certificate rotations"""
    
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.is_running = False
    
    async def start(self):
        """Start rotation scheduler"""
        self.is_running = True
        logger.info("Starting attestation rotation scheduler")
        
        while self.is_running:
            try:
                await self.check_and_process_rotations()
            except Exception as e:
                logger.error(f"Error in rotation scheduler: {str(e)}")
            
            # Check every hour
            await asyncio.sleep(3600)
    
    async def stop(self):
        """Stop rotation scheduler"""
        self.is_running = False
        logger.info("Stopping attestation rotation scheduler")
    
    async def check_and_process_rotations(self):
        """Check for due rotations and process them"""
        db = self.db_session_factory()
        
        try:
            service = AttestationRotationService(db)
            
            # Get schedules due for rotation
            due_schedules = service.get_schedules_due_for_rotation()
            logger.info(f"Found {len(due_schedules)} schedules due for rotation")
            
            for schedule in due_schedules:
                await self.process_rotation(service, schedule)
            
            # Get expiration warnings
            warning_schedules = service.get_expiration_warnings()
            logger.warning(f"Found {len(warning_schedules)} certificates expiring soon")
            
            for schedule in warning_schedules:
                await self.send_expiration_warning(schedule)
        
        finally:
            db.close()
    
    async def process_rotation(self, service, schedule):
        """Process rotation for schedule"""
        try:
            # Initiate rotation
            success, msg = service.initiate_rotation(
                schedule.id,
                reason="scheduled"
            )
            
            if not success:
                logger.error(f"Failed to initiate rotation: {msg}")
                return
            
            # TODO: Call DeviceCheck API to get new certificate
            # For now, mark as completed with mock data
            logger.info(f"Processing rotation for device {schedule.device_id}")
            
        except Exception as e:
            logger.error(f"Error processing rotation: {str(e)}")
            service.fail_rotation(schedule.id, str(e))
    
    async def send_expiration_warning(self, schedule):
        """Send expiration warning"""
        logger.warning(
            f"Certificate expiring soon for device {schedule.device_id}: "
            f"expires at {schedule.current_cert_expires_at}"
        )
        # TODO: Send notification to device/user
```

#### Step 4: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

```python
from rotation_service import AttestationRotationService

@app.post(
    "/attestation/rotation/policy",
    summary="Create rotation policy",
    tags=["Attestation"],
    response_model=dict
)
async def create_rotation_policy(
    request: CreateRotationPolicyRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Create attestation rotation policy"""
    # Verify admin access
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    service = AttestationRotationService(db)
    policy = service.create_rotation_policy(
        device_type=request.device_type,
        rotation_interval_days=request.rotation_interval_days,
        expiration_warning_days=request.expiration_warning_days
    )
    
    return {
        "policy_id": policy.id,
        "device_type": policy.device_type,
        "rotation_interval_days": policy.rotation_interval_days
    }


@app.get(
    "/attestation/rotation/due",
    summary="Get schedules due for rotation",
    tags=["Attestation"],
    response_model=list
)
async def get_due_rotations(
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get all schedules due for rotation"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    service = AttestationRotationService(db)
    schedules = service.get_schedules_due_for_rotation()
    
    return [
        {
            "schedule_id": s.id,
            "device_id": s.device_id,
            "next_rotation_at": s.next_rotation_at.isoformat(),
            "status": s.rotation_status
        }
        for s in schedules
    ]


@app.get(
    "/attestation/rotation/warnings",
    summary="Get expiration warnings",
    tags=["Attestation"],
    response_model=list
)
async def get_expiration_warnings(
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get certificates expiring soon"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    service = AttestationRotationService(db)
    schedules = service.get_expiration_warnings()
    
    return [
        {
            "schedule_id": s.id,
            "device_id": s.device_id,
            "expires_at": s.current_cert_expires_at.isoformat(),
            "days_until_expiry": (s.current_cert_expires_at - datetime.now(timezone.utc)).days
        }
        for s in schedules
    ]


@app.post(
    "/attestation/rotation/{schedule_id}/complete",
    summary="Complete rotation",
    tags=["Attestation"],
    response_model=dict
)
async def complete_rotation(
    schedule_id: str,
    request: CompleteRotationRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Complete rotation for schedule"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = AttestationRotationService(db)
    success, msg = service.complete_rotation(
        schedule_id,
        request.new_cert_id,
        request.new_cert_expires_at
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    return {"message": "Rotation completed"}
```

#### Step 5: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class CreateRotationPolicyRequest(BaseModel):
    device_type: str = Field(..., description="Device type")
    rotation_interval_days: int = Field(default=90, description="Rotation interval")
    expiration_warning_days: int = Field(default=14, description="Warning days")

class CompleteRotationRequest(BaseModel):
    new_cert_id: str = Field(..., description="New certificate ID")
    new_cert_expires_at: datetime = Field(..., description="Expiration date")
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_rotation_service.py`

```python
import pytest
from rotation_service import AttestationRotationService
from datetime import datetime, timedelta, timezone

def test_create_rotation_policy(db):
    """Test policy creation"""
    service = AttestationRotationService(db)
    policy = service.create_rotation_policy("devicecheck")
    
    assert policy.id is not None
    assert policy.device_type == "devicecheck"
    assert policy.rotation_interval_days == 90

def test_create_rotation_schedule(db):
    """Test schedule creation"""
    service = AttestationRotationService(db)
    expires = datetime.now(timezone.utc) + timedelta(days=365)
    
    schedule = service.create_rotation_schedule(
        device_token_id="token-123",
        device_id="device-123",
        device_type="devicecheck",
        current_cert_id="cert-123",
        current_cert_expires_at=expires
    )
    
    assert schedule.id is not None
    assert schedule.rotation_status == "pending"

def test_get_due_rotations(db):
    """Test getting due rotations"""
    service = AttestationRotationService(db)
    # Create schedule with past rotation date
    # Verify it appears in due list
```

---

## Success Criteria

- ✅ Rotation policy models created
- ✅ Rotation schedule models created
- ✅ Rotation service with full lifecycle management
- ✅ Background scheduler for automatic rotations
- ✅ Expiration warning system
- ✅ Rotation history tracking
- ✅ API endpoints for rotation management
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add rotation models
2. **NEW:** `archiveorigin_backend_api/app/rotation_service.py` - Service layer
3. **NEW:** `archiveorigin_backend_api/app/rotation_scheduler.py` - Background scheduler
4. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
5. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
6. **NEW:** `archiveorigin_backend_api/tests/test_rotation_service.py` - Tests

---

## Dependencies

- `sqlalchemy` - ORM (already installed)
- `asyncio` - Async scheduling (built-in)

---

## Resources

- [Certificate Lifecycle Management](https://en.wikipedia.org/wiki/Certificate_authority)
- [Rotation Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/14/orm/relationships.html)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
