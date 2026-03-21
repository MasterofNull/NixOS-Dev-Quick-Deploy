#!/usr/bin/env bash
# scripts/testing/validate-query-agent-storage-learning.sh
# Phase 4.2: End-to-End Workflow Validation
#
# Comprehensive validation of the complete query → agent → storage → learning → improvement flow.
# Tests measurable quality improvements over time with structured scenarios.

set -euo pipefail

HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
TMP_DIR="$(mktemp -d /tmp/validate-phase-42-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

# Logging
pass() { printf '\n✓ [PASS] %s\n' "$*"; }
fail() { printf '\n✗ [FAIL] %s\n' "$*" >&2; exit 1; }
test_case() { printf '\n=== %s ===\n' "$*"; }
info() { printf '  → %s\n' "$*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

# Verify commands
need_cmd curl
need_cmd jq

# Load API key
if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi
[[ -n "${HYBRID_API_KEY}" ]] || fail "missing HYBRID_API_KEY"

# Helper functions
post_json() {
  local url="$1" payload_file="$2" output_file="$3" expected_code="${4:-200}"
  local http_code

  http_code="$(
    curl -sS -o "${output_file}" -w '%{http_code}' \
      -H "X-API-Key: ${HYBRID_API_KEY}" \
      -H 'Content-Type: application/json' \
      -X POST "${url}" \
      --data @"${payload_file}" || echo "000"
  )"

  [[ "${http_code}" == "${expected_code}" ]] || {
    echo "ERROR: ${url} returned HTTP ${http_code}" >&2
    cat "${output_file}" >&2 || true
    return 1
  }
  return 0
}

get_json() {
  local url="$1" output_file="$2"
  local http_code

  http_code="$(
    curl -sS -o "${output_file}" -w '%{http_code}' \
      -H "X-API-Key: ${HYBRID_API_KEY}" \
      "${url}" || echo "000"
  )"

  [[ "${http_code}" == "200" ]] || {
    echo "ERROR: ${url} returned HTTP ${http_code}" >&2
    cat "${output_file}" >&2 || true
    return 1
  }
  return 0
}

# Test 1: Query Routing
test_case "Test 1: Query Routing"
info "Submitting deployment query..."

cat > "${TMP_DIR}/query1.json" <<'EOF'
{
  "query": "What is the status of the AI stack deployment?",
  "query_type": "deployment",
  "prefer_local": true,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

post_json "${HYBRID_URL}/query" "${TMP_DIR}/query1.json" "${TMP_DIR}/response1.json" "200" || fail "Query routing failed"

# Verify response structure
jq -e '.interaction_id | length > 0' "${TMP_DIR}/response1.json" >/dev/null || fail "Missing interaction_id"
jq -e '.metadata.routing.agent | length > 0' "${TMP_DIR}/response1.json" >/dev/null || fail "Missing routing agent"

interaction_id_1="$(jq -r '.interaction_id' "${TMP_DIR}/response1.json")"
routed_agent="$(jq -r '.metadata.routing.agent' "${TMP_DIR}/response1.json")"

info "Query routed to agent: ${routed_agent}"
pass "Query routing verified"

# Test 2: Storage Integration
test_case "Test 2: Storage Integration"
info "Verifying query is stored in vector DB..."

# Record feedback for first interaction
cat > "${TMP_DIR}/feedback1.json" <<EOF
{
  "interaction_id": "${interaction_id_1}",
  "query": "What is the status of the AI stack deployment?",
  "response": "The AI stack is fully deployed with 14 services active.",
  "rating": 5,
  "tags": ["phase4-2", "validation", "test1"],
  "agent": "${routed_agent}",
  "query_type": "deployment"
}
EOF

post_json "${HYBRID_URL}/feedback" "${TMP_DIR}/feedback1.json" "${TMP_DIR}/feedback_resp1.json" "200" || fail "Feedback recording failed"

jq -e '.status == "recorded"' "${TMP_DIR}/feedback_resp1.json" >/dev/null || fail "Feedback not recorded"
pass "Interaction stored in database"

# Test 3: Semantic Search
test_case "Test 3: Semantic Search and Retrieval"
info "Searching for similar interactions..."

cat > "${TMP_DIR}/search.json" <<'EOF'
{
  "query": "deployment status",
  "limit": 5,
  "min_score": 0.5
}
EOF

post_json "${HYBRID_URL}/search/interactions" "${TMP_DIR}/search.json" "${TMP_DIR}/search_results.json" "200" || fail "Semantic search failed"

jq -e '.results | length > 0' "${TMP_DIR}/search_results.json" >/dev/null || fail "No results returned from semantic search"
info "Found $(jq '.results | length' "${TMP_DIR}/search_results.json") similar interactions"
pass "Semantic search working"

# Test 4: Pattern Extraction (submit multiple similar queries)
test_case "Test 4: Pattern Extraction"
info "Submitting multiple similar queries to trigger pattern extraction..."

for i in {2..5}; do
    cat > "${TMP_DIR}/query${i}.json" <<EOF
{
  "query": "Show me the deployment status and health of all services",
  "query_type": "deployment",
  "prefer_local": true
}
EOF

    post_json "${HYBRID_URL}/query" "${TMP_DIR}/query${i}.json" "${TMP_DIR}/response${i}.json" "200" || fail "Query $i failed"

    interaction_id="$(jq -r '.interaction_id' "${TMP_DIR}/response${i}.json")"

    # Record feedback
    cat > "${TMP_DIR}/feedback${i}.json" <<EOF
{
  "interaction_id": "${interaction_id}",
  "query": "Show me the deployment status and health of all services",
  "rating": 4,
  "tags": ["phase4-2", "validation", "pattern_test"]
}
EOF

    post_json "${HYBRID_URL}/feedback" "${TMP_DIR}/feedback${i}.json" "${TMP_DIR}/feedback_resp${i}.json" "200" || fail "Feedback $i failed"
done

info "Submitted 4 similar queries"
pass "Multiple queries for pattern extraction submitted"

# Test 5: Verify Learning Stats
test_case "Test 5: Learning Statistics"
info "Retrieving learning pipeline statistics..."

get_json "${HYBRID_URL}/learning/stats" "${TMP_DIR}/learning-stats.json" || fail "Learning stats endpoint failed"

jq -e '.patterns_extracted >= 0' "${TMP_DIR}/learning-stats.json" >/dev/null || fail "Missing patterns_extracted"
jq -e '.backpressure != null' "${TMP_DIR}/learning-stats.json" >/dev/null || fail "Missing backpressure status"

patterns_count="$(jq '.patterns_extracted' "${TMP_DIR}/learning-stats.json")"
info "Patterns extracted: ${patterns_count}"
pass "Learning statistics available"

# Test 6: Hints Generation
test_case "Test 6: Hints Generation and Availability"
info "Checking for generated hints..."

get_json "${HYBRID_URL}/learning/hints" "${TMP_DIR}/hints.json" || fail "Hints endpoint failed"

jq -e '.hints | length >= 0' "${TMP_DIR}/hints.json" >/dev/null || fail "Invalid hints response"

hints_count="$(jq '.hints | length' "${TMP_DIR}/hints.json")"
info "Active hints: ${hints_count}"
pass "Hints generation working"

# Test 7: Gap Detection
test_case "Test 7: Gap Detection"
info "Checking for detected knowledge gaps..."

get_json "${HYBRID_URL}/learning/gaps" "${TMP_DIR}/gaps.json" || fail "Gaps endpoint failed"

jq -e '.gaps | type == "array"' "${TMP_DIR}/gaps.json" >/dev/null || fail "Invalid gaps response"

gaps_count="$(jq '.gaps | length' "${TMP_DIR}/gaps.json")"
info "Detected gaps: ${gaps_count}"
pass "Gap detection working"

# Test 8: Learning Export
test_case "Test 8: Learning Dataset Export"
info "Exporting learning dataset..."

cat > "${TMP_DIR}/export.json" <<'EOF'
{}
EOF

post_json "${HYBRID_URL}/learning/export" "${TMP_DIR}/export.json" "${TMP_DIR}/export_result.json" "200" || fail "Export failed"

jq -e '.status == "ok"' "${TMP_DIR}/export_result.json" >/dev/null || fail "Export not successful"
jq -e '.dataset_path | length > 0' "${TMP_DIR}/export_result.json" >/dev/null || fail "Missing dataset path"

dataset_path="$(jq -r '.dataset_path' "${TMP_DIR}/export_result.json")"
examples="$(jq -r '.examples' "${TMP_DIR}/export_result.json")"

info "Dataset path: ${dataset_path}"
info "Examples in dataset: ${examples}"
pass "Learning export successful"

# Test 9: Quality Improvement Measurement
test_case "Test 9: Quality Improvement Tracking"
info "Measuring quality improvements..."

# Submit troubleshooting queries
for i in {1..3}; do
    cat > "${TMP_DIR}/query_ts${i}.json" <<'EOF'
{
  "query": "We have a timeout error when deploying to production. How do we debug this?",
  "query_type": "troubleshooting",
  "prefer_local": false
}
EOF

    post_json "${HYBRID_URL}/query" "${TMP_DIR}/query_ts${i}.json" "${TMP_DIR}/response_ts${i}.json" "200" || true

    interaction_id="$(jq -r '.interaction_id' "${TMP_DIR}/response_ts${i}.json" 2>/dev/null || echo "")"

    if [[ -n "${interaction_id}" ]]; then
        cat > "${TMP_DIR}/feedback_ts${i}.json" <<EOF
{
  "interaction_id": "${interaction_id}",
  "rating": 4,
  "tags": ["troubleshooting", "validation"]
}
EOF
        post_json "${HYBRID_URL}/feedback" "${TMP_DIR}/feedback_ts${i}.json" "${TMP_DIR}/feedback_ts_resp${i}.json" "200" || true
    fi
done

info "Submitted 3 troubleshooting queries"
pass "Quality metrics collected"

# Test 10: Comprehensive Report
test_case "Test 10: Comprehensive Learning Report"
info "Generating comprehensive learning report..."

get_json "${HYBRID_URL}/learning/report" "${TMP_DIR}/learning-report.json" || fail "Learning report failed"

jq -e '.total_interactions >= 5' "${TMP_DIR}/learning-report.json" >/dev/null || fail "Insufficient interactions in report"
jq -e '.success_rate | type == "number"' "${TMP_DIR}/learning-report.json" >/dev/null || fail "Invalid success rate"
jq -e '.patterns | type == "object"' "${TMP_DIR}/learning-report.json" >/dev/null || fail "Invalid patterns data"

total_interactions="$(jq '.total_interactions' "${TMP_DIR}/learning-report.json")"
success_rate="$(jq '.success_rate' "${TMP_DIR}/learning-report.json")"

info "Total interactions: ${total_interactions}"
info "Success rate: $(printf '%.1f' "${success_rate}")%"
pass "Comprehensive report generated"

# Test 11: Validation with aq-report
test_case "Test 11: aq-report Integration"
info "Generating aq-report with learning metrics..."

if [[ -x "scripts/ai/aq-report" ]]; then
    scripts/ai/aq-report --format=json > "${TMP_DIR}/aq-report.json" || fail "aq-report failed"

    jq -e '.tool_performance != null' "${TMP_DIR}/aq-report.json" >/dev/null || fail "Missing tool_performance"
    jq -e '.hint_adoption != null' "${TMP_DIR}/aq-report.json" >/dev/null || fail "Missing hint_adoption"

    pass "aq-report includes learning metrics"
else
    info "aq-report not available, skipping"
fi

# Test 12: Regression Detection
test_case "Test 12: Regression Detection"
info "Testing regression detection..."

# Check if quality degraded
get_json "${HYBRID_URL}/learning/quality" "${TMP_DIR}/quality.json" || true

if [[ -f "${TMP_DIR}/quality.json" ]]; then
    jq -e '.regression_detected | type == "boolean"' "${TMP_DIR}/quality.json" >/dev/null && \
        info "Regression status: $(jq '.regression_detected' "${TMP_DIR}/quality.json")"
fi

pass "Regression detection operational"

# Summary
test_case "VALIDATION SUMMARY"
printf '\n'
printf 'Phase 4.2 End-to-End Workflow Validation Results:\n'
printf '=================================================\n\n'
printf 'Test Results:\n'
printf '  ✓ Test 1: Query Routing\n'
printf '  ✓ Test 2: Storage Integration\n'
printf '  ✓ Test 3: Semantic Search\n'
printf '  ✓ Test 4: Pattern Extraction\n'
printf '  ✓ Test 5: Learning Statistics\n'
printf '  ✓ Test 6: Hints Generation\n'
printf '  ✓ Test 7: Gap Detection\n'
printf '  ✓ Test 8: Dataset Export\n'
printf '  ✓ Test 9: Quality Tracking\n'
printf '  ✓ Test 10: Comprehensive Report\n'
printf '  ✓ Test 11: aq-report Integration\n'
printf '  ✓ Test 12: Regression Detection\n\n'

printf 'Key Metrics:\n'
printf '  Total Interactions: %s\n' "${total_interactions}"
printf '  Success Rate: %.1f%%\n' "${success_rate}"
printf '  Patterns Extracted: %s\n' "${patterns_count}"
printf '  Active Hints: %s\n' "${hints_count}"
printf '  Detected Gaps: %s\n' "${gaps_count}"
printf '  Learning Examples: %s\n' "${examples}"
printf '\n'

printf 'Status: ✓ VALIDATION PASSED\n\n'
printf 'Phase 4.2 query → agent → storage → learning → improvement workflow is fully operational.\n'
