#!/usr/bin/env bash
# run-harness-improvement-pass.sh
# Executes a real-world AI harness improvement pass and emits a JSON summary.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

SEED_COUNT="${AI_HARNESS_IMPROVEMENT_SEED_COUNT:-10}"
SUMMARY_OUT="${AI_HARNESS_IMPROVEMENT_SUMMARY_PATH:-/tmp/ai-harness-improvement-latest.json}"
WORKSPACE="${AI_HARNESS_IMPROVEMENT_WORKSPACE:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

HYBRID_KEY="${HYBRID_API_KEY:-}"
HYBRID_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
if [[ -z "$HYBRID_KEY" && -r "$HYBRID_KEY_FILE" ]]; then
  HYBRID_KEY="$(tr -d '[:space:]' < "$HYBRID_KEY_FILE")"
fi

AIDER_KEY="${AIDER_WRAPPER_API_KEY:-}"
AIDER_KEY_FILE="${AIDER_WRAPPER_API_KEY_FILE:-/run/secrets/aider_wrapper_api_key}"
if [[ -z "$AIDER_KEY" && -r "$AIDER_KEY_FILE" ]]; then
  AIDER_KEY="$(tr -d '[:space:]' < "$AIDER_KEY_FILE")"
fi

START_TS="$(date +%s)"
FAILURES=0
HARN_EVAL_OK=false
AIDER_TASK_OK=false

log() {
  printf '[improvement-pass] %s\n' "$*" >&2
}

run_step() {
  local label="$1"
  shift
  log "STEP: ${label}"
  if "$@"; then
    log "PASS: ${label}"
  else
    log "FAIL: ${label}"
    FAILURES=$((FAILURES + 1))
  fi
}

run_step "Health check" "${SCRIPT_DIR}/check-mcp-health.sh"
run_step "Curate residual gaps" "${SCRIPT_DIR}/curate-residual-gaps.sh"
run_step "Seed routing + cache traffic" "${SCRIPT_DIR}/seed-routing-traffic.sh" --count "${SEED_COUNT}"

if [[ -n "$HYBRID_KEY" ]]; then
  if curl -fsS -X POST "${HYBRID_URL%/}/harness/eval" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${HYBRID_KEY}" \
    -d '{"query":"explain lib.mkIf and lib.mkForce","mode":"auto","expected_keywords":["mkIf","mkForce","NixOS"],"max_latency_ms":8000}' \
    >/tmp/ai-harness-eval.json; then
    HARN_EVAL_OK=true
    log "PASS: Harness eval probe"
  else
    FAILURES=$((FAILURES + 1))
    log "FAIL: Harness eval probe"
  fi
else
  log "SKIP: Harness eval probe (HYBRID API key unavailable)"
fi

if curl -fsS -X POST "${AIDER_WRAPPER_URL%/}/tasks" \
  -H "Content-Type: application/json" \
  ${AIDER_KEY:+-H "X-API-Key: ${AIDER_KEY}"} \
  -d "$(jq -cn --arg p 'analysis only: summarize docs/AGENT-PARITY-MATRIX.md in one sentence, no file edits' --arg f 'docs/AGENT-PARITY-MATRIX.md' --arg ws "${WORKSPACE}" '{prompt:$p,files:[$f],workspace:$ws}')" \
  >/tmp/ai-harness-aider-submit.json; then
  TASK_ID="$(jq -r '.task_id // ""' /tmp/ai-harness-aider-submit.json)"
  if [[ -n "$TASK_ID" ]]; then
    for _ in $(seq 1 30); do
      STATUS_JSON="$(curl -fsS "${AIDER_WRAPPER_URL%/}/tasks/${TASK_ID}/status" ${AIDER_KEY:+-H "X-API-Key: ${AIDER_KEY}"} || true)"
      STATUS="$(jq -r '.status // "unknown"' <<<"${STATUS_JSON}")"
      if [[ "$STATUS" == "success" ]]; then
        AIDER_TASK_OK=true
        break
      fi
      if [[ "$STATUS" == "error" || "$STATUS" == "canceled" ]]; then
        break
      fi
      sleep 2
    done
  fi
fi
if [[ "$AIDER_TASK_OK" == true ]]; then
  log "PASS: Aider-wrapper analysis fastpath probe"
else
  FAILURES=$((FAILURES + 1))
  log "FAIL: Aider-wrapper analysis fastpath probe"
fi

if ! "${SCRIPT_DIR}/aq-report" --since=7d --format=json >/tmp/ai-harness-aq-report.json; then
  FAILURES=$((FAILURES + 1))
  log "FAIL: aq-report JSON generation"
fi

END_TS="$(date +%s)"
DURATION_MS="$(( (END_TS - START_TS) * 1000 ))"

ROUTING_LOCAL_PCT="$(jq -r '.routing_split.local_pct // 0' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
CACHE_HIT_PCT="$(jq -r '.semantic_cache.hit_pct // 0' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
HINT_ADOPTION_PCT="$(jq -r '.hint_adoption.adoption_pct // 0' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
EVAL_LATEST_PCT="$(jq -r '.eval_trend.latest_pct // 0' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
TOP_GAPS_COUNT="$(jq -r '(.query_gaps // []) | length' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
TOOL_ROWS="$(jq -r '(.tool_performance // {}) | length' /tmp/ai-harness-aq-report.json 2>/dev/null || echo 0)"
SUCCESS=$([[ "$FAILURES" -eq 0 ]] && echo true || echo false)

SUMMARY_JSON="$(jq -cn \
  --arg run_id "improvement-$(date +%s)" \
  --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --argjson success "${SUCCESS}" \
  --argjson failures "${FAILURES}" \
  --argjson duration_ms "${DURATION_MS}" \
  --argjson harness_eval_ok "${HARN_EVAL_OK}" \
  --argjson aider_task_ok "${AIDER_TASK_OK}" \
  --argjson routing_local_pct "${ROUTING_LOCAL_PCT}" \
  --argjson cache_hit_pct "${CACHE_HIT_PCT}" \
  --argjson hint_adoption_pct "${HINT_ADOPTION_PCT}" \
  --argjson eval_latest_pct "${EVAL_LATEST_PCT}" \
  --argjson top_gaps_count "${TOP_GAPS_COUNT}" \
  --argjson tool_rows "${TOOL_ROWS}" \
  '{
    run_id: $run_id,
    generated_at: $generated_at,
    success: $success,
    failures: $failures,
    duration_ms: $duration_ms,
    probes: {
      harness_eval_ok: $harness_eval_ok,
      aider_task_ok: $aider_task_ok
    },
    report: {
      routing_local_pct: $routing_local_pct,
      cache_hit_pct: $cache_hit_pct,
      hint_adoption_pct: $hint_adoption_pct,
      eval_latest_pct: $eval_latest_pct,
      top_gaps_count: $top_gaps_count,
      tool_rows: $tool_rows
    }
  }')"

printf '%s\n' "${SUMMARY_JSON}" > "${SUMMARY_OUT}"
printf 'IMPROVEMENT_SUMMARY_JSON=%s\n' "${SUMMARY_JSON}"
log "Summary written to ${SUMMARY_OUT}"

if [[ "$FAILURES" -ne 0 ]]; then
  exit 1
fi
