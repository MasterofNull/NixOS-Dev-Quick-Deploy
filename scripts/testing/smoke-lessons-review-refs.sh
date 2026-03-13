#!/usr/bin/env bash
set -euo pipefail

# Verify lesson review responses surface accepted lesson references after approval flow.

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

TMP_DIR="$(mktemp -d /tmp/lessons-review-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  "${HYBRID_URL}/control/ai-coordinator/lessons" > "${TMP_DIR}/lessons.json"

lesson_key="$(jq -r '.agent_lessons.active_lessons[0].lesson_key // .agent_lessons.entries[0].lesson_key // empty' "${TMP_DIR}/lessons.json")"
[[ -n "${lesson_key}" ]] || {
  echo "ERROR: no lesson key available for lessons review smoke" >&2
  exit 1
}

cat > "${TMP_DIR}/review.json.payload" <<EOF
{
  "lesson_key": "${lesson_key}",
  "state": "promoted",
  "reviewer": "codex",
  "comment": "bounded smoke review"
}
EOF

curl -fsS \
  -H "X-API-Key: ${HYBRID_API_KEY}" \
  -H "Content-Type: application/json" \
  -X POST "${HYBRID_URL}/control/ai-coordinator/lessons/review" \
  --data @"${TMP_DIR}/review.json.payload" > "${TMP_DIR}/review.json"

jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/review.json" >/dev/null
jq -e --arg lesson_key "${lesson_key}" '.reviewed_lesson.lesson_key == $lesson_key' "${TMP_DIR}/review.json" >/dev/null
jq -e '.reviewed_lesson.state == "promoted"' "${TMP_DIR}/review.json" >/dev/null

printf 'PASS: lessons/review surfaces active lesson refs\n'
