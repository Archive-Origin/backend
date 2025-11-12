# Archive Origin Backend - Development Roadmap

## Project Overview
Archive Origin Backend is a FastAPI-based proof API that handles device enrollment, capture proof locking, and Merkle ledger sealing. The system uses PostgreSQL for storage and includes Git-based ledger management.

---

## Current Status

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

## Phase 1: DeviceCheck Integration (PRIORITY: HIGH)

### Objectives
Integrate Apple's DeviceCheck service for device attestation and security validation.

### Tasks
- [ ] **1.1** Research DeviceCheck API requirements
  - Review Apple DeviceCheck documentation
  - Understand token generation & validation flow
  - Document security requirements

- [ ] **1.2** Implement DeviceCheck client
  - Create DeviceCheck API wrapper
  - Handle token generation
  - Implement token validation logic
  - Add error handling & retry logic

- [ ] **1.3** Integrate with device enrollment
  - Modify `/device/enroll` endpoint
  - Validate DeviceCheck tokens
  - Store attestation data in DB
  - Add attestation status tracking

- [ ] **1.4** Add DeviceCheck verification to proof locking
  - Validate device attestation before accepting proofs
  - Implement attestation freshness checks
  - Add attestation failure handling

- [ ] **1.5** Testing
  - Unit tests for DeviceCheck client
  - Integration tests with mock DeviceCheck
  - End-to-end device enrollment flow tests

### Acceptance Criteria
- DeviceCheck tokens are validated on device enrollment
- Proof locking requires valid device attestation
- Attestation data is persisted and auditable
- All tests pass with >80% coverage

---

## Phase 2: Attestation & Ledger Hardening (PRIORITY: HIGH)

### Objectives
Strengthen the attestation system and ledger integrity through enhanced security measures.

### 2A: Attestation Hardening

#### Tasks
- [ ] **2A.1** Implement attestation chain validation
  - Validate certificate chains
  - Verify signature chains
  - Implement chain revocation checks

- [ ] **2A.2** Add attestation metadata
  - Store attestation timestamps
  - Track attestation sources
  - Implement attestation versioning

- [ ] **2A.3** Implement attestation rotation
  - Create attestation refresh mechanism
  - Handle expired attestations
  - Implement graceful degradation

- [ ] **2A.4** Add attestation audit logging
  - Log all attestation events
  - Track attestation changes
  - Implement audit trail queries

### 2B: Ledger Hardening

#### Tasks
- [ ] **2B.1** Implement Merkle proof verification
  - Add proof validation logic
  - Verify Merkle paths
  - Implement proof audit

- [ ] **2B.2** Add ledger integrity checks
  - Implement root hash verification
  - Add batch integrity validation
  - Create consistency checks

- [ ] **2B.3** Implement ledger versioning
  - Track ledger versions
  - Support ledger rollback (if needed)
  - Implement version migration

- [ ] **2B.4** Add ledger backup & recovery
  - Implement automated backups
  - Create recovery procedures
  - Test disaster recovery

- [ ] **2B.5** Implement ledger replication
  - Set up ledger replication
  - Implement sync mechanisms
  - Add conflict resolution

### Acceptance Criteria
- All attestation chains are validated
- Ledger integrity is verified on every operation
- Audit logs capture all security-relevant events
- Recovery procedures are tested and documented
- All tests pass with >85% coverage

---

## Phase 3: Documentation & Testing (PRIORITY: MEDIUM)

### 3A: Documentation

#### Tasks
- [ ] **3A.1** API Documentation
  - Create OpenAPI/Swagger docs
  - Document all endpoints
  - Add request/response examples
  - Document error codes

- [ ] **3A.2** Architecture Documentation
  - Create system architecture diagrams
  - Document data flow
  - Explain Merkle ledger design
  - Document security model

- [ ] **3A.3** Deployment Documentation
  - Create deployment guide
  - Document environment setup
  - Add troubleshooting guide
  - Create runbook for operations

- [ ] **3A.4** Developer Guide
  - Setup instructions
  - Development workflow
  - Testing procedures
  - Contribution guidelines

- [ ] **3A.5** Security Documentation
  - Document security model
  - Explain threat model
  - Document security best practices
  - Create security checklist

### 3B: Testing

#### Tasks
- [ ] **3B.1** Unit Test Coverage
  - Achieve >85% code coverage
  - Test all utility functions
  - Test all models & schemas
  - Test error handling

- [ ] **3B.2** Integration Tests
  - Test API endpoints
  - Test database operations
  - Test ledger operations
  - Test authentication flow

- [ ] **3B.3** End-to-End Tests
  - Test complete device enrollment flow
  - Test proof locking flow
  - Test ledger sealing flow
  - Test error scenarios

- [ ] **3B.4** Performance Tests
  - Load testing
  - Stress testing
  - Latency benchmarks
  - Throughput benchmarks

- [ ] **3B.5** Security Tests
  - Penetration testing
  - Vulnerability scanning
  - Authentication bypass tests
  - Authorization tests

### Acceptance Criteria
- All documentation is complete and up-to-date
- Code coverage is >85%
- All tests pass
- Performance benchmarks are documented
- Security tests pass

---

## Phase 4: Additional Features (PRIORITY: MEDIUM)

### Tasks
- [ ] **4.1** Implement proof retrieval endpoint
  - Create `/get-proof` endpoint
  - Implement proof filtering
  - Add pagination support

- [ ] **4.2** Implement proof verification endpoint
  - Create `/verify-proof` endpoint
  - Implement Merkle proof verification
  - Add verification status tracking

- [ ] **4.3** Implement batch operations
  - Create `/batch-enroll` endpoint
  - Create `/batch-lock-proof` endpoint
  - Implement batch error handling

- [ ] **4.4** Implement analytics & monitoring
  - Add metrics collection
  - Create dashboard
  - Implement alerting

- [ ] **4.5** Implement admin endpoints
  - Create admin dashboard
  - Implement user management
  - Add system configuration endpoints

---

## Technical Debt & Improvements

### High Priority
- [ ] Add comprehensive error handling
- [ ] Implement request validation
- [ ] Add rate limiting
- [ ] Implement caching strategy
- [ ] Add logging & monitoring

### Medium Priority
- [ ] Refactor large functions
- [ ] Improve code organization
- [ ] Add type hints
- [ ] Improve test organization
- [ ] Add CI/CD pipeline

### Low Priority
- [ ] Code style improvements
- [ ] Documentation improvements
- [ ] Performance optimizations
- [ ] Dependency updates

---

## Collaboration Guidelines

### Git Workflow
1. Create feature branches from `main`
2. Branch naming: `feature/description` or `fix/description`
3. Commit messages: Clear, descriptive, present tense
4. Pull requests required for all changes
5. Code review before merge

### Code Standards
- Follow PEP 8 for Python
- Add type hints to all functions
- Write docstrings for all modules/functions
- Maintain >85% test coverage
- Use meaningful variable names

### Communication
- Use GitHub issues for tracking
- Use pull request comments for code review
- Update roadmap as progress is made
- Document blockers and dependencies

---

## Timeline Estimate

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 1: DeviceCheck | 2-3 weeks | Week 1 | Week 3 |
| Phase 2: Hardening | 3-4 weeks | Week 3 | Week 7 |
| Phase 3: Docs & Tests | 2-3 weeks | Week 7 | Week 10 |
| Phase 4: Features | 2-3 weeks | Week 10 | Week 13 |

---

## Success Metrics

- [ ] All phases completed on schedule
- [ ] Code coverage >85%
- [ ] All tests passing
- [ ] Zero critical security issues
- [ ] Documentation complete
- [ ] Performance benchmarks met
- [ ] Zero production incidents

---

## Next Steps

1. **Immediate** (This Week)
   - [ ] Review this roadmap
   - [ ] Assign Phase 1 tasks
   - [ ] Set up development environment
   - [ ] Create GitHub issues for Phase 1

2. **Short Term** (Next 2 Weeks)
   - [ ] Complete Phase 1 DeviceCheck integration
   - [ ] Begin Phase 2 attestation hardening
   - [ ] Set up CI/CD pipeline

3. **Medium Term** (Weeks 3-7)
   - [ ] Complete Phase 2 hardening
   - [ ] Begin Phase 3 documentation
   - [ ] Implement comprehensive testing

---

## Questions & Blockers

### Current Blockers
- None identified

### Open Questions
- DeviceCheck API credentials - where are they stored?
- What's the target deployment environment?
- Are there specific performance requirements?
- What's the expected scale (requests/day)?

---

**Last Updated:** November 12, 2025
**Status:** ACTIVE DEVELOPMENT
**Next Review:** November 19, 2025
