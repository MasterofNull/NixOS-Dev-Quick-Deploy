#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
TMP_DIR="$(mktemp -d /tmp/smoke-continue-editor-flow-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf 'PASS: %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

if [[ -z "$HYBRID_API_KEY" && -r "$HYBRID_API_KEY_FILE" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "$HYBRID_API_KEY_FILE")"
fi
if [[ -z "$HYBRID_API_KEY" ]]; then
  for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
    if [[ -r "$candidate" ]]; then
      HYBRID_API_KEY="$(tr -d '[:space:]' < "$candidate")"
      break
    fi
  done
fi

curl_args=(--connect-timeout 5 --max-time 45 -sS)
if [[ -n "$HYBRID_API_KEY" ]]; then
  curl_args+=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

if ! curl -fsS --connect-timeout 5 --max-time 10 "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable; Continue editor smoke skipped"
  exit 0
fi

cat >"${TMP_DIR}/hints.json" <<'EOF'
{
  "query": "@aq-hints continue editor rescue",
  "fullInput": "@aq-hints continue editor rescue",
  "format": "continue",
  "context": {
    "agent_type": "continue"
  },
  "max_hints": 3
}
EOF
curl "${curl_args[@]}" -H 'Content-Type: application/json' \
  "${HYB_URL}/hints" --data @"${TMP_DIR}/hints.json" >"${TMP_DIR}/hints-resp.json"
jq -e 'type == "array" and length >= 1 and .[0].name == "aq-hints" and (.[0].content | test("AI Stack Hints"))' \
  "${TMP_DIR}/hints-resp.json" >/dev/null || fail "continue hints response invalid"
pass "Continue HTTP context provider hints"

curl "${curl_args[@]}" \
  "${HYB_URL}/workflow/plan?q=continue%20editor%20rescue%20message%20exceeds%20context%20limit" \
  >"${TMP_DIR}/plan-resp.json"
jq -e '.phases | length >= 5' "${TMP_DIR}/plan-resp.json" >/dev/null || fail "workflow/plan invalid for Continue editor smoke"
pass "workflow plan for Continue/editor rescue"

cat >"${TMP_DIR}/query.json" <<'EOF'
{
  "query": "Continue agent mode still says message exceeds context limit. Return a compact diagnosis path.",
  "requesting_agent": "continue",
  "requester_role": "orchestrator",
  "prefer_local": true,
  "generate_response": false,
  "context": {
    "agent_type": "continue",
    "editor_surface": "vscodium"
  }
}
EOF
curl "${curl_args[@]}" -H 'Content-Type: application/json' \
  "${HYB_URL}/query" --data @"${TMP_DIR}/query.json" >"${TMP_DIR}/query-resp.json"
jq -e '.orchestration.requesting_agent == "continue" and .metadata.orchestration.requester_role == "orchestrator"' \
  "${TMP_DIR}/query-resp.json" >/dev/null || fail "query orchestration metadata missing"
pass "query path preserves Continue caller identity"

cat >"${TMP_DIR}/feedback.json" <<'EOF'
{
  "query": "Continue editor rescue smoke",
  "correction": "The Continue-facing path must keep aq-hints context provider configured and treat oversized-input transport failures as harness bugs.",
  "original_response": "smoke validation output"
}
EOF
curl "${curl_args[@]}" -H 'Content-Type: application/json' \
  "${HYB_URL}/feedback" --data @"${TMP_DIR}/feedback.json" >"${TMP_DIR}/feedback-resp.json"
jq -e '.status == "recorded" and (.feedback_id | tostring | length > 0)' \
  "${TMP_DIR}/feedback-resp.json" >/dev/null || fail "feedback recording failed"
pass "feedback path records Continue editor smoke outcome"

printf 'PASS: Continue/editor prompt -> hints -> workflow -> query -> feedback smoke succeeded\n'
