#!/usr/bin/env bash
set -euo pipefail

# Smoke-test the Continue -> coordinator authoritative ingress after activation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
TMP_DIR="$(mktemp -d /tmp/smoke-continue-coordinator-ingress-XXXXXX)"
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

curl_args=(--connect-timeout 5 --max-time 60 -sS)
if [[ -n "$HYBRID_API_KEY" ]]; then
  curl_args+=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

if ! curl -fsS --connect-timeout 5 --max-time 10 "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable; Continue coordinator ingress smoke skipped"
  exit 0
fi

status_code="$(
  curl "${curl_args[@]}" -o "${TMP_DIR}/models.json" -w '%{http_code}' \
    "${HYB_URL}/v1/models"
)"
if [[ "${status_code}" != "200" ]]; then
  fail "/v1/models failed with HTTP ${status_code}"
fi
jq -e '.data | type == "array"' "${TMP_DIR}/models.json" >/dev/null || fail "/v1/models returned invalid payload"
pass "coordinator OpenAI-compatible model listing"

cat >"${TMP_DIR}/planning.json" <<'EOF'
{
  "model": "AUTODETECT",
  "messages": [
    {
      "role": "user",
      "content": "Plan the next steps for validating the coordinator ingress migration."
    }
  ],
  "max_tokens": 120
}
EOF

planning_code="$(
  curl "${curl_args[@]}" -D "${TMP_DIR}/planning.headers" -o "${TMP_DIR}/planning.body" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -H 'X-AI-Prefer-Local: true' \
    "${HYB_URL}/v1/chat/completions" \
    --data @"${TMP_DIR}/planning.json"
)"
if [[ "${planning_code}" != "200" ]]; then
  fail "planning chat completion failed with HTTP ${planning_code}"
fi
grep -qi '^X-Coordinator-Task-Archetype: planning' "${TMP_DIR}/planning.headers" || fail "planning request did not classify as planning"
grep -qi '^X-Coordinator-Model-Class: lightweight' "${TMP_DIR}/planning.headers" || fail "planning request did not select lightweight model class"
grep -qi '^X-AI-Profile: default' "${TMP_DIR}/planning.headers" || fail "planning request did not route through default local lane"
pass "planning prompt routed through lightweight local-first lane"

remote_configured="$(
  curl "${curl_args[@]}" "${HYB_URL}/control/ai-coordinator/status" | jq -r '.remote_configured // false'
)"
if [[ "${remote_configured}" == "true" ]]; then
  cat >"${TMP_DIR}/coding.json" <<'EOF'
{
  "model": "AUTODETECT",
  "messages": [
    {
      "role": "user",
      "content": "Implement the coordinator ingress regression fix and summarize the expected verification."
    }
  ],
  "max_tokens": 180
}
EOF

  coding_code="$(
    curl "${curl_args[@]}" -D "${TMP_DIR}/coding.headers" -o "${TMP_DIR}/coding.body" -w '%{http_code}' \
      -H 'Content-Type: application/json' \
      -H 'X-AI-Prefer-Local: false' \
      "${HYB_URL}/v1/chat/completions" \
      --data @"${TMP_DIR}/coding.json"
  )"
  if [[ "${coding_code}" != "200" ]]; then
    fail "coding chat completion failed with HTTP ${coding_code}"
  fi
  grep -qi '^X-Coordinator-Task-Archetype: implementation' "${TMP_DIR}/coding.headers" || fail "coding request did not classify as implementation"
  grep -qi '^X-Coordinator-Model-Class: coding' "${TMP_DIR}/coding.headers" || fail "coding request did not select coding model class"
  grep -qi '^X-AI-Profile: remote-coding' "${TMP_DIR}/coding.headers" || fail "coding request did not route through remote-coding lane"
  pass "coding prompt routed through remote-coding lane"
else
  warn "remote lane not configured; remote-coding ingress smoke skipped"
fi

cat >"${TMP_DIR}/tools.json" <<'EOF'
{
  "model": "AUTODETECT",
  "messages": [
    {
      "role": "user",
      "content": "Use tools to inspect runtime status and report the result."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "runtime_status",
        "description": "Inspect runtime status",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    }
  ],
  "tool_choice": "auto",
  "max_tokens": 180
}
EOF

tool_code="$(
  curl "${curl_args[@]}" -D "${TMP_DIR}/tools.headers" -o "${TMP_DIR}/tools.body" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -H 'X-AI-Prefer-Local: true' \
    "${HYB_URL}/v1/chat/completions" \
    --data @"${TMP_DIR}/tools.json"
)"
if [[ "${tool_code}" != "200" && "${tool_code}" != "400" && "${tool_code}" != "503" ]]; then
  fail "tool-calling ingress returned unexpected HTTP ${tool_code}"
fi
grep -qi '^X-Coordinator-Task-Archetype: tool-calling' "${TMP_DIR}/tools.headers" || fail "tool request did not classify as tool-calling"
grep -qi '^X-Coordinator-Model-Class: tool-calling' "${TMP_DIR}/tools.headers" || fail "tool request did not select tool-calling model class"
pass "tool payload classified through tool-calling lane"

printf 'PASS: Continue coordinator ingress smoke succeeded\n'
