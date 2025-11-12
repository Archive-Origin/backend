# Phase 4A.3: Batch Operations - Task 4.3

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 31, 2026  
**Depends On:** Phase 4A.2 (Complete)

---

## Overview

Implement batch operations to allow processing multiple requests efficiently. This enables bulk device enrollment, bulk proof locking, and bulk queries with optimized database operations.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Webhook Service** - Event notifications (from Phase 4A.2)

### What's Missing
- Batch operation models
- Batch processing service
- Batch job tracking
- Batch result aggregation
- Batch operation endpoints
- Async batch processing

---

## Task 4.3: Implement Batch Operations

### Objectives
1. Create batch operation data models
2. Implement batch processing service
3. Build batch job tracking
4. Create batch operation endpoints
5. Implement async batch processing

### Implementation Steps

#### Step 1: Batch Operation Models

**File:** `archiveorigin_backend_api/models/batch_operations.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class BatchJob(Base):
    """Batch job tracking"""
    __tablename__ = "batch_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)  # enrollment, proof_lock, query
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    success_items = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_user_id_status', 'user_id', 'status'),
        Index('idx_status', 'status'),
    )

class BatchItem(Base):
    """Individual item in a batch job"""
    __tablename__ = "batch_items"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_job_id = Column(String(36), nullable=False)
    item_index = Column(Integer, nullable=False)
    status = Column(String(20), default='pending')  # pending, processing, success, failed
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_batch_job_id_status', 'batch_job_id', 'status'),
    )

class BatchResult(Base):
    """Batch operation result"""
    __tablename__ = "batch_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_job_id = Column(String(36), nullable=False, unique=True)
    total_time_ms = Column(Integer, nullable=True)
    avg_item_time_ms = Column(Float, nullable=True)
    success_rate = Column(Float, nullable=True)
    result_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_batch_job_id', 'batch_job_id'),
    )
```

#### Step 2: Batch Processing Service

**File:** `archiveorigin_backend_api/services/batch_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.batch_operations import BatchJob, BatchItem, BatchResult
from typing import List, Dict, Callable
import asyncio
from concurrent.futures import ThreadPoolExecutor

class BatchService:
    """Service for batch operations"""
    
    @staticmethod
    def create_batch_job(
        db: Session,
        user_id: str,
        job_type: str,
        items: List[Dict]
    ) -> BatchJob:
        """Create a batch job"""
        batch_job = BatchJob(
            user_id=user_id,
            job_type=job_type,
            total_items=len(items)
        )
        db.add(batch_job)
        db.flush()
        
        # Create batch items
        for index, item in enumerate(items):
            batch_item = BatchItem(
                batch_job_id=batch_job.id,
                item_index=index,
                input_data=item
            )
            db.add(batch_item)
        
        db.commit()
        return batch_job
    
    @staticmethod
    def get_batch_job(db: Session, batch_job_id: str) -> BatchJob:
        """Get a batch job"""
        return db.query(BatchJob).filter(
            BatchJob.id == batch_job_id
        ).first()
    
    @staticmethod
    def get_batch_items(db: Session, batch_job_id: str) -> List[BatchItem]:
        """Get all items in a batch job"""
        return db.query(BatchItem).filter(
            BatchItem.batch_job_id == batch_job_id
        ).all()
    
    @staticmethod
    async def process_batch_job(
        db: Session,
        batch_job_id: str,
        processor_func: Callable
    ):
        """Process a batch job"""
        batch_job = BatchService.get_batch_job(db, batch_job_id)
        if not batch_job:
            return
        
        batch_job.status = 'processing'
        batch_job.started_at = datetime.utcnow()
        db.commit()
        
        items = BatchService.get_batch_items(db, batch_job_id)
        start_time = datetime.utcnow()
        
        try:
            for item in items:
                try:
                    item.status = 'processing'
                    db.commit()
                    
                    # Process item
                    result = await processor_func(item.input_data)
                    
                    item.status = 'success'
                    item.output_data = result
                    batch_job.success_items += 1
                
                except Exception as e:
                    item.status = 'failed'
                    item.error_message = str(e)
                    batch_job.failed_items += 1
                
                finally:
                    item.processed_at = datetime.utcnow()
                    batch_job.processed_items += 1
                    batch_job.progress_percent = (
                        batch_job.processed_items / batch_job.total_items * 100
                    )
                    db.commit()
            
            batch_job.status = 'completed'
            batch_job.completed_at = datetime.utcnow()
            
            # Create result
            total_time_ms = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            avg_item_time_ms = total_time_ms / batch_job.total_items
            success_rate = (
                batch_job.success_items / batch_job.total_items * 100
            )
            
            result = BatchResult(
                batch_job_id=batch_job_id,
                total_time_ms=total_time_ms,
                avg_item_time_ms=avg_item_time_ms,
                success_rate=success_rate,
                result_summary={
                    'total': batch_job.total_items,
                    'success': batch_job.success_items,
                    'failed': batch_job.failed_items,
                    'success_rate': success_rate
                }
            )
            db.add(result)
        
        except Exception as e:
            batch_job.status = 'failed'
            batch_job.error_message = str(e)
        
        finally:
            db.commit()
    
    @staticmethod
    def get_batch_result(db: Session, batch_job_id: str) -> Dict:
        """Get batch job result"""
        batch_job = BatchService.get_batch_job(db, batch_job_id)
        if not batch_job:
            return None
        
        result = db.query(BatchResult).filter(
            BatchResult.batch_job_id == batch_job_id
        ).first()
        
        return {
            'batch_job_id': batch_job.id,
            'status': batch_job.status,
            'total_items': batch_job.total_items,
            'processed_items': batch_job.processed_items,
            'success_items': batch_job.success_items,
            'failed_items': batch_job.failed_items,
            'progress_percent': batch_job.progress_percent,
            'result': result.result_summary if result else None
        }
```

#### Step 3: Batch Endpoints

**File:** `archiveorigin_backend_api/routes/batch.py`

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from services.batch_service import BatchService
from database import get_db
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/batch", tags=["batch"])

class BatchJobCreate(BaseModel):
    job_type: str
    items: List[dict]

@router.post("/jobs")
async def create_batch_job(
    batch_job: BatchJobCreate,
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a batch job"""
    try:
        job = BatchService.create_batch_job(
            db,
            user_id,
            batch_job.job_type,
            batch_job.items
        )
        
        # Add background task to process batch
        # background_tasks.add_task(
        #     BatchService.process_batch_job,
        #     db,
        #     job.id,
        #     processor_func
        # )
        
        return {
            'batch_job_id': job.id,
            'status': job.status,
            'total_items': job.total_items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{batch_job_id}")
async def get_batch_job_status(
    batch_job_id: str,
    db: Session = Depends(get_db)
):
    """Get batch job status"""
    try:
        result = BatchService.get_batch_result(db, batch_job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Batch job not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{batch_job_id}/items")
async def get_batch_job_items(
    batch_job_id: str,
    db: Session = Depends(get_db)
):
    """Get batch job items"""
    try:
        items = BatchService.get_batch_items(db, batch_job_id)
        return [
            {
                'item_index': item.item_index,
                'status': item.status,
                'input_data': item.input_data,
                'output_data': item.output_data,
                'error_message': item.error_message
            }
            for item in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Success Criteria

- ✅ Batch operation models created
- ✅ Batch processing service implemented
- ✅ Batch job tracking working
- ✅ Batch result aggregation functional
- ✅ Batch operation endpoints available
- ✅ Async batch processing working
- ✅ Progress tracking implemented
- ✅ Error handling and logging
- ✅ Tests passing
- ✅ Documentation complete

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/models/batch_operations.py` - Batch models
2. **NEW:** `archiveorigin_backend_api/services/batch_service.py` - Batch service
3. **NEW:** `archiveorigin_backend_api/routes/batch.py` - Batch endpoints

---

## Dependencies

- `sqlalchemy` - ORM
- `asyncio` - Async processing

---

## Resources

- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Batch Processing Patterns](https://en.wikipedia.org/wiki/Batch_processing)
- [SQLAlchemy Bulk Operations](https://docs.sqlalchemy.org/en/14/orm/bulk_operations.html)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
