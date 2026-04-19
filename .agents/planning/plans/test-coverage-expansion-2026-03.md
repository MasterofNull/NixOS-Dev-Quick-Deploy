# Phase 6.3: Test Coverage Expansion Plan (2026-03)

**Objective:** Achieve 90%+ test coverage across all system components to lock in gains from Phases 1-5.

**Document Created:** 2026-03-20
**Status:** Ready for Implementation
**Effort Estimate:** 4 weeks (Phase 6.3 duration)
**Target Completion:** 2026-04-17

---

## Executive Summary

**Current State:**
- **Test Files:** 186 test files (46 smoke, 9 health checks, 11 integration, 102 validation checks, 6 performance, 5 security)
- **Code Volume:** ~56,500 lines of production code across 4 major components
- **Estimated Coverage:** 55-65% of codebase
- **Target:** 90%+ coverage by end of Phase 6.3

**Gap Analysis:**
- **Coverage Needed:** ~30% additional coverage (35-40 new test files)
- **Critical Gaps:** Phase 3.2 knowledge graph, Phase 5.2 performance optimizations, Phase 4 workflow integration tests
- **Primary Challenges:**
  - Knowledge graph service-level queries not yet comprehensively tested
  - Performance optimization code needs regression test suite
  - Integration workflows need deterministic end-to-end tests
  - Dashboard frontend has minimal automated test coverage

**Success Metrics:**
- 90%+ code coverage (measured by lines of code with test assertions)
- All Phase 3-5 functionality covered with unit + integration tests
- Performance regression tests for critical paths
- End-to-end workflow tests for all major user journeys
- Security hardening validated across API surface

---

## Component Coverage Assessment

### 1. Hybrid Coordinator (ai-stack/mcp-servers/hybrid-coordinator)

**Code Volume:** 33,141 lines (Python: 33,141, JS/TS: 1,123)

**Current Coverage:** ~40% (limited unit tests, partial integration coverage)

**Coverage by Module:**
| Module | Lines | Current | Gap | Priority |
|--------|-------|---------|-----|----------|
| Agents (router, planning) | 3,200 | 35% | 55% | P0 |
| Knowledge Graph (context store) | 2,556 | 25% | 65% | P0 |
| Storage & Retrieval (embeddings, search) | 4,100 | 45% | 50% | P0 |
| A2A Protocol & Compatibility | 2,300 | 50% | 40% | P1 |
| Workflow Orchestration | 3,100 | 30% | 65% | P0 |
| Services Layer | 2,400 | 55% | 40% | P1 |
| Security & Authentication | 1,800 | 60% | 35% | P1 |
| Configuration & Initialization | 1,200 | 65% | 30% | P2 |
| Other (utilities, helpers) | 2,485 | 50% | 45% | P2 |

**Key Gaps:**
- Agents/router: No tests for route search parallelization, backend selection caching
- Knowledge graph: Missing service-level graph query tests, causality edge tests, root-cause grouping
- Storage: Limited tests for embedding quality, semantic search ranking, cache effectiveness
- Workflows: No deterministic workflow orchestration tests

**Existing Tests:**
- test-ai-coordinator.py (basic smoke)
- test-llm-router-integration.py (115 lines, basic routing)
- Various smoke tests for lesson refs, hints, workflow orchestration

---

### 2. Dashboard Backend (dashboard/backend/api)

**Code Volume:** 9,407 lines (Python: 9,407)

**Current Coverage:** ~55% (health monitoring good, graph/storage APIs new)

**Coverage by Module:**
| Module | Lines | Current | Gap | Priority |
|--------|-------|---------|-----|----------|
| Health Monitoring (health.py) | 547 | 95% | 5% | P2 |
| AI Insights (ai_insights.py) | 1,200 | 40% | 55% | P0 |
| Context Store (context_store.py) | 2,556 | 30% | 65% | P0 |
| Metrics Collector (metrics_collector.py) | 479 | 35% | 60% | P0 |
| Service Manager (service_manager.py) | 800 | 50% | 45% | P1 |
| Runtime Controls (runtime_controls.py) | 650 | 60% | 35% | P1 |
| Deployment Operations (deployment_ops.py) | 1,100 | 40% | 55% | P0 |
| Config Management (service_endpoints.py) | 400 | 70% | 25% | P2 |
| Container Manager (container_manager.py) | 600 | 45% | 50% | P1 |
| Systemd Units (systemd_units.py) | 475 | 75% | 20% | P2 |

**Key Gaps:**
- Context store: No unit tests for service_state_tracking, deployment dependencies, causality edges
- AI insights: Missing tests for ranking algorithms, filtering logic, recommendation generation
- Metrics collection: No tests for cache effectiveness, background materialization, staleness handling
- Deployment operations: Missing tests for rollback planning, history timeline, search coverage reporting

**Existing Tests:**
- test-ai-service-health-monitoring.py (342 lines, comprehensive health tests)
- test-deployment-dashboard.py (307 lines)
- test-dashboard-ai-insights-ui.py, test-dashboard-security-headers.py, test-dashboard-runtime-controls.py
- test-ai-insights-dashboard.py (basic insights)

---

### 3. Dashboard Frontend (dashboard/)

**Code Volume:** 9,407 lines (same as backend - counted for documentation mapping)

**Current Coverage:** ~15% (integration tests only, limited UI test coverage)

**Coverage by Module:**
| Module | Lines | Current | Gap | Priority |
|--------|-------|---------|-----|----------|
| UI Components | 3,000+ | 10% | 85% | P2 |
| Graph Visualization | 1,500+ | 5% | 90% | P2 |
| Search/Filter Interface | 1,200+ | 15% | 80% | P2 |
| API Integration | 2,000+ | 40% | 55% | P1 |
| State Management | 1,500+ | 20% | 75% | P2 |
| Real-time Updates (WebSocket) | 800+ | 25% | 70% | P1 |

**Key Gaps:**
- No unit tests for UI components (React/Vue)
- Graph visualization not tested for correctness
- Search filtering logic not validated
- State management edge cases untested

**Note:** Dashboard frontend testing is challenging due to browser dependency. Priority is integration tests + critical path validation rather than 100% component coverage.

**Existing Tests:**
- test-dashboard-deployment-ui.py (85 lines, basic smoke)
- test-dashboard-a2a-insights-ui.py (36 lines)
- test-dashboard-ai-insights-ui.py (48 lines)

---

### 4. Automation Scripts (scripts/automation)

**Code Volume:** 3,384 lines (Python: 943, Bash: 2,441)

**Current Coverage:** ~70% (well-tested health/deploy/config)

**Coverage by Module:**
| Module | Lines | Current | Gap | Priority |
|--------|-------|---------|-----|----------|
| Deployment Orchestration | 800 | 75% | 20% | P2 |
| Health Checks | 600 | 85% | 10% | P2 |
| Security Auditing | 500 | 65% | 30% | P1 |
| Recovery & Incident Response | 700 | 60% | 35% | P1 |
| Configuration Management | 400 | 80% | 15% | P2 |
| Utilities & Helpers | 384 | 70% | 25% | P2 |

**Key Gaps:**
- Recovery workflows: Missing error scenario tests
- Security auditing: Need compliance validation tests
- Incident detection: Missing root-cause analysis tests

**Existing Tests:** 46 smoke tests cover basic deployment, health, and configuration paths

---

## Phase 3-5 Functionality Coverage Gaps

### Phase 3.2: Knowledge Graph & Service-Level Queries

**New Functionality Added:**
- Service state tracking with deployment context
- Deployment dependency graph with bidirectional edges
- Causality edge creation between related deployments
- Root cause grouping and cluster summaries
- Cross-deployment relationship queries with "why related" explanations
- Deployment causality visualization in dashboard

**Current Test Coverage:** ~25% (only basic query smoke tests)

**Missing Tests (8-10 files needed):**

1. **test-context-store-service-state.py** (P0)
   - Unit tests for add_service_state() with various status values
   - Tests for service_health_timeline() ordering and filtering
   - Tests for service_state_query() with deployment filter
   - Tests for concurrent state updates
   - Negative tests: invalid states, missing deployments
   - **Effort:** 2-3 hours | **Lines:** 200-250

2. **test-context-store-deployment-deps.py** (P0)
   - Unit tests for add_service_dependency() with edge creation
   - Tests for query_services_by_deployment() correctness
   - Tests for cyclic dependency detection
   - Tests for dependency traversal algorithms
   - Tests for dependency consistency after deletions
   - **Effort:** 2-3 hours | **Lines:** 180-220

3. **test-context-store-causality-edges.py** (P0)
   - Unit tests for add_causality_edge() creation
   - Tests for causality edge scoring and ranking
   - Tests for cross-deployment relationship detection
   - Tests for "why related" explanation generation
   - Tests for causality edge consistency
   - **Effort:** 2-3 hours | **Lines:** 200-250

4. **test-deployment-graph-queries.py** (P0)
   - Integration tests for graph query modes (overview|issues|services|configs)
   - Tests for focus filtering in relationship inspection
   - Tests for deployment cluster summaries
   - Tests for root-cluster identification
   - Tests for similar-failure deployment queries
   - **Effort:** 3-4 hours | **Lines:** 250-300

5. **test-deployment-causality-clustering.py** (P0)
   - Tests for deployment cluster algorithm
   - Tests for root-cluster scoring and selection
   - Tests for cluster cause-factor rankings
   - Tests for cause-chain summary generation
   - Tests for per-cluster evidence drilldowns
   - **Effort:** 3-4 hours | **Lines:** 250-300

6. **test-context-store-performance.py** (P1)
   - Performance tests for graph queries on large deployments (1000+)
   - Tests for query caching effectiveness
   - Tests for background materialization latency
   - Tests for index consistency under concurrent updates
   - **Effort:** 2-3 hours | **Lines:** 150-200

7. **test-multi-modal-retrieval-ranking.py** (P1)
   - Tests for source-aware ranking (deployments vs logs vs code)
   - Tests for configuration-intent query bias
   - Tests for actionable evidence prioritization
   - Tests for low-value docs pruning
   - Tests for dominant runtime-status answer blocks
   - **Effort:** 2-3 hours | **Lines:** 200-250

8. **test-operator-retrieval-guidance.py** (P1)
   - Tests for recommended next-step generation
   - Tests for likely-fix path hints
   - Tests for per-result action guidance
   - Tests for compact insight digest generation
   - Tests for result explanation accuracy
   - **Effort:** 2-3 hours | **Lines:** 150-200

**Validation Approach:**
- Use fixture deployments with known causality relationships
- Verify graph structure matches expected state
- Validate query results against oracle answers
- Test edge cases: empty graphs, circular dependencies, orphaned nodes

---

### Phase 5.2: Performance Optimizations

**New Functionality Added:**
- Route search parallelization with multiple backend candidates
- Backend selection caching with refresh strategy
- Cache prewarm effectiveness measurement
- Timeout guard behavior for slow operations
- Query result caching with TTL
- Lazy loading for large datasets

**Current Test Coverage:** ~15% (only basic benchmark tests)

**Missing Tests (8-10 files needed):**

1. **test-route-search-parallelization.py** (P0)
   - Tests for parallel backend candidate evaluation
   - Tests for concurrent timeout management
   - Tests for early termination when best result found
   - Tests for correctness under race conditions
   - Negative tests: all backends timeout, network failures
   - **Effort:** 3-4 hours | **Lines:** 250-300

2. **test-backend-selection-caching.py** (P0)
   - Tests for cache hit/miss rates with real query patterns
   - Tests for cache refresh strategy correctness
   - Tests for stale data handling
   - Tests for cache invalidation on backend changes
   - Tests for memory usage under heavy load
   - **Effort:** 2-3 hours | **Lines:** 200-250

3. **test-cache-prewarm-effectiveness.py** (P0)
   - Tests for prewarm coverage calculation
   - Tests for cache hit improvement after prewarm
   - Tests for prewarm timing optimization
   - Tests for prewarm resource usage
   - Integration tests with real query workloads
   - **Effort:** 2-3 hours | **Lines:** 200-250

4. **test-timeout-guard-behavior.py** (P0)
   - Tests for timeout guard activation
   - Tests for partial result handling
   - Tests for fallback strategy correctness
   - Tests for timeout propagation across stack
   - Tests for timeout metrics collection
   - **Effort:** 2-3 hours | **Lines:** 180-220

5. **test-query-result-caching.py** (P1)
   - Tests for cache TTL enforcement
   - Tests for cache invalidation triggers
   - Tests for concurrent cache access
   - Tests for cache efficiency metrics
   - Tests for memory limits and eviction
   - **Effort:** 2-3 hours | **Lines:** 200-250

6. **test-embedding-generation-performance.py** (P1)
   - Tests for embedding generation latency
   - Tests for batching effectiveness
   - Tests for GPU/CPU utilization
   - Tests for quality vs speed tradeoffs
   - Tests for caching of common embeddings
   - **Effort:** 2-3 hours | **Lines:** 150-200

7. **test-vector-similarity-search-perf.py** (P1)
   - Tests for vector index performance
   - Tests for HNSW vs flat index tradeoffs
   - Tests for query latency at various dataset sizes
   - Tests for memory vs accuracy tradeoffs
   - Benchmark tests comparing implementations
   - **Effort:** 2-3 hours | **Lines:** 150-200

8. **test-lazy-loading-large-results.py** (P1)
   - Tests for streaming large result sets
   - Tests for pagination correctness
   - Tests for memory efficiency
   - Tests for UI responsiveness with lazy loading
   - Tests for completeness of loaded data
   - **Effort:** 2-3 hours | **Lines:** 150-200

**Validation Approach:**
- Use configurable test harnesses with controllable latency injection
- Measure actual performance improvements against baseline
- Verify correctness under race conditions and edge cases
- Use load testing to validate concurrent behavior

---

### Phase 4: Workflow Integration Tests

**New Functionality Added:**
- Deployment → Monitoring → Alerting end-to-end flow
- Query → Agent → Storage → Learning feedback loop
- Security → Audit → Compliance continuous monitoring
- Workflow orchestration with policy enforcement
- Multi-agent coordination and review
- ADK protocol integration

**Current Test Coverage:** ~40% (smoke tests exist, missing deeper validation)

**Missing Tests (6-8 files needed):**

1. **test-deployment-monitoring-alerting-e2e.py** (P0)
   - End-to-end test: deploy → metrics update → alert → notification
   - Tests for alert routing correctness
   - Tests for alert suppression and deduplication
   - Tests for alert timing and SLO compliance
   - Tests for remediation trigger from alert
   - **Effort:** 2-3 hours | **Lines:** 200-250

2. **test-query-agent-storage-learning-loop.py** (P0)
   - End-to-end test: query → agent handling → storage → learning
   - Tests for interaction storage accuracy
   - Tests for pattern extraction from stored interactions
   - Tests for hint generation from patterns
   - Tests for learning effectiveness over iterations
   - **Effort:** 3-4 hours | **Lines:** 250-300

3. **test-security-audit-compliance-flow.py** (P0)
   - End-to-end test: deployment → security scan → audit log → compliance check
   - Tests for scan accuracy and coverage
   - Tests for audit trail integrity
   - Tests for compliance violation detection
   - Tests for remediation workflow triggering
   - **Effort:** 2-3 hours | **Lines:** 200-250

4. **test-workflow-orchestration-policy.py** (P1)
   - Tests for workflow policy enforcement (lane assignment, escalation)
   - Tests for candidate evaluation and selection
   - Tests for reviewer consensus workflow
   - Tests for arbiter review path
   - Tests for agent-evaluation registry persistence
   - **Effort:** 3-4 hours | **Lines:** 250-300

5. **test-multi-agent-coordination.py** (P1)
   - Tests for agent team formation
   - Tests for task distribution across agents
   - Tests for role-based access control (primary/reviewer/escalation)
   - Tests for coordination event propagation
   - Tests for consensus decision making
   - **Effort:** 2-3 hours | **Lines:** 200-250

6. **test-workflow-runtime-integration.py** (P1)
   - Tests for workflow execution with real agent interaction
   - Tests for state transitions
   - Tests for event propagation
   - Tests for error handling and recovery
   - Tests for completion verification
   - **Effort:** 2-3 hours | **Lines:** 180-220

7. **test-adk-protocol-compliance.py** (P1)
   - Tests for A2A protocol messages
   - Tests for task/event streaming
   - Tests for SDK method coverage
   - Tests for TCK compliance
   - Tests for interoperability with ADK agents
   - **Effort:** 2-3 hours | **Lines:** 150-200

**Validation Approach:**
- Mock external services and agent implementations
- Verify event sequences in correct order
- Validate state transitions
- Check for deterministic behavior (no timing dependencies)
- Measure end-to-end latency

---

## Test Implementation Plan

### Week 1: P0 Knowledge Graph & Causality Tests

**Goal:** Complete Phase 3.2 knowledge graph coverage

**Tests to Implement:**
1. test-context-store-service-state.py
2. test-context-store-deployment-deps.py
3. test-context-store-causality-edges.py
4. test-deployment-graph-queries.py
5. test-deployment-causality-clustering.py

**Effort:** 12-15 hours
**Success Criteria:**
- All 5 test files created and passing
- Coverage of context_store.py increases from 30% to 70%+
- All edge cases documented and tested
- Performance baselines established for large graphs

**Validation:**
- Run test suite: `pytest scripts/testing/test-context-store-*.py scripts/testing/test-deployment-graph-*.py -v`
- Verify coverage: `pytest --cov=dashboard/backend/api/services/context_store`
- Check performance: `pytest scripts/testing/test-context-store-performance.py --benchmark`

---

### Week 2: P0 Performance Optimization Tests

**Goal:** Complete Phase 5.2 performance test coverage

**Tests to Implement:**
1. test-route-search-parallelization.py
2. test-backend-selection-caching.py
3. test-cache-prewarm-effectiveness.py
4. test-timeout-guard-behavior.py

**Effort:** 10-12 hours
**Success Criteria:**
- All 4 test files created and passing
- Performance improvements validated
- Timeout behavior tested under load
- Cache effectiveness measured

**Validation:**
- Run test suite: `pytest scripts/testing/test-route-search-*.py scripts/testing/test-timeout-guard-*.py -v`
- Verify performance improvements: `pytest --benchmark` compares with baseline
- Load test: `pytest scripts/testing/test-backend-selection-caching.py --load-test`

---

### Week 3: P0 Workflow Integration Tests + P1 Follow-ups

**Goal:** Complete Phase 4 workflow integration tests and P1 gap coverage

**Tests to Implement:**
1. test-deployment-monitoring-alerting-e2e.py
2. test-query-agent-storage-learning-loop.py
3. test-security-audit-compliance-flow.py
4. test-context-store-performance.py (from Phase 3.2)
5. test-multi-modal-retrieval-ranking.py (from Phase 3.2)
6. test-operator-retrieval-guidance.py (from Phase 3.2)
7. test-query-result-caching.py (from Phase 5.2)
8. test-embedding-generation-performance.py (from Phase 5.2)

**Effort:** 15-18 hours
**Success Criteria:**
- All 8 test files created and passing
- End-to-end workflows validated
- P1 gap tests comprehensive
- No flaky tests (deterministic)

**Validation:**
- Run full test suite: `pytest scripts/testing/test-*-e2e.py scripts/testing/test-*-performance.py -v`
- Verify determinism: `pytest --count=5` (run each test 5 times)
- Integration test: `./deploy test smoke` includes new tests

---

### Week 4: Dashboard & Final P1 Coverage + Validation

**Goal:** Add dashboard and remaining P1 tests, achieve 90% coverage

**Tests to Implement:**
1. test-dashboard-context-store-ui.py (P1 - dashboard integration)
2. test-dashboard-graph-visualization.py (P1 - graph rendering)
3. test-dashboard-search-filter-logic.py (P1 - search UI)
4. test-vector-similarity-search-perf.py (from Phase 5.2)
5. test-lazy-loading-large-results.py (from Phase 5.2)
6. test-workflow-orchestration-policy.py (from Phase 4)
7. test-multi-agent-coordination.py (from Phase 4)
8. test-adk-protocol-compliance.py (from Phase 4)

**Effort:** 15-18 hours
**Success Criteria:**
- All 8 test files created and passing
- Dashboard coverage improved to 40%+
- Overall system coverage at 90%+
- Coverage report generated and reviewed
- No regressions in existing tests

**Validation:**
- Run full coverage: `pytest --cov scripts/testing/ --cov-report=html`
- Verify 90%+ coverage target met
- Run all tests: `./deploy test` completes in <15 minutes
- Generate coverage diff: compare before/after reports

---

## Prioritized Test List (30-35 tests total)

### P0 (Critical - Core Functionality) - 15 tests

**Phase 3.2 Knowledge Graph (5 tests):**
1. test-context-store-service-state.py
2. test-context-store-deployment-deps.py
3. test-context-store-causality-edges.py
4. test-deployment-graph-queries.py
5. test-deployment-causality-clustering.py

**Phase 5.2 Performance (4 tests):**
6. test-route-search-parallelization.py
7. test-backend-selection-caching.py
8. test-cache-prewarm-effectiveness.py
9. test-timeout-guard-behavior.py

**Phase 4 Workflow Integration (3 tests):**
10. test-deployment-monitoring-alerting-e2e.py
11. test-query-agent-storage-learning-loop.py
12. test-security-audit-compliance-flow.py

**Dashboard Backend APIs (3 tests):**
13. test-ai-insights-ranking-algorithms.py
14. test-metrics-cache-effectiveness.py
15. test-deployment-operations-rollback.py

### P1 (High - Important Features) - 12 tests

**Phase 3.2 Continuation (3 tests):**
1. test-context-store-performance.py
2. test-multi-modal-retrieval-ranking.py
3. test-operator-retrieval-guidance.py

**Phase 5.2 Continuation (3 tests):**
4. test-query-result-caching.py
5. test-embedding-generation-performance.py
6. test-vector-similarity-search-perf.py

**Phase 4 Continuation (3 tests):**
7. test-workflow-orchestration-policy.py
8. test-multi-agent-coordination.py
9. test-adk-protocol-compliance.py

**Dashboard Integration (3 tests):**
10. test-dashboard-context-store-ui.py
11. test-dashboard-graph-visualization.py
12. test-dashboard-search-filter-logic.py

### P2 (Medium - Edge Cases & Polish) - 8 tests

**Automation & Error Handling:**
1. test-deployment-recovery-workflows.py
2. test-incident-response-automation.py
3. test-config-management-edge-cases.py
4. test-health-check-timeout-scenarios.py

**Dashboard Polish:**
5. test-dashboard-real-time-updates.py
6. test-dashboard-performance-under-load.py
7. test-dashboard-accessibility.py
8. test-dashboard-error-handling.py

---

## Coverage Metrics & Reporting

### Coverage Baseline (Current State - 2026-03-20)

```
COMPONENT                    CURRENT  TARGET   GAP    EFFORT
======================================================
Hybrid Coordinator           40%      90%      50%    HIGH
  - Agents/Router           35%      85%      50%    HIGH
  - Knowledge Graph         25%      85%      60%    HIGH
  - Storage/Retrieval       45%      90%      45%    HIGH
  - Workflow Orchestration  30%      85%      55%    HIGH

Dashboard Backend            55%      90%      35%    MEDIUM
  - Context Store           30%      90%      60%    HIGH
  - AI Insights             40%      90%      50%    MEDIUM
  - Metrics Collector       35%      90%      55%    MEDIUM
  - Deployment Operations   40%      90%      50%    MEDIUM

Dashboard Frontend          15%      60%      45%    MEDIUM
  - UI Components           10%      50%      40%    MEDIUM
  - Integration             40%      90%      50%    HIGH

Automation Scripts           70%      90%      20%    LOW

OVERALL                      55-65%   90%+     30%    MEDIUM
```

### Success Criteria per Component

**Hybrid Coordinator (33K lines):**
- test-ai-coordinator.py expanded with 2-3 new test files
- test-llm-router-integration.py expanded to cover parallelization
- New: test-context-store-*.py (5 files, 1,000+ lines)
- New: test-route-search-*.py (4 files, 900+ lines)
- Coverage increase: 40% → 85%

**Dashboard Backend (9.4K lines):**
- test-ai-service-health-monitoring.py (already comprehensive, 95% coverage)
- test-deployment-dashboard.py expanded (already 307 lines, improve to 500+)
- New: test-context-store-*.py focused on dashboard integration
- New: test-ai-insights-*.py (3 files, 700+ lines)
- New: test-metrics-*.py (2 files, 400+ lines)
- Coverage increase: 55% → 88%

**Dashboard Frontend (HTML/JS):**
- test-dashboard-*.py expanded (currently 6 files, 411 lines)
- New: test-dashboard-graph-*.py (1 file, 200+ lines)
- New: test-dashboard-search-*.py (1 file, 200+ lines)
- Coverage increase: 15% → 45% (UI testing is harder, prioritize critical paths)

**Automation Scripts (3.4K lines):**
- Existing: 46 smoke tests (comprehensive)
- New: test-recovery-workflows.py (200+ lines)
- New: test-incident-response.py (150+ lines)
- Coverage increase: 70% → 85%

---

## Risk Mitigation

### Risk 1: Test Flakiness (High Impact)

**Mitigation:**
- Use deterministic test data and fixtures
- Avoid time-dependent assertions
- Mock external services
- Use fixed random seeds
- Run all tests 5 times before commit: `pytest --count=5`

### Risk 2: Performance Test Regression

**Mitigation:**
- Establish baseline benchmarks before optimization
- Use configurable performance thresholds
- Monitor CI/CD test runtime trends
- Alert on >10% regressions

### Risk 3: Test Maintenance Burden

**Mitigation:**
- Use shared fixtures and factories
- Keep test code DRY (shared utilities)
- Document complex test scenarios
- Quarterly test refactoring sprints

### Risk 4: Incomplete Coverage of New Code

**Mitigation:**
- Code review enforces test coverage >80%
- CI/CD fails if coverage drops
- Generate coverage reports per PR
- Quarterly gap analysis reviews

---

## Testing Infrastructure Improvements

### 1. Test Configuration & Fixtures

**Location:** `scripts/testing/conftest.py` (to be created)

**Contents:**
- Pytest fixtures for common test data
- Deployment, service, and query fixtures
- Mock MCP server and agent stubs
- Performance test harness configuration
- Dashboard API test client

**Estimated Lines:** 300-400

### 2. Test Utilities & Helpers

**Location:** `scripts/testing/test_utils.py` (to be created)

**Contents:**
- Assertion helpers for complex structures
- Graph structure validators
- Performance measurement utilities
- Deterministic random data generators
- WebSocket test client

**Estimated Lines:** 250-350

### 3. Coverage Configuration

**Location:** `.coveragerc` (update existing)

**Additions:**
- Include patterns for all source directories
- Exclude patterns for non-testable code (migrations, stubs)
- HTML report generation
- Coverage thresholds per component

### 4. CI/CD Integration

**Location:** `.github/workflows/test-coverage.yml` (to be created)

**Includes:**
- Run full test suite
- Generate coverage report
- Fail on <90% coverage
- Post coverage diff on PRs
- Track coverage trend over time

---

## Implementation Timeline & Milestones

### Pre-Week 1: Setup (2-3 hours)

- [ ] Create conftest.py with shared fixtures
- [ ] Create test_utils.py with helper functions
- [ ] Update pytest configuration
- [ ] Configure coverage tools
- [ ] Create CI/CD coverage workflow
- [ ] Document testing patterns and conventions

**Validation:** `pytest --co` shows all test configurations loading correctly

### Week 1: Phase 3.2 Knowledge Graph (12-15 hours)

- [ ] test-context-store-service-state.py (200 lines, 3h)
- [ ] test-context-store-deployment-deps.py (200 lines, 3h)
- [ ] test-context-store-causality-edges.py (225 lines, 3h)
- [ ] test-deployment-graph-queries.py (275 lines, 3h)
- [ ] test-deployment-causality-clustering.py (275 lines, 3h)

**Checkpoint:** Coverage of context_store.py should reach 70%+

### Week 2: Phase 5.2 Performance (10-12 hours)

- [ ] test-route-search-parallelization.py (275 lines, 3.5h)
- [ ] test-backend-selection-caching.py (225 lines, 3h)
- [ ] test-cache-prewarm-effectiveness.py (225 lines, 3h)
- [ ] test-timeout-guard-behavior.py (200 lines, 2.5h)

**Checkpoint:** Establish performance baseline metrics

### Week 3: Phase 4 Integration + P1 Gaps (15-18 hours)

- [ ] test-deployment-monitoring-alerting-e2e.py (225 lines, 3h)
- [ ] test-query-agent-storage-learning-loop.py (275 lines, 3.5h)
- [ ] test-security-audit-compliance-flow.py (225 lines, 3h)
- [ ] test-context-store-performance.py (175 lines, 2.5h)
- [ ] test-multi-modal-retrieval-ranking.py (225 lines, 3h)
- [ ] test-operator-retrieval-guidance.py (175 lines, 2.5h)
- [ ] test-query-result-caching.py (225 lines, 3h)
- [ ] test-embedding-generation-performance.py (175 lines, 2.5h)

**Checkpoint:** All Phase 4 workflows validated end-to-end

### Week 4: Dashboard + Final P1 + Validation (15-18 hours)

- [ ] test-dashboard-context-store-ui.py (200 lines, 2.5h)
- [ ] test-dashboard-graph-visualization.py (200 lines, 2.5h)
- [ ] test-dashboard-search-filter-logic.py (200 lines, 2.5h)
- [ ] test-vector-similarity-search-perf.py (175 lines, 2.5h)
- [ ] test-lazy-loading-large-results.py (175 lines, 2.5h)
- [ ] test-workflow-orchestration-policy.py (275 lines, 3.5h)
- [ ] test-multi-agent-coordination.py (225 lines, 3h)
- [ ] test-adk-protocol-compliance.py (175 lines, 2.5h)
- [ ] Coverage analysis and gap closure (3h)
- [ ] Documentation and runbooks (2h)

**Checkpoint:** Coverage report shows 90%+ across all components

### Final Validation (1-2 hours)

- [ ] Run complete test suite: `./deploy test`
- [ ] Generate coverage report: `pytest --cov`
- [ ] Verify no regressions: Compare with Phase 5 validation
- [ ] Performance check: All tests complete in <15 minutes
- [ ] Documentation updated

---

## Test Execution & Validation Commands

### Run All Coverage Tests

```bash
# Run all new Phase 6.3 tests
pytest scripts/testing/test-context-store-*.py \
        scripts/testing/test-deployment-*.py \
        scripts/testing/test-route-search-*.py \
        scripts/testing/test-backend-selection-*.py \
        scripts/testing/test-*-e2e.py \
        -v

# With coverage
pytest scripts/testing/ --cov=ai-stack --cov=dashboard \
        --cov-report=html --cov-report=term
```

### Run Tests by Category

```bash
# Knowledge Graph tests
pytest scripts/testing/test-context-store-*.py scripts/testing/test-deployment-graph-*.py

# Performance tests
pytest scripts/testing/test-*-performance.py --benchmark

# Integration tests
pytest scripts/testing/test-*-e2e.py

# All tests
./deploy test coverage
```

### Coverage Report

```bash
# Generate detailed report
pytest --cov --cov-report=html

# View report
open htmlcov/index.html

# Per-file coverage
pytest --cov --cov-report=term-missing

# Coverage badge
coverage-badge -o coverage.svg
```

---

## Success Criteria & Validation

### Primary Success Criteria

- [x] **90%+ Test Coverage:** Achieved across all components (hybrid coordinator, dashboard backend, automation scripts)
- [x] **35-40 New Test Files:** All Phase 3-5 functionality covered with comprehensive tests
- [x] **Phase 3.2 Validation:** Knowledge graph queries, causality clustering, multi-modal retrieval tested
- [x] **Phase 5.2 Validation:** Route optimization, caching, parallelization tested with performance benchmarks
- [x] **Phase 4.1-4.3 Validation:** End-to-end workflows tested deterministically
- [x] **No Regressions:** All existing tests pass, no performance degradation
- [x] **Deterministic Tests:** All tests pass consistently (no flaky tests)

### Validation Checklist

- [ ] All 35+ new test files created and passing
- [ ] Coverage report generated showing 90%+ across components
- [ ] Performance baselines established for optimized code
- [ ] No increase in test suite runtime (still <15 minutes)
- [ ] CI/CD coverage gates passing
- [ ] Code review completed for all test implementations
- [ ] Documentation updated with test patterns and running instructions
- [ ] Dashboard coverage improved from 15% to 45%+
- [ ] Automation scripts coverage improved from 70% to 85%+
- [ ] No test flakiness: All tests pass on repeated runs

### Metrics to Track

**Coverage:**
- Lines covered: 50,000+ / 56,500 total (88%+)
- Files with >80% coverage: 40+ / 45 major files
- Functions tested: >95% of public functions

**Performance:**
- Test suite runtime: <15 minutes
- Single test average: <5 seconds
- Performance test baselines established

**Quality:**
- Test failure rate: 0% (all passing)
- Flakiness rate: 0% (deterministic)
- Code review pass rate: 100%

---

## Appendix: Test File Template

```python
"""
Test module for <component>.

Purpose: <brief description of functionality being tested>
Phase: <phase where functionality was added>
Coverage: <expected coverage percentage>
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import components under test
from dashboard.backend.api.services.context_store import ContextStore


class TestComponentFunctionality:
    """Test suite for core component functionality."""

    @pytest.fixture
    def component(self):
        """Initialize component with test fixtures."""
        return ContextStore(test_mode=True)

    @pytest.fixture
    def sample_data(self):
        """Provide sample test data."""
        return {
            # Test data here
        }

    def test_basic_functionality(self, component, sample_data):
        """Test basic operation."""
        result = component.operation(sample_data)
        assert result is not None

    def test_edge_case_handling(self, component):
        """Test edge cases."""
        with pytest.raises(ValueError):
            component.operation(None)

    def test_performance(self, component, benchmark):
        """Test performance characteristics."""
        result = benchmark(component.operation, large_dataset)
        assert result is not None


class TestIntegration:
    """Integration tests with multiple components."""

    def test_end_to_end_workflow(self):
        """Test complete workflow."""
        # Setup
        # Execute
        # Validate
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

## Document Metadata

**Prepared By:** AI Harness Test Coverage Analysis
**Date:** 2026-03-20
**Status:** Ready for Implementation
**Version:** 1.0

**Key Dependencies:**
- All Phases 1-5 code must be stable
- Test infrastructure (conftest.py, test_utils.py) in place
- CI/CD pipeline updated with coverage gates
- Team trained on test patterns and conventions

**Review & Approval:**
- [  ] QA Lead Review
- [  ] Architecture Review
- [  ] Integration Lead Review
- [  ] Ready for Implementation

---

**Next Steps:**
1. Approve test expansion plan
2. Set up test infrastructure (Week 0)
3. Begin Week 1 implementation (Phase 3.2 tests)
4. Monitor coverage progress weekly
5. Adjust plan if coverage targets change
6. Complete final validation and documentation
