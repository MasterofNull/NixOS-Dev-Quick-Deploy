#!/usr/bin/env bash
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
TMP_DIR="$(mktemp -d /tmp/smoke-a2a-compat-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd curl
need_cmd jq

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

auth_hdr=()
if [[ -n "$HYBRID_API_KEY" ]]; then
  auth_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

curl -fsS "${HYB_URL}/.well-known/agent.json" > "${TMP_DIR}/agent.json" || fail "agent card endpoint failed"
jq -e '.protocolVersion == "0.3.0"' "${TMP_DIR}/agent.json" >/dev/null || fail "agent card protocol version mismatch"
jq -e '.endpoints.rpc | endswith("/a2a")' "${TMP_DIR}/agent.json" >/dev/null || fail "agent card missing rpc endpoint"
pass "A2A agent card"

cat > "${TMP_DIR}/send.json" <<'EOF'
{
  "jsonrpc": "2.0",
  "id": "send-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {"type": "text", "text": "Resume the A2A parity validation slice and keep it bounded."}
      ]
    },
    "safetyMode": "plan-readonly"
  }
}
EOF

send_code="$(curl -sS -o "${TMP_DIR}/send-resp.json" -w "%{http_code}" "${auth_hdr[@]}" \
  -H 'Content-Type: application/json' \
  -X POST "${HYB_URL}/a2a" \
  --data @"${TMP_DIR}/send.json" || true)"

if [[ "$send_code" == "401" && -z "$HYBRID_API_KEY" ]]; then
  warn "hybrid API key required but unavailable; authenticated A2A RPC checks skipped"
  exit 0
fi

[[ "$send_code" == "200" ]] || fail "message/send returned code=${send_code}"
task_id="$(jq -r '.result.task.id // empty' "${TMP_DIR}/send-resp.json")"
[[ -n "$task_id" ]] || fail "message/send missing task id"
jq -e '.result.stream.url | contains("/a2a/tasks/")' "${TMP_DIR}/send-resp.json" >/dev/null || fail "message/send missing stream url"
pass "A2A message/send"

cat > "${TMP_DIR}/get.json" <<EOF
{
  "jsonrpc": "2.0",
  "id": "get-1",
  "method": "tasks/get",
  "params": { "id": "${task_id}" }
}
EOF

curl -fsS "${auth_hdr[@]}" -H 'Content-Type: application/json' -X POST "${HYB_URL}/a2a" \
  --data @"${TMP_DIR}/get.json" > "${TMP_DIR}/get-resp.json" || fail "tasks/get failed"
jq -e --arg tid "$task_id" '.result.id == $tid' "${TMP_DIR}/get-resp.json" >/dev/null || fail "tasks/get task id mismatch"
pass "A2A tasks/get"

curl -fsS "${auth_hdr[@]}" "${HYB_URL}/a2a/tasks/${task_id}/events" > "${TMP_DIR}/events.txt" || fail "task events stream failed"
rg -q 'event: task.snapshot' "${TMP_DIR}/events.txt" || fail "task events missing snapshot"
rg -q 'event: task.complete' "${TMP_DIR}/events.txt" || fail "task events missing completion marker"
pass "A2A task events"

printf '\nAll A2A compatibility smoke checks passed.\n'
