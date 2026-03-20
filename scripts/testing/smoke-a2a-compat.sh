#!/usr/bin/env bash
# Smoke-test the hybrid coordinator A2A compatibility endpoints.
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
jq -e '.result.task.artifacts | length >= 1' "${TMP_DIR}/send-resp.json" >/dev/null || fail "message/send missing task artifacts"
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
jq -e '.result.status.message.parts[0].text | length > 0' "${TMP_DIR}/get-resp.json" >/dev/null || fail "tasks/get missing status message"
jq -e '.result.artifacts | length >= 1' "${TMP_DIR}/get-resp.json" >/dev/null || fail "tasks/get missing artifacts"
pass "A2A tasks/get"

cat > "${TMP_DIR}/list.json" <<'EOF'
{
  "jsonrpc": "2.0",
  "id": "list-1",
  "method": "tasks/list",
  "params": { "limit": 10 }
}
EOF

curl -fsS "${auth_hdr[@]}" -H 'Content-Type: application/json' -X POST "${HYB_URL}/a2a" \
  --data @"${TMP_DIR}/list.json" > "${TMP_DIR}/list-resp.json" || fail "tasks/list failed"
jq -e --arg tid "$task_id" '.result.tasks | map(.id) | index($tid) != null' "${TMP_DIR}/list-resp.json" >/dev/null || fail "tasks/list missing created task"
pass "A2A tasks/list"

curl -fsS "${auth_hdr[@]}" "${HYB_URL}/a2a/tasks/${task_id}/events" > "${TMP_DIR}/events.txt" || fail "task events stream failed"
rg -q 'event: task' "${TMP_DIR}/events.txt" || fail "task events missing task snapshot"
rg -q 'event: status-update' "${TMP_DIR}/events.txt" || fail "task events missing status update"
rg -q 'event: artifact-update' "${TMP_DIR}/events.txt" || fail "task events missing artifact update"
rg -q '"kind":"status-update"' "${TMP_DIR}/events.txt" || fail "task events missing A2A status payload"
rg -q '"kind":"artifact-update"' "${TMP_DIR}/events.txt" || fail "task events missing A2A artifact payload"
pass "A2A task events"

cat > "${TMP_DIR}/stream.json" <<'EOF'
{
  "jsonrpc": "2.0",
  "id": "stream-1",
  "method": "message/stream",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {"type": "text", "text": "Stream the A2A task acceptance envelope with status and artifacts."}
      ]
    },
    "safetyMode": "plan-readonly"
  }
}
EOF

curl -fsS "${auth_hdr[@]}" -H 'Content-Type: application/json' -X POST "${HYB_URL}/a2a" \
  --data @"${TMP_DIR}/stream.json" > "${TMP_DIR}/message-stream.txt" || fail "message/stream failed"
rg -q 'event: task' "${TMP_DIR}/message-stream.txt" || fail "message/stream missing task event"
rg -q 'event: status-update' "${TMP_DIR}/message-stream.txt" || fail "message/stream missing status update"
rg -q 'event: artifact-update' "${TMP_DIR}/message-stream.txt" || fail "message/stream missing artifact update"
rg -q '"jsonrpc":"2.0"' "${TMP_DIR}/message-stream.txt" || fail "message/stream missing jsonrpc envelope"
pass "A2A message/stream"

cat > "${TMP_DIR}/cancel.json" <<EOF
{
  "jsonrpc": "2.0",
  "id": "cancel-1",
  "method": "tasks/cancel",
  "params": {
    "id": "${task_id}",
    "reason": "smoke cancel verification"
  }
}
EOF

curl -fsS "${auth_hdr[@]}" -H 'Content-Type: application/json' -X POST "${HYB_URL}/a2a" \
  --data @"${TMP_DIR}/cancel.json" > "${TMP_DIR}/cancel-resp.json" || fail "tasks/cancel failed"
jq -e '.result.status.state == "canceled"' "${TMP_DIR}/cancel-resp.json" >/dev/null || fail "tasks/cancel did not mark task canceled"
pass "A2A tasks/cancel"

printf '\nAll A2A compatibility smoke checks passed.\n'
