#!/usr/bin/env bash
set -euo pipefail

# Verify delegated responses surface accepted lesson references for reviewer traceability.

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

TMP_DIR="$(mktemp -d /tmp/delegate-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/delegate.json.payload" <<'EOF'
{
  "task": "Return a one-word readiness check and keep the response bounded",
  "profile": "continue-local",
  "requesting_agent": "codex",
  "requester_role": "orchestrator",
  "messages": [
    {"role": "user", "content": "Reply with READY only."}
  ],
  "max_tokens": 24,
  "temperature": 0
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/control/ai-coordinator/delegate" \
  --data @"${TMP_DIR}/delegate.json.payload" > "${TMP_DIR}/delegate.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/delegate.json" >/dev/null
jq -e '.orchestration.requester_role == "orchestrator"' "${TMP_DIR}/delegate.json" >/dev/null

printf 'PASS: delegate surfaces active lesson refs\n'
