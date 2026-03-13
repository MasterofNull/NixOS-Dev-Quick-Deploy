#!/usr/bin/env bash
set -euo pipefail

# Verify augment_query, hints feedback, and research endpoints surface active lesson refs.

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

TMP_DIR="$(mktemp -d /tmp/augment-research-lesson-refs-XXXXXX)"
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

cat > "${TMP_DIR}/augment.json.payload" <<'JSON'
{
  "query": "Summarize the bounded research lane and the approved California native plant sources.",
  "agent_type": "remote"
}
JSON

curl_json_with_retry "${TMP_DIR}/augment.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/augment_query" \
  --data @"${TMP_DIR}/augment.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/augment.json" >/dev/null

cat > "${TMP_DIR}/hints.json.payload" <<'JSON'
{
  "query": "research and summarize a source-bounded california native plant dataset",
  "context": {
    "agent_type": "codex"
  },
  "max_hints": 4
}
JSON

curl_json_with_retry "${TMP_DIR}/hints.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/hints" \
  --data @"${TMP_DIR}/hints.json.payload"
hint_id="$(jq -r '.hints[0].id // empty' "${TMP_DIR}/hints.json")"
[[ -n "${hint_id}" ]] || {
  echo "ERROR: no hint id returned for hints feedback smoke" >&2
  cat "${TMP_DIR}/hints.json" >&2 || true
  exit 1
}

cat > "${TMP_DIR}/hints-feedback.json.payload" <<JSON
{
  "hint_id": "${hint_id}",
  "helpful": true,
  "agent": "codex",
  "comment": "bounded lesson-ref parity smoke"
}
JSON

curl_json_with_retry "${TMP_DIR}/hints-feedback.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/hints/feedback" \
  --data @"${TMP_DIR}/hints-feedback.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/hints-feedback.json" >/dev/null

cat > "${TMP_DIR}/web-research.json.payload" <<'JSON'
{
  "urls": ["https://www.calflora.org/"],
  "selectors": ["main", "#content"],
  "max_text_chars": 500
}
JSON

curl_json_with_retry "${TMP_DIR}/web-research.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/research/web/fetch" \
  --data @"${TMP_DIR}/web-research.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/web-research.json" >/dev/null

cat > "${TMP_DIR}/browser-research.json.payload" <<'JSON'
{
  "urls": ["https://www.calflora.org/entry/wgh.html#srch=t&taxon=Eschscholzia+californica"],
  "selectors": ["main", "#content"],
  "max_text_chars": 500
}
JSON

curl_json_with_retry "${TMP_DIR}/browser-research.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/research/web/browser-fetch" \
  --data @"${TMP_DIR}/browser-research.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/browser-research.json" >/dev/null

cat > "${TMP_DIR}/curated-research.json.payload" <<'JSON'
{
  "workflow": "native-plants-california",
  "inputs": {
    "query": "california native plants",
    "county": "Los Angeles"
  },
  "max_text_chars": 500
}
JSON

curl_json_with_retry "${TMP_DIR}/curated-research.json" "${json_hdr[@]}" -X POST "${HYBRID_URL}/research/workflows/curated-fetch" \
  --data @"${TMP_DIR}/curated-research.json.payload"
jq -e '.active_lesson_refs | length >= 1' "${TMP_DIR}/curated-research.json" >/dev/null

echo "PASS: augment_query, hints feedback, and research endpoints surface active lesson refs"
