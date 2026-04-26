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

# --- AIDB health ---
AIDB_URL="${AIDB_URL:-http://127.0.0.1:8002}"
AIDB_KEY_FILE="${AIDB_KEY_FILE:-/run/secrets/aidb_api_key}"
AIDB_KEY="${AIDB_KEY:-}"
[[ -z "$AIDB_KEY" && -r "$AIDB_KEY_FILE" ]] && AIDB_KEY="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"
aidb_hdr=()
[[ -n "$AIDB_KEY" ]] && aidb_hdr=(-H "X-API-Key: ${AIDB_KEY}")
if curl -fsS --max-time 5 --connect-timeout 2 "${aidb_hdr[@]}" "${AIDB_URL}/health" >/dev/null 2>&1; then
  pass "AIDB service healthy"
else
  warn "AIDB not reachable at ${AIDB_URL}"
fi

# --- Metric SLOs from aq-report (cache hit, route_search p95, recent health) ---
if command -v aq-report >/dev/null 2>&1; then
  report_json="$(aq-report --since=1h --format=json 2>/dev/null)" || report_json=""
  if [[ -n "$report_json" ]]; then
    cache_hit="$(printf '%s' "$report_json" | jq -r '.cache.hit_pct // empty')"
    cache_min="$(jq -r '.slo.cache_hit_rate_min // 85.0' "$SLO_FILE")"
    if [[ -n "$cache_hit" ]]; then
      if python3 -c "import sys; sys.exit(0 if float('${cache_hit}') >= float('${cache_min}') else 1)" 2>/dev/null; then
        pass "cache hit rate within SLO (${cache_hit}% >= ${cache_min}%)"
      else
        warn "cache hit rate below SLO (${cache_hit}% < ${cache_min}%)"
      fi
    else
      warn "cache hit rate: no data in last 1h window"
    fi

    p95="$(printf '%s' "$report_json" | jq -r '.tool_performance.route_search.p95_ms // empty')"
    p95_slo="$(jq -r '.slo.hybrid_query_p95_latency_ms' "$SLO_FILE")"
    if [[ -n "$p95" ]]; then
      if python3 -c "import sys; sys.exit(0 if float('${p95}') <= float('${p95_slo}') else 1)" 2>/dev/null; then
        pass "route_search p95 within SLO (${p95%.*}ms <= ${p95_slo}ms)"
      else
        warn "route_search p95 exceeds SLO (${p95%.*}ms > ${p95_slo}ms)"
      fi
    else
      warn "route_search p95: no data in last 1h window"
    fi

    rh_healthy="$(printf '%s' "$report_json" | jq -r '.recent_health.healthy // false')"
    slow_tools="$(printf '%s' "$report_json" | jq -r '.recent_health.slow_tools | length // 0')"
    flaky_tools="$(printf '%s' "$report_json" | jq -r '.recent_health.flaky_tools | length // 0')"
    if [[ "$rh_healthy" == "true" ]]; then
      pass "recent health: no slow/flaky tools in last 1h (slow=${slow_tools} flaky=${flaky_tools})"
    else
      warn "recent health degraded (slow=${slow_tools} flaky=${flaky_tools}) — check aq-report"
    fi
  else
    warn "aq-report produced no output; skipping metric SLO checks"
  fi
else
  warn "aq-report not found; skipping metric SLO checks"
fi
