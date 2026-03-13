#!/usr/bin/env bash
set -euo pipefail

# Verify health, search, memory, harness, cache, learning, and model-status endpoints surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/health-memory-learning-lesson-refs-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
json_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}" -H "Content-Type: application/json")

curl_json_with_retry() {
  local output_file="$1"
  shift
  local attempt=1
  local max_attempts=6
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

curl_json_with_retry "${TMP_DIR}/health.json" "${hdr[@]}" "${HYBRID_URL}/health"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/health.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/health-detailed.json" "${hdr[@]}" "${HYBRID_URL}/health/detailed"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/health-detailed.json" >/dev/null

cat > "${TMP_DIR}/tree-search.json.payload" <<'JSON'
{
  "query": "lesson ref parity smoke for tree search",
  "limit": 2,
  "keyword_limit": 2,
  "score_threshold": 0.0
}
JSON

curl_json_with_retry "${TMP_DIR}/tree-search.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/search/tree" \
  --data @"${TMP_DIR}/tree-search.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/tree-search.json" >/dev/null

cat > "${TMP_DIR}/memory-store.json.payload" <<'JSON'
{
  "memory_type": "semantic",
  "summary": "lesson ref parity smoke memory",
  "content": "store one bounded memory item for lesson reference parity smoke",
  "metadata": {
    "source": "smoke-health-memory-learning-lesson-refs"
  }
}
JSON

curl_json_with_retry "${TMP_DIR}/memory-store.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/memory/store" \
  --data @"${TMP_DIR}/memory-store.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/memory-store.json" >/dev/null

cat > "${TMP_DIR}/memory-recall.json.payload" <<'JSON'
{
  "query": "lesson ref parity smoke memory",
  "limit": 2
}
JSON

curl_json_with_retry "${TMP_DIR}/memory-recall.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/memory/recall" \
  --data @"${TMP_DIR}/memory-recall.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/memory-recall.json" >/dev/null

cat > "${TMP_DIR}/harness-eval.json.payload" <<'JSON'
{
  "query": "lesson ref parity smoke harness eval",
  "mode": "auto"
}
JSON

curl_json_with_retry "${TMP_DIR}/harness-eval.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/harness/eval" \
  --data @"${TMP_DIR}/harness-eval.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/harness-eval.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/harness-stats.json" "${hdr[@]}" "${HYBRID_URL}/harness/stats"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/harness-stats.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/harness-scorecard.json" "${hdr[@]}" "${HYBRID_URL}/harness/scorecard"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/harness-scorecard.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/cache-stats.json" "${hdr[@]}" "${HYBRID_URL}/cache/stats"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/cache-stats.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/learning-stats.json" "${hdr[@]}" "${HYBRID_URL}/learning/stats"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/learning-stats.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/learning-export.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/learning/export" \
  --data '{}'
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/learning-export.json" >/dev/null

curl_json_with_retry "${TMP_DIR}/model-status.json" "${hdr[@]}" "${HYBRID_URL}/model/status"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/model-status.json" >/dev/null

echo "PASS: health, memory, harness, cache, learning, and model endpoints surface active lesson refs"
