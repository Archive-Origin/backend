# Phase 2A.4: Attestation Audit Logging (Task 2A.4)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** January 3, 2026  
**Depends On:** Task 2A.3 (Attestation Rotation)

---

## Overview

Implement comprehensive audit logging for all attestation operations. This creates an immutable audit trail for compliance, security analysis, and forensic investigation of all attestation-related activities.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/rotation_service.py** - Rotation management (from 2A.3)
- **archiveorigin_backend_api/app/metadata_service.py** - Metadata management (from 2A.2)
- **archiveorigin_backend_api/app/attestation_validator.py** - Chain validation (from 2A.1)
- **Database:** PostgreSQL with attestation storage

### What's Missing
- Comprehensive audit logging system
- Immutable audit trail storage
- Audit log querying and filtering
- Compliance reporting
- Log retention policies
- Audit log encryption

---

## Task 2A.4: Implement Attestation Audit Logging

### Objectives
1. Create comprehensive audit logging system
2. Log all attestation operations
3. Ensure immutability of audit logs
4. Enable audit trail queries
5. Support compliance reporting

### Implementation Steps

#### Step 1: Create Audit Logging Models

**File:** `archiveorigin_backend_api/app/models.py`

Add audit logging models:

```python
class AttestationAuditLog(Base):
    """Immutable audit log for attestation operations"""
    __tablename__ = "attestation_audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Operation Details
    operation_type = Column(String(50), nullable=False, index=True)  # create, validate, rotate, revoke, query
    operation_status = Column(String(50), nullable=False)  # success, failure, warning
    operation_result = Column(String(500))
    
    # Entity Information
    entity_type = Column(String(50), nullable=False, index=True)  # metadata, chain, rotation, policy
    entity_id = Column(String(36), nullable=False, index=True)
    
    # Actor Information
    actor_type = Column(String(50), nullable=False)  # system, user, device, admin
    actor_id = Column(String(255), nullable=False, index=True)
    actor_name = Column(String(255))
    
    # Request Context
    request_id = Column(String(36), index=True)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Changes
    changes_before = Column(JSON)  # Previous state
    changes_after = Column(JSON)   # New state
    change_summary = Column(String(500))
    
    # Security Context
    authentication_method = Column(String(50))  # bearer_token, api_key, mTLS, etc
    authorization_level = Column(String(50))  # public, user, admin, system
    
    # Compliance
    compliance_tags = Column(JSON)  # GDPR, HIPAA, SOC2, etc
    data_classification = Column(String(50))  # public, internal, confidential, restricted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    event_timestamp = Column(DateTime, nullable=False, index=True)  # When event occurred
    
    # Immutability
    log_hash = Column(String(64), unique=True)  # SHA256 hash for integrity
    previous_log_hash = Column(String(64))  # Hash of previous log (chain)
    
    # Retention
    retention_until = Column(DateTime, index=True)
    is_archived = Column(Boolean, default=False)


class AttestationAuditLogArchive(Base):
    """Archived audit logs for long-term storage"""
    __tablename__ = "attestation_audit_log_archives"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Archive Information
    archive_id = Column(String(36), unique=True)
    archive_date = Column(DateTime, default=datetime.utcnow)
    archive_period_start = Column(DateTime)
    archive_period_end = Column(DateTime)
    
    # Content
    log_count = Column(Integer)
    compressed_data = Column(LargeBinary)  # Compressed JSON logs
    
    # Integrity
    archive_hash = Column(String(64), unique=True)
    signature = Column(String(500))  # Digital signature
    
    # Storage
    storage_location = Column(String(255))  # S3, GCS, etc
    storage_key = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime)


class AttestationAuditLogQuery(Base):
    """Track audit log queries for compliance"""
    __tablename__ = "attestation_audit_log_queries"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Query Details
    query_type = Column(String(50), nullable=False)  # search, export, report
    query_filters = Column(JSON)
    query_result_count = Column(Integer)
    
    # Actor Information
    queried_by = Column(String(255), nullable=False)
    query_reason = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Compliance
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(String(255))
    approved_at = Column(DateTime)
```

#### Step 2: Create Audit Logging Service

**File:** `archiveorigin_backend_api/app/audit_logger.py`

```python
"""
Attestation Audit Logging Service

Manages immutable audit trail for all attestation operations.
"""

from typing import Dict, Optional, Any, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import logging
import uuid
import hashlib
import json

from models import (
    AttestationAuditLog,
    AttestationAuditLogArchive,
    AttestationAuditLogQuery
)

logger = logging.getLogger("archiveorigin.audit_logger")


class AttestationAuditLogger:
    """Service for audit logging"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_operation(
        self,
        operation_type: str,
        entity_type: str,
        entity_id: str,
        actor_type: str,
        actor_id: str,
        operation_status: str = "success",
        operation_result: Optional[str] = None,
        changes_before: Optional[Dict] = None,
        changes_after: Optional[Dict] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        authentication_method: Optional[str] = None,
        authorization_level: str = "user",
        compliance_tags: Optional[List[str]] = None,
        data_classification: str = "internal"
    ) -> AttestationAuditLog:
        """
        Log an attestation operation
        
        Args:
            operation_type: Type of operation (create, validate, rotate, etc)
            entity_type: Type of entity (metadata, chain, rotation, etc)
            entity_id: ID of entity
            actor_type: Type of actor (system, user, device, admin)
            actor_id: ID of actor
            operation_status: Status of operation (success, failure, warning)
            operation_result: Result message
            changes_before: State before operation
            changes_after: State after operation
            request_id: Request ID for tracing
            ip_address: IP address of requester
            user_agent: User agent string
            authentication_method: How actor was authenticated
            authorization_level: Authorization level of actor
            compliance_tags: Compliance tags (GDPR, HIPAA, etc)
            data_classification: Data classification level
        
        Returns:
            Created AttestationAuditLog
        """
        # Get previous log for chaining
        previous_log = self.db.query(AttestationAuditLog).order_by(
            AttestationAuditLog.created_at.desc()
        ).first()
        
        previous_log_hash = previous_log.log_hash if previous_log else None
        
        # Create log entry
        log_entry = AttestationAuditLog(
            id=str(uuid.uuid4()),
            operation_type=operation_type,
            operation_status=operation_status,
            operation_result=operation_result,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            request_id=request_id or str(uuid.uuid4()),
            ip_address=ip_address,
            user_agent=user_agent,
            changes_before=changes_before,
            changes_after=changes_after,
            change_summary=self._summarize_changes(changes_before, changes_after),
            authentication_method=authentication_method,
            authorization_level=authorization_level,
            compliance_tags=compliance_tags or [],
            data_classification=data_classification,
            event_timestamp=datetime.now(timezone.utc),
            previous_log_hash=previous_log_hash
        )
        
        # Calculate log hash
        log_entry.log_hash = self._calculate_log_hash(log_entry)
        
        # Set retention
        log_entry.retention_until = datetime.now(timezone.utc) + timedelta(days=2555)  # 7 years
        
        self.db.add(log_entry)
        self.db.commit()
        
        logger.info(
            f"Logged {operation_type} on {entity_type} {entity_id} "
            f"by {actor_type} {actor_id}: {operation_status}"
        )
        
        return log_entry
    
    def _calculate_log_hash(self, log_entry: AttestationAuditLog) -> str:
        """Calculate SHA256 hash of log entry"""
        log_data = {
            "id": log_entry.id,
            "operation_type": log_entry.operation_type,
            "entity_type": log_entry.entity_type,
            "entity_id": log_entry.entity_id,
            "actor_id": log_entry.actor_id,
            "event_timestamp": log_entry.event_timestamp.isoformat(),
            "previous_log_hash": log_entry.previous_log_hash
        }
        
        log_json = json.dumps(log_data, sort_keys=True)
        return hashlib.sha256(log_json.encode()).hexdigest()
    
    def _summarize_changes(
        self,
        before: Optional[Dict],
        after: Optional[Dict]
    ) -> str:
        """Summarize changes between before and after"""
        if not before or not after:
            return "No changes tracked"
        
        changes = []
        for key in after:
            if key not in before:
                changes.append(f"Added {key}")
            elif before[key] != after[key]:
                changes.append(f"Changed {key}: {before[key]} -> {after[key]}")
        
        return "; ".join(changes) if changes else "No changes"
    
    def query_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AttestationAuditLog]:
        """
        Query audit logs
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            actor_id: Filter by actor ID
            operation_type: Filter by operation type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results
        
        Returns:
            List of matching audit logs
        """
        query = self.db.query(AttestationAuditLog)
        
        if entity_type:
            query = query.filter(AttestationAuditLog.entity_type == entity_type)
        
        if entity_id:
            query = query.filter(AttestationAuditLog.entity_id == entity_id)
        
        if actor_id:
            query = query.filter(AttestationAuditLog.actor_id == actor_id)
        
        if operation_type:
            query = query.filter(AttestationAuditLog.operation_type == operation_type)
        
        if start_date:
            query = query.filter(AttestationAuditLog.event_timestamp >= start_date)
        
        if end_date:
            query = query.filter(AttestationAuditLog.event_timestamp <= end_date)
        
        return query.order_by(
            AttestationAuditLog.created_at.desc()
        ).limit(limit).all()
    
    def verify_log_integrity(self, log_id: str) -> Tuple[bool, str]:
        """
        Verify integrity of audit log
        
        Args:
            log_id: Log ID to verify
        
        Returns:
            Tuple of (is_valid, message)
        """
        log_entry = self.db.query(AttestationAuditLog).filter(
            AttestationAuditLog.id == log_id
        ).first()
        
        if not log_entry:
            return False, "Log not found"
        
        # Recalculate hash
        calculated_hash = self._calculate_log_hash(log_entry)
        
        if calculated_hash != log_entry.log_hash:
            return False, "Log hash mismatch - log may have been tampered with"
        
        # Verify chain
        if log_entry.previous_log_hash:
            previous_log = self.db.query(AttestationAuditLog).filter(
                AttestationAuditLog.log_hash == log_entry.previous_log_hash
            ).first()
            
            if not previous_log:
                return False, "Previous log not found - chain broken"
        
        return True, "Log integrity verified"
    
    def log_query(
        self,
        query_type: str,
        query_filters: Dict,
        result_count: int,
        queried_by: str,
        query_reason: Optional[str] = None,
        requires_approval: bool = False
    ) -> AttestationAuditLogQuery:
        """Log an audit log query"""
        query_log = AttestationAuditLogQuery(
            id=str(uuid.uuid4()),
            query_type=query_type,
            query_filters=query_filters,
            query_result_count=result_count,
            queried_by=queried_by,
            query_reason=query_reason,
            requires_approval=requires_approval
        )
        
        self.db.add(query_log)
        self.db.commit()
        
        logger.info(f"Logged audit query by {queried_by}: {query_type}")
        
        return query_log
    
    def archive_logs(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Tuple[bool, str]:
        """
        Archive logs for a period
        
        Args:
            period_start: Start of period
            period_end: End of period
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get logs for period
            logs = self.db.query(AttestationAuditLog).filter(
                AttestationAuditLog.event_timestamp >= period_start,
                AttestationAuditLog.event_timestamp <= period_end
            ).all()
            
            if not logs:
                return False, "No logs found for period"
            
            # Serialize logs
            logs_data = [
                {
                    "id": log.id,
                    "operation_type": log.operation_type,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "actor_id": log.actor_id,
                    "event_timestamp": log.event_timestamp.isoformat(),
                    "operation_status": log.operation_status
                }
                for log in logs
            ]
            
            # Compress
            import gzip
            compressed = gzip.compress(json.dumps(logs_data).encode())
            
            # Create archive
            archive = AttestationAuditLogArchive(
                id=str(uuid.uuid4()),
                archive_id=str(uuid.uuid4()),
                archive_period_start=period_start,
                archive_period_end=period_end,
                log_count=len(logs),
                compressed_data=compressed,
                archive_hash=hashlib.sha256(compressed).hexdigest()
            )
            
            self.db.add(archive)
            self.db.commit()
            
            logger.info(f"Archived {len(logs)} logs for period {period_start} to {period_end}")
            return True, f"Archived {len(logs)} logs"
        
        except Exception as e:
            logger.error(f"Error archiving logs: {str(e)}")
            return False, f"Archive failed: {str(e)}"
```

#### Step 3: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

```python
from audit_logger import AttestationAuditLogger

@app.get(
    "/attestation/audit-logs",
    summary="Query audit logs",
    tags=["Attestation"],
    response_model=list
)
async def query_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Query attestation audit logs"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    logger_service = AttestationAuditLogger(db)
    
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    
    logs = logger_service.query_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        operation_type=operation_type,
        start_date=start,
        end_date=end,
        limit=limit
    )
    
    # Log the query
    logger_service.log_query(
        query_type="search",
        query_filters={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor_id": actor_id,
            "operation_type": operation_type
        },
        result_count=len(logs),
        queried_by=get_actor_id(auth_header),
        query_reason="Audit log search"
    )
    
    return [
        {
            "id": log.id,
            "operation_type": log.operation_type,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "actor_id": log.actor_id,
            "operation_status": log.operation_status,
            "event_timestamp": log.event_timestamp.isoformat(),
            "log_hash": log.log_hash
        }
        for log in logs
    ]


@app.get(
    "/attestation/audit-logs/{log_id}/verify",
    summary="Verify audit log integrity",
    tags=["Attestation"],
    response_model=dict
)
async def verify_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Verify integrity of audit log"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    logger_service = AttestationAuditLogger(db)
    is_valid, message = logger_service.verify_log_integrity(log_id)
    
    return {
        "log_id": log_id,
        "is_valid": is_valid,
        "message": message
    }


@app.post(
    "/attestation/audit-logs/archive",
    summary="Archive audit logs",
    tags=["Attestation"],
    response_model=dict
)
async def archive_audit_logs(
    request: ArchiveLogsRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Archive audit logs for a period"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    logger_service = AttestationAuditLogger(db)
    
    start = datetime.fromisoformat(request.period_start)
    end = datetime.fromisoformat(request.period_end)
    
    success, message = logger_service.archive_logs(start, end)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message}
```

#### Step 4: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class ArchiveLogsRequest(BaseModel):
    period_start: str = Field(..., description="Start date (ISO format)")
    period_end: str = Field(..., description="End date (ISO format)")

class AuditLogResponse(BaseModel):
    id: str
    operation_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    operation_status: str
    event_timestamp: str
    log_hash: str
```

#### Step 5: Integration with Existing Services

Modify existing services to log operations:

**File:** `archiveorigin_backend_api/app/metadata_service.py`

```python
def create_metadata(self, ...):
    # ... existing code ...
    
    # Log operation
    audit_logger = AttestationAuditLogger(self.db)
    audit_logger.log_operation(
        operation_type="create",
        entity_type="metadata",
        entity_id=metadata.id,
        actor_type="system",
        actor_id="metadata_service",
        operation_status="success",
        changes_after={
            "device_id": metadata.device_id,
            "security_level": metadata.security_level
        },
        data_classification="confidential"
    )
    
    return metadata
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_audit_logger.py`

```python
import pytest
from audit_logger import AttestationAuditLogger
from datetime import datetime, timezone

def test_log_operation(db):
    """Test logging operation"""
    logger = AttestationAuditLogger(db)
    log = logger.log_operation(
        operation_type="create",
        entity_type="metadata",
        entity_id="meta-123",
        actor_type="system",
        actor_id="system",
        operation_status="success"
    )
    
    assert log.id is not None
    assert log.log_hash is not None

def test_verify_log_integrity(db):
    """Test log integrity verification"""
    logger = AttestationAuditLogger(db)
    log = logger.log_operation(...)
    
    is_valid, msg = logger.verify_log_integrity(log.id)
    assert is_valid is True

def test_query_logs(db):
    """Test querying logs"""
    logger = AttestationAuditLogger(db)
    # Create multiple logs
    # Query and verify results
```

---

## Success Criteria

- ✅ Audit logging models created
- ✅ Immutable audit trail with hash chaining
- ✅ Comprehensive logging service
- ✅ Log integrity verification
- ✅ Query and filtering capabilities
- ✅ Archive functionality
- ✅ API endpoints for audit operations
- ✅ Integration with existing services
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add audit models
2. **NEW:** `archiveorigin_backend_api/app/audit_logger.py` - Audit service
3. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
4. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
5. **MODIFY:** `archiveorigin_backend_api/app/metadata_service.py` - Add logging
6. **MODIFY:** `archiveorigin_backend_api/app/rotation_service.py` - Add logging
7. **NEW:** `archiveorigin_backend_api/tests/test_audit_logger.py` - Tests

---

## Dependencies

- `sqlalchemy` - ORM (already installed)
- `gzip` - Compression (built-in)
- `hashlib` - Hashing (built-in)

---

## Resources

- [Audit Logging Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [Immutable Audit Trails](https://en.wikipedia.org/wiki/Audit_trail)
- [Compliance Requirements](https://www.nist.gov/publications/security-and-privacy-controls-information-systems-and-organizations)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
