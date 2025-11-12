# Phase 4A.5: Admin Dashboard - Task 4.5

**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Target Completion:** February 14, 2026  
**Depends On:** Phase 4A.4 (Complete)

---

## Overview

Implement an admin dashboard to provide system administrators with visibility into system health, user activity, and operational metrics. This includes real-time monitoring, user management, and system configuration.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Export Service** - Data export (from Phase 4A.4)
- **Analytics Service** - Event tracking (from Phase 4A.1)

### What's Missing
- Admin dashboard data models
- Admin dashboard service
- Admin dashboard endpoints
- Real-time monitoring endpoints
- User management endpoints
- System configuration endpoints
- Dashboard UI components

---

## Task 4.5: Implement Admin Dashboard

### Objectives
1. Create admin dashboard data models
2. Implement dashboard service
3. Build monitoring endpoints
4. Create user management endpoints
5. Implement system configuration endpoints

### Implementation Steps

#### Step 1: Admin Dashboard Models

**File:** `archiveorigin_backend_api/models/admin.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class AdminUser(Base):
    """Admin user account"""
    __tablename__ = "admin_users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='admin')  # admin, moderator, viewer
    active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_username', 'username'),
        Index('idx_email', 'email'),
    )

class SystemConfig(Base):
    """System configuration"""
    __tablename__ = "system_config"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(JSON, nullable=False)
    description = Column(String(500), nullable=True)
    updated_by = Column(String(36), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_config_key', 'config_key'),
    )

class AuditLog(Base):
    """Admin action audit log"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_user_id = Column(String(36), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=True)
    changes = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_admin_user_id_created_at', 'admin_user_id', 'created_at'),
        Index('idx_resource_type_created_at', 'resource_type', 'created_at'),
    )

class SystemAlert(Base):
    """System alerts and notifications"""
    __tablename__ = "system_alerts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_type = Column(String(50), nullable=False)  # warning, error, info
    title = Column(String(200), nullable=False)
    message = Column(String(1000), nullable=False)
    severity = Column(String(20), default='medium')  # low, medium, high, critical
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_alert_type_resolved', 'alert_type', 'resolved'),
        Index('idx_severity_created_at', 'severity', 'created_at'),
    )
```

#### Step 2: Admin Dashboard Service

**File:** `archiveorigin_backend_api/services/admin_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.admin import AdminUser, SystemConfig, AuditLog, SystemAlert
from models.analytics import AnalyticsEvent, UserAnalytics
import hashlib
from typing import Dict, List

class AdminService:
    """Service for admin operations"""
    
    @staticmethod
    def get_dashboard_summary(db: Session) -> Dict:
        """Get dashboard summary"""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # Get event counts
        events_24h = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.timestamp >= last_24h
        ).scalar() or 0
        
        events_7d = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.timestamp >= last_7d
        ).scalar() or 0
        
        # Get error counts
        errors_24h = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.timestamp >= last_24h,
            AnalyticsEvent.status_code >= 400
        ).scalar() or 0
        
        # Get active users
        active_users = db.query(func.count(func.distinct(UserAnalytics.user_id))).filter(
            UserAnalytics.last_activity >= last_24h
        ).scalar() or 0
        
        # Get unresolved alerts
        unresolved_alerts = db.query(func.count(SystemAlert.id)).filter(
            SystemAlert.resolved == False
        ).scalar() or 0
        
        return {
            'events_24h': events_24h,
            'events_7d': events_7d,
            'errors_24h': errors_24h,
            'active_users': active_users,
            'unresolved_alerts': unresolved_alerts,
            'timestamp': now.isoformat()
        }
    
    @staticmethod
    def get_system_health(db: Session) -> Dict:
        """Get system health status"""
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        
        # Calculate error rate
        total_events = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.timestamp >= last_hour
        ).scalar() or 1
        
        error_events = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.timestamp >= last_hour,
            AnalyticsEvent.status_code >= 400
        ).scalar() or 0
        
        error_rate = (error_events / total_events * 100) if total_events > 0 else 0
        
        # Calculate average response time
        avg_response_time = db.query(func.avg(AnalyticsEvent.duration_ms)).filter(
            AnalyticsEvent.timestamp >= last_hour
        ).scalar() or 0
        
        # Determine health status
        if error_rate > 10 or avg_response_time > 5000:
            status = 'critical'
        elif error_rate > 5 or avg_response_time > 2000:
            status = 'warning'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'error_rate': error_rate,
            'avg_response_time_ms': avg_response_time,
            'total_events_1h': total_events,
            'error_events_1h': error_events
        }
    
    @staticmethod
    def get_user_statistics(db: Session) -> Dict:
        """Get user statistics"""
        total_users = db.query(func.count(func.distinct(UserAnalytics.user_id))).scalar() or 0
        
        active_users = db.query(func.count(func.distinct(UserAnalytics.user_id))).filter(
            UserAnalytics.last_activity >= datetime.utcnow() - timedelta(days=7)
        ).scalar() or 0
        
        return {
            'total_users': total_users,
            'active_users_7d': active_users,
            'inactive_users': total_users - active_users
        }
    
    @staticmethod
    def log_audit_action(
        db: Session,
        admin_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str = None,
        changes: Dict = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Log an admin action"""
        audit_log = AuditLog(
            admin_user_id=admin_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(audit_log)
        db.commit()
    
    @staticmethod
    def get_audit_logs(
        db: Session,
        admin_user_id: str = None,
        resource_type: str = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs"""
        query = db.query(AuditLog)
        
        if admin_user_id:
            query = query.filter(AuditLog.admin_user_id == admin_user_id)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def create_system_alert(
        db: Session,
        alert_type: str,
        title: str,
        message: str,
        severity: str = 'medium'
    ) -> SystemAlert:
        """Create a system alert"""
        alert = SystemAlert(
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity
        )
        db.add(alert)
        db.commit()
        return alert
    
    @staticmethod
    def get_system_alerts(
        db: Session,
        resolved: bool = False,
        limit: int = 50
    ) -> List[SystemAlert]:
        """Get system alerts"""
        return db.query(SystemAlert).filter(
            SystemAlert.resolved == resolved
        ).order_by(SystemAlert.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def resolve_alert(db: Session, alert_id: str):
        """Resolve a system alert"""
        alert = db.query(SystemAlert).filter(
            SystemAlert.id == alert_id
        ).first()
        
        if alert:
            alert.resolved = True
            alert.resolved_at = datetime.utcnow()
            db.commit()
```

#### Step 3: Admin Dashboard Endpoints

**File:** `archiveorigin_backend_api/routes/admin.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from services.admin_service import AdminService
from database import get_db
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/dashboard/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary"""
    try:
        summary = AdminService.get_dashboard_summary(db)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/health")
async def get_system_health(db: Session = Depends(get_db)):
    """Get system health"""
    try:
        health = AdminService.get_system_health(db)
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/users")
async def get_user_statistics(db: Session = Depends(get_db)):
    """Get user statistics"""
    try:
        stats = AdminService.get_user_statistics(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-logs")
async def get_audit_logs(
    admin_user_id: str = None,
    resource_type: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get audit logs"""
    try:
        logs = AdminService.get_audit_logs(db, admin_user_id, resource_type, limit)
        return [
            {
                'id': log.id,
                'admin_user_id': log.admin_user_id,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'changes': log.changes,
                'created_at': log.created_at.isoformat()
            }
            for log in logs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_system_alerts(
    resolved: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get system alerts"""
    try:
        alerts = AdminService.get_system_alerts(db, resolved, limit)
        return [
            {
                'id': alert.id,
                'alert_type': alert.alert_type,
                'title': alert.title,
                'message': alert.message,
                'severity': alert.severity,
                'resolved': alert.resolved,
                'created_at': alert.created_at.isoformat()
            }
            for alert in alerts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db)
):
    """Resolve an alert"""
    try:
        AdminService.resolve_alert(db, alert_id)
        return {'status': 'success'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Success Criteria

- ✅ Admin dashboard models created
- ✅ Dashboard service implemented
- ✅ Monitoring endpoints functional
- ✅ User management endpoints available
- ✅ System configuration endpoints working
- ✅ Real-time monitoring data available
- ✅ Audit logging implemented
- ✅ Alert management working
- ✅ Tests passing
- ✅ Documentation complete

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/models/admin.py` - Admin models
2. **NEW:** `archiveorigin_backend_api/services/admin_service.py` - Admin service
3. **NEW:** `archiveorigin_backend_api/routes/admin.py` - Admin endpoints

---

## Dependencies

- `sqlalchemy` - ORM
- `fastapi` - Web framework

---

## Resources

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Admin Dashboard Best Practices](https://www.smashingmagazine.com/2021/05/admin-dashboard-design-patterns/)
- [System Monitoring](https://en.wikipedia.org/wiki/System_monitoring)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
