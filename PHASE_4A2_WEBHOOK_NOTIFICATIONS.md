# Phase 4A.2: Webhook Notifications - Task 4.2

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 24, 2026  
**Depends On:** Phase 4A.1 (Complete)

---

## Overview

Implement webhook notifications to allow external systems to subscribe to events. This enables real-time notifications for important system events like device enrollment, proof locking, and errors.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Analytics Service** - Event tracking (from Phase 4A.1)

### What's Missing
- Webhook subscription management
- Webhook event delivery system
- Webhook retry logic
- Webhook signature verification
- Webhook management endpoints
- Event filtering and routing

---

## Task 4.2: Implement Webhook Notifications

### Objectives
1. Create webhook data models
2. Implement webhook subscription management
3. Build webhook event delivery system
4. Implement retry logic and error handling
5. Create webhook management endpoints

### Implementation Steps

#### Step 1: Webhook Data Models

**File:** `archiveorigin_backend_api/models/webhooks.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class WebhookSubscription(Base):
    """Webhook subscription"""
    __tablename__ = "webhook_subscriptions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    events = Column(JSON, nullable=False)  # List of event types to subscribe to
    secret = Column(String(255), nullable=False)  # For HMAC signature
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_active', 'active'),
    )

class WebhookEvent(Base):
    """Webhook event delivery"""
    __tablename__ = "webhook_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String(36), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), default='pending')  # pending, delivered, failed
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    next_retry = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_subscription_id_status', 'subscription_id', 'status'),
        Index('idx_status_next_retry', 'status', 'next_retry'),
    )

class WebhookLog(Base):
    """Webhook delivery log"""
    __tablename__ = "webhook_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_event_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), nullable=False)
    request_body = Column(JSON, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(String(1000), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_webhook_event_id', 'webhook_event_id'),
        Index('idx_subscription_id', 'subscription_id'),
    )
```

#### Step 2: Webhook Service

**File:** `archiveorigin_backend_api/services/webhook_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.webhooks import WebhookSubscription, WebhookEvent, WebhookLog
import httpx
import hmac
import hashlib
import json
import asyncio
from typing import List, Dict

class WebhookService:
    """Service for webhook operations"""
    
    @staticmethod
    def create_subscription(
        db: Session,
        user_id: str,
        url: str,
        events: List[str],
        secret: str = None
    ) -> WebhookSubscription:
        """Create a webhook subscription"""
        if not secret:
            secret = hashlib.sha256(
                f"{user_id}{url}{datetime.utcnow()}".encode()
            ).hexdigest()
        
        subscription = WebhookSubscription(
            user_id=user_id,
            url=url,
            events=events,
            secret=secret
        )
        db.add(subscription)
        db.commit()
        return subscription
    
    @staticmethod
    def get_subscriptions(db: Session, user_id: str) -> List[WebhookSubscription]:
        """Get all subscriptions for a user"""
        return db.query(WebhookSubscription).filter(
            WebhookSubscription.user_id == user_id
        ).all()
    
    @staticmethod
    def delete_subscription(db: Session, subscription_id: str) -> bool:
        """Delete a subscription"""
        subscription = db.query(WebhookSubscription).filter(
            WebhookSubscription.id == subscription_id
        ).first()
        
        if subscription:
            db.delete(subscription)
            db.commit()
            return True
        return False
    
    @staticmethod
    def trigger_event(
        db: Session,
        event_type: str,
        payload: Dict
    ):
        """Trigger a webhook event"""
        # Find all subscriptions for this event type
        subscriptions = db.query(WebhookSubscription).filter(
            WebhookSubscription.active == True
        ).all()
        
        for subscription in subscriptions:
            if event_type in subscription.events:
                # Create webhook event
                webhook_event = WebhookEvent(
                    subscription_id=subscription.id,
                    event_type=event_type,
                    payload=payload
                )
                db.add(webhook_event)
        
        db.commit()
    
    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    async def deliver_webhook(
        db: Session,
        webhook_event_id: str
    ):
        """Deliver a webhook event"""
        webhook_event = db.query(WebhookEvent).filter(
            WebhookEvent.id == webhook_event_id
        ).first()
        
        if not webhook_event:
            return
        
        subscription = db.query(WebhookSubscription).filter(
            WebhookSubscription.id == webhook_event.subscription_id
        ).first()
        
        if not subscription:
            return
        
        # Prepare payload
        payload = {
            'id': webhook_event.id,
            'event': webhook_event.event_type,
            'timestamp': webhook_event.created_at.isoformat(),
            'data': webhook_event.payload
        }
        
        payload_json = json.dumps(payload)
        signature = WebhookService.generate_signature(
            payload_json,
            subscription.secret
        )
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Webhook-ID': webhook_event.id
        }
        
        try:
            start_time = datetime.utcnow()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    subscription.url,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log delivery
            log = WebhookLog(
                webhook_event_id=webhook_event.id,
                subscription_id=subscription.id,
                request_body=payload,
                response_status=response.status_code,
                response_body=response.text[:1000],
                duration_ms=duration_ms,
                success=response.status_code < 400
            )
            db.add(log)
            
            if response.status_code < 400:
                webhook_event.status = 'delivered'
                webhook_event.delivered_at = datetime.utcnow()
                subscription.last_triggered = datetime.utcnow()
                subscription.failure_count = 0
            else:
                webhook_event.attempts += 1
                if webhook_event.attempts < webhook_event.max_attempts:
                    webhook_event.status = 'pending'
                    webhook_event.next_retry = datetime.utcnow() + timedelta(
                        minutes=5 * webhook_event.attempts
                    )
                else:
                    webhook_event.status = 'failed'
                    webhook_event.error_message = f"Max attempts reached: {response.status_code}"
                    subscription.failure_count += 1
                    if subscription.failure_count >= 10:
                        subscription.active = False
            
            db.commit()
        
        except Exception as e:
            webhook_event.attempts += 1
            webhook_event.error_message = str(e)
            
            if webhook_event.attempts < webhook_event.max_attempts:
                webhook_event.status = 'pending'
                webhook_event.next_retry = datetime.utcnow() + timedelta(
                    minutes=5 * webhook_event.attempts
                )
            else:
                webhook_event.status = 'failed'
                subscription.failure_count += 1
                if subscription.failure_count >= 10:
                    subscription.active = False
            
            db.commit()
    
    @staticmethod
    def get_pending_webhooks(db: Session) -> List[WebhookEvent]:
        """Get pending webhook events"""
        return db.query(WebhookEvent).filter(
            WebhookEvent.status == 'pending',
            (WebhookEvent.next_retry.is_(None)) | 
            (WebhookEvent.next_retry <= datetime.utcnow())
        ).all()
```

#### Step 3: Webhook Endpoints

**File:** `archiveorigin_backend_api/routes/webhooks.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from services.webhook_service import WebhookService
from database import get_db
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class WebhookSubscriptionCreate(BaseModel):
    url: str
    events: List[str]

class WebhookSubscriptionResponse(BaseModel):
    id: str
    url: str
    events: List[str]
    active: bool
    created_at: str

@router.post("/subscriptions")
async def create_webhook_subscription(
    subscription: WebhookSubscriptionCreate,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Create a webhook subscription"""
    try:
        new_subscription = WebhookService.create_subscription(
            db,
            user_id,
            subscription.url,
            subscription.events
        )
        return {
            'id': new_subscription.id,
            'url': new_subscription.url,
            'events': new_subscription.events,
            'secret': new_subscription.secret,
            'active': new_subscription.active
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscriptions")
async def list_webhook_subscriptions(
    user_id: str,
    db: Session = Depends(get_db)
):
    """List all webhook subscriptions for a user"""
    try:
        subscriptions = WebhookService.get_subscriptions(db, user_id)
        return [
            {
                'id': s.id,
                'url': s.url,
                'events': s.events,
                'active': s.active,
                'created_at': s.created_at.isoformat()
            }
            for s in subscriptions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/subscriptions/{subscription_id}")
async def delete_webhook_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """Delete a webhook subscription"""
    try:
        if WebhookService.delete_subscription(db, subscription_id):
            return {'status': 'success'}
        raise HTTPException(status_code=404, detail="Subscription not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Step 4: Webhook Background Task

**File:** `archiveorigin_backend_api/tasks/webhook_delivery.py`

```python
import asyncio
from sqlalchemy.orm import Session
from services.webhook_service import WebhookService
from database import SessionLocal

async def process_pending_webhooks():
    """Process pending webhook deliveries"""
    db = SessionLocal()
    try:
        while True:
            pending = WebhookService.get_pending_webhooks(db)
            for webhook_event in pending:
                await WebhookService.deliver_webhook(db, webhook_event.id)
            
            await asyncio.sleep(30)  # Check every 30 seconds
    finally:
        db.close()
```

---

## Success Criteria

- ✅ Webhook subscription management working
- ✅ Event delivery system functional
- ✅ Retry logic implemented
- ✅ Signature verification working
- ✅ Webhook endpoints available
- ✅ Background task processing webhooks
- ✅ Error handling and logging
- ✅ Subscription management endpoints
- ✅ Tests passing
- ✅ Documentation complete

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/models/webhooks.py` - Webhook models
2. **NEW:** `archiveorigin_backend_api/services/webhook_service.py` - Webhook service
3. **NEW:** `archiveorigin_backend_api/routes/webhooks.py` - Webhook endpoints
4. **NEW:** `archiveorigin_backend_api/tasks/webhook_delivery.py` - Background task
5. **MODIFY:** `archiveorigin_backend_api/main.py` - Add webhook task

---

## Dependencies

- `httpx` - Async HTTP client
- `sqlalchemy` - ORM

---

## Resources

- [Webhook Best Practices](https://www.svix.com/resources/guides/webhook-best-practices/)
- [HMAC Signatures](https://en.wikipedia.org/wiki/HMAC)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
