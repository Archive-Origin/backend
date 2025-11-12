# Archive Origin Backend - Quick Start Guide

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.9+
- Git
- GitHub token (for authentication)

### Clone & Setup

```bash
# Clone the repository
git clone https://github.com/Archive-Origin/backend.git
cd backend

# Copy environment template
cp .env.example .env

# Start the stack
docker compose up -d --build

# Verify health
curl -s http://localhost:8001/health | jq
```

---

## 📋 Project Structure

```
backend/
├── archiveorigin_backend_api/
│   ├── app/
│   │   ├── main.py              # FastAPI app & endpoints
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── db.py                # Database connection
│   │   ├── auth.py              # Authentication logic
│   │   ├── security.py          # Security utilities
│   │   ├── merkle.py            # Merkle tree implementation
│   │   ├── ledger.py            # Ledger management
│   │   ├── verification.py      # Signature verification
│   │   ├── config.py            # Configuration
│   │   ├── migrations/
│   │   │   └── init.sql         # Database schema
│   │   └── tests/
│   │       ├── conftest.py      # Test fixtures
│   │       └── test_*.py        # Test files
│   └── docker-compose.yml       # Docker configuration
├── ROADMAP.md                   # Original roadmap
├── DEVELOPMENT_ROADMAP.md       # Detailed development roadmap
└── README.md                    # Project documentation
```

---

## 🔑 Core Endpoints

### Device Enrollment
```bash
POST /device/enroll
Content-Type: application/json

{
  "device_id": "unique-device-id",
  "device_check_token": "token-from-apple"
}

Response:
{
  "device_token": "64-byte-url-safe-string",
  "expires_at": "2025-11-25T21:38:00Z",
  "renewal_buffer_seconds": 604800
}
```

### Lock Proof
```bash
POST /lock-proof
Authorization: Bearer {device_token}
Content-Type: application/json

{
  "capture_id": "unique-capture-id",
  "manifest": "c2pa-manifest-data",
  "signature": "ed25519-signature",
  "timestamp": "2025-11-12T21:38:00Z"
}

Response:
{
  "proof_id": "unique-proof-id",
  "merkle_root": "hash",
  "batch_id": "batch-identifier",
  "locked_at": "2025-11-12T21:38:00Z"
}
```

### Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-11-12T21:38:00Z"
}
```

---

## 🧪 Testing

### Run All Tests
```bash
docker compose exec api pytest -v
```

### Run Specific Test File
```bash
docker compose exec api pytest tests/test_verification_validation.py -v
```

### Run with Coverage
```bash
docker compose exec api pytest --cov=app --cov-report=html
```

### Run Tests Locally (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v
```

---

## 📊 Merkle Ledger Sealing

### Seal Pending Proofs
```bash
docker compose exec api python -m ledger
```

### Seal with Git Commit
```bash
docker compose exec api python -m ledger --commit
```

### Seal with Git Push
```bash
docker compose exec api python -m ledger --push
```

### View Ledger Help
```bash
docker compose exec api python -m ledger --help
```

---

## 🔧 Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
```bash
# Edit files
# Run tests
docker compose exec api pytest -v
```

### 3. Commit Changes
```bash
git add .
git commit -m "Add your feature description"
```

### 4. Push & Create PR
```bash
git push origin feature/your-feature-name
# Create PR on GitHub
```

### 5. Code Review & Merge
- Request review from team
- Address feedback
- Merge to main

---

## �� Debugging

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f db
```

### Access Database
```bash
docker compose exec db psql -U archiveorigin -d origin_proofs
```

### Interactive Python Shell
```bash
docker compose exec api python
```

---

## 📝 Environment Variables

Key variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://archiveorigin:supersecret@db:5432/origin_proofs

# Verification
VERIFY_BASE_URL=https://verify.archiveorigin.com
VERIFY_SIGNATURES=true

# Device Tokens
DEVICE_TOKEN_TTL_SECONDS=2592000        # 30 days
DEVICE_TOKEN_RENEWAL_BUFFER=604800      # 7 days

# Ledger
LEDGER_REPO_ROOT=ledger/
LEDGER_BATCHES_SUBDIR=batches
LEDGER_ROOTS_SUBDIR=roots
LEDGER_PROOFS_SUBDIR=proofs

# Git Auto-Commit
LEDGER_GIT_AUTO_COMMIT=false
LEDGER_GIT_AUTO_PUSH=false
LEDGER_GIT_REMOTE=origin
LEDGER_GIT_BRANCH=main
```

---

## 🚨 Common Issues

### Database Connection Failed
```bash
# Check if DB is running
docker compose ps

# Restart services
docker compose restart db api

# Check logs
docker compose logs db
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
# Or kill process using port 8001
lsof -i :8001
kill -9 <PID>
```

### Tests Failing
```bash
# Clear cache
docker compose exec api pytest --cache-clear

# Run with verbose output
docker compose exec api pytest -vv -s
```

---

## 📚 Documentation

- **README.md** - Project overview & quickstart
- **ROADMAP.md** - Original roadmap (3 items)
- **DEVELOPMENT_ROADMAP.md** - Detailed 4-phase roadmap
- **API Docs** - Available at `http://localhost:8001/docs` (Swagger UI)

---

## 🤝 Collaboration

### Before Starting Work
1. Check DEVELOPMENT_ROADMAP.md for current phase
2. Review open GitHub issues
3. Discuss with team if unclear

### During Development
1. Write tests for new code
2. Maintain >85% code coverage
3. Follow PEP 8 style guide
4. Add docstrings to functions

### Before Submitting PR
1. Run all tests: `pytest -v`
2. Check coverage: `pytest --cov`
3. Lint code: `flake8 app/`
4. Update documentation if needed

---

## 📞 Getting Help

- Check README.md for detailed info
- Review DEVELOPMENT_ROADMAP.md for current work
- Check GitHub issues for known problems
- Ask in team chat/email

---

**Last Updated:** November 12, 2025
**Status:** ACTIVE DEVELOPMENT
