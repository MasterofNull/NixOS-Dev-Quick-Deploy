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

TMP_DIR="$(mktemp -d /tmp/hints-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  "${HYBRID_URL}/hints?q=continue+with+the+current+agent+lesson+and+keep+the+response+bounded&agent=codex" \
  > "${TMP_DIR}/hints.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/hints.json" >/dev/null
jq -e '.feedback_contract.endpoint == "/hints/feedback"' "${TMP_DIR}/hints.json" >/dev/null

printf 'PASS: hints surface active lesson refs\n'
