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

TMP_DIR="$(mktemp -d /tmp/query-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/query.json.payload" <<'EOF'
{
  "query": "continue with the current runtime lesson and keep the response bounded",
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
  --data @"${TMP_DIR}/query.json.payload" > "${TMP_DIR}/query.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/query.json" >/dev/null
jq -e '.metadata.active_lesson_refs | length >= 1' "${TMP_DIR}/query.json" >/dev/null
jq -e '.metadata.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/query.json" >/dev/null

printf 'PASS: query surfaces active lesson refs\n'
