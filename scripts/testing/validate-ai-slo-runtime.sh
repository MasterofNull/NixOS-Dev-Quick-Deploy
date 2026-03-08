#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
SLO_FILE="${SLO_FILE:-${ROOT}/config/ai-slo-thresholds.json}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

[[ -f "$SLO_FILE" ]] || fail "missing SLO config: $SLO_FILE"
command -v jq >/dev/null 2>&1 || fail "missing jq"

jq -e '.version == 1 and .slo.switchboard_p95_latency_ms and .slo.error_rate_percent_max' "$SLO_FILE" >/dev/null || fail "invalid SLO config schema"
pass "SLO config schema"

if [[ -z "${HYBRID_API_KEY}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "${HYBRID_API_KEY_FILE}")"
fi
hyb_hdr=()
if [[ -n "${HYBRID_API_KEY}" ]]; then
  hyb_hdr=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

if curl -fsS --max-time 5 --connect-timeout 2 "${hyb_hdr[@]}" "${HYB_URL}/stats" >/dev/null 2>&1; then
  qdepth="$(curl -fsS --max-time 5 --connect-timeout 2 "${hyb_hdr[@]}" "${HYB_URL}/status" | jq -r '.local_llm.queue_depth // 0')"
  max_q="$(jq -r '.slo.model_loading_queue_depth_max' "$SLO_FILE")"
  if [[ "$qdepth" =~ ^[0-9]+$ ]] && [[ "$qdepth" -le "$max_q" ]]; then
    pass "queue depth within SLO (${qdepth} <= ${max_q})"
  else
    warn "queue depth exceeds SLO (${qdepth} > ${max_q})"
  fi
else
  warn "hybrid coordinator unavailable/unauthorized; runtime SLO checks skipped"
fi

if curl -fsS --max-time 5 --connect-timeout 2 "${SWB_URL}/v1/models" >/dev/null 2>&1; then
  pass "switchboard reachable for latency/error SLO monitoring"
else
  warn "switchboard unavailable; runtime SLO checks skipped"
fi
