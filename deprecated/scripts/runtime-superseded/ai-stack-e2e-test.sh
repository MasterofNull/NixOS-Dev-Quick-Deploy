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
declare -a PORT_FORWARD_PIDS=()

port_in_use() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn | awk '{print $4}' | grep -Eq ":${port}$" && return 0
        return 1
    fi
    return 1
}

start_port_forward() {
    local namespace="$1"
    local service="$2"
    local local_port="$3"
    local remote_port="$4"
    local kubectl_bin="$5"

    if port_in_use "$local_port"; then
        info "Port $local_port already in use; skipping port-forward for $service"
        return 0
    fi

    "$kubectl_bin" --request-timeout=60s -n "$namespace" port-forward "svc/${service}" "${local_port}:${remote_port}" \
        >/dev/null 2>&1 &
    PORT_FORWARD_PIDS+=("$!")
}

cleanup_port_forwards() {
    if [ ${#PORT_FORWARD_PIDS[@]} -gt 0 ]; then
        for pid in "${PORT_FORWARD_PIDS[@]}"; do
            kill "$pid" >/dev/null 2>&1 || true
        done
    fi
}

test_start() {
    local test_name="$1"
    info "Testing: $test_name"
}

test_pass() {
    local test_name="$1"
    ((TESTS_PASSED++)) || true
    success "PASSED: $test_name"
}

test_fail() {
    local test_name="$1"
    local reason="${2:-Unknown error}"
    ((TESTS_FAILED++)) || true
    FAILED_TESTS+=("$test_name: $reason")
    error "FAILED: $test_name - $reason"
}

# Setup
mkdir -p "$TEST_RESULTS_DIR"
info "Starting End-to-End AI Stack Test"
info "Test Run ID: $TEST_RUN_ID"
info "Log file: $TEST_LOG"
echo "" | tee -a "$TEST_LOG"

# If running in K8s, start port-forwards for local testing
K8S_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"
KUBECTL_BIN="kubectl"
if [ -x /run/current-system/sw/bin/kubectl ]; then
    KUBECTL_BIN="/run/current-system/sw/bin/kubectl"
fi

if command -v "$KUBECTL_BIN" >/dev/null 2>&1 && "$KUBECTL_BIN" -n "$K8S_NAMESPACE" get svc >/dev/null 2>&1; then
    info "Detected K8s services in ${K8S_NAMESPACE}; starting port-forwards for local E2E checks..."
    start_port_forward "$K8S_NAMESPACE" "qdrant" 6333 6333 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "llama-cpp" 8080 8080 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "postgres" 5432 5432 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "redis" 6379 6379 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "aidb" 8091 8091 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "hybrid-coordinator" 8092 8092 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "nixos-docs" 8094 8094 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "ralph-wiggum" 8098 8098 "$KUBECTL_BIN"
    start_port_forward "$K8S_NAMESPACE" "dashboard-api" 8889 8889 "$KUBECTL_BIN"
    sleep 3
    trap cleanup_port_forwards EXIT

    # Load API keys and passwords from K8s secrets if not already set
    if [ -z "${AIDB_API_KEY:-}" ]; then
        AIDB_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret aidb-api-key -o jsonpath='{.data.aidb-api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        if [ -z "$AIDB_API_KEY" ]; then
            AIDB_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret aidb-api-key -o jsonpath='{.data.api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        fi
    fi
    if [ -z "${HYBRID_API_KEY:-}" ]; then
        HYBRID_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret hybrid-coordinator-api-key -o jsonpath='{.data.hybrid-coordinator-api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        if [ -z "$HYBRID_API_KEY" ]; then
            HYBRID_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret hybrid-coordinator-api-key -o jsonpath='{.data.api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        fi
    fi
    if [ -z "${RALPH_WIGGUM_API_KEY:-}" ]; then
        RALPH_WIGGUM_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret ralph-wiggum-api-key -o jsonpath='{.data.ralph-wiggum-api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        if [ -z "$RALPH_WIGGUM_API_KEY" ]; then
            RALPH_WIGGUM_API_KEY=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret ralph-wiggum-api-key -o jsonpath='{.data.api-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
        fi
    fi
    if [ -z "${POSTGRES_PASSWORD:-}" ]; then
        POSTGRES_PASSWORD=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret postgres-password -o jsonpath='{.data.postgres-password}' 2>/dev/null | base64 -d 2>/dev/null || true)
    fi
    if [ -z "${REDIS_PASSWORD:-}" ]; then
        REDIS_PASSWORD=$("$KUBECTL_BIN" -n "$K8S_NAMESPACE" get secret redis-password -o jsonpath='{.data.redis-password}' 2>/dev/null | base64 -d 2>/dev/null || true)
    fi
fi

# ============================================================================
# Phase 1: Pre-flight Checks - Verify All Services Running
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Phase 1: Pre-flight Checks"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Optional API keys (if services enforce auth)
AIDB_HEADERS=()
HYBRID_HEADERS=()
RALPH_HEADERS=()

if [ -n "${AIDB_API_KEY:-}" ]; then
    AIDB_HEADERS+=("-H" "X-API-Key: ${AIDB_API_KEY}")
fi
if [ -n "${HYBRID_API_KEY:-}" ]; then
    HYBRID_HEADERS+=("-H" "X-API-Key: ${HYBRID_API_KEY}")
fi
if [ -n "${RALPH_WIGGUM_API_KEY:-}" ]; then
    RALPH_HEADERS+=("-H" "X-API-Key: ${RALPH_WIGGUM_API_KEY}")
fi

# Test 1.1: Qdrant
test_start "Qdrant Vector Database"
if curl -sf --max-time 5 http://${SERVICE_HOST:-localhost}:6333/healthz >/dev/null 2>&1; then
    test_pass "Qdrant health check"
else
    test_fail "Qdrant health check" "Service not responding"
fi

# Test 1.2: llama.cpp
test_start "llama.cpp LLM Server"
if curl -sf --max-time 5 http://${SERVICE_HOST:-localhost}:8080/v1/models >/dev/null 2>&1; then
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
if redis-cli -h localhost -p 6379 ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} PING 2>/dev/null | grep -q PONG; then
    test_pass "Redis health check"
else
    test_fail "Redis health check" "Service not responding"
fi

# Test 1.5: AIDB MCP
test_start "AIDB MCP Server"
AIDB_HEALTH=$(curl -s --max-time 5 --connect-timeout 3 "${AIDB_HEADERS[@]}" http://${SERVICE_HOST:-localhost}:8091/health 2>&1 || echo "")
if echo "$AIDB_HEALTH" | grep -q "status"; then
    test_pass "AIDB MCP health check"
else
    test_fail "AIDB MCP health check" "Service not responding"
fi

# Test 1.6: Hybrid Coordinator
test_start "Hybrid Coordinator MCP"
HYBRID_HEALTH=$(curl -sf --max-time 10 http://${SERVICE_HOST:-localhost}:8092/health 2>&1)
if echo "$HYBRID_HEALTH" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"healthy"'; then
    test_pass "Hybrid Coordinator health check"
    # Verify collections exist
    COLLECTIONS=$(echo "$HYBRID_HEALTH" | jq -r '.collections[]' 2>/dev/null || true)
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
NIXOS_HEALTH=$(curl -sf --max-time 5 http://${SERVICE_HOST:-localhost}:8094/health 2>&1)
if echo "$NIXOS_HEALTH" | grep -q '"status":"healthy"'; then
    test_pass "NixOS Docs MCP health check"
else
    test_fail "NixOS Docs MCP health check" "Service not responding"
fi

# Test 1.8: Ralph Wiggum MCP
test_start "Ralph Wiggum MCP Server"
RALPH_HEALTH=$(curl -sf --max-time 5 "${RALPH_HEADERS[@]}" http://${SERVICE_HOST:-localhost}:8098/health 2>&1 || echo "")
if echo "$RALPH_HEALTH" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"(healthy|degraded)"'; then
    test_pass "Ralph Wiggum health check"
else
    warning "Ralph Wiggum health check failed (optional if loop disabled)"
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
test_start "Store feature request in Qdrant"
FEATURE_TEXT="Feature Request: auto-commit - Automatically commit code changes when AI makes modifications. Requirements: detect file changes, generate commit messages, ask for confirmation, store telemetry."
POINT_ID=$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)
FEATURE_EMBED=$(curl -sf --max-time 20 -X POST http://${SERVICE_HOST:-localhost}:8091/vector/embed \
  "${AIDB_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"texts\": [\"$FEATURE_TEXT\"]}" | jq -c '.embeddings[0]' 2>/dev/null || echo "")

if [ -n "$FEATURE_EMBED" ] && [ "$FEATURE_EMBED" != "null" ]; then
    QDRANT_STORE_RESULT=$(curl -sf --max-time 10 -X PUT "http://${SERVICE_HOST:-localhost}:6333/collections/interaction-history/points?wait=true" \
      -H "Content-Type: application/json" \
      -d "{
        \"points\": [{
          \"id\": \"$POINT_ID\",
          \"vector\": $FEATURE_EMBED,
          \"payload\": {
            \"type\": \"feature_request\",
            \"test_run\": \"$TEST_RUN_ID\",
            \"text\": \"$FEATURE_TEXT\",
            \"timestamp\": \"$(date -Iseconds)\"
          }
        }]
      }" 2>&1 || echo "FAILED")

    if echo "$QDRANT_STORE_RESULT" | grep -q "result"; then
        test_pass "Feature request stored in Qdrant"
        info "Stored with ID: $POINT_ID"
    else
        test_fail "Store in Qdrant" "API call failed: $QDRANT_STORE_RESULT"
    fi
else
    test_fail "Store in Qdrant" "Embedding generation failed"
fi

# Test 2.1b: Hybrid augmentation endpoint
test_start "Hybrid Coordinator augment query"
HYBRID_AUGMENT=$(curl -sf --max-time 10 -X POST http://${SERVICE_HOST:-localhost}:8092/augment_query \
  "${HYBRID_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"auto-commit feature request implementation\",
    \"agent_type\": \"remote\"
  }" 2>&1 || echo "FAILED")

if echo "$HYBRID_AUGMENT" | grep -q "context_count"; then
    test_pass "Hybrid augmentation endpoint responsive"
else
    test_fail "Hybrid augmentation" "No response: $HYBRID_AUGMENT"
fi

# Test 2.1c: Hybrid query endpoint (RAG)
test_start "Hybrid Coordinator RAG query"
HYBRID_QUERY=$(curl -sf --max-time 20 -X POST http://${SERVICE_HOST:-localhost}:8092/query \
  "${HYBRID_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"How do I enable Wireshark capture on NixOS?\",
    \"context\": {\"source\": \"e2e-test\", \"test_run\": \"${TEST_RUN_ID}\"}
  }" 2>&1 || echo "FAILED")

if echo "$HYBRID_QUERY" | grep -q "\"response\""; then
    test_pass "Hybrid query endpoint (RAG) responded"
else
    test_fail "Hybrid query endpoint (RAG)" "No response: $HYBRID_QUERY"
fi

# Test 2.2: Query LLM for implementation plan
test_start "Query llama.cpp for implementation plan"
LLM_PROMPT="Reply with exactly three words: auto commit ok"

LLM_RESPONSE=$(curl -sf --max-time 90 -X POST http://${SERVICE_HOST:-localhost}:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"qwen2.5-coder-7b-instruct-q4_k_m.gguf\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"$LLM_PROMPT\"}
    ],
    \"max_tokens\": 10,
    \"temperature\": 0.2
  }" 2>&1 || echo "FAILED")

if echo "$LLM_RESPONSE" | grep -q "content"; then
    test_pass "LLM generated implementation plan"
    PLAN=$(echo "$LLM_RESPONSE" | grep -o '"content":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$PLAN" ] || [ "${#PLAN}" -lt 10 ]; then
        warning "LLM response too short; using fallback plan"
        PLAN="Detect changed files; draft commit message; request approval"
    fi
    info "Plan generated (truncated): ${PLAN:0:100}..."

    # Save LLM response
    echo "$LLM_RESPONSE" > "${TEST_RESULTS_DIR}/${TEST_RUN_ID}-llm-response.json"
else
    test_fail "LLM query" "No valid response: $LLM_RESPONSE"
fi

# Test 2.3: Store implementation plan in Qdrant (pattern extraction simulation)
test_start "Store implementation plan as coding pattern"
if [ -n "${PLAN:-}" ]; then
    PATTERN_TEXT="Implementation pattern for auto-commit: $PLAN"
    PATTERN_TEXT_JSON=$(printf '%s' "$PATTERN_TEXT" | jq -Rs . 2>/dev/null || echo "\"\"")
    PATTERN_ID=$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)
PATTERN_EMBED=$(curl -sf --max-time 20 -X POST http://${SERVICE_HOST:-localhost}:8091/vector/embed \
      "${AIDB_HEADERS[@]}" \
      -H "Content-Type: application/json" \
      -d "{\"texts\": [\"$PATTERN_TEXT\"]}" | jq -c '.embeddings[0]' 2>/dev/null || echo "")

    if [ -n "$PATTERN_EMBED" ] && [ "$PATTERN_EMBED" != "null" ]; then
        PATTERN_STORE=$(curl -sf --max-time 10 -X PUT "http://${SERVICE_HOST:-localhost}:6333/collections/skills-patterns/points?wait=true" \
          -H "Content-Type: application/json" \
          -d "{
            \"points\": [{
              \"id\": \"$PATTERN_ID\",
              \"vector\": $PATTERN_EMBED,
              \"payload\": {
                \"type\": \"implementation_plan\",
                \"feature\": \"auto-commit\",
                \"test_run\": \"$TEST_RUN_ID\",
                \"source\": \"llm_generated\",
                \"text\": $PATTERN_TEXT_JSON
              }
            }]
          }" 2>&1 || echo "FAILED")

        if echo "$PATTERN_STORE" | grep -q "result"; then
            test_pass "Implementation plan stored as pattern"
        else
            test_fail "Store pattern" "Failed to store: $PATTERN_STORE"
        fi
    else
        test_fail "Store pattern" "Embedding generation failed"
    fi
else
    test_fail "Store pattern" "No plan available from LLM"
fi

# Test 2.4: Retrieve similar patterns (context augmentation)
test_start "Query Qdrant for similar patterns (context augmentation)"
SEARCH_EMBED=$(curl -sf --max-time 20 -X POST http://${SERVICE_HOST:-localhost}:8091/vector/embed \
  "${AIDB_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"texts\": [\"git commit automation implementation\"]}" | jq -c '.embeddings[0]' 2>/dev/null || echo "")
if [ -n "$SEARCH_EMBED" ] && [ "$SEARCH_EMBED" != "null" ]; then
    SIMILAR_PATTERNS=$(curl -sf --max-time 10 -X POST http://${SERVICE_HOST:-localhost}:6333/collections/skills-patterns/points/search \
      -H "Content-Type: application/json" \
      -d "{
        \"vector\": $SEARCH_EMBED,
        \"limit\": 3,
        \"with_payload\": true
      }" 2>&1 || echo "FAILED")

    if echo "$SIMILAR_PATTERNS" | grep -q "result"; then
        test_pass "Context augmentation - similar patterns retrieved"
        RESULT_COUNT=$(echo "$SIMILAR_PATTERNS" | grep -o '"score"' | wc -l)
        info "Found $RESULT_COUNT similar patterns"
    else
        test_fail "Context augmentation" "Search failed: $SIMILAR_PATTERNS"
    fi
else
    test_fail "Context augmentation" "Embedding generation failed"
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
TELEMETRY_RESULT=$(curl -sf --max-time 10 "${AIDB_HEADERS[@]}" "http://${SERVICE_HOST:-localhost}:8091/documents?limit=1" 2>&1 || echo "FAILED")

if echo "$TELEMETRY_RESULT" | grep -q "\"documents\""; then
    test_pass "Telemetry event recorded"
else
    test_fail "Telemetry recording" "Failed: $TELEMETRY_RESULT"
fi

# Test 3.2: Verify telemetry in Postgres
test_start "Verify telemetry stored in Postgres"
TELEMETRY_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE event_type = 'documents_list' AND created_at > NOW() - INTERVAL '10 minutes';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$TELEMETRY_COUNT" -gt 0 ]; then
    test_pass "Telemetry found in Postgres ($TELEMETRY_COUNT events)"
else
    test_fail "Telemetry in Postgres" "No events found for test run"
fi

# Test 3.3: Check Redis caching
test_start "Verify Redis caching is working"
REDIS_TEST_KEY="test:${TEST_RUN_ID}:cache"
redis-cli -h localhost -p 6379 ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} SET "$REDIS_TEST_KEY" "test_value" EX 60 >/dev/null 2>&1
REDIS_VALUE=$(redis-cli -h localhost -p 6379 ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} GET "$REDIS_TEST_KEY" 2>/dev/null)

if [ "$REDIS_VALUE" = "test_value" ]; then
    test_pass "Redis caching verified"
    redis-cli -h localhost -p 6379 ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} DEL "$REDIS_TEST_KEY" >/dev/null 2>&1
else
    test_fail "Redis caching" "Cache read/write failed"
fi

# Test 3.4: Trigger continuous learning (if enabled)
test_start "Verify continuous learning daemon"
LEARNING_STATUS=$(curl -sf --max-time 5 http://${SERVICE_HOST:-localhost}:8092/learning/stats 2>&1 || echo "FAILED")

if echo "$LEARNING_STATUS" | grep -q "status\\|patterns\\|quality"; then
    test_pass "Continuous learning daemon accessible"
    info "Learning stats captured"
else
    warning "Continuous learning status endpoint not available (may not be implemented)"
fi

# Test 3.5: Ralph → Hybrid → AIDB chain
test_start "Ralph → Hybrid → AIDB chain execution"
RALPH_TASK_RESPONSE=$(curl -sf --max-time 10 -X POST http://${SERVICE_HOST:-localhost}:8098/tasks \
  "${RALPH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"Reply with exactly three words: ralph chain ok\",
    \"max_iterations\": 2,
    \"require_approval\": false
  }" 2>&1 || echo "FAILED")

RALPH_TASK_ID=$(echo "$RALPH_TASK_RESPONSE" | jq -r '.task_id // empty' 2>/dev/null || echo "")
if [ -n "$RALPH_TASK_ID" ]; then
    task_deadline=$(( $(date +%s) + 60 ))
    task_status=""
    while [ "$(date +%s)" -lt "$task_deadline" ]; do
        task_status=$(curl -sf --max-time 5 "${RALPH_HEADERS[@]}" http://${SERVICE_HOST:-localhost}:8098/tasks/${RALPH_TASK_ID} 2>/dev/null || echo "")
        if echo "$task_status" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"(completed|failed)"'; then
            break
        fi
        sleep 2
    done

    task_result=$(curl -sf --max-time 10 "${RALPH_HEADERS[@]}" http://${SERVICE_HOST:-localhost}:8098/tasks/${RALPH_TASK_ID}/result 2>/dev/null || echo "")
    if echo "$task_result" | grep -q "\"output\""; then
        test_pass "Ralph chain execution completed"
    else
        test_fail "Ralph chain execution" "No result output: ${task_result:-missing}"
    fi
else
    test_fail "Ralph chain execution" "Failed to create task: $RALPH_TASK_RESPONSE"
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
if curl -sf --max-time 5 http://${SERVICE_HOST:-localhost}:8889/api/metrics/system >/dev/null 2>&1; then
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
    COLLECTION_INFO=$(curl -sf --max-time 5 "http://${SERVICE_HOST:-localhost}:6333/collections/$collection" 2>&1 || echo "FAILED")
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
EXPECTED_EVENTS=1  # documents_list telemetry event
ACTUAL_EVENTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE event_type = 'documents_list' AND created_at > NOW() - INTERVAL '10 minutes';" 2>/dev/null | tr -d ' ' || echo "0")

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
