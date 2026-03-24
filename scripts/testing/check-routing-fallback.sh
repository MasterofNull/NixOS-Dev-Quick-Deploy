#!/usr/bin/env bash
# Purpose: validate remote-routing fallback when the hybrid coordinator is reachable and authorized.
set -euo pipefail

HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
if [[ -z "${HYBRID_API_KEY}" ]]; then
  warn "missing HYBRID API key; skipping routing fallback probe"
  exit 0
fi

if ! curl -fsS --max-time 5 --connect-timeout 3 "${HYB_URL%/}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable at ${HYB_URL}; skipping routing fallback probe"
  exit 0
fi

hdr=(-H "Content-Type: application/json" -H "X-API-Key: ${HYBRID_API_KEY}")

before_json="$(mktemp)"
after_json="$(mktemp)"
trap 'rm -f "${before_json}" "${after_json}"' EXIT

curl -fsS --max-time 5 --connect-timeout 3 "http://127.0.0.1:9090/api/v1/query?query=sum(hybrid_llm_backend_selections_total%7Bbackend%3D%22remote%22%7D)%20or%20vector(0)" > "${before_json}" || true
before_remote="$(jq -r '.data.result[0].value[1] // 0' "${before_json}" 2>/dev/null || echo 0)"

attempt_query_with_retry() {
  local payload="$1"
  local attempts="${ROUTING_FALLBACK_MAX_ATTEMPTS:-3}"
  local max_retry_after="${ROUTING_FALLBACK_MAX_RETRY_AFTER_SECONDS:-20}"
  local attempt=1
  local response_file headers_file status retry_after

  response_file="$(mktemp)"
  headers_file="$(mktemp)"
  trap 'rm -f "${response_file}" "${headers_file}"' RETURN

  while (( attempt <= attempts )); do
    status="$(
      curl -sS \
        --connect-timeout 3 \
        --max-time 15 \
        -D "${headers_file}" \
        -o "${response_file}" \
        -w '%{http_code}' \
        "${hdr[@]}" \
        -X POST "${HYB_URL%/}/query" \
        -d "${payload}" || echo "000"
    )"

    if [[ "${status}" == "200" ]]; then
      cat "${response_file}"
      return 0
    fi

    if [[ "${status}" != "429" ]]; then
      echo "[FAIL] /query returned HTTP ${status}" >&2
      cat "${response_file}" >&2 || true
      return 1
    fi

    retry_after="$(awk 'BEGIN{IGNORECASE=1} /^Retry-After:/ {gsub("\r","",$2); print $2; exit}' "${headers_file}")"
    if [[ ! "${retry_after}" =~ ^[0-9]+$ ]]; then
      retry_after=5
    fi
    if (( retry_after > max_retry_after )); then
      retry_after="${max_retry_after}"
    fi
    echo "[INFO] transient rate limit on fallback probe; retrying in ${retry_after}s (attempt ${attempt}/${attempts})" >&2
    sleep "${retry_after}"
    attempt=$((attempt + 1))
  done

  echo "[FAIL] routing fallback probe exhausted retries after repeated 429 responses" >&2
  cat "${response_file}" >&2 || true
  return 1
}

attempt_remote_evidence() {
  local payload="$1"
  local resp backend route
  resp="$(attempt_query_with_retry "${payload}")"
  backend="$(jq -r '.backend // "unknown"' <<<"${resp}")"
  route="$(jq -r '.route // "unknown"' <<<"${resp}")"
  [[ -n "${route}" && "${route}" != "unknown" ]] || fail "query route missing"
  [[ "${backend}" == "remote" || "${route}" == "remote" ]]
}

remote_observed=false
payload_remote='{"query":"edge fallback validation: distributed multi-region policy rollout with rollback constraints","mode":"remote","prefer_local":false,"generate_response":false,"limit":4,"context":{"skip_gap_tracking":true,"source":"fallback-validation"}}'
payload_hybrid='{"query":"fallback stress validation requiring high-context synthesis and policy arbitration","mode":"hybrid","prefer_local":false,"generate_response":true,"limit":4,"context":{"skip_gap_tracking":true,"source":"fallback-validation"}}'
if attempt_remote_evidence "${payload_remote}"; then
  remote_observed=true
elif attempt_remote_evidence "${payload_hybrid}"; then
  remote_observed=true
fi

curl -fsS --max-time 5 --connect-timeout 3 "http://127.0.0.1:9090/api/v1/query?query=sum(hybrid_llm_backend_selections_total%7Bbackend%3D%22remote%22%7D)%20or%20vector(0)" > "${after_json}" || true
after_remote="$(jq -r '.data.result[0].value[1] // 0' "${after_json}" 2>/dev/null || echo 0)"

if awk "BEGIN{exit !(${after_remote} > ${before_remote})}"; then
  pass "remote backend counter increased (${before_remote} -> ${after_remote})"
else
  if [[ "${remote_observed}" == "true" ]]; then
    pass "remote backend selected in response path (counter unchanged on retrieval-only path)"
  else
    fail "remote fallback/backend evidence missing"
  fi
fi
