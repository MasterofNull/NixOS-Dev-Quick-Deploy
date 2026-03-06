#!/usr/bin/env bash
# Prime AI harness tooling defaults and persist a post-deploy readiness snapshot.
set -euo pipefail

REPO_ROOT="${POST_DEPLOY_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DATA_DIR="${POST_DEPLOY_DATA_DIR:-/var/lib/ai-stack}"
HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
OUT_PATH="${POST_DEPLOY_AI_TOOLING_SNAPSHOT_OUT:-${DATA_DIR}/hybrid/telemetry/ai-tooling-prime-latest.json}"

if [[ "${1:-}" == "--output" ]]; then
  [[ -n "${2:-}" ]] || {
    echo "missing value for --output" >&2
    exit 2
  }
  OUT_PATH="$2"
  shift 2
fi

if [[ $# -gt 0 ]]; then
  echo "usage: $0 [--output <path>]" >&2
  exit 2
fi

log() {
  printf '[prime-ai-tooling] %s\n' "$*"
}

mkdir -p "$(dirname "${OUT_PATH}")"

AQD_BIN="${REPO_ROOT}/scripts/ai/aqd"
AQ_HINTS_BIN="${REPO_ROOT}/scripts/ai/aq-hints"
HARNESS_RPC_BIN="${REPO_ROOT}/scripts/ai/harness-rpc.js"

has_aqd=false
has_hints=false
has_harness_rpc=false
[[ -x "${AQD_BIN}" ]] && has_aqd=true
[[ -x "${AQ_HINTS_BIN}" ]] && has_hints=true
[[ -f "${HARNESS_RPC_BIN}" ]] && has_harness_rpc=true

workflow_list_raw=""
workflow_list_json='[]'
if [[ "${has_aqd}" == true ]]; then
  workflow_list_raw="$("${AQD_BIN}" workflows list 2>/dev/null || true)"
  workflow_list_json="$(printf '%s\n' "${workflow_list_raw}" | awk -F'\\. ' '/^[0-9]+\./{print $2}' | jq -Rsc 'split("\n") | map(select(length > 0))')"
fi

hints_ok=false
hints_count=0
top_hint_id=""
if [[ "${has_hints}" == true ]]; then
  hints_json="$("${AQ_HINTS_BIN}" "post deploy tooling prime" --format=json --agent=codex 2>/dev/null || true)"
  if [[ -n "${hints_json}" ]] && printf '%s' "${hints_json}" | jq -e '.' >/dev/null 2>&1; then
    hints_ok=true
    hints_count="$(printf '%s' "${hints_json}" | jq -r '(.hints // []) | length' 2>/dev/null || echo 0)"
    top_hint_id="$(printf '%s' "${hints_json}" | jq -r '.hints[0].id // ""' 2>/dev/null || echo "")"
  fi
fi

hybrid_health_ok=false
workflow_blueprints_ok=false
if curl -fsS --max-time 6 --connect-timeout 3 "${HYBRID_URL%/}/health" >/dev/null 2>&1; then
  hybrid_health_ok=true
fi
if curl -fsS --max-time 6 --connect-timeout 3 "${HYBRID_URL%/}/workflow/blueprints" >/dev/null 2>&1; then
  workflow_blueprints_ok=true
fi

jq -n \
  --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg repo_root "${REPO_ROOT}" \
  --arg hybrid_url "${HYBRID_URL}" \
  --arg out_path "${OUT_PATH}" \
  --argjson has_aqd "${has_aqd}" \
  --argjson has_hints "${has_hints}" \
  --argjson has_harness_rpc "${has_harness_rpc}" \
  --argjson hints_ok "${hints_ok}" \
  --argjson hints_count "${hints_count}" \
  --arg top_hint_id "${top_hint_id}" \
  --argjson hybrid_health_ok "${hybrid_health_ok}" \
  --argjson workflow_blueprints_ok "${workflow_blueprints_ok}" \
  --arg workflow_list_raw "${workflow_list_raw}" \
  --argjson workflows "${workflow_list_json}" \
  '{
    generated_at: $ts,
    repo_root: $repo_root,
    hybrid_url: $hybrid_url,
    outputs: {
      snapshot_path: $out_path
    },
    command_availability: {
      aqd: $has_aqd,
      aq_hints: $has_hints,
      harness_rpc_js: $has_harness_rpc
    },
    workflows: {
      discovered: $workflows,
      raw_text: $workflow_list_raw
    },
    hints_probe: {
      ok: $hints_ok,
      count: $hints_count,
      top_hint_id: $top_hint_id
    },
    harness_probe: {
      hybrid_health_ok: $hybrid_health_ok,
      workflow_blueprints_ok: $workflow_blueprints_ok
    }
  }' > "${OUT_PATH}"

log "tooling snapshot refreshed: ${OUT_PATH}"
