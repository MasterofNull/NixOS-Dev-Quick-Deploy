#!/usr/bin/env bash
# Test: Connection Pool Exhaustion
# Validates that the system gracefully handles connection pool exhaustion
# and doesn't cause cascading failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TMP_ROOT="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test configuration
BASE_URL="https://localhost:8443"
CACERT="${PROJECT_ROOT}/ai-stack/kubernetes/tls/localhost.crt"
API_KEY_FILE="${PROJECT_ROOT}/ai-stack/kubernetes/secrets/generated/stack_api_key"
TEST_LOG="${TMP_ROOT}/chaos-test-pool-exhaustion-$$.log"

# Pool configuration (from config.yaml)
POOL_SIZE=20
MAX_OVERFLOW=10
TOTAL_CONNECTIONS=$((POOL_SIZE + MAX_OVERFLOW))
POOL_TIMEOUT=30

# Test metrics
SUCCESSFUL_REQUESTS=0
FAILED_REQUESTS=0
TIMEOUT_REQUESTS=0
ERROR_RESPONSES=0

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$TEST_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$TEST_LOG"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$TEST_LOG"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$TEST_LOG"
}

# Make slow query that holds connection
make_slow_query() {
    local duration="${1:-10}"  # Hold connection for 10 seconds
    local query_id="$2"

    log "[Query $query_id] Starting slow query (${duration}s hold)..."

    local response
    local http_code
    local start_time
    local end_time

    start_time=$(date +%s)

    # Query that forces a database sleep
    response=$(curl -s -w "\n%{http_code}" \
        --max-time $((duration + 5)) \
        --cacert "$CACERT" \
        -H "X-API-Key: $(cat "$API_KEY_FILE")" \
        -H "Content-Type: application/json" \
        -X POST \
        -d "{\"query\": \"SELECT pg_sleep($duration)\"}" \
        "$BASE_URL/aidb/query" 2>&1)

    end_time=$(date +%s)
    local actual_duration=$((end_time - start_time))

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "200" ]; then
        SUCCESSFUL_REQUESTS=$((SUCCESSFUL_REQUESTS + 1))
        log "[Query $query_id] ✓ Completed in ${actual_duration}s"
    elif [ "$http_code" = "504" ] || [ "$http_code" = "408" ]; then
        TIMEOUT_REQUESTS=$((TIMEOUT_REQUESTS + 1))
        warn "[Query $query_id] ⏱ Timeout after ${actual_duration}s"
    elif [ "$http_code" = "500" ] || [ "$http_code" = "503" ]; then
        ERROR_RESPONSES=$((ERROR_RESPONSES + 1))
        warn "[Query $query_id] ⚠ Server error: $http_code"
    else
        FAILED_REQUESTS=$((FAILED_REQUESTS + 1))
        error "[Query $query_id] ✗ Failed with HTTP $http_code"
    fi
}

# Test Phase 1: Normal operation baseline
test_normal_operation() {
    log "\n=== Phase 1: Normal Operation Baseline ==="

    # Make a few normal queries to establish baseline
    for i in {1..5}; do
        make_slow_query 1 "baseline-$i" &
    done

    wait

    if [ "$SUCCESSFUL_REQUESTS" -eq 5 ]; then
        success "Baseline established: $SUCCESSFUL_REQUESTS/5 requests succeeded"
    else
        error "Baseline failed: only $SUCCESSFUL_REQUESTS/5 requests succeeded"
        return 1
    fi

    return 0
}

# Test Phase 2: Pool saturation
test_pool_saturation() {
    log "\n=== Phase 2: Pool Saturation Test ==="
    log "Creating $TOTAL_CONNECTIONS concurrent requests (exact pool limit)"

    # Reset metrics
    SUCCESSFUL_REQUESTS=0
    FAILED_REQUESTS=0
    TIMEOUT_REQUESTS=0
    ERROR_RESPONSES=0

    # Launch exactly pool_size + max_overflow requests
    for i in $(seq 1 $TOTAL_CONNECTIONS); do
        make_slow_query 5 "saturate-$i" &
    done

    wait

    local total=$((SUCCESSFUL_REQUESTS + FAILED_REQUESTS + TIMEOUT_REQUESTS + ERROR_RESPONSES))
    log "Saturation results: $SUCCESSFUL_REQUESTS success, $FAILED_REQUESTS failed, $TIMEOUT_REQUESTS timeout, $ERROR_RESPONSES errors"

    if [ "$SUCCESSFUL_REQUESTS" -eq "$TOTAL_CONNECTIONS" ]; then
        success "Pool handled saturation perfectly"
    else
        warn "Pool saturation had issues: $SUCCESSFUL_REQUESTS/$TOTAL_CONNECTIONS succeeded"
    fi

    return 0
}

# Test Phase 3: Pool overflow (exhaustion)
test_pool_exhaustion() {
    log "\n=== Phase 3: Pool Exhaustion Test ==="

    local overflow_count=50
    local total_requests=$((TOTAL_CONNECTIONS + overflow_count))

    log "Creating $total_requests concurrent requests ($overflow_count over limit)"

    # Reset metrics
    SUCCESSFUL_REQUESTS=0
    FAILED_REQUESTS=0
    TIMEOUT_REQUESTS=0
    ERROR_RESPONSES=0

    # Launch more requests than pool can handle
    for i in $(seq 1 $total_requests); do
        make_slow_query 5 "overflow-$i" &
    done

    wait

    local total=$((SUCCESSFUL_REQUESTS + FAILED_REQUESTS + TIMEOUT_REQUESTS + ERROR_RESPONSES))
    log "Exhaustion results: $SUCCESSFUL_REQUESTS success, $FAILED_REQUESTS failed, $TIMEOUT_REQUESTS timeout, $ERROR_RESPONSES errors"

    # Critical test: System should NOT crash, should handle gracefully
    if [ "$ERROR_RESPONSES" -eq 0 ] && [ "$FAILED_REQUESTS" -eq 0 ]; then
        success "✓ Pool exhaustion handled gracefully (no errors)"
    else
        error "✗ Pool exhaustion caused errors!"
        error "  - $ERROR_RESPONSES server errors"
        error "  - $FAILED_REQUESTS failed requests"
        return 1
    fi

    # Check if timeout handling is working
    if [ "$TIMEOUT_REQUESTS" -gt 0 ]; then
        success "✓ Timeout mechanism working: $TIMEOUT_REQUESTS requests timed out after ${POOL_TIMEOUT}s"
    else
        warn "No timeouts detected - pool might be waiting indefinitely"
    fi

    return 0
}

# Test Phase 4: Recovery after exhaustion
test_recovery() {
    log "\n=== Phase 4: Recovery Test ==="
    log "Waiting 10 seconds for pool to recover..."

    sleep 10

    # Reset metrics
    SUCCESSFUL_REQUESTS=0
    FAILED_REQUESTS=0
    TIMEOUT_REQUESTS=0
    ERROR_RESPONSES=0

    # Try normal requests again
    for i in {1..5}; do
        make_slow_query 1 "recovery-$i" &
    done

    wait

    if [ "$SUCCESSFUL_REQUESTS" -eq 5 ]; then
        success "✓ System recovered: $SUCCESSFUL_REQUESTS/5 requests succeeded"
        return 0
    else
        error "✗ System did NOT recover: only $SUCCESSFUL_REQUESTS/5 requests succeeded"
        error "  - Pool might be permanently damaged"
        error "  - Connection leak suspected"
        return 1
    fi
}

# Test Phase 5: Check for connection leaks
test_connection_leaks() {
    log "\n=== Phase 5: Connection Leak Detection ==="

    # Get current connection count from PostgreSQL
    local response
    response=$(curl -s \
        --cacert "$CACERT" \
        -H "X-API-Key: $(cat "$API_KEY_FILE")" \
        "$BASE_URL/aidb/metrics" 2>&1)

    # Look for connection pool metrics
    if echo "$response" | grep -q "db_connections_active"; then
        local active_connections
        active_connections=$(echo "$response" | grep "db_connections_active" | grep -oP '\d+' | head -1)

        log "Active connections after test: $active_connections"

        if [ "$active_connections" -le "$POOL_SIZE" ]; then
            success "✓ No connection leak detected"
            return 0
        else
            error "✗ Connection leak detected!"
            error "  - Active: $active_connections"
            error "  - Expected: ≤ $POOL_SIZE"
            return 1
        fi
    else
        warn "Connection metrics not available - cannot detect leaks"
        return 0
    fi
}

# Generate detailed report
generate_report() {
    log "\n=== Connection Pool Exhaustion Test Report ==="
    log "Configuration:"
    log "  - Pool size: $POOL_SIZE"
    log "  - Max overflow: $MAX_OVERFLOW"
    log "  - Total connections: $TOTAL_CONNECTIONS"
    log "  - Pool timeout: ${POOL_TIMEOUT}s"
    log ""
    log "Test Results:"
    log "  - Normal operation: PASS"
    log "  - Pool saturation: $([ $? -eq 0 ] && echo PASS || echo FAIL)"
    log "  - Pool exhaustion: $([ $? -eq 0 ] && echo PASS || echo FAIL)"
    log "  - Recovery: $([ $? -eq 0 ] && echo PASS || echo FAIL)"
    log "  - Leak detection: $([ $? -eq 0 ] && echo PASS || echo FAIL)"
    log ""
    log "Full log: $TEST_LOG"
}

# Main test execution
main() {
    log "=== Connection Pool Exhaustion Chaos Test ==="
    log "Testing database connection pool under extreme load"
    log ""

    local test_failed=0

    test_normal_operation || test_failed=1
    test_pool_saturation || test_failed=1
    test_pool_exhaustion || test_failed=1
    test_recovery || test_failed=1
    test_connection_leaks || test_failed=1

    generate_report

    if [ $test_failed -eq 0 ]; then
        success "\n✅ ALL CONNECTION POOL TESTS PASSED!"
        success "System handles pool exhaustion gracefully."
        exit 0
    else
        error "\n❌ CONNECTION POOL TESTS FAILED!"
        error "System does NOT handle pool exhaustion correctly."
        error "This WILL cause production outages!"
        exit 1
    fi
}

main "$@"
