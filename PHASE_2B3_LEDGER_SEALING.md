# Phase 2B.3: Ledger Sealing (Task 2B.3)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** January 24, 2026  
**Depends On:** Task 2B.2 (Ledger Integrity Checks)

---

## Overview

Implement ledger sealing mechanism to create immutable snapshots of ledger state at specific points in time. Sealed ledgers cannot be modified, ensuring historical integrity and enabling time-based verification of ledger state.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/integrity_checker.py** - Integrity checking (from 2B.2)
- **archiveorigin_backend_api/app/merkle_service.py** - Merkle trees (from 2B.1)
- **Database:** PostgreSQL with ledger storage

### What's Missing
- Ledger sealing mechanism
- Seal creation and verification
- Sealed ledger snapshots
- Seal integrity validation
- Seal scheduling

---

## Task 2B.3: Implement Ledger Sealing

### Objectives
1. Create ledger sealing system
2. Generate immutable seals
3. Verify seal integrity
4. Track seal history
5. Enable time-based verification

### Implementation Steps

#### Step 1: Create Ledger Sealing Models

**File:** `archiveorigin_backend_api/app/models.py`

Add sealing models:

```python
class LedgerSeal(Base):
    """Immutable ledger seal"""
    __tablename__ = "ledger_seals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Seal Information
    ledger_id = Column(String(36), nullable=False, index=True)
    seal_version = Column(Integer, default=1)
    seal_status = Column(String(50), nullable=False)  # active, revoked, expired
    
    # Ledger State at Seal Time
    ledger_entry_count = Column(Integer, nullable=False)
    merkle_root_at_seal = Column(String(64), nullable=False)
    ledger_hash = Column(String(64), nullable=False, unique=True)
    
    # Seal Cryptography
    seal_signature = Column(String(500), nullable=False)  # Digital signature
    seal_certificate = Column(Text)  # X.509 certificate
    signing_algorithm = Column(String(50), default="ES256")
    
    # Seal Metadata
    seal_timestamp = Column(DateTime, nullable=False, index=True)
    seal_reason = Column(String(255))  # scheduled, manual, compliance
    sealed_by = Column(String(255))  # Actor who sealed
    
    # Validity
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime)
    revocation_reason = Column(String(500))
    
    # Relationships
    snapshots = relationship("LedgerSnapshot", back_populates="seal")
    verifications = relationship("LedgerSealVerification", back_populates="seal")


class LedgerSnapshot(Base):
    """Snapshot of ledger state at seal time"""
    __tablename__ = "ledger_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seal_id = Column(String(36), ForeignKey("ledger_seals.id"), nullable=False)
    
    # Snapshot Information
    snapshot_index = Column(Integer, nullable=False)
    snapshot_data = Column(JSON, nullable=False)  # Compressed ledger state
    
    # Integrity
    snapshot_hash = Column(String(64), nullable=False, unique=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    seal = relationship("LedgerSeal", back_populates="snapshots")


class LedgerSealVerification(Base):
    """Verification record for seal"""
    __tablename__ = "ledger_seal_verifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seal_id = Column(String(36), ForeignKey("ledger_seals.id"), nullable=False)
    
    # Verification Information
    verification_type = Column(String(50), nullable=False)  # signature, timestamp, integrity
    verification_status = Column(String(50), nullable=False)  # success, failure
    verification_result = Column(String(500))
    
    # Verifier Information
    verified_by = Column(String(255))
    verification_method = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    seal = relationship("LedgerSeal", back_populates="verifications")


class LedgerSealPolicy(Base):
    """Policy for automatic ledger sealing"""
    __tablename__ = "ledger_seal_policies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Policy Information
    ledger_id = Column(String(36), nullable=False, unique=True, index=True)
    policy_name = Column(String(255), nullable=False)
    policy_status = Column(String(50), default="active")  # active, inactive
    
    # Sealing Schedule
    seal_interval_hours = Column(Integer, default=24)  # Seal every N hours
    seal_on_entry_count = Column(Integer)  # Seal after N entries
    seal_on_size_mb = Column(Integer)  # Seal after N MB
    
    # Seal Configuration
    require_signature = Column(Boolean, default=True)
    require_timestamp = Column(Boolean, default=True)
    retention_days = Column(Integer, default=2555)  # 7 years
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seal_at = Column(DateTime)
    next_seal_at = Column(DateTime)
```

#### Step 2: Create Ledger Sealing Service

**File:** `archiveorigin_backend_api/app/ledger_sealer.py`

```python
"""
Ledger Sealing Service

Manages ledger sealing and verification.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid
import hashlib
import json
import gzip
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from models import (
    LedgerSeal,
    LedgerSnapshot,
    LedgerSealVerification,
    LedgerSealPolicy,
    MerkleTree as MerkleTreeModel,
    MerkleLeaf
)

logger = logging.getLogger("archiveorigin.ledger_sealer")


class LedgerSealer:
    """Service for sealing ledgers"""
    
    def __init__(self, db: Session, private_key_path: Optional[str] = None):
        self.db = db
        self.private_key_path = private_key_path
        self.private_key = None
        
        if private_key_path:
            self._load_private_key()
    
    def _load_private_key(self):
        """Load private key for signing"""
        try:
            with open(self.private_key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
        except Exception as e:
            logger.error(f"Failed to load private key: {str(e)}")
    
    def create_seal(
        self,
        ledger_id: str,
        seal_reason: str = "scheduled",
        sealed_by: str = "system"
    ) -> Optional[LedgerSeal]:
        """
        Create seal for ledger
        
        Args:
            ledger_id: Ledger ID
            seal_reason: Reason for sealing
            sealed_by: Actor sealing ledger
        
        Returns:
            Created LedgerSeal or None
        """
        # Get tree
        tree = self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.id == ledger_id
        ).first()
        
        if not tree:
            logger.error(f"Tree {ledger_id} not found")
            return None
        
        # Get all leaves
        leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == ledger_id
        ).order_by(MerkleLeaf.leaf_index).all()
        
        # Calculate ledger hash
        ledger_data = {
            "tree_id": ledger_id,
            "entry_count": len(leaves),
            "merkle_root": tree.merkle_root,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        ledger_json = json.dumps(ledger_data, sort_keys=True)
        ledger_hash = hashlib.sha256(ledger_json.encode()).hexdigest()
        
        # Create seal
        seal = LedgerSeal(
            id=str(uuid.uuid4()),
            ledger_id=ledger_id,
            ledger_entry_count=len(leaves),
            merkle_root_at_seal=tree.merkle_root,
            ledger_hash=ledger_hash,
            seal_timestamp=datetime.now(timezone.utc),
            seal_reason=seal_reason,
            sealed_by=sealed_by,
            valid_from=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=2555)
        )
        
        # Sign seal
        if self.private_key:
            seal.seal_signature = self._sign_seal(seal)
        
        self.db.add(seal)
        self.db.flush()
        
        # Create snapshot
        self._create_snapshot(seal, leaves)
        
        self.db.commit()
        
        logger.info(f"Created seal {seal.id} for ledger {ledger_id}")
        return seal
    
    def _sign_seal(self, seal: LedgerSeal) -> str:
        """Sign seal with private key"""
        if not self.private_key:
            return ""
        
        seal_data = {
            "ledger_id": seal.ledger_id,
            "ledger_hash": seal.ledger_hash,
            "merkle_root": seal.merkle_root_at_seal,
            "timestamp": seal.seal_timestamp.isoformat()
        }
        
        seal_json = json.dumps(seal_data, sort_keys=True)
        
        signature = self.private_key.sign(
            seal_json.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        
        return signature.hex()
    
    def _create_snapshot(self, seal: LedgerSeal, leaves: List):
        """Create snapshot of ledger state"""
        snapshot_data = {
            "seal_id": seal.id,
            "ledger_id": seal.ledger_id,
            "entry_count": len(leaves),
            "merkle_root": seal.merkle_root_at_seal,
            "entries": [
                {
                    "index": leaf.leaf_index,
                    "hash": leaf.leaf_hash,
                    "content_id": leaf.content_id
                }
                for leaf in leaves
            ]
        }
        
        # Compress snapshot
        snapshot_json = json.dumps(snapshot_data)
        compressed = gzip.compress(snapshot_json.encode())
        
        # Calculate snapshot hash
        snapshot_hash = hashlib.sha256(compressed).hexdigest()
        
        snapshot = LedgerSnapshot(
            id=str(uuid.uuid4()),
            seal_id=seal.id,
            snapshot_index=0,
            snapshot_data=snapshot_data,
            snapshot_hash=snapshot_hash
        )
        
        self.db.add(snapshot)
    
    def verify_seal(self, seal_id: str) -> Tuple[bool, str]:
        """
        Verify seal integrity
        
        Args:
            seal_id: Seal ID
        
        Returns:
            Tuple of (is_valid, message)
        """
        seal = self.db.query(LedgerSeal).filter(
            LedgerSeal.id == seal_id
        ).first()
        
        if not seal:
            return False, "Seal not found"
        
        # Check if seal is revoked
        if seal.seal_status == "revoked":
            return False, "Seal has been revoked"
        
        # Check if seal is expired
        if seal.valid_until and datetime.now(timezone.utc) > seal.valid_until:
            return False, "Seal has expired"
        
        # Verify signature
        if seal.seal_signature and self.private_key:
            is_valid = self._verify_signature(seal)
            if not is_valid:
                return False, "Seal signature verification failed"
        
        # Log verification
        verification = LedgerSealVerification(
            id=str(uuid.uuid4()),
            seal_id=seal_id,
            verification_type="signature",
            verification_status="success",
            verification_result="Seal verified successfully"
        )
        
        self.db.add(verification)
        self.db.commit()
        
        return True, "Seal verified successfully"
    
    def _verify_signature(self, seal: LedgerSeal) -> bool:
        """Verify seal signature"""
        if not self.private_key or not seal.seal_signature:
            return False
        
        try:
            seal_data = {
                "ledger_id": seal.ledger_id,
                "ledger_hash": seal.ledger_hash,
                "merkle_root": seal.merkle_root_at_seal,
                "timestamp": seal.seal_timestamp.isoformat()
            }
            
            seal_json = json.dumps(seal_data, sort_keys=True)
            signature_bytes = bytes.fromhex(seal.seal_signature)
            
            # Verify using public key
            public_key = self.private_key.public_key()
            public_key.verify(
                signature_bytes,
                seal_json.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            
            return True
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def revoke_seal(
        self,
        seal_id: str,
        reason: str
    ) -> Tuple[bool, str]:
        """
        Revoke seal
        
        Args:
            seal_id: Seal ID
            reason: Revocation reason
        
        Returns:
            Tuple of (success, message)
        """
        seal = self.db.query(LedgerSeal).filter(
            LedgerSeal.id == seal_id
        ).first()
        
        if not seal:
            return False, "Seal not found"
        
        seal.seal_status = "revoked"
        seal.revoked_at = datetime.now(timezone.utc)
        seal.revocation_reason = reason
        
        self.db.commit()
        
        logger.info(f"Revoked seal {seal_id}: {reason}")
        return True, "Seal revoked successfully"
    
    def get_seal(self, seal_id: str) -> Optional[LedgerSeal]:
        """Get seal by ID"""
        return self.db.query(LedgerSeal).filter(
            LedgerSeal.id == seal_id
        ).first()
    
    def get_seals_for_ledger(
        self,
        ledger_id: str,
        limit: int = 50
    ) -> List[LedgerSeal]:
        """Get seals for ledger"""
        return self.db.query(LedgerSeal).filter(
            LedgerSeal.ledger_id == ledger_id
        ).order_by(
            LedgerSeal.seal_timestamp.desc()
        ).limit(limit).all()
    
    def create_seal_policy(
        self,
        ledger_id: str,
        policy_name: str,
        seal_interval_hours: int = 24
    ) -> LedgerSealPolicy:
        """Create sealing policy"""
        policy = LedgerSealPolicy(
            id=str(uuid.uuid4()),
            ledger_id=ledger_id,
            policy_name=policy_name,
            seal_interval_hours=seal_interval_hours,
            next_seal_at=datetime.now(timezone.utc) + timedelta(hours=seal_interval_hours)
        )
        
        self.db.add(policy)
        self.db.commit()
        
        logger.info(f"Created seal policy {policy_name} for ledger {ledger_id}")
        return policy
    
    def get_policies_due_for_sealing(self) -> List[LedgerSealPolicy]:
        """Get policies due for sealing"""
        return self.db.query(LedgerSealPolicy).filter(
            LedgerSealPolicy.policy_status == "active",
            LedgerSealPolicy.next_seal_at <= datetime.now(timezone.utc)
        ).all()
```

#### Step 3: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

```python
from ledger_sealer import LedgerSealer

@app.post(
    "/ledger/{ledger_id}/seal",
    summary="Create ledger seal",
    tags=["Ledger"],
    response_model=dict
)
async def create_ledger_seal(
    ledger_id: str,
    request: CreateSealRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Create seal for ledger"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    sealer = LedgerSealer(db)
    seal = sealer.create_seal(
        ledger_id=ledger_id,
        seal_reason=request.seal_reason,
        sealed_by=get_actor_id(auth_header)
    )
    
    if not seal:
        raise HTTPException(status_code=400, detail="Failed to create seal")
    
    return {
        "seal_id": seal.id,
        "ledger_id": seal.ledger_id,
        "merkle_root": seal.merkle_root_at_seal,
        "entry_count": seal.ledger_entry_count,
        "seal_timestamp": seal.seal_timestamp.isoformat()
    }


@app.post(
    "/ledger/seal/{seal_id}/verify",
    summary="Verify ledger seal",
    tags=["Ledger"],
    response_model=dict
)
async def verify_ledger_seal(
    seal_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Verify ledger seal"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    sealer = LedgerSealer(db)
    is_valid, msg = sealer.verify_seal(seal_id)
    
    return {
        "seal_id": seal_id,
        "is_valid": is_valid,
        "message": msg
    }


@app.post(
    "/ledger/seal/{seal_id}/revoke",
    summary="Revoke ledger seal",
    tags=["Ledger"],
    response_model=dict
)
async def revoke_ledger_seal(
    seal_id: str,
    request: RevokeSealRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Revoke ledger seal"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    sealer = LedgerSealer(db)
    success, msg = sealer.revoke_seal(seal_id, request.reason)
    
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    return {"message": msg}


@app.get(
    "/ledger/{ledger_id}/seals",
    summary="Get ledger seals",
    tags=["Ledger"],
    response_model=list
)
async def get_ledger_seals(
    ledger_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get seals for ledger"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    sealer = LedgerSealer(db)
    seals = sealer.get_seals_for_ledger(ledger_id, limit)
    
    return [
        {
            "seal_id": seal.id,
            "seal_status": seal.seal_status,
            "entry_count": seal.ledger_entry_count,
            "seal_timestamp": seal.seal_timestamp.isoformat()
        }
        for seal in seals
    ]
```

#### Step 4: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class CreateSealRequest(BaseModel):
    seal_reason: str = Field(..., description="Reason for sealing")

class RevokeSealRequest(BaseModel):
    reason: str = Field(..., description="Revocation reason")
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_ledger_sealer.py`

```python
import pytest
from ledger_sealer import LedgerSealer

def test_create_seal(db):
    """Test seal creation"""
    sealer = LedgerSealer(db)
    # Create test ledger
    # Create seal
    # Verify seal created

def test_verify_seal(db):
    """Test seal verification"""
    sealer = LedgerSealer(db)
    # Create seal
    # Verify seal
    # Check verification record

def test_revoke_seal(db):
    """Test seal revocation"""
    sealer = LedgerSealer(db)
    # Create seal
    # Revoke seal
    # Verify revocation
```

---

## Success Criteria

- ✅ Ledger sealing models created
- ✅ Seal creation with cryptographic signing
- ✅ Seal verification logic
- ✅ Snapshot creation and storage
- ✅ Seal revocation mechanism
- ✅ Sealing policy management
- ✅ API endpoints for seal operations
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add sealing models
2. **NEW:** `archiveorigin_backend_api/app/ledger_sealer.py` - Sealing service
3. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
4. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
5. **NEW:** `archiveorigin_backend_api/tests/test_ledger_sealer.py` - Tests

---

## Dependencies

- `cryptography` - Digital signatures
- `gzip` - Compression (built-in)
- `hashlib` - Hashing (built-in)
- `json` - JSON handling (built-in)

---

## Resources

- [Digital Signatures](https://en.wikipedia.org/wiki/Digital_signature)
- [ECDSA](https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm)
- [Ledger Sealing](https://en.wikipedia.org/wiki/Ledger_(accounting))

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
