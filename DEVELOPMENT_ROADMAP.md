# Archive Origin Backend - Development Roadmap (Updated)

## Project Overview
Archive Origin Backend is a FastAPI-based proof API that handles device enrollment, capture proof locking, and Merkle ledger sealing. The system uses PostgreSQL for storage and includes Git-based ledger management.

---

## Current Status - November 12, 2025

### ✅ Completed Components
- **Core API Framework** (FastAPI)
  - `/device/enroll` - Device enrollment & token renewal
  - `/lock-proof` - Immutable capture proof storage
  - `/health` - Health check & DB verification

- **Database Layer**
  - PostgreSQL integration
  - Schema initialization (init.sql)
  - Migration system

- **Authentication & Security**
  - Ed25519 signature verification
  - Bearer token validation
  - Device token management (TTL & renewal buffer)

- **Merkle Ledger System**
  - Merkle root computation
  - Batch file generation
  - Root/proof manifest management
  - Git auto-commit/push support

- **Configuration**
  - Environment-based config
  - Docker Compose setup
  - Rate limiting infrastructure

---

## Phase 1: DeviceCheck Integration (PRIORITY: HIGH) - IN PROGRESS 🔄

### Objectives
Integrate Apple's DeviceCheck service for device attestation and security validation.

### Progress Summary
- **Task 1.1:** ✅ COMPLETE - DeviceCheck research documented
- **Task 1.2:** ✅ COMPLETE - DeviceCheck client implemented (MOCK)
- **Task 1.3:** 🔄 IN PROGRESS - Device enrollment integration
- **Task 1.4:** ⏳ PENDING - Proof locking verification
- **Task 1.5:** 🔄 IN PROGRESS - Comprehensive testing

### Completed Deliverables

1. **DEVICECHECK_RESEARCH.md** - Comprehensive research guide
   - DeviceCheck concepts and architecture
   - JWT authentication details
   - API endpoints documentation
   - Security considerations
   - Database schema design

2. **archiveorigin_backend_api/app/devicecheck.py** - DeviceCheck client
   - ⚠️ **MOCK IMPLEMENTATION FOR DEVELOPMENT**
   - Mock JWT generation (TODO: Replace with real ES256)
   - Mock token validation (TODO: Replace with real httpx API calls)
   - Error handling structure
   - Async-ready architecture
   
   **TODO for Production:**
   - [ ] Replace mock JWT with real `jwt.encode()` using ES256 algorithm
   - [ ] Replace mock validation with real `httpx.Client` POST to Apple's API
   - [ ] Load real credentials from settings (team_id, key_id, private_key)
   - [ ] Implement real error handling for Apple API responses (400, 401, 429, etc.)
   - [ ] Add retry logic with exponential backoff
   - [ ] Add rate limiting handling

3. **archiveorigin_backend_api/app/tests/test_devicecheck.py** - Unit tests
   - Client initialization tests
   - JWT creation tests
   - Response model tests
   - Exception handling tests

### Next Steps (Task 1.3)
- [ ] Modify `/device/enroll` endpoint to use DeviceCheck client
- [ ] Add DeviceCheck token validation to enrollment flow
- [ ] Store attestation data in database
- [ ] Add attestation status tracking
- [ ] Write integration tests

**Target Completion:** November 14, 2025

---

## Phase 2: Attestation & Ledger Hardening (PRIORITY: HIGH)

### Objectives
Strengthen the attestation system and ledger integrity through enhanced security measures.

### 2A: Attestation Hardening

#### Tasks
- [ ] **2A.1** Implement attestation chain validation
- [ ] **2A.2** Add attestation metadata
- [ ] **2A.3** Implement attestation rotation
- [ ] **2A.4** Add attestation audit logging

### 2B: Ledger Hardening

#### Tasks
- [ ] **2B.1** Implement Merkle proof verification
- [ ] **2B.2** Add ledger integrity checks
- [ ] **2B.3** Implement ledger sealing
- [ ] **2B.4** Add ledger audit trail

**Target Completion:** December 20, 2025

---

## Phase 3: Documentation & Testing (PRIORITY: MEDIUM)

### Objectives
Comprehensive documentation and test coverage for all components.

### Tasks
- [ ] **3.1** API documentation (OpenAPI/Swagger)
- [ ] **3.2** Architecture documentation
- [ ] **3.3** Deployment guide
- [ ] **3.4** Security audit
- [ ] **3.5** Performance testing
- [ ] **3.6** Load testing

**Target Completion:** January 10, 2026

---

## Phase 4: Additional Features (PRIORITY: LOW)

### Objectives
Additional features and enhancements based on requirements.

### Tasks
- [ ] **4.1** Advanced analytics
- [ ] **4.2** Webhook notifications
- [ ] **4.3** Batch operations
- [ ] **4.4** Export functionality
- [ ] **4.5** Admin dashboard

**Target Completion:** January 31, 2026

---

## Development Guidelines

### Code Quality Standards
- **Language:** Python 3.9+
- **Framework:** FastAPI
- **Database:** PostgreSQL
- **Testing:** pytest with >85% coverage
- **Code Style:** PEP 8
- **Type Hints:** Required for all functions

### Git Workflow
- Branch naming: `feature/description` or `fix/description`
- Commit messages: Clear and descriptive
- Pull requests required for all changes
- Code review before merge

### Testing Requirements
- Unit tests for all new functions
- Integration tests for API endpoints
- Mock external services (Apple DeviceCheck, etc.)
- Minimum 85% code coverage

### Security Considerations
- Never commit credentials or secrets
- Use environment variables for configuration
- Validate all inputs
- Use HTTPS for all external API calls
- Implement rate limiting
- Log security events

---

## Important Notes

### Mock Implementation Status
The DeviceCheck client (`archiveorigin_backend_api/app/devicecheck.py`) is currently a **MOCK IMPLEMENTATION** for development purposes. Before moving to production:

1. Replace mock JWT generation with real ES256 signing
2. Replace mock validation with real Apple API calls
3. Load real credentials from secure configuration
4. Implement proper error handling for all Apple API responses
5. Add comprehensive logging and monitoring

### Collaboration
- Both agents working on same repository
- Pull frequently to avoid conflicts
- Coordinate on task assignments
- Update roadmap as progress is made

---

**Last Updated:** November 12, 2025
**Updated By:** Augment Agent
**Next Review:** November 14, 2025
