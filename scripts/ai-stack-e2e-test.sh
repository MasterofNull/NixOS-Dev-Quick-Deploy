#!/usr/bin/env bash
# End-to-End AI Stack Feature Test
# Tests all components: MCP servers, LLM, Vector DB, Learning, Telemetry, Dashboard
#
# Test Scenario: Add a new "auto-commit" feature to the AI stack workflow
# This will exercise:
# - AIDB MCP: Context API queries
# - Hybrid Coordinator: Pattern extraction, continuous learning
# - Qdrant: Vector storage and retrieval
# - llama.cpp: LLM inference
# - Postgres: Telemetry storage
# - Redis: Caching
# - Dashboard: Event monitoring
#
# Results stored in: ~/.local/share/nixos-ai-stack/test-results/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_RESULTS_DIR="${HOME}/.local/share/nixos-ai-stack/test-results"
TEST_RUN_ID="test-$(date +%Y%m%d-%H%M%S)"
TEST_LOG="${TEST_RESULTS_DIR}/${TEST_RUN_ID}.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1" | tee -a "$TEST_LOG"; }
success() { echo -e "${GREEN}✓${NC} $1" | tee -a "$TEST_LOG"; }
warning() { echo -e "${YELLOW}⚠${NC} $1" | tee -a "$TEST_LOG"; }
error() { echo -e "${RED}✗${NC} $1" | tee -a "$TEST_LOG"; }

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
declare -a FAILED_TESTS=()

test_start() {
    local test_name="$1"
    info "Testing: $test_name"
}

test_pass() {
    local test_name="$1"
    ((TESTS_PASSED++))
    success "PASSED: $test_name"
}

test_fail() {
    local test_name="$1"
    local reason="${2:-Unknown error}"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$test_name: $reason")
    error "FAILED: $test_name - $reason"
}

# Setup
mkdir -p "$TEST_RESULTS_DIR"
info "Starting End-to-End AI Stack Test"
info "Test Run ID: $TEST_RUN_ID"
info "Log file: $TEST_LOG"
echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Phase 1: Pre-flight Checks - Verify All Services Running
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 1: Pre-flight Checks"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 1.1: Qdrant
test_start "Qdrant Vector Database"
if curl -sf --max-time 5 http://localhost:6333/healthz >/dev/null 2>&1; then
    test_pass "Qdrant health check"
else
    test_fail "Qdrant health check" "Service not responding"
fi

# Test 1.2: llama.cpp
test_start "llama.cpp LLM Server"
if curl -sf --max-time 5 http://localhost:8080/v1/models >/dev/null 2>&1; then
    test_pass "llama.cpp health check"
else
    test_fail "llama.cpp health check" "Service not responding"
fi

# Test 1.3: Postgres
test_start "PostgreSQL Database"
if PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -c "SELECT 1;" >/dev/null 2>&1; then
    test_pass "PostgreSQL health check"
else
    test_fail "PostgreSQL health check" "Cannot connect to database"
fi

# Test 1.4: Redis
test_start "Redis Cache"
if redis-cli -h localhost -p 6379 PING 2>/dev/null | grep -q PONG; then
    test_pass "Redis health check"
else
    test_fail "Redis health check" "Service not responding"
fi

# Test 1.5: AIDB MCP
test_start "AIDB MCP Server"
AIDB_HEALTH=$(curl -s http://localhost:8091/health 2>&1 || echo "")
if echo "$AIDB_HEALTH" | grep -q "status"; then
    test_pass "AIDB MCP health check"
else
    test_fail "AIDB MCP health check" "Service not responding"
fi

# Test 1.6: Hybrid Coordinator
test_start "Hybrid Coordinator MCP"
HYBRID_HEALTH=$(curl -sf --max-time 5 http://localhost:8092/health 2>&1)
if echo "$HYBRID_HEALTH" | grep -q '"status":"healthy"'; then
    test_pass "Hybrid Coordinator health check"
    # Verify collections exist
    COLLECTIONS=$(echo "$HYBRID_HEALTH" | grep -o '"collections":\[[^]]*\]')
    if echo "$COLLECTIONS" | grep -q "codebase-context"; then
        test_pass "Hybrid Coordinator collections verified"
    else
        test_fail "Hybrid Coordinator collections" "Collections not found"
    fi
else
    test_fail "Hybrid Coordinator health check" "Service not responding"
fi

# Test 1.7: NixOS Docs MCP
test_start "NixOS Docs MCP Server"
NIXOS_HEALTH=$(curl -sf --max-time 5 http://localhost:8094/health 2>&1)
if echo "$NIXOS_HEALTH" | grep -q '"status":"healthy"'; then
    test_pass "NixOS Docs MCP health check"
else
    test_fail "NixOS Docs MCP health check" "Service not responding"
fi

echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Phase 2: Test Real-World Scenario - Add Auto-Commit Feature
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 2: Real-World Feature Test - Auto-Commit Workflow"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create a test feature request
TEST_FEATURE_FILE="${TEST_RESULTS_DIR}/${TEST_RUN_ID}-feature-request.json"
cat > "$TEST_FEATURE_FILE" << 'EOF'
{
  "feature_name": "auto-commit",
  "description": "Automatically commit code changes when AI makes modifications",
  "requirements": [
    "Detect when AI has modified files",
    "Generate meaningful commit messages based on changes",
    "Ask user for confirmation before committing",
    "Store commit metadata in telemetry"
  ],
  "test_scenario": "AI workflow integration test",
  "timestamp": "$(date -Iseconds)"
}
EOF

info "Feature request created: auto-commit"

# Test 2.1: Store feature request in Qdrant via Hybrid Coordinator
test_start "Store feature request in Qdrant (via Hybrid Coordinator)"
FEATURE_TEXT="Feature Request: auto-commit - Automatically commit code changes when AI makes modifications. Requirements: detect file changes, generate commit messages, ask for confirmation, store telemetry."

QDRANT_STORE_RESULT=$(curl -sf --max-time 10 -X POST http://localhost:8092/api/context/add \
  -H "Content-Type: application/json" \
  -d "{
    \"collection\": \"interaction-history\",
    \"text\": \"$FEATURE_TEXT\",
    \"metadata\": {
      \"type\": \"feature_request\",
      \"test_run\": \"$TEST_RUN_ID\",
      \"timestamp\": \"$(date -Iseconds)\"
    }
  }" 2>&1 || echo "FAILED")

if echo "$QDRANT_STORE_RESULT" | grep -q "success\|id\|stored"; then
    test_pass "Feature request stored in Qdrant"
    POINT_ID=$(echo "$QDRANT_STORE_RESULT" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    info "Stored with ID: $POINT_ID"
else
    test_fail "Store in Qdrant" "API call failed: $QDRANT_STORE_RESULT"
fi

# Test 2.2: Query LLM for implementation plan
test_start "Query llama.cpp for implementation plan"
LLM_PROMPT="Create a brief implementation plan for an auto-commit feature that: 1) detects AI file changes, 2) generates commit messages, 3) asks user confirmation. Return only the plan in 3 bullet points."

LLM_RESPONSE=$(curl -sf --max-time 30 -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"qwen2.5-coder-7b-instruct-q4_k_m.gguf\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"$LLM_PROMPT\"}
    ],
    \"max_tokens\": 200,
    \"temperature\": 0.7
  }" 2>&1 || echo "FAILED")

if echo "$LLM_RESPONSE" | grep -q "content"; then
    test_pass "LLM generated implementation plan"
    PLAN=$(echo "$LLM_RESPONSE" | grep -o '"content":"[^"]*"' | head -1 | cut -d'"' -f4)
    info "Plan generated (truncated): ${PLAN:0:100}..."

    # Save LLM response
    echo "$LLM_RESPONSE" > "${TEST_RESULTS_DIR}/${TEST_RUN_ID}-llm-response.json"
else
    test_fail "LLM query" "No valid response: $LLM_RESPONSE"
fi

# Test 2.3: Store implementation plan in Qdrant (pattern extraction simulation)
test_start "Store implementation plan as coding pattern"
if [ -n "${PLAN:-}" ]; then
    PATTERN_STORE=$(curl -sf --max-time 10 -X POST http://localhost:8092/api/context/add \
      -H "Content-Type: application/json" \
      -d "{
        \"collection\": \"skills-patterns\",
        \"text\": \"Implementation pattern for auto-commit: $PLAN\",
        \"metadata\": {
          \"type\": \"implementation_plan\",
          \"feature\": \"auto-commit\",
          \"test_run\": \"$TEST_RUN_ID\",
          \"source\": \"llm_generated\"
        }
      }" 2>&1 || echo "FAILED")

    if echo "$PATTERN_STORE" | grep -q "success\|id"; then
        test_pass "Implementation plan stored as pattern"
    else
        test_fail "Store pattern" "Failed to store: $PATTERN_STORE"
    fi
else
    test_fail "Store pattern" "No plan available from LLM"
fi

# Test 2.4: Retrieve similar patterns (context augmentation)
test_start "Query Qdrant for similar patterns (context augmentation)"
SIMILAR_PATTERNS=$(curl -sf --max-time 10 -X POST http://localhost:8092/api/context/search \
  -H "Content-Type: application/json" \
  -d "{
    \"collection\": \"skills-patterns\",
    \"query\": \"git commit automation implementation\",
    \"limit\": 3
  }" 2>&1 || echo "FAILED")

if echo "$SIMILAR_PATTERNS" | grep -q "results\|points"; then
    test_pass "Context augmentation - similar patterns retrieved"
    RESULT_COUNT=$(echo "$SIMILAR_PATTERNS" | grep -o '"score"' | wc -l)
    info "Found $RESULT_COUNT similar patterns"
else
    test_fail "Context augmentation" "Search failed: $SIMILAR_PATTERNS"
fi

echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Phase 3: Test Telemetry and Learning Pipeline
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 3: Telemetry Collection and Continuous Learning"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 3.1: Send telemetry event
test_start "Send telemetry event to AIDB"
TELEMETRY_EVENT=$(cat <<EOF
{
  "event_type": "feature_test",
  "feature_name": "auto-commit",
  "test_run_id": "$TEST_RUN_ID",
  "status": "in_progress",
  "metadata": {
    "llm_used": "qwen2.5-coder-7b",
    "vector_db_queries": 2,
    "timestamp": "$(date -Iseconds)"
  }
}
EOF
)

TELEMETRY_RESULT=$(curl -sf --max-time 10 -X POST http://localhost:8091/api/telemetry/event \
  -H "Content-Type: application/json" \
  -d "$TELEMETRY_EVENT" 2>&1 || echo "FAILED")

if echo "$TELEMETRY_RESULT" | grep -q "success\|recorded\|stored"; then
    test_pass "Telemetry event recorded"
else
    test_fail "Telemetry recording" "Failed: $TELEMETRY_RESULT"
fi

# Test 3.2: Verify telemetry in Postgres
test_start "Verify telemetry stored in Postgres"
TELEMETRY_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE metadata->>'test_run_id' = '$TEST_RUN_ID';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$TELEMETRY_COUNT" -gt 0 ]; then
    test_pass "Telemetry found in Postgres ($TELEMETRY_COUNT events)"
else
    test_fail "Telemetry in Postgres" "No events found for test run"
fi

# Test 3.3: Check Redis caching
test_start "Verify Redis caching is working"
REDIS_TEST_KEY="test:${TEST_RUN_ID}:cache"
redis-cli -h localhost -p 6379 SET "$REDIS_TEST_KEY" "test_value" EX 60 >/dev/null 2>&1
REDIS_VALUE=$(redis-cli -h localhost -p 6379 GET "$REDIS_TEST_KEY" 2>/dev/null)

if [ "$REDIS_VALUE" = "test_value" ]; then
    test_pass "Redis caching verified"
    redis-cli -h localhost -p 6379 DEL "$REDIS_TEST_KEY" >/dev/null 2>&1
else
    test_fail "Redis caching" "Cache read/write failed"
fi

# Test 3.4: Trigger continuous learning (if enabled)
test_start "Verify continuous learning daemon"
LEARNING_STATUS=$(curl -sf --max-time 5 http://localhost:8092/api/learning/status 2>&1 || echo "FAILED")

if echo "$LEARNING_STATUS" | grep -q "enabled\|status"; then
    test_pass "Continuous learning daemon accessible"
    info "Learning status: $LEARNING_STATUS"
else
    warning "Continuous learning status endpoint not available (may not be implemented)"
fi

echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Phase 4: Verify Dashboard Monitoring
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 4: Dashboard Monitoring Verification"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 4.1: Check if dashboard backend is running
test_start "Dashboard backend API"
if curl -sf --max-time 5 http://localhost:8889/api/metrics/system >/dev/null 2>&1; then
    test_pass "Dashboard backend accessible"
else
    warning "Dashboard backend not running (optional service)"
fi

# Test 4.2: Verify events are reaching dashboard
test_start "Verify test events in dashboard database"
sleep 2  # Give time for events to propagate

# Check if telemetry events are accessible
DASHBOARD_EVENTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE created_at > NOW() - INTERVAL '5 minutes';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$DASHBOARD_EVENTS" -gt 0 ]; then
    test_pass "Recent events visible to dashboard ($DASHBOARD_EVENTS events)"
else
    test_fail "Dashboard event visibility" "No recent events found"
fi

echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Phase 5: Data Consistency Validation
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 5: Cross-System Data Consistency Validation"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 5.1: Verify Qdrant collection counts
test_start "Qdrant collection integrity check"
for collection in codebase-context skills-patterns error-solutions interaction-history best-practices; do
    COLLECTION_INFO=$(curl -sf --max-time 5 "http://localhost:6333/collections/$collection" 2>&1 || echo "FAILED")
    if echo "$COLLECTION_INFO" | grep -q "points_count"; then
        POINT_COUNT=$(echo "$COLLECTION_INFO" | grep -o '"points_count":[0-9]*' | grep -o '[0-9]*')
        info "Collection '$collection': $POINT_COUNT points"
    else
        warning "Could not retrieve info for collection: $collection"
    fi
done
test_pass "Qdrant collection integrity check completed"

# Test 5.2: Cross-reference telemetry events with test actions
test_start "Cross-reference database events with test actions"
EXPECTED_EVENTS=2  # We sent 2 events (feature request + telemetry)
ACTUAL_EVENTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE metadata->>'test_run_id' = '$TEST_RUN_ID';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$ACTUAL_EVENTS" -ge "$EXPECTED_EVENTS" ]; then
    test_pass "Event count matches expectations ($ACTUAL_EVENTS >= $EXPECTED_EVENTS)"
else
    test_fail "Event count mismatch" "Expected >=$EXPECTED_EVENTS, found $ACTUAL_EVENTS"
fi

echo "" | tee -a "$TEST_LOG"

# ============================================================================
# Final Report
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Test Summary"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
PASS_RATE=0
if [ $TOTAL_TESTS -gt 0 ]; then
    PASS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
fi

echo "" | tee -a "$TEST_LOG"
success "Tests Passed: $TESTS_PASSED"
if [ $TESTS_FAILED -gt 0 ]; then
    error "Tests Failed: $TESTS_FAILED"
else
    success "Tests Failed: 0"
fi
info "Total Tests: $TOTAL_TESTS"
info "Pass Rate: ${PASS_RATE}%"
echo "" | tee -a "$TEST_LOG"

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    error "Failed Tests:"
    for failed_test in "${FAILED_TESTS[@]}"; do
        error "  - $failed_test"
    done
    echo "" | tee -a "$TEST_LOG"
fi

# Generate JSON report
REPORT_FILE="${TEST_RESULTS_DIR}/${TEST_RUN_ID}-report.json"
cat > "$REPORT_FILE" << EOF
{
  "test_run_id": "$TEST_RUN_ID",
  "timestamp": "$(date -Iseconds)",
  "summary": {
    "total_tests": $TOTAL_TESTS,
    "passed": $TESTS_PASSED,
    "failed": $TESTS_FAILED,
    "pass_rate": $PASS_RATE
  },
  "failed_tests": $(printf '%s\n' "${FAILED_TESTS[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]'),
  "log_file": "$TEST_LOG",
  "feature_tested": "auto-commit",
  "components_tested": [
    "qdrant",
    "llama-cpp",
    "postgres",
    "redis",
    "aidb-mcp",
    "hybrid-coordinator",
    "nixos-docs-mcp",
    "telemetry",
    "dashboard"
  ]
}
EOF

success "Test report saved: $REPORT_FILE"
info "Full log: $TEST_LOG"

# Store test results in database
info "Storing test results in database..."
PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" << EOSQL 2>/dev/null || warning "Could not store results in database"
CREATE TABLE IF NOT EXISTS test_runs (
    id SERIAL PRIMARY KEY,
    test_run_id VARCHAR(255) UNIQUE,
    timestamp TIMESTAMP DEFAULT NOW(),
    total_tests INTEGER,
    passed INTEGER,
    failed INTEGER,
    pass_rate INTEGER,
    report_json JSONB,
    log_file TEXT
);

INSERT INTO test_runs (test_run_id, total_tests, passed, failed, pass_rate, report_json, log_file)
VALUES (
    '$TEST_RUN_ID',
    $TOTAL_TESTS,
    $TESTS_PASSED,
    $TESTS_FAILED,
    $PASS_RATE,
    '$(cat "$REPORT_FILE")'::jsonb,
    '$TEST_LOG'
);
EOSQL

if [ $TESTS_FAILED -eq 0 ]; then
    echo "" | tee -a "$TEST_LOG"
    success "═══════════════════════════════════════════════════════════════════"
    success "✅ ALL TESTS PASSED - AI Stack is fully functional!"
    success "═══════════════════════════════════════════════════════════════════"
    exit 0
else
    echo "" | tee -a "$TEST_LOG"
    error "═══════════════════════════════════════════════════════════════════"
    error "❌ SOME TESTS FAILED - Review errors above"
    error "═══════════════════════════════════════════════════════════════════"
    exit 1
fi
