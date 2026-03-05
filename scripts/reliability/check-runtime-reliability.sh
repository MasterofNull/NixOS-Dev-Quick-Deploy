#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 2
  fi
}

require_cmd curl
require_cmd jq

HYBRID_KEY="${HYBRID_API_KEY:-}"
HYBRID_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -z "${HYBRID_KEY}" && -r "${HYBRID_KEY_FILE}" ]]; then
  HYBRID_KEY="$(tr -d '[:space:]' < "${HYBRID_KEY_FILE}")"
fi

check_json_field() {
  local name="$1"
  local url="$2"
  local jq_expr="$3"
  local expected="${4:-}"
  local headers=()
  if [[ "${url}" == "${HYBRID_URL%/}"* && -n "${HYBRID_KEY}" ]]; then
    headers+=(-H "X-API-Key: ${HYBRID_KEY}")
  fi

  local body
  if ! body="$(curl -fsS --max-time 8 --connect-timeout 3 "${headers[@]}" "${url}")"; then
    echo "FAIL ${name}: request failed (${url})"
    return 1
  fi

  local value
  value="$(printf '%s' "${body}" | jq -r "${jq_expr}" 2>/dev/null || true)"
  if [[ -z "${value}" || "${value}" == "null" ]]; then
    echo "FAIL ${name}: field missing (${jq_expr})"
    return 1
  fi
  if [[ -n "${expected}" && "${value}" != "${expected}" ]]; then
    echo "FAIL ${name}: expected=${expected} got=${value}"
    return 1
  fi
  echo "PASS ${name}: ${value}"
}

fail=0

check_json_field "AIDB health detailed status" "${AIDB_URL%/}/health/detailed" '.status' || fail=1
check_json_field "AIDB health has circuit_breakers" "${AIDB_URL%/}/health" '.circuit_breakers | type' "object" || fail=1

check_json_field "Hybrid health detailed status" "${HYBRID_URL%/}/health/detailed" '.status' || fail=1
check_json_field "Hybrid health detailed dependencies" "${HYBRID_URL%/}/health/detailed" '.dependencies | type' "object" || fail=1
check_json_field "Hybrid health detailed performance" "${HYBRID_URL%/}/health/detailed" '.performance | type' "object" || fail=1

check_json_field "Ralph health detailed status" "${RALPH_URL%/}/health/detailed" '.status' || fail=1
check_json_field "Ralph health detailed dependencies" "${RALPH_URL%/}/health/detailed" '.dependencies | type' "object" || fail=1
check_json_field "Ralph health detailed performance" "${RALPH_URL%/}/health/detailed" '.performance | type' "object" || fail=1

if [[ "${fail}" -ne 0 ]]; then
  echo "Runtime reliability checks failed." >&2
  exit 1
fi

echo "Runtime reliability checks passed."
