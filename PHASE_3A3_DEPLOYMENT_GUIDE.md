# Phase 3A.3: Deployment Guide - Task 3.3

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** January 10, 2026  
**Depends On:** Phase 2 (Complete)

---

## Overview

Create comprehensive deployment guide covering local development setup, staging deployment, production deployment, and operational procedures. This enables teams to deploy and manage the application across different environments.

---

## Current State

### Existing Components
- **Docker Compose** - Local development setup
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Git Repository** - Version control

### What's Missing
- Detailed deployment procedures
- Environment configuration guide
- Database migration procedures
- Backup and recovery procedures
- Monitoring setup
- Troubleshooting guide

---

## Task 3.3: Implement Deployment Guide

### Objectives
1. Document local development setup
2. Create staging deployment guide
3. Create production deployment guide
4. Document operational procedures
5. Provide troubleshooting guide

### Implementation Steps

#### Step 1: Local Development Setup

**File:** `archiveorigin_backend_api/docs/DEPLOYMENT.md`

```markdown
# Deployment Guide

## Local Development Setup

### Prerequisites
- Python 3.9+
- Docker and Docker Compose
- Git
- PostgreSQL client tools (optional)

### Installation Steps

#### 1. Clone Repository
\`\`\`bash
git clone https://github.com/Archive-Origin/backend.git
cd backend
\`\`\`

#### 2. Create Environment File
\`\`\`bash
cp .env.example .env
\`\`\`

**File:** `.env`
\`\`\`
# Environment
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql://archiveorigin:password@localhost:5432/archiveorigin_dev
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# DeviceCheck
DEVICECHECK_TEAM_ID=your-team-id
DEVICECHECK_KEY_ID=your-key-id
DEVICECHECK_PRIVATE_KEY=your-private-key

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
\`\`\`

#### 3. Start Docker Compose
\`\`\`bash
docker-compose up -d
\`\`\`

This starts:
- PostgreSQL database on port 5432
- FastAPI application on port 8000

#### 4. Initialize Database
\`\`\`bash
docker-compose exec api python -m alembic upgrade head
\`\`\`

#### 5. Verify Installation
\`\`\`bash
curl http://localhost:8000/health
\`\`\`

Expected response:
\`\`\`json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-11-12T22:55:00Z"
}
\`\`\`

### Development Workflow

#### Running Tests
\`\`\`bash
docker-compose exec api pytest tests/ -v --cov=app
\`\`\`

#### Running Linting
\`\`\`bash
docker-compose exec api flake8 app/
docker-compose exec api mypy app/
\`\`\`

#### Viewing Logs
\`\`\`bash
docker-compose logs -f api
docker-compose logs -f db
\`\`\`

#### Database Shell
\`\`\`bash
docker-compose exec db psql -U archiveorigin -d archiveorigin_dev
\`\`\`

#### Stopping Services
\`\`\`bash
docker-compose down
\`\`\`

---

## Staging Deployment

### Prerequisites
- AWS account (or similar cloud provider)
- Kubernetes cluster (EKS, GKE, AKS)
- kubectl configured
- Docker registry access

### Deployment Steps

#### 1. Build Docker Image
\`\`\`bash
docker build -t archiveorigin/backend:staging-v1.0.0 .
docker push archiveorigin/backend:staging-v1.0.0
\`\`\`

#### 2. Create Kubernetes Namespace
\`\`\`bash
kubectl create namespace archiveorigin-staging
\`\`\`

#### 3. Create Secrets
\`\`\`bash
kubectl create secret generic db-credentials \
  --from-literal=url=postgresql://user:password@db-host:5432/archiveorigin_staging \
  -n archiveorigin-staging

kubectl create secret generic api-secrets \
  --from-literal=secret-key=your-secret-key \
  --from-literal=devicecheck-key=your-key \
  -n archiveorigin-staging
\`\`\`

#### 4. Deploy Application
\`\`\`bash
kubectl apply -f k8s/staging/deployment.yaml -n archiveorigin-staging
kubectl apply -f k8s/staging/service.yaml -n archiveorigin-staging
kubectl apply -f k8s/staging/ingress.yaml -n archiveorigin-staging
\`\`\`

#### 5. Verify Deployment
\`\`\`bash
kubectl get pods -n archiveorigin-staging
kubectl get svc -n archiveorigin-staging
kubectl logs -f deployment/archiveorigin-api -n archiveorigin-staging
\`\`\`

#### 6. Run Database Migrations
\`\`\`bash
kubectl run migration --image=archiveorigin/backend:staging-v1.0.0 \
  --env="DATABASE_URL=postgresql://..." \
  --command -- python -m alembic upgrade head \
  -n archiveorigin-staging
\`\`\`

---

## Production Deployment

### Prerequisites
- Production Kubernetes cluster
- Production database (managed service)
- SSL/TLS certificates
- Monitoring and logging infrastructure
- Backup systems

### Deployment Steps

#### 1. Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Code review completed
- [ ] Security scan passed
- [ ] Performance testing completed
- [ ] Backup created
- [ ] Rollback plan documented

#### 2. Build and Push Image
\`\`\`bash
docker build -t archiveorigin/backend:v1.0.0 .
docker tag archiveorigin/backend:v1.0.0 archiveorigin/backend:latest
docker push archiveorigin/backend:v1.0.0
docker push archiveorigin/backend:latest
\`\`\`

#### 3. Create Production Namespace
\`\`\`bash
kubectl create namespace archiveorigin-prod
\`\`\`

#### 4. Create Secrets
\`\`\`bash
kubectl create secret generic db-credentials \
  --from-literal=url=postgresql://user:password@prod-db-host:5432/archiveorigin \
  -n archiveorigin-prod

kubectl create secret generic api-secrets \
  --from-literal=secret-key=your-production-secret-key \
  --from-literal=devicecheck-key=your-production-key \
  -n archiveorigin-prod

kubectl create secret tls tls-cert \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n archiveorigin-prod
\`\`\`

#### 5. Deploy Application
\`\`\`bash
kubectl apply -f k8s/prod/deployment.yaml -n archiveorigin-prod
kubectl apply -f k8s/prod/service.yaml -n archiveorigin-prod
kubectl apply -f k8s/prod/ingress.yaml -n archiveorigin-prod
kubectl apply -f k8s/prod/hpa.yaml -n archiveorigin-prod
\`\`\`

#### 6. Run Database Migrations
\`\`\`bash
kubectl run migration --image=archiveorigin/backend:v1.0.0 \
  --env="DATABASE_URL=postgresql://..." \
  --command -- python -m alembic upgrade head \
  -n archiveorigin-prod
\`\`\`

#### 7. Verify Deployment
\`\`\`bash
kubectl get pods -n archiveorigin-prod
kubectl get svc -n archiveorigin-prod
kubectl logs -f deployment/archiveorigin-api -n archiveorigin-prod
\`\`\`

#### 8. Health Checks
\`\`\`bash
# Check API health
curl https://api.archiveorigin.com/health

# Check database connectivity
kubectl exec -it deployment/archiveorigin-api -n archiveorigin-prod -- \
  python -c "from app.database import engine; engine.connect()"

# Check external service connectivity
kubectl exec -it deployment/archiveorigin-api -n archiveorigin-prod -- \
  python -c "from app.devicecheck import client; client.test_connection()"
\`\`\`

---

## Database Management

### Migrations

#### Create Migration
\`\`\`bash
docker-compose exec api alembic revision --autogenerate -m "Add new table"
\`\`\`

#### Apply Migrations
\`\`\`bash
docker-compose exec api alembic upgrade head
\`\`\`

#### Rollback Migration
\`\`\`bash
docker-compose exec api alembic downgrade -1
\`\`\`

### Backup and Recovery

#### Create Backup
\`\`\`bash
docker-compose exec db pg_dump -U archiveorigin archiveorigin_dev > backup.sql
\`\`\`

#### Restore from Backup
\`\`\`bash
docker-compose exec db psql -U archiveorigin archiveorigin_dev < backup.sql
\`\`\`

#### Automated Backups
\`\`\`bash
# Create backup script
cat > backup.sh << 'BACKUP'
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/archiveorigin_$TIMESTAMP.sql"

pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_FILE
gzip $BACKUP_FILE

# Keep only last 30 days
find $BACKUP_DIR -name "archiveorigin_*.sql.gz" -mtime +30 -delete
BACKUP

# Schedule with cron
0 2 * * * /path/to/backup.sh
\`\`\`

---

## Monitoring and Logging

### Prometheus Metrics
\`\`\`yaml
# prometheus.yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'archiveorigin-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
\`\`\`

### ELK Stack Setup
\`\`\`yaml
# docker-compose.yml additions
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
  environment:
    - discovery.type=single-node
  ports:
    - "9200:9200"

kibana:
  image: docker.elastic.co/kibana/kibana:8.0.0
  ports:
    - "5601:5601"

logstash:
  image: docker.elastic.co/logstash/logstash:8.0.0
  volumes:
    - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
\`\`\`

---

## Troubleshooting

### Common Issues

#### Database Connection Failed
\`\`\`bash
# Check database status
docker-compose ps db

# Check logs
docker-compose logs db

# Verify connection string
echo $DATABASE_URL

# Test connection
docker-compose exec api python -c "from app.database import engine; engine.connect()"
\`\`\`

#### API Not Responding
\`\`\`bash
# Check API status
docker-compose ps api

# Check logs
docker-compose logs api

# Check port availability
lsof -i :8000

# Restart API
docker-compose restart api
\`\`\`

#### High Memory Usage
\`\`\`bash
# Check memory usage
docker stats

# Check for memory leaks
docker-compose exec api python -m memory_profiler app/main.py

# Increase memory limit
# Edit docker-compose.yml and set memory limit
\`\`\`

#### Slow Queries
\`\`\`bash
# Enable query logging
# Set LOG_LEVEL=DEBUG in .env

# Analyze slow queries
docker-compose exec db psql -U archiveorigin -d archiveorigin_dev -c \
  "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Create indexes
docker-compose exec db psql -U archiveorigin -d archiveorigin_dev -c \
  "CREATE INDEX idx_device_id ON devices(device_id);"
\`\`\`

---

## Rollback Procedures

### Rollback to Previous Version
\`\`\`bash
# Get previous image version
kubectl rollout history deployment/archiveorigin-api -n archiveorigin-prod

# Rollback to previous version
kubectl rollout undo deployment/archiveorigin-api -n archiveorigin-prod

# Rollback to specific revision
kubectl rollout undo deployment/archiveorigin-api --to-revision=2 -n archiveorigin-prod

# Verify rollback
kubectl get pods -n archiveorigin-prod
kubectl logs -f deployment/archiveorigin-api -n archiveorigin-prod
\`\`\`

### Database Rollback
\`\`\`bash
# Get migration history
kubectl exec deployment/archiveorigin-api -n archiveorigin-prod -- \
  alembic history

# Rollback to specific migration
kubectl exec deployment/archiveorigin-api -n archiveorigin-prod -- \
  alembic downgrade <revision>
\`\`\`

---

## Success Criteria

- ✅ Local development setup documented
- ✅ Staging deployment guide created
- ✅ Production deployment guide created
- ✅ Database management procedures documented
- ✅ Backup and recovery procedures documented
- ✅ Monitoring setup documented
- ✅ Troubleshooting guide created
- ✅ Rollback procedures documented
- ✅ All procedures tested
- ✅ Documentation reviewed

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/docs/DEPLOYMENT.md` - Main deployment guide
2. **NEW:** `archiveorigin_backend_api/.env.example` - Environment template
3. **NEW:** `archiveorigin_backend_api/k8s/staging/deployment.yaml` - Staging deployment
4. **NEW:** `archiveorigin_backend_api/k8s/prod/deployment.yaml` - Production deployment
5. **NEW:** `archiveorigin_backend_api/scripts/backup.sh` - Backup script

---

## Dependencies

- Docker and Docker Compose
- Kubernetes cluster
- kubectl CLI
- PostgreSQL client tools
- Monitoring tools (Prometheus, ELK, etc.)

---

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/current/backup.html)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
