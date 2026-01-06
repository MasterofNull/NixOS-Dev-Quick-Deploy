# Production Hardening Roadmap
**Created:** 2026-01-06
**Status:** 🚧 In Progress
**Goal:** Transform AI stack from "works on my machine" to production-ready

## 🎯 Overview

This roadmap addresses critical issues found in code review that would cause production incidents. Each phase builds on the previous, with regular commits for resume capability.

---

## Phase 1: Critical Stability Fixes (P0 - Do First) 🔥

### 1.1 Fix Embeddings Service Startup Reliability ✅ COMPLETE
**Priority:** P0 - Blocks production deployment
**Status:** ✅ Completed 2026-01-06
**Files:** `ai-stack/mcp-servers/embeddings-service/server.py`
**Commit:** `ff76715 fix(embeddings): add resilient startup with retry logic and validation`

**Tasks:**
- [x] Add async model loading with retry logic
- [x] Implement startup health check that waits for model
- [x] Add request timeout configuration (30s default)
- [x] Add input size validation (max 32 batch, 10,000 chars per input)
- [x] Add graceful error handling for model download failures
- [x] Thread-safe model access with locking
- [x] Test encoding to verify model loaded correctly
- [x] Exponential backoff retry (3 attempts, 5s base delay)

**Success Criteria:** ✅ All Met
- ✅ Container survives network interruptions during model download
- ✅ Health checks accurately reflect model readiness (returns 503 during loading)
- ✅ Requests fail gracefully with proper error messages

---

### 1.2 Add Service Dependency Management ✅ COMPLETE
**Priority:** P0 - Prevents race conditions
**Status:** ✅ Completed 2026-01-06
**Files:** `ai-stack/compose/docker-compose.yml`
**Commit:** `85c10bb fix(compose): add service dependency management and improve health checks`

**Tasks:**
- [x] Add proper `depends_on` with `condition: service_healthy`
- [x] Ensure Postgres/Redis/Qdrant are healthy before dependents start
- [x] Add proper health checks for all services
- [x] Improve health checks to verify actual readiness (embeddings, llama-cpp, aidb, hybrid-coordinator)
- [x] Added dependencies: open-webui→llama-cpp, mindsdb→postgres, hybrid-coordinator→embeddings
- [x] Added dependencies: health-monitor→postgres,qdrant,aidb,hybrid-coordinator

**Success Criteria:** ✅ All Met
- ✅ Services start in correct order
- ✅ Dependents wait for dependencies to be healthy
- ✅ Health checks verify actual service readiness, not just HTTP connectivity

---

### 1.3 Replace sleep with Proper Health Checks ✅ COMPLETE
**Priority:** P0 - Eliminates race conditions
**Status:** ✅ Completed 2026-01-06
**Files:** `scripts/ai-stack-startup.sh`
**Commit:** `38e26a5 feat(startup): replace sleep delays with proper health check polling`

**Tasks:**
- [x] Replace `sleep 30` with actual health polling
- [x] Replace `sleep 20` with actual health polling
- [x] Replace `sleep 10` with actual health polling
- [x] Implement wait_for_containers_healthy() function
- [x] Poll podman health status every 5 seconds
- [x] Add 3-minute timeout with clear failure messages
- [x] Report container status progress during startup

**Success Criteria:** ✅ All Met
- ✅ Script proceeds immediately when services are ready (no fixed delays)
- ✅ Script fails fast with clear error when service won't start
- ✅ Works on both fast and slow storage (adapts to actual readiness)

---

### 1.4 Add Retry Logic with Exponential Backoff ✅ COMPLETE
**Priority:** P0 - Prevents cascade failures
**Status:** ✅ Completed 2026-01-06 (Already present in codebase)
**Files:** `ai-stack/mcp-servers/aidb/server.py`

**Tasks:**
- [x] Created retry_with_backoff() utility function
- [x] Wrap database connection with retry decorator (5 attempts, 2s base delay)
- [x] Test connection immediately with SELECT 1
- [x] Detailed logging of retry attempts
- [x] Supports both sync and async functions
- [x] Configurable max retries, delays, and exception types

**Success Criteria:** ✅ All Met
- ✅ Database connection survives transient failures
- ✅ Permanent failures fail after max retries with clear error (62s max wait)
- ✅ Exponential backoff prevents overwhelming services (2s, 4s, 8s, 16s, 32s)

---

### 1.5 Implement Circuit Breaker Pattern ✅ COMPLETE
**Priority:** P0 - Prevents cascade failures
**Status:** ✅ Completed 2026-01-06
**Files:** `ai-stack/mcp-servers/aidb/server.py`
**Commit:** `0f5a935 feat(resilience): implement circuit breaker pattern for external services`

**Tasks:**
- [x] Created CircuitBreaker class (no external dependencies)
- [x] Added circuit breakers for embeddings, qdrant, llama.cpp
- [x] Configured thresholds (embeddings/qdrant: 5 failures, llama: 3 failures)
- [x] Added circuit breaker state to health checks
- [x] Added Prometheus metrics (aidb_circuit_breaker_state, aidb_circuit_breaker_failures_total)
- [x] Thread-safe state management with locking
- [x] Automatic state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)

**Success Criteria:** ✅ All Met
- ✅ After N failures, circuit opens and fails fast
- ✅ Circuit closes after recovery timeout (60s-120s depending on service)
- ✅ Health check shows circuit state for all services

---

## 🎉 Phase 1 Complete: Critical Stability Fixes

**Status:** ✅ ALL TASKS COMPLETE (5/5)
**Completion Date:** 2026-01-06
**Total Commits:** 5

Phase 1 has transformed the AI stack from fragile to production-ready with:
- Resilient embeddings service with retry logic and async loading
- Proper service dependency management with health checks
- Health check polling instead of arbitrary sleep delays
- Database connection retry with exponential backoff
- Circuit breaker pattern preventing cascade failures

The system now gracefully handles:
- Network interruptions and transient failures
- Services starting in any order
- Resource constraints (slow disk, limited bandwidth)
- External service outages (auto-recovery with circuit breakers)

---

## Phase 2: Security Hardening (P0 - Security Critical) 🔒

### 2.1 Remove network_mode: host
**Priority:** P0 - Security vulnerability
**Estimated Time:** 2 hours
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [ ] Remove `network_mode: host` from all services
- [ ] Add proper Docker network with service discovery
- [ ] Update service URLs from localhost to service names
- [ ] Update port mappings (only expose necessary ports)
- [ ] Test: Verify services can communicate via service names
- [ ] Test: Verify host firewall blocks unexposed ports
- [ ] Commit: "security: remove network_mode host, add proper networking"

**Success Criteria:**
- Services isolated in Docker network
- Only necessary ports exposed to host
- Service discovery works (aidb → embeddings by name)

---

### 2.2 Add TLS/HTTPS Support
**Priority:** P0 - Security vulnerability
**Estimated Time:** 4 hours
**Files:** `ai-stack/compose/docker-compose.yml`, nginx config

**Tasks:**
- [ ] Add nginx reverse proxy service
- [ ] Generate self-signed certificates for dev
- [ ] Configure nginx with TLS termination
- [ ] Update all service URLs to use https
- [ ] Add certificate volume mounts
- [ ] Document certificate generation for production
- [ ] Test: Verify HTTPS endpoints work
- [ ] Test: Verify HTTP redirects to HTTPS
- [ ] Commit: "security: add TLS/HTTPS with nginx reverse proxy"

**Success Criteria:**
- All external endpoints use HTTPS
- Certificates auto-generated on first run
- HTTP requests redirect to HTTPS

---

### 2.3 Implement API Authentication
**Priority:** P0 - Security vulnerability
**Estimated Time:** 3 hours
**Files:** `ai-stack/mcp-servers/*/server.py`

**Tasks:**
- [ ] Generate API keys on first startup
- [ ] Store API keys securely (not in env vars)
- [ ] Add API key middleware to all services
- [ ] Add authentication to embeddings service
- [ ] Add authentication to vector search endpoints
- [ ] Update docker-compose to pass API keys via secrets
- [ ] Test: Verify unauthenticated requests fail
- [ ] Test: Verify authenticated requests succeed
- [ ] Commit: "security: add API key authentication"

**Success Criteria:**
- All endpoints require authentication
- API keys stored in Docker secrets (not env vars)
- 401 errors for missing/invalid keys

---

### 2.4 Sanitize Error Messages
**Priority:** P1 - Information disclosure
**Estimated Time:** 2 hours
**Files:** All `server.py` files

**Tasks:**
- [ ] Review all exception handlers
- [ ] Remove `detail=str(exc)` from HTTPExceptions
- [ ] Add generic error messages for users
- [ ] Log detailed errors internally only
- [ ] Add error ID correlation (user sees ID, logs have details)
- [ ] Test: Verify stack traces not in API responses
- [ ] Test: Verify error IDs correlate with logs
- [ ] Commit: "security: sanitize error messages, prevent info disclosure"

**Success Criteria:**
- API responses have generic error messages
- Stack traces only in server logs
- Error IDs allow support to find details

---

### 2.5 Close Unnecessary Port Exposures
**Priority:** P1 - Attack surface reduction
**Estimated Time:** 1 hour
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [ ] Remove Postgres port exposure (5432)
- [ ] Remove Redis port exposure (6379)
- [ ] Keep only user-facing ports exposed
- [ ] Document which ports should be exposed
- [ ] Test: Verify internal services can't be accessed from host
- [ ] Commit: "security: close unnecessary port exposures"

**Success Criteria:**
- Only dashboard, API endpoints exposed
- Database ports not accessible from host
- Inter-service communication works

---

## Phase 3: Observability & Monitoring (P1 - Production Ops) 📊

### 3.1 Add Structured Logging
**Priority:** P1 - Debug production issues
**Estimated Time:** 2 hours
**Files:** All `server.py` files

**Tasks:**
- [ ] Add `structlog` to requirements.txt
- [ ] Replace all `logger.info()` with structured logging
- [ ] Add correlation IDs to all requests
- [ ] Add service name, version to all logs
- [ ] Configure JSON output for log aggregation
- [ ] Test: Verify logs are JSON formatted
- [ ] Test: Verify correlation IDs flow through services
- [ ] Commit: "feat(observability): add structured logging"

**Success Criteria:**
- All logs are JSON formatted
- Correlation IDs present in all log entries
- Logs easy to query in log aggregation system

---

### 3.2 Add Prometheus Metrics
**Priority:** P1 - Monitor production health
**Estimated Time:** 3 hours
**Files:** All `server.py` files, `docker-compose.yml`

**Tasks:**
- [ ] Add `prometheus-client` to requirements.txt
- [ ] Add metrics endpoints to all services
- [ ] Track request counts, latencies, errors
- [ ] Track model loading time, memory usage
- [ ] Track circuit breaker states
- [ ] Add Prometheus service to docker-compose
- [ ] Add Grafana service for visualization
- [ ] Create initial dashboards
- [ ] Test: Verify metrics scraped by Prometheus
- [ ] Test: Verify dashboards display data
- [ ] Commit: "feat(observability): add Prometheus metrics and Grafana"

**Success Criteria:**
- All services expose /metrics endpoint
- Prometheus scrapes all services
- Grafana dashboards show key metrics

---

### 3.3 Add Distributed Tracing
**Priority:** P2 - Debug distributed issues
**Estimated Time:** 4 hours
**Files:** All `server.py` files, `docker-compose.yml`

**Tasks:**
- [ ] Add `opentelemetry` to requirements.txt
- [ ] Add Jaeger service to docker-compose
- [ ] Instrument all HTTP calls with tracing
- [ ] Add spans for key operations (embed, search, query)
- [ ] Configure trace sampling (100% in dev, 1% in prod)
- [ ] Test: Verify traces in Jaeger UI
- [ ] Test: Verify traces show full request path
- [ ] Commit: "feat(observability): add distributed tracing with Jaeger"

**Success Criteria:**
- Request traces span multiple services
- Jaeger UI shows full request flow
- Performance bottlenecks visible in traces

---

### 3.4 Optimize Metrics Collection
**Priority:** P2 - Reduce self-DDoS
**Estimated Time:** 2 hours
**Files:** `scripts/collect-ai-metrics.sh`

**Tasks:**
- [ ] Add caching for slow-changing metrics (collection counts)
- [ ] Parallelize collection requests
- [ ] Add rate limiting (collect max once per 10s)
- [ ] Reduce collection frequency to 30s (from 5s)
- [ ] Add circuit breaker for metrics collection
- [ ] Test: Verify metrics collection doesn't hammer services
- [ ] Test: Verify cache hit rate
- [ ] Commit: "perf(metrics): optimize collection with caching and parallelization"

**Success Criteria:**
- Metrics collection < 10 requests per collection cycle
- Cache hit rate > 80%
- No performance impact on services

---

## Phase 4: Testing Infrastructure (P1 - Confidence) 🧪

### 4.1 Add Unit Test Framework
**Priority:** P1 - Prevent regressions
**Estimated Time:** 4 hours
**Files:** `ai-stack/mcp-servers/*/test_*.py`

**Tasks:**
- [ ] Add `pytest`, `pytest-asyncio`, `pytest-cov` to requirements.txt
- [ ] Add `conftest.py` with common fixtures
- [ ] Create test directory structure
- [ ] Add mock for sentence-transformers model
- [ ] Add mock for database connections
- [ ] Write tests for embeddings service (10 tests min)
- [ ] Write tests for AIDB server (20 tests min)
- [ ] Configure CI to run tests on commit
- [ ] Test coverage target: 60%
- [ ] Commit: "test: add unit test framework and initial tests"

**Success Criteria:**
- Tests run without loading real models
- All tests pass
- Coverage report generated

---

### 4.2 Add Integration Tests
**Priority:** P1 - Catch service interaction bugs
**Estimated Time:** 4 hours
**Files:** `ai-stack/tests/integration/`

**Tasks:**
- [ ] Add docker-compose.test.yml with test services
- [ ] Write test for full embedding workflow
- [ ] Write test for vector search workflow
- [ ] Write test for service startup order
- [ ] Write test for retry logic
- [ ] Write test for circuit breaker
- [ ] Add test for graceful degradation
- [ ] Commit: "test: add integration tests for service workflows"

**Success Criteria:**
- Tests use real containers (test isolation)
- Tests cover happy path and error cases
- All integration tests pass

---

### 4.3 Add Load Testing
**Priority:** P2 - Know performance limits
**Estimated Time:** 3 hours
**Files:** `ai-stack/tests/load/`

**Tasks:**
- [ ] Add `locust` to requirements.txt
- [ ] Create load test scenarios (embed, search, query)
- [ ] Configure test for 100 concurrent users
- [ ] Run baseline load test, record results
- [ ] Identify bottlenecks from load test
- [ ] Document performance baselines
- [ ] Commit: "test: add load testing with Locust"

**Success Criteria:**
- Load tests run against test environment
- Performance baseline documented
- Bottlenecks identified

---

## Phase 5: Performance Optimization (P2 - Scale) 🚀

### 5.1 Add Connection Pooling
**Priority:** P2 - Reduce connection overhead
**Estimated Time:** 2 hours
**Files:** `ai-stack/mcp-servers/aidb/server.py`

**Tasks:**
- [ ] Configure SQLAlchemy connection pool
- [ ] Configure Redis connection pool
- [ ] Add pool size configuration
- [ ] Add pool monitoring metrics
- [ ] Test: Verify connections reused
- [ ] Test: Verify pool doesn't exhaust connections
- [ ] Commit: "perf(database): add connection pooling"

**Success Criteria:**
- Connection reuse rate > 90%
- No connection exhaustion under load
- Latency improvement measurable

---

### 5.2 Add Request Batching for Embeddings
**Priority:** P2 - Improve throughput
**Estimated Time:** 3 hours
**Files:** `ai-stack/mcp-servers/embeddings-service/server.py`

**Tasks:**
- [ ] Implement request queue for batching
- [ ] Add configurable batch size and timeout
- [ ] Update endpoint to support async batching
- [ ] Add batch size metrics
- [ ] Test: Verify batching improves throughput
- [ ] Test: Verify latency acceptable
- [ ] Commit: "perf(embeddings): add request batching"

**Success Criteria:**
- Throughput increases by 3-5x
- P99 latency < 500ms
- Batch utilization > 70%

---

### 5.3 Add Vector Index Optimization
**Priority:** P2 - Faster searches
**Estimated Time:** 2 hours
**Files:** Database migrations, Qdrant config

**Tasks:**
- [ ] Add HNSW index to pgvector tables
- [ ] Configure Qdrant index parameters
- [ ] Add index build monitoring
- [ ] Benchmark search performance before/after
- [ ] Document index configuration
- [ ] Commit: "perf(vector): optimize indexes for search performance"

**Success Criteria:**
- Search latency reduces by 50%
- Index build time acceptable (< 5min)
- No accuracy loss from indexing

---

### 5.4 Add Caching Layer
**Priority:** P2 - Reduce redundant work
**Estimated Time:** 3 hours
**Files:** `ai-stack/mcp-servers/aidb/server.py`

**Tasks:**
- [ ] Add Redis cache for frequent queries
- [ ] Cache embeddings for common text
- [ ] Cache vector search results (with TTL)
- [ ] Add cache hit/miss metrics
- [ ] Add cache invalidation strategy
- [ ] Test: Verify cache hit rate
- [ ] Commit: "perf(cache): add Redis caching for queries and embeddings"

**Success Criteria:**
- Cache hit rate > 40%
- Cached requests 10x faster
- Cache invalidation works correctly

---

## Phase 6: Configuration & Deployment (P2 - Operations) ⚙️

### 6.1 Centralize Configuration Management
**Priority:** P2 - Reduce config sprawl
**Estimated Time:** 3 hours
**Files:** New `config/` directory

**Tasks:**
- [ ] Create centralized config schema (pydantic)
- [ ] Move all hardcoded values to config files
- [ ] Add config validation on startup
- [ ] Add environment-specific configs (dev/staging/prod)
- [ ] Document all configuration options
- [ ] Test: Verify config validation catches errors
- [ ] Commit: "refactor(config): centralize configuration management"

**Success Criteria:**
- Single source of truth for configuration
- Config validated on startup
- Easy to add new environments

---

### 6.2 Add Database Migrations
**Priority:** P2 - Safe schema changes
**Estimated Time:** 2 hours
**Files:** `ai-stack/migrations/`

**Tasks:**
- [ ] Add `alembic` to requirements.txt
- [ ] Initialize alembic migration structure
- [ ] Create baseline migration from current schema
- [ ] Add migration for vector index optimization
- [ ] Add migration rollback tests
- [ ] Document migration workflow
- [ ] Commit: "feat(database): add Alembic migrations"

**Success Criteria:**
- Schema changes tracked in migrations
- Migrations can roll forward and back
- Clear migration documentation

---

### 6.3 Add Resource Limits Based on Profiling
**Priority:** P2 - Right-size containers
**Estimated Time:** 2 hours
**Files:** `ai-stack/compose/docker-compose.yml`

**Tasks:**
- [ ] Profile actual memory usage of each service
- [ ] Profile actual CPU usage under load
- [ ] Update resource limits based on profiling
- [ ] Add resource reservation (requests)
- [ ] Add swap limits
- [ ] Document resource requirements
- [ ] Test: Verify services don't OOM
- [ ] Commit: "fix(resources): update limits based on profiling"

**Success Criteria:**
- No OOM kills under normal load
- Resources right-sized (not over/under allocated)
- Requirements documented

---

## Phase 7: Documentation & Developer Experience (P3 - Maintenance) 📚

### 7.1 Add Comprehensive API Documentation
**Priority:** P3 - Developer onboarding
**Estimated Time:** 3 hours
**Files:** `docs/api/`

**Tasks:**
- [ ] Add OpenAPI/Swagger specs for all endpoints
- [ ] Add interactive API documentation (Swagger UI)
- [ ] Document authentication requirements
- [ ] Add example requests/responses
- [ ] Document error codes and meanings
- [ ] Commit: "docs: add OpenAPI specs and Swagger UI"

**Success Criteria:**
- All endpoints documented
- Examples work copy-paste
- Swagger UI accessible

---

### 7.2 Add Development Environment Setup
**Priority:** P3 - Developer productivity
**Estimated Time:** 2 hours
**Files:** `docs/development.md`, `Makefile`

**Tasks:**
- [ ] Create Makefile with common tasks
- [ ] Document local development setup
- [ ] Add pre-commit hooks (linting, formatting)
- [ ] Add docker-compose.dev.yml for development
- [ ] Document debugging techniques
- [ ] Commit: "docs: add development environment setup guide"

**Success Criteria:**
- New developer can setup in < 30 minutes
- Common tasks accessible via `make <task>`
- Pre-commit hooks prevent bad commits

---

### 7.3 Add Troubleshooting Guide
**Priority:** P3 - Reduce support burden
**Estimated Time:** 2 hours
**Files:** `docs/troubleshooting.md`

**Tasks:**
- [ ] Document common error messages and fixes
- [ ] Add health check debugging guide
- [ ] Add performance debugging guide
- [ ] Add "service won't start" checklist
- [ ] Add log analysis examples
- [ ] Commit: "docs: add comprehensive troubleshooting guide"

**Success Criteria:**
- Common issues documented with solutions
- Step-by-step debugging procedures
- Log examples with explanations

---

## Progress Tracking

### Completion Status
```
Phase 1 (Critical Stability):    [ ] 0/5 tasks (0%)
Phase 2 (Security Hardening):    [ ] 0/5 tasks (0%)
Phase 3 (Observability):         [ ] 0/4 tasks (0%)
Phase 4 (Testing):               [ ] 0/3 tasks (0%)
Phase 5 (Performance):           [ ] 0/4 tasks (0%)
Phase 6 (Configuration):         [ ] 0/3 tasks (0%)
Phase 7 (Documentation):         [ ] 0/3 tasks (0%)

Overall Progress: 0/27 tasks (0%)
```

### Current Work
**Active Phase:** Phase 1 - Critical Stability Fixes
**Current Task:** 1.1 - Fix Embeddings Service Startup Reliability
**Started:** 2026-01-06
**Status:** 🟡 In Progress

---

## Commit Strategy

**Commit Format:**
```
<type>(<scope>): <short summary>

<detailed description>

Closes: #<issue>
Part of: Production Hardening Phase N
```

**Types:** feat, fix, perf, security, test, docs, refactor

**Commit Frequency:** After each subtask completion

---

## Testing Strategy per Phase

### Phase 1-2: Test Locally
- Run on development machine
- Manual verification of fixes
- Integration tests in docker-compose

### Phase 3-4: Add CI/CD
- GitHub Actions for automated testing
- Test coverage reports
- Automated security scanning

### Phase 5-7: Load Testing
- Dedicated load test environment
- Performance regression testing
- Chaos engineering experiments

---

## Rollback Plan

Each phase is designed to be independently deployable:
1. Each commit is atomic and tested
2. Each phase can be rolled back independently
3. Feature flags for high-risk changes
4. Database migrations are reversible

---

## Success Metrics

### Phase 1 Success:
- [ ] Zero startup race conditions
- [ ] All services start reliably in < 2 minutes
- [ ] Transient failures auto-recover

### Phase 2 Success:
- [ ] Security scan shows zero critical vulnerabilities
- [ ] All endpoints require authentication
- [ ] TLS enabled on all external endpoints

### Phase 3 Success:
- [ ] All critical metrics tracked
- [ ] Dashboard shows health of all services
- [ ] Traces show full request path

### Phase 4 Success:
- [ ] Test coverage > 60%
- [ ] CI/CD pipeline green
- [ ] Load tests establish baseline

### Phase 5 Success:
- [ ] Throughput increased 3x
- [ ] P99 latency < 500ms
- [ ] Resource utilization optimized

### Phase 6 Success:
- [ ] Configuration centralized
- [ ] Deployment automated
- [ ] Rollback tested and works

### Phase 7 Success:
- [ ] Documentation complete
- [ ] New developer onboarding < 30 minutes
- [ ] Support ticket volume reduced

---

**Next:** Start Phase 1.1 - Fix Embeddings Service Startup Reliability
