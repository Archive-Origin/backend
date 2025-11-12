# Phase 2B.2: Ledger Integrity Checks (Task 2B.2)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** January 17, 2026  
**Depends On:** Task 2B.1 (Merkle Proof Verification)

---

## Overview

Implement comprehensive ledger integrity checking system. This ensures that the ledger remains consistent, tamper-proof, and trustworthy through continuous validation of ledger state, proof chains, and data consistency.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/merkle_service.py** - Merkle tree management (from 2B.1)
- **archiveorigin_backend_api/app/audit_logger.py** - Audit logging (from 2A.4)
- **Database:** PostgreSQL with ledger storage

### What's Missing
- Ledger integrity validation
- Consistency checking
- Proof chain validation
- Data integrity verification
- Integrity check scheduling

---

## Task 2B.2: Implement Ledger Integrity Checks

### Objectives
1. Create comprehensive integrity checking system
2. Validate ledger consistency
3. Verify proof chains
4. Detect tampering
5. Enable automated integrity monitoring

### Implementation Steps

#### Step 1: Create Integrity Check Models

**File:** `archiveorigin_backend_api/app/models.py`

Add integrity check models:

```python
class LedgerIntegrityCheck(Base):
    """Ledger integrity check record"""
    __tablename__ = "ledger_integrity_checks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Check Information
    check_type = Column(String(50), nullable=False)  # full, incremental, spot
    check_status = Column(String(50), nullable=False)  # success, failure, warning
    check_result = Column(String(500))
    
    # Scope
    ledger_id = Column(String(36), nullable=False, index=True)
    check_start_index = Column(Integer, default=0)
    check_end_index = Column(Integer)
    
    # Results
    total_entries_checked = Column(Integer, default=0)
    entries_valid = Column(Integer, default=0)
    entries_invalid = Column(Integer, default=0)
    entries_warning = Column(Integer, default=0)
    
    # Issues Found
    issues = Column(JSON)  # List of issues found
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    check_duration_ms = Column(Integer)
    
    # Relationships
    issues_found = relationship("LedgerIntegrityIssue", back_populates="check")


class LedgerIntegrityIssue(Base):
    """Integrity issue found during check"""
    __tablename__ = "ledger_integrity_issues"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    check_id = Column(String(36), ForeignKey("ledger_integrity_checks.id"), nullable=False)
    
    # Issue Information
    issue_type = Column(String(50), nullable=False)  # hash_mismatch, proof_invalid, data_inconsistent
    severity = Column(String(50), nullable=False)  # critical, high, medium, low
    
    # Location
    entry_index = Column(Integer)
    entry_id = Column(String(36))
    
    # Details
    expected_value = Column(String(500))
    actual_value = Column(String(500))
    issue_description = Column(String(1000))
    
    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolution_action = Column(String(500))
    resolved_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    check = relationship("LedgerIntegrityCheck", back_populates="issues_found")


class LedgerConsistencyCheck(Base):
    """Ledger consistency check"""
    __tablename__ = "ledger_consistency_checks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Check Information
    ledger_id = Column(String(36), nullable=False, index=True)
    check_type = Column(String(50), nullable=False)  # merkle_root, proof_chain, data_consistency
    
    # Results
    is_consistent = Column(Boolean, nullable=False)
    consistency_score = Column(Float)  # 0.0 to 1.0
    
    # Details
    expected_state = Column(JSON)
    actual_state = Column(JSON)
    discrepancies = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    check_duration_ms = Column(Integer)
```

#### Step 2: Create Integrity Check Service

**File:** `archiveorigin_backend_api/app/integrity_checker.py`

```python
"""
Ledger Integrity Checker

Validates ledger consistency and detects tampering.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid
import hashlib
import time
from datetime import datetime, timezone

from models import (
    LedgerIntegrityCheck,
    LedgerIntegrityIssue,
    LedgerConsistencyCheck,
    MerkleProof,
    MerkleLeaf,
    MerkleTree as MerkleTreeModel
)
from merkle_service import MerkleService

logger = logging.getLogger("archiveorigin.integrity_checker")


class LedgerIntegrityChecker:
    """Service for checking ledger integrity"""
    
    def __init__(self, db: Session):
        self.db = db
        self.merkle_service = MerkleService(db)
    
    def perform_full_check(
        self,
        ledger_id: str
    ) -> LedgerIntegrityCheck:
        """
        Perform full integrity check on ledger
        
        Args:
            ledger_id: Ledger ID
        
        Returns:
            LedgerIntegrityCheck record
        """
        start_time = time.time()
        
        # Get all proofs for ledger
        proofs = self.db.query(MerkleProof).filter(
            MerkleProof.tree_id == ledger_id
        ).all()
        
        if not proofs:
            return self._create_check_record(
                ledger_id=ledger_id,
                check_type="full",
                check_status="warning",
                check_result="No proofs found",
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                warning_entries=0,
                issues=[],
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        issues = []
        valid_count = 0
        invalid_count = 0
        warning_count = 0
        
        # Check each proof
        for proof in proofs:
            is_valid, msg = self.merkle_service.verify_proof(proof.id)
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                issues.append({
                    "proof_id": proof.id,
                    "issue_type": "proof_invalid",
                    "severity": "critical",
                    "message": msg
                })
        
        # Determine overall status
        if invalid_count > 0:
            check_status = "failure"
        elif warning_count > 0:
            check_status = "warning"
        else:
            check_status = "success"
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return self._create_check_record(
            ledger_id=ledger_id,
            check_type="full",
            check_status=check_status,
            check_result=f"Checked {len(proofs)} proofs",
            total_entries=len(proofs),
            valid_entries=valid_count,
            invalid_entries=invalid_count,
            warning_entries=warning_count,
            issues=issues,
            duration_ms=duration_ms
        )
    
    def perform_incremental_check(
        self,
        ledger_id: str,
        start_index: int = 0
    ) -> LedgerIntegrityCheck:
        """
        Perform incremental integrity check
        
        Args:
            ledger_id: Ledger ID
            start_index: Start index for check
        
        Returns:
            LedgerIntegrityCheck record
        """
        start_time = time.time()
        
        # Get proofs from start index
        proofs = self.db.query(MerkleProof).filter(
            MerkleProof.tree_id == ledger_id
        ).offset(start_index).limit(100).all()
        
        if not proofs:
            return self._create_check_record(
                ledger_id=ledger_id,
                check_type="incremental",
                check_status="success",
                check_result="No new proofs to check",
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                warning_entries=0,
                issues=[],
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        issues = []
        valid_count = 0
        invalid_count = 0
        
        # Check each proof
        for proof in proofs:
            is_valid, msg = self.merkle_service.verify_proof(proof.id)
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                issues.append({
                    "proof_id": proof.id,
                    "issue_type": "proof_invalid",
                    "severity": "critical"
                })
        
        check_status = "failure" if invalid_count > 0 else "success"
        duration_ms = int((time.time() - start_time) * 1000)
        
        return self._create_check_record(
            ledger_id=ledger_id,
            check_type="incremental",
            check_status=check_status,
            check_result=f"Checked {len(proofs)} proofs",
            total_entries=len(proofs),
            valid_entries=valid_count,
            invalid_entries=invalid_count,
            warning_entries=0,
            issues=issues,
            duration_ms=duration_ms,
            start_index=start_index,
            end_index=start_index + len(proofs)
        )
    
    def check_merkle_root_consistency(
        self,
        ledger_id: str
    ) -> Tuple[bool, float, Dict]:
        """
        Check Merkle root consistency
        
        Args:
            ledger_id: Ledger ID
        
        Returns:
            Tuple of (is_consistent, score, details)
        """
        tree = self.merkle_service.get_tree(ledger_id)
        
        if not tree:
            return False, 0.0, {"error": "Tree not found"}
        
        # Get all leaves
        leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == ledger_id
        ).order_by(MerkleLeaf.leaf_index).all()
        
        if not leaves:
            return False, 0.0, {"error": "No leaves found"}
        
        # Rebuild tree
        from merkle_tree import MerkleTree
        leaf_hashes = [leaf.leaf_hash for leaf in leaves]
        rebuilt_tree = MerkleTree(leaf_hashes)
        
        # Compare roots
        is_consistent = rebuilt_tree.get_root() == tree.merkle_root
        score = 1.0 if is_consistent else 0.0
        
        return is_consistent, score, {
            "expected_root": tree.merkle_root,
            "calculated_root": rebuilt_tree.get_root(),
            "leaf_count": len(leaves)
        }
    
    def check_proof_chain_integrity(
        self,
        ledger_id: str
    ) -> Tuple[bool, float, List[Dict]]:
        """
        Check integrity of proof chain
        
        Args:
            ledger_id: Ledger ID
        
        Returns:
            Tuple of (is_valid, score, issues)
        """
        proofs = self.db.query(MerkleProof).filter(
            MerkleProof.tree_id == ledger_id
        ).all()
        
        if not proofs:
            return True, 1.0, []
        
        issues = []
        valid_count = 0
        
        for proof in proofs:
            is_valid, msg = self.merkle_service.verify_proof(proof.id)
            
            if is_valid:
                valid_count += 1
            else:
                issues.append({
                    "proof_id": proof.id,
                    "message": msg
                })
        
        score = valid_count / len(proofs) if proofs else 0.0
        is_valid = score == 1.0
        
        return is_valid, score, issues
    
    def check_data_consistency(
        self,
        ledger_id: str
    ) -> Tuple[bool, float, Dict]:
        """
        Check data consistency
        
        Args:
            ledger_id: Ledger ID
        
        Returns:
            Tuple of (is_consistent, score, details)
        """
        # Get tree
        tree = self.merkle_service.get_tree(ledger_id)
        
        if not tree:
            return False, 0.0, {"error": "Tree not found"}
        
        # Get leaves
        leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == ledger_id
        ).all()
        
        # Check for duplicates
        leaf_hashes = [leaf.leaf_hash for leaf in leaves]
        unique_hashes = set(leaf_hashes)
        
        has_duplicates = len(leaf_hashes) != len(unique_hashes)
        
        # Check for orphaned leaves
        orphaned_count = 0
        for leaf in leaves:
            proofs = self.db.query(MerkleProof).filter(
                MerkleProof.leaf_id == leaf.id
            ).count()
            
            if proofs == 0:
                orphaned_count += 1
        
        # Calculate score
        issues = []
        if has_duplicates:
            issues.append("Duplicate leaf hashes detected")
        if orphaned_count > 0:
            issues.append(f"{orphaned_count} orphaned leaves found")
        
        score = 1.0 - (len(issues) * 0.5)
        is_consistent = len(issues) == 0
        
        return is_consistent, score, {
            "total_leaves": len(leaves),
            "unique_leaves": len(unique_hashes),
            "orphaned_leaves": orphaned_count,
            "issues": issues
        }
    
    def _create_check_record(
        self,
        ledger_id: str,
        check_type: str,
        check_status: str,
        check_result: str,
        total_entries: int,
        valid_entries: int,
        invalid_entries: int,
        warning_entries: int,
        issues: List[Dict],
        duration_ms: int,
        start_index: int = 0,
        end_index: Optional[int] = None
    ) -> LedgerIntegrityCheck:
        """Create integrity check record"""
        check = LedgerIntegrityCheck(
            id=str(uuid.uuid4()),
            check_type=check_type,
            check_status=check_status,
            check_result=check_result,
            ledger_id=ledger_id,
            check_start_index=start_index,
            check_end_index=end_index,
            total_entries_checked=total_entries,
            entries_valid=valid_entries,
            entries_invalid=invalid_entries,
            entries_warning=warning_entries,
            issues=issues,
            check_duration_ms=duration_ms
        )
        
        self.db.add(check)
        self.db.commit()
        
        logger.info(
            f"Created {check_type} integrity check for ledger {ledger_id}: "
            f"{valid_entries} valid, {invalid_entries} invalid"
        )
        
        return check
    
    def get_check_history(
        self,
        ledger_id: str,
        limit: int = 50
    ) -> List[LedgerIntegrityCheck]:
        """Get integrity check history"""
        return self.db.query(LedgerIntegrityCheck).filter(
            LedgerIntegrityCheck.ledger_id == ledger_id
        ).order_by(
            LedgerIntegrityCheck.created_at.desc()
        ).limit(limit).all()
```

#### Step 3: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

```python
from integrity_checker import LedgerIntegrityChecker

@app.post(
    "/ledger/{ledger_id}/integrity/check/full",
    summary="Perform full integrity check",
    tags=["Ledger"],
    response_model=dict
)
async def full_integrity_check(
    ledger_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Perform full integrity check on ledger"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    checker = LedgerIntegrityChecker(db)
    check = checker.perform_full_check(ledger_id)
    
    return {
        "check_id": check.id,
        "check_type": check.check_type,
        "check_status": check.check_status,
        "total_entries": check.total_entries_checked,
        "valid_entries": check.entries_valid,
        "invalid_entries": check.entries_invalid,
        "duration_ms": check.check_duration_ms
    }


@app.post(
    "/ledger/{ledger_id}/integrity/check/incremental",
    summary="Perform incremental integrity check",
    tags=["Ledger"],
    response_model=dict
)
async def incremental_integrity_check(
    ledger_id: str,
    start_index: int = 0,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Perform incremental integrity check"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    checker = LedgerIntegrityChecker(db)
    check = checker.perform_incremental_check(ledger_id, start_index)
    
    return {
        "check_id": check.id,
        "check_type": check.check_type,
        "check_status": check.check_status,
        "total_entries": check.total_entries_checked,
        "valid_entries": check.entries_valid,
        "invalid_entries": check.entries_invalid
    }


@app.get(
    "/ledger/{ledger_id}/integrity/consistency",
    summary="Check Merkle root consistency",
    tags=["Ledger"],
    response_model=dict
)
async def check_consistency(
    ledger_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Check Merkle root consistency"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    checker = LedgerIntegrityChecker(db)
    is_consistent, score, details = checker.check_merkle_root_consistency(ledger_id)
    
    return {
        "is_consistent": is_consistent,
        "consistency_score": score,
        "details": details
    }


@app.get(
    "/ledger/{ledger_id}/integrity/history",
    summary="Get integrity check history",
    tags=["Ledger"],
    response_model=list
)
async def get_integrity_history(
    ledger_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Get integrity check history"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    checker = LedgerIntegrityChecker(db)
    checks = checker.get_check_history(ledger_id, limit)
    
    return [
        {
            "check_id": check.id,
            "check_type": check.check_type,
            "check_status": check.check_status,
            "created_at": check.created_at.isoformat(),
            "duration_ms": check.check_duration_ms
        }
        for check in checks
    ]
```

#### Step 4: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class IntegrityCheckResponse(BaseModel):
    check_id: str
    check_type: str
    check_status: str
    total_entries: int
    valid_entries: int
    invalid_entries: int
    duration_ms: int
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_integrity_checker.py`

```python
import pytest
from integrity_checker import LedgerIntegrityChecker

def test_full_integrity_check(db):
    """Test full integrity check"""
    checker = LedgerIntegrityChecker(db)
    # Create test ledger and proofs
    # Perform check
    # Verify results

def test_incremental_check(db):
    """Test incremental check"""
    checker = LedgerIntegrityChecker(db)
    # Create test ledger
    # Perform incremental check
    # Verify results

def test_merkle_root_consistency(db):
    """Test Merkle root consistency check"""
    checker = LedgerIntegrityChecker(db)
    # Create test tree
    # Check consistency
    # Verify results
```

---

## Success Criteria

- ✅ Integrity check models created
- ✅ Full and incremental check implementation
- ✅ Merkle root consistency verification
- ✅ Proof chain validation
- ✅ Data consistency checking
- ✅ API endpoints for integrity operations
- ✅ Check history tracking
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add integrity models
2. **NEW:** `archiveorigin_backend_api/app/integrity_checker.py` - Checker service
3. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
4. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
5. **NEW:** `archiveorigin_backend_api/tests/test_integrity_checker.py` - Tests

---

## Dependencies

- `sqlalchemy` - ORM (already installed)
- `hashlib` - Hashing (built-in)
- `time` - Timing (built-in)

---

## Resources

- [Data Integrity](https://en.wikipedia.org/wiki/Data_integrity)
- [Consistency Checking](https://en.wikipedia.org/wiki/Consistency_check)
- [Merkle Tree Verification](https://en.wikipedia.org/wiki/Merkle_tree)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
