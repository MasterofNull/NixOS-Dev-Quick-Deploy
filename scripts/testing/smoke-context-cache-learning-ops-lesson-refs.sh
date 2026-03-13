#!/usr/bin/env bash
set -euo pipefail

# Verify context, cache, and learning helper endpoints surface active lesson refs.

HYBRID_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_COORDINATOR_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_COORDINATOR_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
[[ -n "${HYBRID_API_KEY}" ]] || {
  echo "ERROR: missing HYBRID_COORDINATOR_API_KEY" >&2
  exit 2
}

TMP_DIR="$(mktemp -d /tmp/context-cache-learning-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

curl_json_with_retry() {
  local output_file="$1"
  shift
  local attempt=1
  local max_attempts=8
  local http_code
  local retry_after

  while (( attempt <= max_attempts )); do
    http_code="$(curl -sS -o "${output_file}" -w '%{http_code}' "$@")"
    if [[ "${http_code}" == "429" ]]; then
      retry_after="$(jq -r '.retry_after_seconds // 2' "${output_file}" 2>/dev/null || printf '2')"
      sleep "${retry_after}"
      attempt=$((attempt + 1))
      continue
    fi
    [[ "${http_code}" == "200" ]] || {
      echo "ERROR: request failed with HTTP ${http_code}" >&2
      cat "${output_file}" >&2 || true
      return 1
    }
    return 0
  done

  echo "ERROR: request remained rate-limited after ${max_attempts} attempts" >&2
  cat "${output_file}" >&2 || true
  return 1
}

cat > "${TMP_DIR}/context.json.payload" <<'JSON'
{
  "session_id": "lesson-ref-context-smoke",
  "query": "Summarize the current bounded context for lesson-ref smoke coverage.",
  "context_level": "standard",
  "max_tokens": 256,
  "metadata": {
    "source": "smoke-context-cache-learning-ops-lesson-refs"
  }
}
JSON

curl_json_with_retry "${TMP_DIR}/context.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/context/multi_turn" \
  --data @"${TMP_DIR}/context.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/context.json" >/dev/null

cat > "${TMP_DIR}/cache-invalidate.json.payload" <<'JSON'
{
  "trigger": "manual",
  "scope": "all"
}
JSON

curl_json_with_retry "${TMP_DIR}/cache-invalidate.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/cache/invalidate" \
  --data @"${TMP_DIR}/cache-invalidate.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/cache-invalidate.json" >/dev/null
jq -e '.status == "ok"' "${TMP_DIR}/cache-invalidate.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/learning-process.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/learning/process" \
  --data '{}'
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/learning-process.json" >/dev/null
jq -e '.status == "ok"' "${TMP_DIR}/learning-process.json" >/dev/null

cat > "${TMP_DIR}/learning-ab-compare.json.payload" <<'JSON'
{
  "variant_a": "lesson-parity-a",
  "variant_b": "lesson-parity-b",
  "days": 30
}
JSON

curl_json_with_retry "${TMP_DIR}/learning-ab-compare.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/learning/ab_compare" \
  --data @"${TMP_DIR}/learning-ab-compare.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/learning-ab-compare.json" >/dev/null
jq -e '.status == "ok"' "${TMP_DIR}/learning-ab-compare.json" >/dev/null

echo "PASS: context, cache, and learning helper endpoints surface active lesson refs"
