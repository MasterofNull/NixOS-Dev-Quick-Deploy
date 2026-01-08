#!/usr/bin/env bash
# Test: Agent Progressive Disclosure E2E
# Validates the core claim: "220 tokens vs 3000+ without progressive disclosure"
#
# This test MUST pass for the system to be considered functional.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test configuration
BASE_URL="https://localhost:8443"
CACERT="${PROJECT_ROOT}/ai-stack/compose/nginx/certs/localhost.crt"
API_KEY_FILE="${PROJECT_ROOT}/ai-stack/compose/secrets/stack_api_key"
TEST_LOG="/tmp/chaos-test-progressive-disclosure-$$.log"

# Metrics
TOKENS_USED=0
CALLS_MADE=0
ERRORS=0

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$TEST_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$TEST_LOG"
    ERRORS=$((ERRORS + 1))
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$TEST_LOG"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$TEST_LOG"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    if [ ! -f "$CACERT" ]; then
        error "TLS certificate not found: $CACERT"
        return 1
    fi

    if [ ! -f "$API_KEY_FILE" ]; then
        error "API key file not found: $API_KEY_FILE"
        return 1
    fi

    # Check if API key is readable
    if ! API_KEY=$(cat "$API_KEY_FILE" 2>/dev/null); then
        error "Cannot read API key file"
        return 1
    fi

    # Check if API key is valid (not empty, no whitespace issues)
    if [ -z "$API_KEY" ]; then
        error "API key is empty"
        return 1
    fi

    if [[ "$API_KEY" =~ [[:space:]] ]]; then
        warn "API key contains whitespace - this might cause issues"
    fi

    success "Prerequisites check passed"
    return 0
}

# Make API call with token counting
api_call() {
    local endpoint="$1"
    local method="${2:-GET}"
    local data="${3:-}"
    local expected_tokens="${4:-0}"

    CALLS_MADE=$((CALLS_MADE + 1))

    log "API Call #$CALLS_MADE: $method $endpoint"

    local response
    local http_code
    local actual_tokens

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" \
            --cacert "$CACERT" \
            -H "X-API-Key: $(cat "$API_KEY_FILE")" \
            -X "$method" \
            "$BASE_URL$endpoint" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" \
            --cacert "$CACERT" \
            -H "X-API-Key: $(cat "$API_KEY_FILE")" \
            -H "Content-Type: application/json" \
            -X "$method" \
            -d "$data" \
            "$BASE_URL$endpoint" 2>&1)
    fi

    http_code=$(echo "$response" | tail -n1)
    response=$(echo "$response" | head -n -1)

    # Estimate tokens (rough: 4 chars = 1 token)
    actual_tokens=$((${#response} / 4))
    TOKENS_USED=$((TOKENS_USED + actual_tokens))

    log "  HTTP $http_code | ~$actual_tokens tokens | Total: $TOKENS_USED tokens"

    if [ "$http_code" != "200" ]; then
        error "  Expected HTTP 200, got $http_code"
        error "  Response: $response"
        return 1
    fi

    # Validate token usage is within expected range (±20% tolerance)
    if [ "$expected_tokens" -gt 0 ]; then
        local min_tokens=$((expected_tokens * 80 / 100))
        local max_tokens=$((expected_tokens * 120 / 100))

        if [ "$actual_tokens" -lt "$min_tokens" ] || [ "$actual_tokens" -gt "$max_tokens" ]; then
            warn "  Token usage outside expected range"
            warn "  Expected: ~$expected_tokens | Actual: $actual_tokens | Range: $min_tokens-$max_tokens"
        fi
    fi

    echo "$response"
    return 0
}

# Test Step 1: Health Check (should be minimal)
test_health_check() {
    log "\n=== Test Step 1: Health Check ==="

    local response
    if ! response=$(api_call "/aidb/health" "GET" "" 20); then
        error "Health check failed"
        return 1
    fi

    # Validate response structure
    if ! echo "$response" | jq -e '.status' > /dev/null 2>&1; then
        error "Health check response missing 'status' field"
        return 1
    fi

    local status
    status=$(echo "$response" | jq -r '.status')

    if [ "$status" != "healthy" ]; then
        error "Service is not healthy: $status"
        return 1
    fi

    success "Health check passed"
    return 0
}

# Test Step 2: Discovery Info (should be ~50 tokens)
test_discovery_info() {
    log "\n=== Test Step 2: Discovery Info ==="

    local response
    if ! response=$(api_call "/aidb/discovery/info" "GET" "" 50); then
        error "Discovery info failed"
        return 1
    fi

    # Validate response has key fields
    if ! echo "$response" | jq -e '.capabilities' > /dev/null 2>&1; then
        error "Discovery response missing 'capabilities' field"
        return 1
    fi

    success "Discovery info passed"
    return 0
}

# Test Step 3: Quickstart Guide (should be ~150 tokens)
test_quickstart_guide() {
    log "\n=== Test Step 3: Quickstart Guide ==="

    local response
    if ! response=$(api_call "/aidb/discovery/quickstart" "GET" "" 150); then
        error "Quickstart guide failed"
        return 1
    fi

    # Validate response has workflow steps
    if ! echo "$response" | jq -e '.workflow' > /dev/null 2>&1; then
        error "Quickstart response missing 'workflow' field"
        return 1
    fi

    local workflow_steps
    workflow_steps=$(echo "$response" | jq '.workflow | length')

    if [ "$workflow_steps" -lt 3 ]; then
        warn "Quickstart workflow has only $workflow_steps steps (expected 3+)"
    fi

    success "Quickstart guide passed"
    return 0
}

# Test Step 4: Validate Total Token Usage
test_validate_total_tokens() {
    log "\n=== Test Step 4: Validate Total Token Usage ==="

    # Core claim: Progressive disclosure uses ~220 tokens
    # Allow 300 tokens max (36% tolerance)
    local max_acceptable_tokens=300

    log "Total tokens used in progressive disclosure: $TOKENS_USED"
    log "Target: ~220 tokens | Max acceptable: $max_acceptable_tokens tokens"

    if [ "$TOKENS_USED" -gt "$max_acceptable_tokens" ]; then
        error "PROGRESSIVE DISCLOSURE FAILED!"
        error "Used $TOKENS_USED tokens (limit: $max_acceptable_tokens)"
        error "Core claim of '220 tokens vs 3000+' is FALSE"
        return 1
    fi

    local savings=$((3000 - TOKENS_USED))
    local savings_pct=$((savings * 100 / 3000))

    success "Progressive disclosure validated!"
    success "Token savings: $savings tokens ($savings_pct% reduction)"
    return 0
}

# Test Step 5: Error Handling Edge Cases
test_error_handling() {
    log "\n=== Test Step 5: Error Handling Edge Cases ==="

    # Test 1: Invalid API Key
    log "  Testing invalid API key..."
    local response
    response=$(curl -s -w "\n%{http_code}" \
        --cacert "$CACERT" \
        -H "X-API-Key: INVALID_KEY_12345" \
        "$BASE_URL/aidb/health" 2>&1)

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "401" ] && [ "$http_code" != "403" ]; then
        error "Invalid API key should return 401/403, got $http_code"
    else
        success "Invalid API key correctly rejected"
    fi

    # Test 2: Missing API Key
    log "  Testing missing API key..."
    response=$(curl -s -w "\n%{http_code}" \
        --cacert "$CACERT" \
        "$BASE_URL/aidb/health" 2>&1)

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "401" ] && [ "$http_code" != "403" ]; then
        error "Missing API key should return 401/403, got $http_code"
    else
        success "Missing API key correctly rejected"
    fi

    # Test 3: Malformed JSON
    log "  Testing malformed JSON..."
    response=$(curl -s -w "\n%{http_code}" \
        --cacert "$CACERT" \
        -H "X-API-Key: $(cat "$API_KEY_FILE")" \
        -H "Content-Type: application/json" \
        -X POST \
        -d '{invalid json}' \
        "$BASE_URL/aidb/query" 2>&1)

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "400" ] && [ "$http_code" != "422" ]; then
        error "Malformed JSON should return 400/422, got $http_code"
    else
        success "Malformed JSON correctly rejected"
    fi

    return 0
}

# Generate report
generate_report() {
    log "\n=== Test Summary ==="
    log "Calls made: $CALLS_MADE"
    log "Tokens used: $TOKENS_USED"
    log "Errors: $ERRORS"

    if [ "$ERRORS" -eq 0 ]; then
        success "\n✅ ALL TESTS PASSED!"
        success "Progressive disclosure is working as claimed."
    else
        error "\n❌ TESTS FAILED!"
        error "$ERRORS error(s) detected."
        error "Progressive disclosure is NOT working correctly."
    fi

    log "\nFull log: $TEST_LOG"
}

# Main test execution
main() {
    log "=== Agent Progressive Disclosure E2E Test ==="
    log "Testing core claim: 220 tokens vs 3000+ without progressive disclosure"
    log ""

    # Run tests in sequence
    check_prerequisites || exit 1
    test_health_check || exit 1
    test_discovery_info || exit 1
    test_quickstart_guide || exit 1
    test_validate_total_tokens || exit 1
    test_error_handling || true  # Non-fatal

    generate_report

    # Exit code based on errors
    if [ "$ERRORS" -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
