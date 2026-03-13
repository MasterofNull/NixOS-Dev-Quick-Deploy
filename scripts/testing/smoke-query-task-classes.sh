#!/usr/bin/env bash
set -euo pipefail

HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" && -r "/run/secrets/hybrid_api_key" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
fi
[[ -n "${HYBRID_API_KEY}" ]] || {
  echo "ERROR: missing HYBRID_API_KEY or readable key file" >&2
  exit 2
}

TMP_DIR="$(mktemp -d /tmp/query-task-classes-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/bugfix.json.payload" <<'EOF'
{
  "query": "debug this failing regression safely and keep the bugfix bounded with explicit validation",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "continue",
  "requesting_agent": "continue",
  "requester_role": "orchestrator"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/query" \
  --data @"${TMP_DIR}/bugfix.json.payload" > "${TMP_DIR}/bugfix.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/bugfix.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/bugfix.json" >/dev/null

cat > "${TMP_DIR}/hardening.json.payload" <<'EOF'
{
  "query": "harden this nixos service declaratively and preserve health checks plus rollback guidance",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/query" \
  --data @"${TMP_DIR}/hardening.json.payload" > "${TMP_DIR}/hardening.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/hardening.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/hardening.json" >/dev/null

cat > "${TMP_DIR}/prsi.json.payload" <<'EOF'
{
  "query": "run one pessimistic self-improvement cycle with rollback and strict validation gates",
  "prefer_local": true,
  "generate_response": false,
  "agent_type": "codex",
  "requesting_agent": "codex",
  "requester_role": "orchestrator"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/query" \
  --data @"${TMP_DIR}/prsi.json.payload" > "${TMP_DIR}/prsi.json"

jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.prompt_coaching.score > 0' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.prompt_coaching.suggested_prompt | length > 0' "${TMP_DIR}/prsi.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/prsi.json" >/dev/null

printf 'PASS: query task-class smoke\n'
