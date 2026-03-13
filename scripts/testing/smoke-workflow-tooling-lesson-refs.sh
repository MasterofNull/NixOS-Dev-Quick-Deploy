#!/usr/bin/env bash
set -euo pipefail

# Verify /workflow/tooling-manifest surfaces accepted lesson references for direct tooling consumers.

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

TMP_DIR="$(mktemp -d /tmp/workflow-tooling-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H 'Content-Type: application/json' \
  -X POST "${HYBRID_URL}/workflow/tooling-manifest" \
  -d '{"query":"continue editor rescue planning lesson traceability"}' \
  > "${TMP_DIR}/tooling.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/tooling.json" >/dev/null
jq -e '.metadata.active_lesson_refs | length >= 1' "${TMP_DIR}/tooling.json" >/dev/null
jq -e '.tools | length >= 1' "${TMP_DIR}/tooling.json" >/dev/null

printf 'PASS: workflow/tooling-manifest surfaces active lesson refs\n'
