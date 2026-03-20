#!/usr/bin/env bash
# smoke-query-agent-storage-learning.sh
# Phase 4.2 validation: query -> agent -> storage -> learning flow.
#
# Verifies that:
# - a bounded hybrid /query request succeeds with orchestration metadata
# - feedback/correction data is accepted for the produced interaction id
# - learning stats and export surfaces are reachable and structured
# - aq-report sees the runtime telemetry surfaces needed for this workflow

set -euo pipefail

HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
TMP_DIR="$(mktemp -d /tmp/smoke-query-agent-storage-learning-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd curl
need_cmd jq

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi
[[ -n "${HYBRID_API_KEY}" ]] || fail "missing HYBRID_API_KEY or readable key file"

post_json_with_retry() {
  local url="$1"
  local payload_file="$2"
  local output_file="$3"
  local expected_code="${4:-200}"
  local attempt=1
  local max_attempts=8
  local http_code
  local retry_after

  while (( attempt <= max_attempts )); do
    http_code="$(
      curl -sS -o "${output_file}" -w '%{http_code}' \
        -H "X-API-Key: ${HYBRID_API_KEY}" \
        -H 'Content-Type: application/json' \
        -X POST "${url}" \
        --data @"${payload_file}" || true
    )"
    if [[ "${http_code}" == "429" ]]; then
      retry_after="$(jq -r '.retry_after_seconds // 2' "${output_file}" 2>/dev/null || printf '2')"
      sleep "${retry_after}"
      attempt=$((attempt + 1))
      continue
    fi
    [[ "${http_code}" == "${expected_code}" ]] || {
      echo "ERROR: ${url} returned HTTP ${http_code}" >&2
      cat "${output_file}" >&2 || true
      return 1
    }
    return 0
  done

  echo "ERROR: ${url} remained rate-limited after ${max_attempts} attempts" >&2
  cat "${output_file}" >&2 || true
  return 1
}

get_with_retry() {
  local url="$1"
  local output_file="$2"
  local attempt=1
  local max_attempts=6
  local http_code
  local retry_after

  while (( attempt <= max_attempts )); do
    http_code="$(
      curl -sS -o "${output_file}" -w '%{http_code}' \
        -H "X-API-Key: ${HYBRID_API_KEY}" \
        "${url}" || true
    )"
    if [[ "${http_code}" == "429" ]]; then
      retry_after="$(jq -r '.retry_after_seconds // 2' "${output_file}" 2>/dev/null || printf '2')"
      sleep "${retry_after}"
      attempt=$((attempt + 1))
      continue
    fi
    [[ "${http_code}" == "200" ]] || {
      echo "ERROR: ${url} returned HTTP ${http_code}" >&2
      cat "${output_file}" >&2 || true
      return 1
    }
    return 0
  done

  echo "ERROR: ${url} remained rate-limited after ${max_attempts} attempts" >&2
  cat "${output_file}" >&2 || true
  return 1
}

cat > "${TMP_DIR}/query.json.payload" <<'EOF'
{
  "query": "debug this failing regression safely and keep the bugfix bounded with explicit validation",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

post_json_with_retry "${HYBRID_URL}/query" "${TMP_DIR}/query.json.payload" "${TMP_DIR}/query.json" "200" \
  || fail "bounded query failed"
jq -e '.interaction_id | length > 0' "${TMP_DIR}/query.json" >/dev/null \
  || fail "query missing interaction_id"
jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/query.json" >/dev/null \
  || fail "query missing orchestration metadata"
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/query.json" >/dev/null \
  || fail "query missing prompt coaching"
interaction_id="$(jq -r '.interaction_id' "${TMP_DIR}/query.json")"
pass "query -> agent route succeeded"

cat > "${TMP_DIR}/feedback.json.payload" <<EOF
{
  "interaction_id": "${interaction_id}",
  "query": "phase 4.2 validation query",
  "correction": "Prefer bounded regression triage with explicit file scope and validation evidence.",
  "rating": 1,
  "tags": ["phase4-2", "validation"],
  "model": "local",
  "variant": "smoke"
}
EOF

post_json_with_retry "${HYBRID_URL}/feedback" "${TMP_DIR}/feedback.json.payload" "${TMP_DIR}/feedback.json" "200" \
  || fail "feedback recording failed"
jq -e '.status == "recorded" and (.feedback_id | length > 0)' "${TMP_DIR}/feedback.json" >/dev/null \
  || fail "feedback payload mismatch"
pass "feedback stored for learning"

get_with_retry "${HYBRID_URL}/learning/stats" "${TMP_DIR}/learning-stats.json" \
  || fail "learning stats failed"
jq -e '.backpressure != null and .deduplication != null' "${TMP_DIR}/learning-stats.json" >/dev/null \
  || fail "learning stats missing expected structure"
pass "learning stats readable"

cat > "${TMP_DIR}/learning-export.json.payload" <<'EOF'
{}
EOF

post_json_with_retry "${HYBRID_URL}/learning/export" "${TMP_DIR}/learning-export.json.payload" "${TMP_DIR}/learning-export.json" "200" \
  || fail "learning export failed"
jq -e '.status == "ok" and (.dataset_path | length > 0) and (.examples >= 1)' "${TMP_DIR}/learning-export.json" >/dev/null \
  || fail "learning export payload mismatch"
dataset_path="$(jq -r '.dataset_path' "${TMP_DIR}/learning-export.json")"
[[ -f "${dataset_path}" ]] || fail "learning export dataset path not found: ${dataset_path}"
pass "learning export available"

scripts/ai/aq-report --format=json > "${TMP_DIR}/aq-report.json" \
  || fail "aq-report generation failed"
jq -e '
  .tool_performance != null
  and .tool_performance.route_search != null
  and .recent_routing != null
  and .hint_adoption != null
  and .intent_contract_compliance != null
' "${TMP_DIR}/aq-report.json" >/dev/null || fail "aq-report missing expected telemetry sections"
pass "aq-report reflects query/storage/learning telemetry"

printf '\nPhase 4.2 query -> agent -> storage -> learning smoke passed.\n'
