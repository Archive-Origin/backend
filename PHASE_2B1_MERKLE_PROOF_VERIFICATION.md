# Phase 2B.1: Merkle Proof Verification (Task 2B.1)

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** January 10, 2026  
**Depends On:** Phase 2A (Attestation Hardening)

---

## Overview

Implement Merkle tree proof verification to ensure the integrity and immutability of the ledger. This enables cryptographic verification that proofs haven't been tampered with and belong to a specific ledger state.

---

## Current State

### Existing Components
- **archiveorigin_backend_api/app/main.py** - FastAPI application
- **archiveorigin_backend_api/models.py** - Database models
- **Database:** PostgreSQL with proof storage

### What's Missing
- Merkle tree construction
- Proof generation
- Proof verification logic
- Merkle root tracking
- Proof validation endpoints

---

## Task 2B.1: Implement Merkle Proof Verification

### Objectives
1. Implement Merkle tree data structure
2. Generate cryptographic proofs
3. Verify proof membership
4. Track Merkle roots
5. Enable ledger integrity verification

### Implementation Steps

#### Step 1: Create Merkle Tree Models

**File:** `archiveorigin_backend_api/app/models.py`

Add Merkle tree models:

```python
class MerkleTree(Base):
    """Merkle tree for ledger integrity"""
    __tablename__ = "merkle_trees"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Tree Information
    tree_name = Column(String(255), nullable=False, unique=True)
    tree_type = Column(String(50), nullable=False)  # proof_ledger, attestation_ledger
    
    # Tree State
    leaf_count = Column(Integer, default=0)
    tree_height = Column(Integer, default=0)
    merkle_root = Column(String(64), nullable=False, index=True)  # SHA256 hash
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_root_update = Column(DateTime)
    
    # Relationships
    leaves = relationship("MerkleLeaf", back_populates="tree")
    nodes = relationship("MerkleNode", back_populates="tree")
    proofs = relationship("MerkleProof", back_populates="tree")


class MerkleLeaf(Base):
    """Leaf node in Merkle tree"""
    __tablename__ = "merkle_leaves"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tree_id = Column(String(36), ForeignKey("merkle_trees.id"), nullable=False)
    
    # Leaf Information
    leaf_index = Column(Integer, nullable=False)  # Position in tree
    leaf_hash = Column(String(64), nullable=False, unique=True)  # SHA256 hash
    
    # Content Reference
    content_type = Column(String(50), nullable=False)  # proof, attestation, etc
    content_id = Column(String(36), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tree = relationship("MerkleTree", back_populates="leaves")
    proofs = relationship("MerkleProof", back_populates="leaf")


class MerkleNode(Base):
    """Internal node in Merkle tree"""
    __tablename__ = "merkle_nodes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tree_id = Column(String(36), ForeignKey("merkle_trees.id"), nullable=False)
    
    # Node Information
    node_level = Column(Integer, nullable=False)  # 0 = leaves, 1 = parents, etc
    node_index = Column(Integer, nullable=False)  # Position at this level
    node_hash = Column(String(64), nullable=False)  # SHA256 hash
    
    # Parent/Child References
    left_child_hash = Column(String(64))
    right_child_hash = Column(String(64))
    parent_hash = Column(String(64))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tree = relationship("MerkleTree", back_populates="nodes")


class MerkleProof(Base):
    """Merkle proof for ledger membership"""
    __tablename__ = "merkle_proofs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tree_id = Column(String(36), ForeignKey("merkle_trees.id"), nullable=False)
    leaf_id = Column(String(36), ForeignKey("merkle_leaves.id"), nullable=False)
    
    # Proof Information
    proof_path = Column(JSON, nullable=False)  # List of hashes from leaf to root
    proof_indices = Column(JSON, nullable=False)  # Indices for each level
    
    # Verification
    merkle_root = Column(String(64), nullable=False)  # Root at time of proof
    is_valid = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime)
    
    # Relationships
    tree = relationship("MerkleTree", back_populates="proofs")
    leaf = relationship("MerkleLeaf", back_populates="proofs")
```

#### Step 2: Create Merkle Tree Service

**File:** `archiveorigin_backend_api/app/merkle_tree.py`

```python
"""
Merkle Tree Implementation

Provides Merkle tree construction and proof verification.
"""

from typing import List, Dict, Optional, Tuple
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger("archiveorigin.merkle_tree")


class MerkleTreeNode:
    """Merkle tree node"""
    
    def __init__(self, hash_value: str, left=None, right=None):
        self.hash = hash_value
        self.left = left
        self.right = right


class MerkleTree:
    """Merkle tree implementation"""
    
    def __init__(self, leaves: List[str]):
        """
        Initialize Merkle tree
        
        Args:
            leaves: List of leaf hashes
        """
        self.leaves = leaves
        self.tree = []
        self.root = None
        self._build_tree()
    
    def _build_tree(self):
        """Build Merkle tree from leaves"""
        if not self.leaves:
            raise ValueError("Cannot build tree with no leaves")
        
        # Start with leaves
        current_level = [MerkleTreeNode(leaf) for leaf in self.leaves]
        self.tree.append(current_level)
        
        # Build tree bottom-up
        while len(current_level) > 1:
            next_level = []
            
            # Process pairs of nodes
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                # Hash pair
                combined = left.hash + right.hash
                parent_hash = hashlib.sha256(combined.encode()).hexdigest()
                
                parent = MerkleTreeNode(parent_hash, left, right)
                next_level.append(parent)
            
            self.tree.append(next_level)
            current_level = next_level
        
        # Root is the last node
        self.root = current_level[0].hash
    
    def get_proof(self, leaf_index: int) -> Tuple[List[str], List[int]]:
        """
        Get Merkle proof for leaf
        
        Args:
            leaf_index: Index of leaf
        
        Returns:
            Tuple of (proof_path, proof_indices)
        """
        if leaf_index >= len(self.leaves):
            raise ValueError(f"Leaf index {leaf_index} out of range")
        
        proof_path = []
        proof_indices = []
        
        current_index = leaf_index
        
        # Traverse from leaf to root
        for level in range(len(self.tree) - 1):
            level_nodes = self.tree[level]
            
            # Get sibling
            if current_index % 2 == 0:
                # Current is left child
                sibling_index = current_index + 1
                if sibling_index < len(level_nodes):
                    proof_path.append(level_nodes[sibling_index].hash)
                    proof_indices.append(1)  # Right sibling
            else:
                # Current is right child
                sibling_index = current_index - 1
                proof_path.append(level_nodes[sibling_index].hash)
                proof_indices.append(0)  # Left sibling
            
            # Move to parent level
            current_index = current_index // 2
        
        return proof_path, proof_indices
    
    def verify_proof(
        self,
        leaf_hash: str,
        proof_path: List[str],
        proof_indices: List[int]
    ) -> bool:
        """
        Verify Merkle proof
        
        Args:
            leaf_hash: Hash of leaf
            proof_path: Proof path from leaf to root
            proof_indices: Indices indicating sibling positions
        
        Returns:
            True if proof is valid
        """
        current_hash = leaf_hash
        
        # Traverse proof path
        for i, sibling_hash in enumerate(proof_path):
            if proof_indices[i] == 0:
                # Sibling is on left
                combined = sibling_hash + current_hash
            else:
                # Sibling is on right
                combined = current_hash + sibling_hash
            
            current_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        # Check if we reached the root
        return current_hash == self.root
    
    def get_root(self) -> str:
        """Get Merkle root"""
        return self.root
    
    def get_height(self) -> int:
        """Get tree height"""
        return len(self.tree)
    
    def get_leaf_count(self) -> int:
        """Get number of leaves"""
        return len(self.leaves)
```

#### Step 3: Create Merkle Service

**File:** `archiveorigin_backend_api/app/merkle_service.py`

```python
"""
Merkle Tree Service

Manages Merkle trees and proof generation/verification.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid
from datetime import datetime, timezone

from models import (
    MerkleTree as MerkleTreeModel,
    MerkleLeaf,
    MerkleNode,
    MerkleProof
)
from merkle_tree import MerkleTree

logger = logging.getLogger("archiveorigin.merkle_service")


class MerkleService:
    """Service for managing Merkle trees"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_tree(
        self,
        tree_name: str,
        tree_type: str,
        initial_leaves: List[Dict[str, str]]
    ) -> MerkleTreeModel:
        """
        Create new Merkle tree
        
        Args:
            tree_name: Name of tree
            tree_type: Type of tree (proof_ledger, attestation_ledger)
            initial_leaves: List of leaf data with content_type, content_id, content_hash
        
        Returns:
            Created MerkleTreeModel
        """
        # Extract leaf hashes
        leaf_hashes = [leaf["content_hash"] for leaf in initial_leaves]
        
        # Build Merkle tree
        merkle_tree = MerkleTree(leaf_hashes)
        
        # Create tree record
        tree = MerkleTreeModel(
            id=str(uuid.uuid4()),
            tree_name=tree_name,
            tree_type=tree_type,
            leaf_count=len(initial_leaves),
            tree_height=merkle_tree.get_height(),
            merkle_root=merkle_tree.get_root(),
            last_root_update=datetime.now(timezone.utc)
        )
        
        self.db.add(tree)
        self.db.flush()
        
        # Create leaf records
        for i, leaf_data in enumerate(initial_leaves):
            leaf = MerkleLeaf(
                id=str(uuid.uuid4()),
                tree_id=tree.id,
                leaf_index=i,
                leaf_hash=leaf_hashes[i],
                content_type=leaf_data["content_type"],
                content_id=leaf_data["content_id"],
                content_hash=leaf_data["content_hash"]
            )
            self.db.add(leaf)
        
        self.db.commit()
        
        logger.info(f"Created Merkle tree {tree_name} with {len(initial_leaves)} leaves")
        return tree
    
    def add_leaf(
        self,
        tree_id: str,
        content_type: str,
        content_id: str,
        content_hash: str
    ) -> Tuple[bool, str]:
        """
        Add leaf to tree (rebuilds tree)
        
        Args:
            tree_id: Tree ID
            content_type: Type of content
            content_id: Content ID
            content_hash: Content hash
        
        Returns:
            Tuple of (success, message)
        """
        tree = self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.id == tree_id
        ).first()
        
        if not tree:
            return False, "Tree not found"
        
        # Get all existing leaves
        existing_leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == tree_id
        ).order_by(MerkleLeaf.leaf_index).all()
        
        # Add new leaf
        new_leaf_index = len(existing_leaves)
        new_leaf = MerkleLeaf(
            id=str(uuid.uuid4()),
            tree_id=tree_id,
            leaf_index=new_leaf_index,
            leaf_hash=content_hash,
            content_type=content_type,
            content_id=content_id,
            content_hash=content_hash
        )
        
        self.db.add(new_leaf)
        
        # Rebuild tree
        all_leaf_hashes = [leaf.leaf_hash for leaf in existing_leaves] + [content_hash]
        merkle_tree = MerkleTree(all_leaf_hashes)
        
        # Update tree
        tree.leaf_count = len(all_leaf_hashes)
        tree.tree_height = merkle_tree.get_height()
        tree.merkle_root = merkle_tree.get_root()
        tree.updated_at = datetime.now(timezone.utc)
        tree.last_root_update = datetime.now(timezone.utc)
        
        self.db.commit()
        
        logger.info(f"Added leaf to tree {tree_id}")
        return True, "Leaf added successfully"
    
    def generate_proof(
        self,
        tree_id: str,
        leaf_index: int
    ) -> Optional[MerkleProof]:
        """
        Generate Merkle proof for leaf
        
        Args:
            tree_id: Tree ID
            leaf_index: Leaf index
        
        Returns:
            Created MerkleProof or None
        """
        tree = self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.id == tree_id
        ).first()
        
        if not tree:
            logger.error(f"Tree {tree_id} not found")
            return None
        
        # Get all leaves
        leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == tree_id
        ).order_by(MerkleLeaf.leaf_index).all()
        
        if leaf_index >= len(leaves):
            logger.error(f"Leaf index {leaf_index} out of range")
            return None
        
        # Build tree
        leaf_hashes = [leaf.leaf_hash for leaf in leaves]
        merkle_tree = MerkleTree(leaf_hashes)
        
        # Get proof
        proof_path, proof_indices = merkle_tree.get_proof(leaf_index)
        
        # Create proof record
        proof = MerkleProof(
            id=str(uuid.uuid4()),
            tree_id=tree_id,
            leaf_id=leaves[leaf_index].id,
            proof_path=proof_path,
            proof_indices=proof_indices,
            merkle_root=tree.merkle_root,
            is_valid=True
        )
        
        self.db.add(proof)
        self.db.commit()
        
        logger.info(f"Generated proof for leaf {leaf_index} in tree {tree_id}")
        return proof
    
    def verify_proof(
        self,
        proof_id: str
    ) -> Tuple[bool, str]:
        """
        Verify Merkle proof
        
        Args:
            proof_id: Proof ID
        
        Returns:
            Tuple of (is_valid, message)
        """
        proof = self.db.query(MerkleProof).filter(
            MerkleProof.id == proof_id
        ).first()
        
        if not proof:
            return False, "Proof not found"
        
        # Get leaf
        leaf = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.id == proof.leaf_id
        ).first()
        
        if not leaf:
            return False, "Leaf not found"
        
        # Get tree
        tree = self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.id == proof.tree_id
        ).first()
        
        if not tree:
            return False, "Tree not found"
        
        # Build tree
        leaves = self.db.query(MerkleLeaf).filter(
            MerkleLeaf.tree_id == tree.id
        ).order_by(MerkleLeaf.leaf_index).all()
        
        leaf_hashes = [l.leaf_hash for l in leaves]
        merkle_tree = MerkleTree(leaf_hashes)
        
        # Verify proof
        is_valid = merkle_tree.verify_proof(
            leaf.leaf_hash,
            proof.proof_path,
            proof.proof_indices
        )
        
        # Update proof
        proof.is_valid = is_valid
        proof.verified_at = datetime.now(timezone.utc)
        self.db.commit()
        
        if is_valid:
            return True, "Proof verified successfully"
        else:
            return False, "Proof verification failed"
    
    def get_tree(self, tree_id: str) -> Optional[MerkleTreeModel]:
        """Get tree by ID"""
        return self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.id == tree_id
        ).first()
    
    def get_tree_by_name(self, tree_name: str) -> Optional[MerkleTreeModel]:
        """Get tree by name"""
        return self.db.query(MerkleTreeModel).filter(
            MerkleTreeModel.tree_name == tree_name
        ).first()
```

#### Step 4: Add API Endpoints

**File:** `archiveorigin_backend_api/app/main.py`

```python
from merkle_service import MerkleService

@app.post(
    "/merkle/tree",
    summary="Create Merkle tree",
    tags=["Merkle"],
    response_model=dict
)
async def create_merkle_tree(
    request: CreateMerkleTreeRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Create new Merkle tree"""
    if not is_admin(auth_header):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    service = MerkleService(db)
    tree = service.create_tree(
        tree_name=request.tree_name,
        tree_type=request.tree_type,
        initial_leaves=request.initial_leaves
    )
    
    return {
        "tree_id": tree.id,
        "tree_name": tree.tree_name,
        "merkle_root": tree.merkle_root,
        "leaf_count": tree.leaf_count
    }


@app.post(
    "/merkle/tree/{tree_id}/leaf",
    summary="Add leaf to tree",
    tags=["Merkle"],
    response_model=dict
)
async def add_merkle_leaf(
    tree_id: str,
    request: AddMerkleLeafRequest,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Add leaf to Merkle tree"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = MerkleService(db)
    success, msg = service.add_leaf(
        tree_id=tree_id,
        content_type=request.content_type,
        content_id=request.content_id,
        content_hash=request.content_hash
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    tree = service.get_tree(tree_id)
    return {
        "tree_id": tree.id,
        "merkle_root": tree.merkle_root,
        "leaf_count": tree.leaf_count
    }


@app.post(
    "/merkle/proof/{tree_id}/{leaf_index}",
    summary="Generate Merkle proof",
    tags=["Merkle"],
    response_model=dict
)
async def generate_merkle_proof(
    tree_id: str,
    leaf_index: int,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Generate Merkle proof for leaf"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = MerkleService(db)
    proof = service.generate_proof(tree_id, leaf_index)
    
    if not proof:
        raise HTTPException(status_code=404, detail="Proof generation failed")
    
    return {
        "proof_id": proof.id,
        "tree_id": proof.tree_id,
        "leaf_index": leaf_index,
        "merkle_root": proof.merkle_root,
        "proof_path": proof.proof_path
    }


@app.post(
    "/merkle/proof/{proof_id}/verify",
    summary="Verify Merkle proof",
    tags=["Merkle"],
    response_model=dict
)
async def verify_merkle_proof(
    proof_id: str,
    db: Session = Depends(get_db),
    auth_header: str = Header(None)
):
    """Verify Merkle proof"""
    device_token = authenticate_request(auth_header, db)
    if not device_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    service = MerkleService(db)
    is_valid, msg = service.verify_proof(proof_id)
    
    return {
        "proof_id": proof_id,
        "is_valid": is_valid,
        "message": msg
    }
```

#### Step 5: Add Schemas

**File:** `archiveorigin_backend_api/app/schemas.py`

```python
class CreateMerkleTreeRequest(BaseModel):
    tree_name: str = Field(..., description="Name of tree")
    tree_type: str = Field(..., description="Type of tree")
    initial_leaves: List[Dict[str, str]] = Field(..., description="Initial leaves")

class AddMerkleLeafRequest(BaseModel):
    content_type: str = Field(..., description="Content type")
    content_id: str = Field(..., description="Content ID")
    content_hash: str = Field(..., description="Content hash")
```

---

## Testing

**File:** `archiveorigin_backend_api/tests/test_merkle_tree.py`

```python
import pytest
from merkle_tree import MerkleTree

def test_merkle_tree_creation():
    """Test Merkle tree creation"""
    leaves = ["hash1", "hash2", "hash3", "hash4"]
    tree = MerkleTree(leaves)
    
    assert tree.get_leaf_count() == 4
    assert tree.get_root() is not None

def test_merkle_proof_generation():
    """Test proof generation"""
    leaves = ["hash1", "hash2", "hash3", "hash4"]
    tree = MerkleTree(leaves)
    
    proof_path, proof_indices = tree.get_proof(0)
    assert len(proof_path) > 0

def test_merkle_proof_verification():
    """Test proof verification"""
    leaves = ["hash1", "hash2", "hash3", "hash4"]
    tree = MerkleTree(leaves)
    
    proof_path, proof_indices = tree.get_proof(0)
    is_valid = tree.verify_proof(leaves[0], proof_path, proof_indices)
    
    assert is_valid is True
```

---

## Success Criteria

- ✅ Merkle tree models created
- ✅ Merkle tree implementation with proof generation
- ✅ Proof verification logic
- ✅ Merkle service with full lifecycle
- ✅ API endpoints for tree and proof operations
- ✅ Proof integrity verification
- ✅ Unit tests passing (>85% coverage)
- ✅ Database migrations created

---

## Files to Create/Modify

1. **MODIFY:** `archiveorigin_backend_api/app/models.py` - Add Merkle models
2. **NEW:** `archiveorigin_backend_api/app/merkle_tree.py` - Merkle tree implementation
3. **NEW:** `archiveorigin_backend_api/app/merkle_service.py` - Service layer
4. **MODIFY:** `archiveorigin_backend_api/app/main.py` - Add endpoints
5. **MODIFY:** `archiveorigin_backend_api/app/schemas.py` - Add schemas
6. **NEW:** `archiveorigin_backend_api/tests/test_merkle_tree.py` - Tests

---

## Dependencies

- `hashlib` - Hashing (built-in)
- `sqlalchemy` - ORM (already installed)

---

## Resources

- [Merkle Trees](https://en.wikipedia.org/wiki/Merkle_tree)
- [Merkle Proofs](https://en.wikipedia.org/wiki/Merkle_tree#Merkle_proof)
- [Cryptographic Hash Functions](https://en.wikipedia.org/wiki/Cryptographic_hash_function)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
