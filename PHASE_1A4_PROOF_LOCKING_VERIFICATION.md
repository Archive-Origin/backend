# Phase 1A.4: Proof Locking Verification - Task 1.4

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** November 15, 2025  
**Depends On:** Phase 1A.3 (Complete)

---

## Overview

Implement proof locking verification to ensure that only enrolled devices can lock capture proofs. This adds a security layer by validating device attestation before allowing proof submission.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API with `/lock-proof` endpoint
- **PostgreSQL Database** - Proof storage
- **Device Enrollment** - Device validation (from Phase 1A.3)
- **Ed25519 Service** - Signature verification

### What's Missing
- Device validation in `/lock-proof` endpoint
- Proof ownership verification
- Proof status tracking
- Proof metadata storage
- Proof locking workflow

---

## Task 1.4: Implement Proof Locking Verification

### Objectives
1. Validate device enrollment before locking proof
2. Verify proof ownership
3. Store proof metadata
4. Track proof status
5. Implement proof locking workflow

### Implementation Steps

#### Step 1: Create Proof Model

**File:** `archiveorigin_backend_api/app/models.py` (Add to existing file)

```python
class Proof(Base):
    """Capture proof record"""
    __tablename__ = "proofs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), nullable=False)
    proof_hash = Column(String(255), nullable=False, unique=True)
    proof_data = Column(JSON, nullable=False)
    
    # Proof status
    status = Column(String(20), default='locked')  # locked, verified, revoked
    locked_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    
    # Signature verification
    signature = Column(String(500), nullable=False)
    signature_algorithm = Column(String(50), default='Ed25519')
    
    # Metadata
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Merkle ledger
    merkle_root = Column(String(255), nullable=True)
    merkle_proof = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Proof {self.proof_hash}>"

class ProofLog(Base):
    """Proof operation log"""
    __tablename__ = "proof_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proof_id = Column(String(36), nullable=False)
    operation = Column(String(50), nullable=False)  # lock, verify, revoke
    operation_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False)  # success, failure
    error_message = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<ProofLog {self.proof_id}>"
```

#### Step 2: Create Proof Service

**File:** `archiveorigin_backend_api/app/services/proof_service.py`

```python
from datetime import datetime
from sqlalchemy.orm import Session
from models import Proof, ProofLog, Device
from ed25519_service import Ed25519Service
from typing import Dict, Optional
import uuid
import hashlib

class ProofService:
    """Service for proof locking and verification"""
    
    def __init__(self, ed25519_service: Ed25519Service):
        self.ed25519_service = ed25519_service
    
    async def lock_proof(
        self,
        db: Session,
        device_id: str,
        proof_data: Dict,
        signature: str,
        content_type: str = None,
        file_size: int = None,
        metadata: Dict = None
    ) -> Proof:
        """Lock a capture proof"""
        
        # Verify device is enrolled and active
        device = db.query(Device).filter(
            Device.device_id == device_id,
            Device.is_active == True,
            Device.attestation_status == 'valid'
        ).first()
        
        if not device:
            raise ValueError("Device not enrolled or attestation invalid")
        
        # Calculate proof hash
        proof_json = str(proof_data).encode('utf-8')
        proof_hash = hashlib.sha256(proof_json).hexdigest()
        
        # Check if proof already locked
        existing_proof = db.query(Proof).filter(
            Proof.proof_hash == proof_hash
        ).first()
        
        if existing_proof:
            raise ValueError("Proof already locked")
        
        # Verify signature
        try:
            is_valid = self.ed25519_service.verify_signature(
                proof_json,
                signature,
                device.device_id
            )
            
            if not is_valid:
                raise ValueError("Signature verification failed")
        
        except Exception as e:
            self._log_proof_operation(
                db, None, 'lock', 'failure', str(e)
            )
            raise
        
        # Create proof record
        proof = Proof(
            id=str(uuid.uuid4()),
            device_id=device.id,
            proof_hash=proof_hash,
            proof_data=proof_data,
            signature=signature,
            content_type=content_type,
            file_size=file_size,
            metadata=metadata or {},
            status='locked'
        )
        
        db.add(proof)
        db.commit()
        db.refresh(proof)
        
        # Log successful lock
        self._log_proof_operation(
            db, proof.id, 'lock', 'success'
        )
        
        # Update device activity
        device.last_activity = datetime.utcnow()
        db.commit()
        
        return proof
    
    async def verify_proof(
        self,
        db: Session,
        proof_id: str
    ) -> Proof:
        """Verify a locked proof"""
        
        proof = db.query(Proof).filter(Proof.id == proof_id).first()
        
        if not proof:
            raise ValueError("Proof not found")
        
        if proof.status != 'locked':
            raise ValueError(f"Proof status is {proof.status}, not locked")
        
        try:
            # Verify signature
            proof_json = str(proof.proof_data).encode('utf-8')
            is_valid = self.ed25519_service.verify_signature(
                proof_json,
                proof.signature,
                proof.device_id
            )
            
            if not is_valid:
                raise ValueError("Signature verification failed")
            
            # Update proof status
            proof.status = 'verified'
            proof.verified_at = datetime.utcnow()
            db.commit()
            
            # Log successful verification
            self._log_proof_operation(
                db, proof.id, 'verify', 'success'
            )
        
        except Exception as e:
            self._log_proof_operation(
                db, proof.id, 'verify', 'failure', str(e)
            )
            raise
        
        return proof
    
    def get_proof(self, db: Session, proof_id: str) -> Optional[Proof]:
        """Get proof by ID"""
        return db.query(Proof).filter(Proof.id == proof_id).first()
    
    def get_proof_by_hash(self, db: Session, proof_hash: str) -> Optional[Proof]:
        """Get proof by hash"""
        return db.query(Proof).filter(Proof.proof_hash == proof_hash).first()
    
    def get_device_proofs(
        self,
        db: Session,
        device_id: str,
        status: str = None,
        limit: int = 100
    ):
        """Get proofs for a device"""
        query = db.query(Proof).filter(Proof.device_id == device_id)
        
        if status:
            query = query.filter(Proof.status == status)
        
        return query.order_by(Proof.locked_at.desc()).limit(limit).all()
    
    def _log_proof_operation(
        self,
        db: Session,
        proof_id: str,
        operation: str,
        status: str,
        error_message: str = None,
        metadata: Dict = None
    ):
        """Log proof operation"""
        log = ProofLog(
            id=str(uuid.uuid4()),
            proof_id=proof_id,
            operation=operation,
            status=status,
            error_message=error_message,
            metadata=metadata or {}
        )
        db.add(log)
        db.commit()
```

#### Step 3: Create Proof Endpoints

**File:** `archiveorigin_backend_api/app/routes/proofs.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from services.proof_service import ProofService
from ed25519_service import Ed25519Service

router = APIRouter(prefix="/proofs", tags=["proofs"])

class LockProofRequest(BaseModel):
    device_id: str
    proof_data: dict
    signature: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    metadata: Optional[dict] = None

class LockProofResponse(BaseModel):
    proof_id: str
    proof_hash: str
    status: str
    locked_at: str
    message: str

@router.post("/lock")
async def lock_proof(
    request: LockProofRequest,
    db: Session = Depends(get_db)
):
    """Lock a capture proof"""
    try:
        ed25519_service = Ed25519Service()
        proof_service = ProofService(ed25519_service)
        
        proof = await proof_service.lock_proof(
            db,
            request.device_id,
            request.proof_data,
            request.signature,
            request.content_type,
            request.file_size,
            request.metadata
        )
        
        return LockProofResponse(
            proof_id=proof.id,
            proof_hash=proof.proof_hash,
            status=proof.status,
            locked_at=proof.locked_at.isoformat(),
            message="Proof locked successfully"
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/verify/{proof_id}")
async def verify_proof(
    proof_id: str,
    db: Session = Depends(get_db)
):
    """Verify a locked proof"""
    try:
        ed25519_service = Ed25519Service()
        proof_service = ProofService(ed25519_service)
        
        proof = await proof_service.verify_proof(db, proof_id)
        
        return {
            'proof_id': proof.id,
            'status': proof.status,
            'verified_at': proof.verified_at.isoformat(),
            'message': 'Proof verified successfully'
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{proof_id}")
async def get_proof(
    proof_id: str,
    db: Session = Depends(get_db)
):
    """Get proof details"""
    try:
        ed25519_service = Ed25519Service()
        proof_service = ProofService(ed25519_service)
        
        proof = proof_service.get_proof(db, proof_id)
        if not proof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof not found"
            )
        
        return {
            'proof_id': proof.id,
            'proof_hash': proof.proof_hash,
            'status': proof.status,
            'locked_at': proof.locked_at.isoformat(),
            'verified_at': proof.verified_at.isoformat() if proof.verified_at else None,
            'content_type': proof.content_type,
            'file_size': proof.file_size
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/device/{device_id}")
async def get_device_proofs(
    device_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get proofs for a device"""
    try:
        ed25519_service = Ed25519Service()
        proof_service = ProofService(ed25519_service)
        
        proofs = proof_service.get_device_proofs(db, device_id, status, limit)
        
        return [
            {
                'proof_id': p.id,
                'proof_hash': p.proof_hash,
                'status': p.status,
                'locked_at': p.locked_at.isoformat()
            }
            for p in proofs
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

---

## Success Criteria

- ✅ Proof model created
- ✅ Proof service implemented
- ✅ Device validation working
- ✅ Signature verification working
- ✅ Proof locking working
- ✅ Proof verification working
- ✅ Proof endpoints available
- ✅ Proof logging implemented
- ✅ Tests passing

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add Proof and ProofLog models
2. **NEW:** `archiveorigin_backend_api/app/services/proof_service.py` - Proof service
3. **NEW:** `archiveorigin_backend_api/app/routes/proofs.py` - Proof endpoints

---

## Dependencies

- `sqlalchemy` - ORM
- `fastapi` - Web framework
- `hashlib` - Hashing

---

## Resources

- [Ed25519 Signatures](https://en.wikipedia.org/wiki/EdDSA)
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
