#!/usr/bin/env bash
set -euo pipefail

# Verify discovery helpers surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/discovery-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

cat > "${TMP_DIR}/discover.json.payload" <<'EOF'
{
  "level": "overview",
  "categories": ["workflow", "skills"],
  "token_budget": 300
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/discovery/capabilities" \
  --data @"${TMP_DIR}/discover.json.payload" > "${TMP_DIR}/discover.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/discover.json" >/dev/null

cat > "${TMP_DIR}/budget.json.payload" <<'EOF'
{
  "query_type": "repo_task",
  "context_level": "standard"
}
EOF

curl -fsS "${json_hdr[@]}" -X POST "${HYBRID_URL}/discovery/token_budget" \
  --data @"${TMP_DIR}/budget.json.payload" > "${TMP_DIR}/budget.json"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/budget.json" >/dev/null

printf 'PASS: discovery helpers surface active lesson refs\n'
