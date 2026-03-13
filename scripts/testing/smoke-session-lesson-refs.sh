#!/usr/bin/env bash
set -euo pipefail

# Verify session info and clear responses surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/session-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")
hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")

cat > "${TMP_DIR}/start.json.payload" <<'EOF'
{
  "query": "create a compact multi-turn session for lesson ref parity"
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/context/multi_turn" \
  --data @"${TMP_DIR}/start.json.payload" > "${TMP_DIR}/start.json"
session_id="$(jq -r '.session_id // empty' "${TMP_DIR}/start.json")"
[[ -n "${session_id}" ]] || {
  echo "ERROR: context/multi_turn did not return session_id" >&2
  exit 1
}

curl -fsS "${hdr[@]}" "${HYBRID_URL}/session/${session_id}" > "${TMP_DIR}/session.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/session.json" >/dev/null

curl -fsS "${hdr[@]}" -X DELETE "${HYBRID_URL}/session/${session_id}" > "${TMP_DIR}/clear.json"
jq -e '.status == "cleared"' "${TMP_DIR}/clear.json" >/dev/null
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/clear.json" >/dev/null

printf 'PASS: session info and clear surface active lesson refs\n'
