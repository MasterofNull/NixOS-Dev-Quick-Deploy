#!/usr/bin/env bash
# Seed hybrid HTTP endpoints to populate tool-audit coverage with diverse tools.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../../../config/service-endpoints.sh"

HYBRID_KEY="${HYBRID_API_KEY:-}"
HYBRID_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -z "${HYBRID_KEY}" && -r "${HYBRID_KEY_FILE}" ]]; then
  HYBRID_KEY="$(tr -d '[:space:]' < "${HYBRID_KEY_FILE}")"
fi

if [[ -z "${HYBRID_KEY}" ]]; then
  echo "seed-tool-audit-traffic: SKIP (missing HYBRID API key)" >&2
  exit 0
fi

hdr=(
  -H "Content-Type: application/json"
  -H "X-API-Key: ${HYBRID_KEY}"
)

pass=0
fail=0
required_min=5
run_post() {
  local endpoint="$1"
  local payload="$2"
  local code
  code="$(curl -sS -o /tmp/seed-tool-audit.out -w '%{http_code}' --max-time 12 --connect-timeout 3 "${hdr[@]}" -X POST "${HYBRID_URL%/}${endpoint}" -d "${payload}" || true)"
  if [[ "${code}" =~ ^[24] ]]; then
    # 4xx still exercises tool audit path and is acceptable for smoke coverage.
    printf '  OK  %s (HTTP %s)\n' "${endpoint}" "${code}"
    pass=$((pass + 1))
  else
    printf '  FAIL %s (HTTP %s)\n' "${endpoint}" "${code}" >&2
    fail=$((fail + 1))
  fi
}

run_get() {
  local endpoint="$1"
  local code
  code="$(curl -sS -o /tmp/seed-tool-audit.out -w '%{http_code}' --max-time 12 --connect-timeout 3 -H "X-API-Key: ${HYBRID_KEY}" "${HYBRID_URL%/}${endpoint}" || true)"
  if [[ "${code}" =~ ^[24] ]]; then
    printf '  OK  %s (HTTP %s)\n' "${endpoint}" "${code}"
    pass=$((pass + 1))
  else
    printf '  FAIL %s (HTTP %s)\n' "${endpoint}" "${code}" >&2
    fail=$((fail + 1))
  fi
}

echo "seed-tool-audit-traffic: exercising hybrid endpoints for audit coverage..."
run_get "/hints?q=nixos+module+options&agent=codex&max=3"
run_post "/hints/feedback" '{"hint_id":"seed_tool_audit_hint","helpful":true,"score":0.2,"comment":"seed_tool_audit","agent":"seed-tool-audit","task_id":"seed-tool-audit"}'
run_get "/discovery/capabilities?q=nixos+service+routing"
run_post "/workflow/plan" '{"query":"plan safe remediation steps for nixos module conflict"}'
run_post "/search/tree" '{"query":"nixos service module options basics","limit":3,"context":{"skip_gap_tracking":true,"source":"seed-tool-audit"}}'
run_post "/memory/recall" '{"query":"nixos flake lock behavior","top_k":3}'
run_post "/harness/eval" '{"query":"what is NixOS","mode":"auto","expected_keywords":["NixOS"]}'
run_post "/query" '{"query":"how does hybrid coordinator route queries","mode":"auto","prefer_local":false,"generate_response":false,"limit":3,"context":{"skip_gap_tracking":true,"source":"seed-tool-audit"}}'

echo "seed-tool-audit-traffic: ${pass} OK, ${fail} FAIL"
if (( pass < required_min )); then
  echo "seed-tool-audit-traffic: FAIL — insufficient successful endpoint coverage (${pass} < ${required_min})" >&2
  exit 1
fi
