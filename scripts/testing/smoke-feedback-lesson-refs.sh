#!/usr/bin/env bash
set -euo pipefail

# Verify feedback responses surface active lesson refs for traceability.

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

TMP_DIR="$(mktemp -d /tmp/feedback-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat > "${TMP_DIR}/feedback.json.payload" <<'EOF'
{
  "query": "bounded feedback lesson smoke",
  "correction": "Keep the task bounded, include evidence, and preserve rollback notes.",
  "original_response": "Initial bounded response.",
  "rating": 1,
  "tags": ["smoke", "lesson-refs"],
  "model": "local-smoke",
  "variant": "feedback-path"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/feedback" \
  --data @"${TMP_DIR}/feedback.json.payload" > "${TMP_DIR}/feedback.json"

jq -e '.status == "recorded"' "${TMP_DIR}/feedback.json" >/dev/null
jq -e '.feedback_id | length > 0' "${TMP_DIR}/feedback.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/feedback.json" >/dev/null

printf 'PASS: feedback surfaces active lesson refs\n'
