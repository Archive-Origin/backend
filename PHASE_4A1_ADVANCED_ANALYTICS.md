# Phase 4A.1: Advanced Analytics - Task 4.1

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 17, 2026  
**Depends On:** Phase 3 (Complete)

---

## Overview

Implement advanced analytics to track system usage, performance metrics, and user behavior. This provides insights into system health, usage patterns, and optimization opportunities.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Prometheus** - Metrics collection (from Phase 3B.2)
- **Logging Framework** - Event logging

### What's Missing
- Analytics data models
- Analytics collection service
- Analytics aggregation procedures
- Analytics reporting endpoints
- Dashboard data endpoints
- Time-series data storage

---

## Task 4.1: Implement Advanced Analytics

### Objectives
1. Create analytics data models
2. Implement analytics collection service
3. Create analytics aggregation procedures
4. Build analytics reporting endpoints
5. Implement dashboard data endpoints

### Implementation Steps

#### Step 1: Analytics Data Models

**File:** `archiveorigin_backend_api/models/analytics.py`

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AnalyticsEvent(Base):
    """Analytics event tracking"""
    __tablename__ = "analytics_events"
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)  # enrollment, proof_lock, query, etc.
    user_id = Column(String(255), nullable=True)
    device_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer, nullable=True)  # Request duration
    status_code = Column(Integer, nullable=True)
    error_message = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional event data
    
    __table_args__ = (
        Index('idx_event_type_timestamp', 'event_type', 'timestamp'),
        Index('idx_user_id_timestamp', 'user_id', 'timestamp'),
        Index('idx_device_id_timestamp', 'device_id', 'timestamp'),
    )

class AnalyticsMetric(Base):
    """Aggregated metrics"""
    __tablename__ = "analytics_metrics"
    
    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    value = Column(Float, nullable=False)
    labels = Column(JSON, nullable=True)  # Metric labels/tags
    
    __table_args__ = (
        Index('idx_metric_name_timestamp', 'metric_name', 'timestamp'),
    )

class AnalyticsAggregation(Base):
    """Pre-aggregated analytics data"""
    __tablename__ = "analytics_aggregations"
    
    id = Column(Integer, primary_key=True)
    aggregation_type = Column(String(50), nullable=False)  # hourly, daily, weekly
    event_type = Column(String(50), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    count = Column(Integer, default=0)
    avg_duration_ms = Column(Float, nullable=True)
    min_duration_ms = Column(Integer, nullable=True)
    max_duration_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, default=0)
    success_rate = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_aggregation_type_period', 'aggregation_type', 'period_start'),
    )

class UserAnalytics(Base):
    """Per-user analytics"""
    __tablename__ = "user_analytics"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True)
    total_enrollments = Column(Integer, default=0)
    total_proof_locks = Column(Integer, default=0)
    total_queries = Column(Integer, default=0)
    last_activity = Column(DateTime, nullable=True)
    total_errors = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )
```

#### Step 2: Analytics Service

**File:** `archiveorigin_backend_api/services/analytics_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.analytics import (
    AnalyticsEvent, AnalyticsMetric, AnalyticsAggregation, UserAnalytics
)
import json

class AnalyticsService:
    """Service for analytics operations"""
    
    @staticmethod
    def record_event(
        db: Session,
        event_type: str,
        user_id: str = None,
        device_id: str = None,
        duration_ms: int = None,
        status_code: int = None,
        error_message: str = None,
        metadata: dict = None
    ):
        """Record an analytics event"""
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            device_id=device_id,
            duration_ms=duration_ms,
            status_code=status_code,
            error_message=error_message,
            metadata=metadata or {}
        )
        db.add(event)
        db.commit()
        return event
    
    @staticmethod
    def record_metric(
        db: Session,
        metric_name: str,
        metric_type: str,
        value: float,
        labels: dict = None
    ):
        """Record a metric"""
        metric = AnalyticsMetric(
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            labels=labels or {}
        )
        db.add(metric)
        db.commit()
        return metric
    
    @staticmethod
    def aggregate_events(db: Session, hours: int = 1):
        """Aggregate events for the last N hours"""
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(hours=hours)
        
        # Get event counts by type
        event_stats = db.query(
            AnalyticsEvent.event_type,
            func.count(AnalyticsEvent.id).label('count'),
            func.avg(AnalyticsEvent.duration_ms).label('avg_duration'),
            func.min(AnalyticsEvent.duration_ms).label('min_duration'),
            func.max(AnalyticsEvent.duration_ms).label('max_duration'),
            func.sum(
                func.case(
                    (AnalyticsEvent.status_code >= 400, 1),
                    else_=0
                )
            ).label('error_count')
        ).filter(
            AnalyticsEvent.timestamp >= period_start,
            AnalyticsEvent.timestamp <= period_end
        ).group_by(AnalyticsEvent.event_type).all()
        
        # Store aggregations
        for stat in event_stats:
            total = stat.count
            errors = stat.error_count or 0
            success_rate = ((total - errors) / total * 100) if total > 0 else 0
            
            aggregation = AnalyticsAggregation(
                aggregation_type='hourly',
                event_type=stat.event_type,
                period_start=period_start,
                period_end=period_end,
                count=total,
                avg_duration_ms=stat.avg_duration,
                min_duration_ms=stat.min_duration,
                max_duration_ms=stat.max_duration,
                error_count=errors,
                success_rate=success_rate
            )
            db.add(aggregation)
        
        db.commit()
    
    @staticmethod
    def get_event_summary(db: Session, hours: int = 24) -> dict:
        """Get event summary for the last N hours"""
        period_start = datetime.utcnow() - timedelta(hours=hours)
        
        events = db.query(
            AnalyticsEvent.event_type,
            func.count(AnalyticsEvent.id).label('count'),
            func.avg(AnalyticsEvent.duration_ms).label('avg_duration')
        ).filter(
            AnalyticsEvent.timestamp >= period_start
        ).group_by(AnalyticsEvent.event_type).all()
        
        return {
            event.event_type: {
                'count': event.count,
                'avg_duration_ms': event.avg_duration
            }
            for event in events
        }
    
    @staticmethod
    def get_user_analytics(db: Session, user_id: str) -> dict:
        """Get analytics for a specific user"""
        user_analytics = db.query(UserAnalytics).filter(
            UserAnalytics.user_id == user_id
        ).first()
        
        if not user_analytics:
            return None
        
        return {
            'user_id': user_analytics.user_id,
            'total_enrollments': user_analytics.total_enrollments,
            'total_proof_locks': user_analytics.total_proof_locks,
            'total_queries': user_analytics.total_queries,
            'last_activity': user_analytics.last_activity,
            'total_errors': user_analytics.total_errors,
            'avg_response_time_ms': user_analytics.avg_response_time_ms
        }
    
    @staticmethod
    def update_user_analytics(db: Session, user_id: str, event_type: str):
        """Update user analytics"""
        user_analytics = db.query(UserAnalytics).filter(
            UserAnalytics.user_id == user_id
        ).first()
        
        if not user_analytics:
            user_analytics = UserAnalytics(user_id=user_id)
            db.add(user_analytics)
        
        if event_type == 'enrollment':
            user_analytics.total_enrollments += 1
        elif event_type == 'proof_lock':
            user_analytics.total_proof_locks += 1
        elif event_type == 'query':
            user_analytics.total_queries += 1
        
        user_analytics.last_activity = datetime.utcnow()
        db.commit()
```

#### Step 3: Analytics Endpoints

**File:** `archiveorigin_backend_api/routes/analytics.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from services.analytics_service import AnalyticsService
from database import get_db
from datetime import datetime, timedelta

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/summary")
async def get_analytics_summary(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get analytics summary for the last N hours"""
    try:
        summary = AnalyticsService.get_event_summary(db, hours)
        return {
            'period_hours': hours,
            'timestamp': datetime.utcnow(),
            'summary': summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}")
async def get_user_analytics(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get analytics for a specific user"""
    try:
        analytics = AnalyticsService.get_user_analytics(db, user_id)
        if not analytics:
            raise HTTPException(status_code=404, detail="User not found")
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db)
):
    """Get dashboard data"""
    try:
        # Get last 24 hours summary
        summary_24h = AnalyticsService.get_event_summary(db, 24)
        
        # Get last 7 days summary
        summary_7d = AnalyticsService.get_event_summary(db, 168)
        
        return {
            'last_24_hours': summary_24h,
            'last_7_days': summary_7d,
            'timestamp': datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/aggregate")
async def aggregate_analytics(
    hours: int = 1,
    db: Session = Depends(get_db)
):
    """Trigger analytics aggregation"""
    try:
        AnalyticsService.aggregate_events(db, hours)
        return {'status': 'success', 'message': 'Analytics aggregated'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Step 4: Analytics Middleware

**File:** `archiveorigin_backend_api/middleware/analytics_middleware.py`

```python
from fastapi import Request
from services.analytics_service import AnalyticsService
from database import SessionLocal
import time
import json

async def analytics_middleware(request: Request, call_next):
    """Middleware to track analytics"""
    start_time = time.time()
    
    # Get user ID from token if available
    user_id = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        # Extract user ID from token (simplified)
        user_id = auth_header.split(' ')[1][:20]
    
    # Call the endpoint
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Record analytics
    db = SessionLocal()
    try:
        event_type = request.url.path.split('/')[1] or 'unknown'
        AnalyticsService.record_event(
            db,
            event_type=event_type,
            user_id=user_id,
            duration_ms=duration_ms,
            status_code=response.status_code,
            metadata={
                'path': request.url.path,
                'method': request.method
            }
        )
        
        if user_id:
            AnalyticsService.update_user_analytics(db, user_id, event_type)
    finally:
        db.close()
    
    return response
```

---

## Success Criteria

- ✅ Analytics data models created
- ✅ Analytics collection service implemented
- ✅ Analytics aggregation procedures working
- ✅ Analytics reporting endpoints functional
- ✅ Dashboard data endpoints available
- ✅ Middleware tracking events
- ✅ User analytics tracking
- ✅ Time-series data stored
- ✅ Tests passing
- ✅ Documentation complete

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/models/analytics.py` - Analytics models
2. **NEW:** `archiveorigin_backend_api/services/analytics_service.py` - Analytics service
3. **NEW:** `archiveorigin_backend_api/routes/analytics.py` - Analytics endpoints
4. **NEW:** `archiveorigin_backend_api/middleware/analytics_middleware.py` - Analytics middleware
5. **MODIFY:** `archiveorigin_backend_api/main.py` - Add analytics middleware

---

## Dependencies

- `sqlalchemy` - ORM
- `prometheus-client` - Metrics export

---

## Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Prometheus Metrics](https://prometheus.io/docs/concepts/metric_types/)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
