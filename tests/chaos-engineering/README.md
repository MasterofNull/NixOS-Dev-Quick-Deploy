# Chaos Engineering Test Suite
**Purpose:** Find production failures BEFORE they happen
**Status:** 🔴 CRITICAL - Run before any production deployment
**Created:** 2026-01-09

---

## What This Is

This is a **comprehensive chaos engineering test suite** designed to stress-test the AI stack and expose edge cases, race conditions, and failure modes that WILL cause production incidents if not fixed.

### Why This Exists

The system claimed to be "production-ready" with:
- ✅ Unit tests (30/30 passing)
- ✅ Integration tests (7/7 passing)
- ✅ Load tests (baseline recorded)

But it was missing **THE MOST IMPORTANT TESTS**:

- ❌ End-to-end agent lifecycle tests
- ❌ Authentication edge case testing
- ❌ TLS certificate failure scenarios
- ❌ Database connection pool exhaustion
- ❌ Circuit breaker race conditions
- ❌ Real-world failure mode testing

This test suite fills that gap.

---

## Quick Start

```bash
# Run all chaos tests (recommended)
./run-all-chaos-tests.sh

# Run specific test category
./06-full-agent-lifecycle/test-agent-progressive-disclosure.sh

# Run database chaos tests
./03-database-failure-modes/test-connection-pool-exhaustion.sh
```

---

## Test Categories

### 1. Authentication Torture (`01-authentication-torture/`)
**Tests:** API key validation, malformed inputs, concurrent auth storms

**Critical Findings Expected:**
- API key files with mode 0444 (world-readable)
- No key rotation mechanism
- No rate limiting

---

### 2. TLS Certificate Chaos (`02-tls-certificate-chaos/`)
**Tests:** Expired certs, missing files, renewal under load

**Critical Findings Expected:**
- No cert expiration monitoring
- Manual renewal process (will be forgotten)

---

### 3. Database Failure Modes (`03-database-failure-modes/`)
**Tests:** Connection pool exhaustion, read-only mode, disk full

**Critical Findings Expected:**
- Pool configuration too small (30 connections max)
- No connection leak detection
- Cascading failures on pool exhaustion

**Example Test:**
```bash
# Test connection pool under extreme load
./test-connection-pool-exhaustion.sh

# This test will:
# 1. Establish baseline (5 requests)
# 2. Saturate pool (30 concurrent requests)
# 3. Exhaust pool (80 concurrent requests)
# 4. Validate graceful degradation
# 5. Test recovery after exhaustion
```

---

### 4. Vector Search Edge Cases (`04-vector-search-edge-cases/`)
**Tests:** Empty collections, malicious queries, NaN embeddings

**Critical Findings Expected:**
- No query size validation
- No pagination limits
- Path traversal vulnerabilities

---

### 5. Circuit Breaker Race Conditions (`05-circuit-breaker-race-conditions/`)
**Tests:** Concurrent failures, state transition races

**Critical Findings Expected:**
- Thread-unsafe counter increments
- State transition windows
- Recovery race conditions

---

### 6. Full Agent Lifecycle (`06-full-agent-lifecycle/`)
**Tests:** Progressive disclosure, continuous learning, hybrid routing

**The Most Important Test:** `test-agent-progressive-disclosure.sh`

This test validates the **core claim** of the system:
> "220 tokens vs 3000+ without progressive disclosure"

**Test Steps:**
1. Health check (~20 tokens)
2. Discovery info (~50 tokens)
3. Quickstart guide (~150 tokens)
4. Validate total < 300 tokens
5. Test error handling

**Pass Criteria:**
- Total tokens ≤ 300 (vs claimed 220)
- All API calls return 200
- Invalid auth properly rejected
- Error responses are well-formed

**Example Run:**
```bash
./06-full-agent-lifecycle/test-agent-progressive-disclosure.sh

# Expected output:
# ✅ Health check passed (~20 tokens)
# ✅ Discovery info passed (~50 tokens)
# ✅ Quickstart guide passed (~150 tokens)
# ✅ Total tokens: 220 (73% savings vs 3000+)
# ✅ ALL TESTS PASSED!
```

---

### 7. Monitoring & Alerting (`07-monitoring-and-alerting/`)
**Tests:** Alert rules, metric accuracy, trace completeness

**Critical Findings Expected:**
- No AlertManager configuration
- No critical alert rules
- No alert testing

---

### 8. Load & Chaos (`08-load-and-chaos/`)
**Tests:** 1000 concurrent agents, random crashes, network chaos

**Critical Findings Expected:**
- System death under 100+ concurrent requests
- No graceful degradation
- Cascade failures

---

## How to Use This Suite

### Pre-Production Checklist

Before deploying to production, you MUST:

1. ✅ Run full chaos test suite: `./run-all-chaos-tests.sh`
2. ✅ Review comprehensive report in `99-comprehensive-report/`
3. ✅ Fix ALL P0 issues found
4. ✅ Re-run tests until 100% pass
5. ✅ Add chaos testing to CI/CD

### Continuous Chaos Testing

Add to CI/CD pipeline:

```yaml
# .github/workflows/chaos-tests.yml
name: Chaos Engineering Tests

on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Mondays

jobs:
  chaos-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Chaos Tests
        run: |
          ./tests/chaos-engineering/run-all-chaos-tests.sh
      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: chaos-test-report
          path: tests/chaos-engineering/99-comprehensive-report/
```

---

## Expected Failures

### On First Run

You WILL see failures in:

1. **Authentication Tests**
   - API key permissions (0444 instead of 0400)
   - No key rotation
   - No rate limiting

2. **Database Tests**
   - Connection pool exhaustion
   - No leak detection
   - Poor recovery

3. **TLS Tests**
   - No expiration monitoring
   - Manual renewal

4. **Circuit Breaker Tests**
   - Race conditions
   - Unsafe state transitions

### After Fixes

You SHOULD see:

- ✅ 100% test pass rate
- ✅ Graceful degradation under load
- ✅ Proper error handling
- ✅ Fast recovery from failures

---

## Adding New Tests

### Test Template

```bash
#!/usr/bin/env bash
# Test: <Description>
# Validates: <What you're testing>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Test configuration
BASE_URL="https://localhost:8443"
CACERT="${PROJECT_ROOT}/ai-stack/tls/localhost.crt"
API_KEY_FILE="${PROJECT_ROOT}/ai-stack/secrets/generated/stack_api_key"

# Test logic here
test_something() {
    # Make API calls
    # Validate responses
    # Check edge cases
    # Return 0 for pass, 1 for fail
}

main() {
    test_something || exit 1
    echo "✅ TEST PASSED"
    exit 0
}

main "$@"
```

---

## Interpreting Results

### Test Report Location

After running `./run-all-chaos-tests.sh`, find the comprehensive report at:

```
99-comprehensive-report/CHAOS-TEST-RESULTS-<timestamp>.md
```

### Report Sections

1. **Executive Summary** - Pass/fail counts
2. **Test Results** - Detailed per-test results
3. **Critical Findings** - Issues that MUST be fixed
4. **Recommendations** - Prioritized action items

### Pass Criteria

**System is production-ready when:**

- ✅ 100% of tests pass
- ✅ No P0 critical findings
- ✅ All edge cases handled gracefully
- ✅ Recovery from failures is automatic
- ✅ Monitoring and alerting in place

---

## Critical Issues You WILL Find

Based on code review, expect to find:

### P0 - Critical (Production Blockers)

1. **API Key Security**
   - File mode 0444 (world-readable)
   - No rotation mechanism
   - Same key for all services

2. **Database Pool Exhaustion**
   - Pool too small (30 max)
   - No graceful degradation
   - Cascading failures

3. **Circuit Breaker Races**
   - Thread-unsafe counters
   - State transition bugs
   - Recovery failures

### P1 - High (Fix Soon)

1. **TLS Certificate Management**
   - No expiration monitoring
   - Manual renewal process
   - Hardcoded localhost

2. **Query Validation**
   - No size limits
   - No pagination
   - Injection vulnerabilities

3. **Monitoring Gaps**
   - No AlertManager
   - No critical alerts
   - No SLO tracking

---

## Next Steps After Testing

### If Tests Pass (Unlikely on First Run)

1. Review report for any warnings
2. Add chaos testing to CI/CD
3. Set up continuous monitoring
4. Proceed with production deployment

### If Tests Fail (Expected)

1. **DO NOT DEPLOY TO PRODUCTION**
2. Review `CRITICAL-SYSTEM-REVIEW.md` for full analysis
3. Fix issues in priority order:
   - P0 first (security, data integrity)
   - P1 next (resilience, monitoring)
   - P2 later (performance, features)
4. Re-run tests after each fix
5. Achieve 100% pass before production

---

## Maintenance

### Weekly Tasks

- Run full chaos suite
- Review any new failures
- Update tests for new features

### After Each Deployment

- Run smoke tests (subset of chaos tests)
- Validate no regressions
- Update baselines if needed

### When Adding Features

- Add chaos tests for new code paths
- Test edge cases
- Validate failure modes

---

## Support

**Questions?** Review:
- `CRITICAL-SYSTEM-REVIEW.md` - Detailed failure analysis
- Individual test logs in `${TMPDIR:-/tmp}/chaos-test-*.log`
- Comprehensive report in `99-comprehensive-report/`

**Found a new edge case?** Add a test and submit a PR!

---

**Remember:** The goal of chaos engineering is to find failures in a controlled environment before they cause production outages. Every failure found here is a potential disaster avoided in production.

**Run these tests. Fix the issues. Save your production environment.**
