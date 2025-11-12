# Phase 3B.2: Performance Testing - Task 3.5

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 10, 2026  
**Depends On:** Phase 2 (Complete)

---

## Overview

Implement comprehensive performance testing covering response times, throughput, resource utilization, and scalability. This ensures the system meets performance requirements and can handle production loads.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Docker Compose** - Local testing environment
- **pytest Framework** - Testing infrastructure

### What's Missing
- Performance benchmarks
- Load testing procedures
- Profiling tools
- Performance monitoring
- Optimization recommendations

---

## Task 3.5: Implement Performance Testing

### Objectives
1. Establish performance baselines
2. Create load testing scenarios
3. Profile application performance
4. Identify bottlenecks
5. Provide optimization recommendations

### Implementation Steps

#### Step 1: Performance Testing Framework

**File:** `archiveorigin_backend_api/docs/PERFORMANCE_TESTING.md`

```markdown
# Performance Testing Guide

## Performance Baselines

### API Response Times
- Device enrollment: < 500ms (p95)
- Proof locking: < 300ms (p95)
- Health check: < 50ms (p95)
- Ledger query: < 1000ms (p95)

### Throughput
- Device enrollment: 100 req/s
- Proof locking: 500 req/s
- Health check: 1000 req/s
- Ledger query: 50 req/s

### Resource Utilization
- CPU: < 80% under normal load
- Memory: < 512MB per instance
- Database connections: < 50 active
- Disk I/O: < 100MB/s

## Load Testing

### Tools
- Apache JMeter
- Locust
- k6
- Gatling

### Test Scenarios

#### Scenario 1: Normal Load
- 100 concurrent users
- 10 requests per user
- Device enrollment, proof locking, queries
- Duration: 5 minutes

#### Scenario 2: Peak Load
- 500 concurrent users
- 20 requests per user
- Mixed operations
- Duration: 10 minutes

#### Scenario 3: Stress Test
- 1000+ concurrent users
- Continuous requests
- Until system breaks
- Identify breaking point

#### Scenario 4: Soak Test
- 200 concurrent users
- 8 hours duration
- Identify memory leaks
- Monitor resource degradation

### Load Testing with Locust

**File:** `archiveorigin_backend_api/tests/load_test.py`

\`\`\`python
from locust import HttpUser, task, between
import random

class ArchiveOriginUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Enroll device
        response = self.client.post(
            "/device/enroll",
            json={
                "device_id": f"device-{random.randint(1, 1000)}",
                "device_token": "test-token",
                "device_name": "Test Device",
                "os_version": "17.1"
            }
        )
        self.token = response.json()["enrollment_token"]
    
    @task(3)
    def lock_proof(self):
        self.client.post(
            "/lock-proof",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "capture_id": f"capture-{random.randint(1, 10000)}",
                "proof_data": "base64encodeddata",
                "metadata": {"timestamp": "2025-11-12T22:55:00Z"}
            }
        )
    
    @task(1)
    def health_check(self):
        self.client.get("/health")
    
    @task(2)
    def query_ledger(self):
        self.client.get(
            "/ledger/entries",
            headers={"Authorization": f"Bearer {self.token}"}
        )
\`\`\`

### Running Load Tests

\`\`\`bash
# Install Locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000

# Run with specific parameters
locust -f tests/load_test.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless
\`\`\`

## Profiling

### CPU Profiling

\`\`\`python
import cProfile
import pstats
from app.main import app

def profile_app():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run application
    # ...
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
\`\`\`

### Memory Profiling

\`\`\`python
from memory_profiler import profile

@profile
def lock_proof(proof_data):
    # Function to profile
    pass

# Run with memory profiler
# python -m memory_profiler app/services/proof_service.py
\`\`\`

### Database Query Profiling

\`\`\`python
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, params, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop(-1)
    if total_time > 0.1:  # Log slow queries
        print(f"Slow query ({total_time:.2f}s): {statement}")
\`\`\`

## Performance Monitoring

### Metrics to Monitor
- Request latency (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- CPU usage
- Memory usage
- Database connection pool
- Cache hit rate

### Prometheus Metrics

\`\`\`python
from prometheus_client import Counter, Histogram, Gauge

request_count = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint']
)

active_connections = Gauge(
    'db_active_connections',
    'Active database connections'
)
\`\`\`

## Performance Optimization

### Database Optimization
- Add indexes on frequently queried columns
- Use connection pooling
- Implement query caching
- Optimize N+1 queries
- Use batch operations

### API Optimization
- Implement response caching
- Use compression (gzip)
- Optimize JSON serialization
- Implement pagination
- Use async operations

### Infrastructure Optimization
- Horizontal scaling
- Load balancing
- CDN for static content
- Database replication
- Connection pooling

## Performance Targets

### Response Times
| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| /health | 10ms | 50ms | 100ms |
| /device/enroll | 100ms | 500ms | 1000ms |
| /lock-proof | 50ms | 300ms | 500ms |
| /ledger/entries | 200ms | 1000ms | 2000ms |

### Throughput
| Endpoint | Target |
|----------|--------|
| /health | 1000 req/s |
| /device/enroll | 100 req/s |
| /lock-proof | 500 req/s |
| /ledger/entries | 50 req/s |

### Resource Utilization
| Resource | Target |
|----------|--------|
| CPU | < 80% |
| Memory | < 512MB |
| Disk I/O | < 100MB/s |
| Network | < 1Gbps |
```

#### Step 2: Create Performance Test Suite

**File:** `archiveorigin_backend_api/tests/test_performance.py`

```python
"""Performance tests"""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestResponseTimes:
    """Response time performance tests"""
    
    def test_health_check_performance(self):
        """Test health check response time"""
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.05  # 50ms target
    
    def test_device_enrollment_performance(self):
        """Test device enrollment response time"""
        start = time.time()
        response = client.post(
            "/device/enroll",
            json={
                "device_id": "device-123",
                "device_token": "token",
                "device_name": "iPhone",
                "os_version": "17.1"
            }
        )
        duration = time.time() - start
        
        assert response.status_code in [200, 401]
        assert duration < 0.5  # 500ms target
    
    def test_proof_locking_performance(self):
        """Test proof locking response time"""
        # First enroll device
        enroll_response = client.post(
            "/device/enroll",
            json={
                "device_id": "device-123",
                "device_token": "token",
                "device_name": "iPhone",
                "os_version": "17.1"
            }
        )
        
        if enroll_response.status_code == 200:
            token = enroll_response.json()["enrollment_token"]
            
            start = time.time()
            response = client.post(
                "/lock-proof",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "capture_id": "capture-123",
                    "proof_data": "data",
                    "metadata": {}
                }
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 400]
            assert duration < 0.3  # 300ms target

class TestThroughput:
    """Throughput performance tests"""
    
    def test_health_check_throughput(self):
        """Test health check throughput"""
        start = time.time()
        count = 0
        
        while time.time() - start < 1.0:  # 1 second
            response = client.get("/health")
            if response.status_code == 200:
                count += 1
        
        # Should handle at least 100 requests per second
        assert count >= 100

class TestMemoryUsage:
    """Memory usage performance tests"""
    
    def test_no_memory_leak_on_repeated_requests(self):
        """Test for memory leaks on repeated requests"""
        import tracemalloc
        
        tracemalloc.start()
        
        # Make initial requests
        for _ in range(100):
            client.get("/health")
        
        snapshot1 = tracemalloc.take_snapshot()
        
        # Make more requests
        for _ in range(100):
            client.get("/health")
        
        snapshot2 = tracemalloc.take_snapshot()
        
        # Compare snapshots
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # Memory growth should be minimal
        total_growth = sum(stat.size_diff for stat in top_stats)
        assert total_growth < 10 * 1024 * 1024  # Less than 10MB growth

class TestDatabasePerformance:
    """Database performance tests"""
    
    def test_query_performance(self, db):
        """Test database query performance"""
        from app.models import Device
        
        start = time.time()
        devices = db.query(Device).limit(100).all()
        duration = time.time() - start
        
        # Query should complete in less than 100ms
        assert duration < 0.1
    
    def test_connection_pool_efficiency(self, db):
        """Test connection pool efficiency"""
        # Make multiple concurrent-like requests
        for _ in range(10):
            db.query(Device).first()
        
        # Connection pool should be efficient
        # (Implementation depends on pool configuration)
```

---

## Success Criteria

- ✅ Performance baselines established
- ✅ Load testing scenarios created
- ✅ Profiling tools configured
- ✅ Performance tests implemented
- ✅ Bottlenecks identified
- ✅ Optimization recommendations provided
- ✅ Monitoring configured
- ✅ All tests passing
- ✅ Documentation complete
- ✅ Performance targets met

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/docs/PERFORMANCE_TESTING.md` - Performance guide
2. **NEW:** `archiveorigin_backend_api/tests/load_test.py` - Load testing
3. **NEW:** `archiveorigin_backend_api/tests/test_performance.py` - Performance tests

---

## Dependencies

- `locust` - Load testing
- `memory-profiler` - Memory profiling
- `prometheus-client` - Metrics collection
- `pytest-benchmark` - Benchmark testing

---

## Resources

- [Locust Documentation](https://locust.io/)
- [Python Profiling](https://docs.python.org/3/library/profile.html)
- [Prometheus Metrics](https://prometheus.io/)
- [Performance Testing Best Practices](https://www.perfmatrix.com/performance-testing/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
