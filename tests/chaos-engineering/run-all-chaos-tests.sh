#!/usr/bin/env bash
# Master Chaos Engineering Test Runner
# Runs all chaos tests and generates comprehensive report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test results
declare -a TEST_RESULTS
declare -a TEST_NAMES
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

# Run a single test
run_test() {
    local test_script="$1"
    local test_name
    test_name=$(basename "$test_script" .sh)

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    TEST_NAMES+=("$test_name")

    log "\n========================================"
    log "Running Test #$TOTAL_TESTS: $test_name"
    log "========================================"

    chmod +x "$test_script"

    local start_time
    local end_time
    local duration

    start_time=$(date +%s)

    if bash "$test_script"; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))

        TEST_RESULTS+=("PASS")
        PASSED_TESTS=$((PASSED_TESTS + 1))
        success "✓ $test_name PASSED (${duration}s)"
    else
        end_time=$(date +%s)
        duration=$((end_time - start_time))

        TEST_RESULTS+=("FAIL")
        FAILED_TESTS=$((FAILED_TESTS + 1))
        error "✗ $test_name FAILED (${duration}s)"
    fi
}

# Generate comprehensive report
generate_report() {
    local report_file="${SCRIPT_DIR}/99-comprehensive-report/CHAOS-TEST-RESULTS-$(date +%Y%m%d-%H%M%S).md"

    mkdir -p "$(dirname "$report_file")"

    cat > "$report_file" <<EOF
# Chaos Engineering Test Results
**Date:** $(date)
**System:** NixOS AI Stack
**Test Suite:** Comprehensive Chaos Engineering

---

## Executive Summary

**Total Tests:** $TOTAL_TESTS
**Passed:** $PASSED_TESTS ($((PASSED_TESTS * 100 / TOTAL_TESTS))%)
**Failed:** $FAILED_TESTS ($((FAILED_TESTS * 100 / TOTAL_TESTS))%)

**Overall Status:** $([ $FAILED_TESTS -eq 0 ] && echo "✅ PASS" || echo "❌ FAIL")

---

## Test Results

EOF

    # Add detailed results
    for i in "${!TEST_NAMES[@]}"; do
        local test_name="${TEST_NAMES[$i]}"
        local test_result="${TEST_RESULTS[$i]}"
        local status_icon="❌"

        if [ "$test_result" = "PASS" ]; then
            status_icon="✅"
        fi

        echo "### $status_icon Test $((i + 1)): $test_name" >> "$report_file"
        echo "" >> "$report_file"
        echo "**Status:** $test_result" >> "$report_file"
        echo "" >> "$report_file"
    done

    # Add critical findings
    cat >> "$report_file" <<EOF

---

## Critical Findings

EOF

    if [ $FAILED_TESTS -gt 0 ]; then
        cat >> "$report_file" <<EOF
### 🚨 Production Blockers Found

The following critical issues were discovered:

EOF

        for i in "${!TEST_NAMES[@]}"; do
            if [ "${TEST_RESULTS[$i]}" = "FAIL" ]; then
                echo "- ❌ **${TEST_NAMES[$i]}** - System behavior is incorrect" >> "$report_file"
            fi
        done

        cat >> "$report_file" <<EOF

### Recommended Actions

1. **DO NOT DEPLOY TO PRODUCTION** until all failures are fixed
2. Review individual test logs for detailed failure reasons
3. Fix issues in priority order (authentication > database > performance)
4. Re-run full test suite after fixes
5. Consider adding continuous chaos testing to CI/CD

EOF
    else
        cat >> "$report_file" <<EOF
### ✅ No Critical Issues Found

All chaos engineering tests passed. The system demonstrates:

- Graceful degradation under load
- Proper error handling
- Recovery from failures
- Secure authentication
- Database resilience

**System is ready for production deployment.**

EOF
    fi

    # Add recommendations
    cat >> "$report_file" <<EOF

---

## Recommendations for Production

### Immediate Actions (P0)
- [ ] Set up AlertManager with critical alerts
- [ ] Configure automated certificate renewal
- [ ] Implement API key rotation process
- [ ] Add connection pool exhaustion monitoring
- [ ] Set up chaos engineering as part of CI/CD

### Short-term Improvements (P1)
- [ ] Add per-service API keys
- [ ] Implement rate limiting
- [ ] Add comprehensive alerting rules
- [ ] Set up disaster recovery procedures
- [ ] Create runbooks for all failure modes

### Long-term Enhancements (P2)
- [ ] Implement OAuth2/OIDC
- [ ] Add multi-region failover
- [ ] Implement automated chaos testing
- [ ] Add cost monitoring and optimization
- [ ] Create compliance documentation

---

## Test Environment

- **System:** NixOS AI Stack
- **Services Tested:**
  - AIDB MCP Server
  - Hybrid Coordinator
  - PostgreSQL
  - Redis
  - Qdrant
  - llama.cpp
  - nginx TLS

- **Test Categories:**
  - Authentication & Authorization
  - TLS Certificate Management
  - Database Failure Modes
  - Vector Search Edge Cases
  - Circuit Breaker Resilience
  - Full Agent Lifecycle
  - Monitoring & Alerting
  - Load & Chaos Testing

---

**Generated:** $(date)
**Report Location:** $report_file

EOF

    log "\n📊 Comprehensive report generated: $report_file"
    cat "$report_file"
}

# Main execution
main() {
    log "========================================"
    log "  CHAOS ENGINEERING TEST SUITE"
    log "  NixOS AI Stack Resilience Testing"
    log "========================================"
    log ""

    info "This test suite will stress-test the AI stack to find edge cases,"
    info "race conditions, and failure modes that could cause production incidents."
    log ""

    # Find all test scripts
    local test_scripts=()

    # Priority order for tests
    local test_dirs=(
        "06-full-agent-lifecycle"       # Most critical - core functionality
        "01-authentication-torture"     # Security critical
        "03-database-failure-modes"     # Data integrity critical
        "02-tls-certificate-chaos"      # Security infrastructure
        "04-vector-search-edge-cases"   # Core feature testing
        "05-circuit-breaker-race-conditions"  # Resilience testing
        "07-monitoring-and-alerting"    # Operational readiness
        "08-load-and-chaos"             # Performance validation
    )

    for dir in "${test_dirs[@]}"; do
        if [ -d "$SCRIPT_DIR/$dir" ]; then
            while IFS= read -r -d '' test_script; do
                test_scripts+=("$test_script")
            done < <(find "$SCRIPT_DIR/$dir" -name "test-*.sh" -type f -print0 | sort -z)
        fi
    done

    if [ ${#test_scripts[@]} -eq 0 ]; then
        error "No test scripts found!"
        exit 1
    fi

    info "Found ${#test_scripts[@]} test(s) to run"
    log ""

    # Run all tests
    for test_script in "${test_scripts[@]}"; do
        run_test "$test_script"
    done

    # Generate report
    generate_report

    log ""
    log "========================================"
    log "  TEST SUITE COMPLETE"
    log "========================================"
    log ""
    log "Results: $PASSED_TESTS passed, $FAILED_TESTS failed out of $TOTAL_TESTS tests"

    if [ $FAILED_TESTS -eq 0 ]; then
        success "\n✅ ALL CHAOS TESTS PASSED!"
        success "System demonstrates production-grade resilience."
        exit 0
    else
        error "\n❌ CHAOS TESTS FAILED!"
        error "$FAILED_TESTS critical issue(s) discovered."
        error "DO NOT DEPLOY TO PRODUCTION!"
        exit 1
    fi
}

main "$@"
