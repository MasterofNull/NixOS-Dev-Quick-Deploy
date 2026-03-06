#!/usr/bin/env bash
# Execute bounded post-deploy convergence tasks and emit telemetry snapshots.
set -euo pipefail

REPO_ROOT="${POST_DEPLOY_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DATA_DIR="${POST_DEPLOY_DATA_DIR:-/var/lib/ai-stack}"
HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
NPM_OUT_DIR="${POST_DEPLOY_NPM_OUT_DIR:-${DATA_DIR}/security/npm}"
AQ_REPORT_OUT="${POST_DEPLOY_AQ_REPORT_OUT:-${DATA_DIR}/hybrid/telemetry/latest-aq-report.json}"
CONVERGE_SUMMARY_OUT="${POST_DEPLOY_SUMMARY_OUT:-${DATA_DIR}/hybrid/telemetry/post-deploy-converge-latest.json}"
AI_TOOLING_SNAPSHOT_OUT="${POST_DEPLOY_AI_TOOLING_SNAPSHOT_OUT:-${DATA_DIR}/hybrid/telemetry/ai-tooling-prime-latest.json}"
HINT_FEEDBACK_SYNC_OUT="${POST_DEPLOY_HINT_FEEDBACK_SYNC_OUT:-${DATA_DIR}/hybrid/telemetry/hint-feedback-sync-latest.json}"
AUTO_REMEDIATE_SUMMARY_OUT="${POST_DEPLOY_AUTO_REMEDIATE_OUT:-${DATA_DIR}/hybrid/telemetry/aq-auto-remediation-latest.json}"
HINT_FEEDBACK_LOG_PATH="${HINT_FEEDBACK_LOG_PATH:-/var/log/nixos-ai-stack/hint-feedback.jsonl}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-}"
AUTO_REMEDIATE_ENABLE="${POST_DEPLOY_AUTO_REMEDIATE_ENABLE:-true}"
INTENT_BOUNDED_ENABLE="${POST_DEPLOY_INTENT_BOUNDED_ENABLE:-true}"
INTENT_BOUNDED_TARGET_COVERAGE_PCT="${POST_DEPLOY_INTENT_BOUNDED_TARGET_COVERAGE_PCT:-65}"
INTENT_BOUNDED_RUNS_PER_PASS="${POST_DEPLOY_INTENT_BOUNDED_RUNS_PER_PASS:-8}"
INTENT_BOUNDED_MAX_TOTAL_RUNS="${POST_DEPLOY_INTENT_BOUNDED_MAX_TOTAL_RUNS:-24}"
INTENT_BOUNDED_MAX_PASSES="${POST_DEPLOY_INTENT_BOUNDED_MAX_PASSES:-4}"
INTENT_BOUNDED_SLEEP_SECONDS="${POST_DEPLOY_INTENT_BOUNDED_SLEEP_SECONDS:-2}"
INTENT_BOUNDED_TIMEOUT_SECONDS="${POST_DEPLOY_INTENT_BOUNDED_TIMEOUT_SECONDS:-180}"
HINT_BOUNDED_ENABLE="${POST_DEPLOY_HINT_BOUNDED_ENABLE:-true}"
HINT_BOUNDED_TARGET_ADOPTION_PCT="${POST_DEPLOY_HINT_BOUNDED_TARGET_ADOPTION_PCT:-70}"
HINT_BOUNDED_RUNS_PER_PASS="${POST_DEPLOY_HINT_BOUNDED_RUNS_PER_PASS:-3}"
HINT_BOUNDED_MAX_TOTAL_RUNS="${POST_DEPLOY_HINT_BOUNDED_MAX_TOTAL_RUNS:-9}"
HINT_BOUNDED_MAX_PASSES="${POST_DEPLOY_HINT_BOUNDED_MAX_PASSES:-5}"
HINT_BOUNDED_POLL_MAX_SECONDS="${POST_DEPLOY_HINT_BOUNDED_POLL_MAX_SECONDS:-90}"
HINT_BOUNDED_SLEEP_SECONDS="${POST_DEPLOY_HINT_BOUNDED_SLEEP_SECONDS:-2}"
HINT_BOUNDED_TIMEOUT_SECONDS="${POST_DEPLOY_HINT_BOUNDED_TIMEOUT_SECONDS:-420}"
HINT_BOUNDED_WORKSPACE="${POST_DEPLOY_HINT_BOUNDED_WORKSPACE:-${DATA_DIR}/hybrid/remediation}"
HINT_BOUNDED_FILE="${POST_DEPLOY_HINT_BOUNDED_FILE:-hint-remediation/notes.md}"
HYBRID_HEALTH_RETRIES="${POST_DEPLOY_HYBRID_HEALTH_RETRIES:-12}"
HYBRID_HEALTH_RETRY_SECONDS="${POST_DEPLOY_HYBRID_HEALTH_RETRY_SECONDS:-5}"
ROUTING_SEED_TIMEOUT_SECONDS="${POST_DEPLOY_ROUTING_SEED_TIMEOUT_SECONDS:-120}"
QDRANT_REBUILD_TIMEOUT_SECONDS="${POST_DEPLOY_QDRANT_REBUILD_TIMEOUT_SECONDS:-900}"
QDRANT_REBUILD_MODE="${POST_DEPLOY_QDRANT_REBUILD_MODE:-auto}" # auto|always|never
AQ_REPORT_TIMEOUT_SECONDS="${POST_DEPLOY_AQ_REPORT_TIMEOUT_SECONDS:-120}"
BASH_TIMEOUT_BIN="${POST_DEPLOY_TIMEOUT_BIN:-timeout}"
BASH_BIN="${POST_DEPLOY_BASH_BIN:-bash}"
PYTHON_BIN="${POST_DEPLOY_PYTHON_BIN:-python3}"

log() {
  printf '[post-deploy-converge] %s\n' "$*"
}

run_step() {
  local name="$1"
  shift
  if "$@"; then
    log "step=${name} status=ok"
    STEP_RESULTS+=("${name}:ok")
    return 0
  fi
  log "step=${name} status=warn"
  STEP_RESULTS+=("${name}:warn")
  return 1
}

run_with_timeout() {
  local timeout_secs="$1"
  shift
  if command -v "${BASH_TIMEOUT_BIN}" >/dev/null 2>&1 && [[ "${timeout_secs}" =~ ^[0-9]+$ ]] && (( timeout_secs > 0 )); then
    "${BASH_TIMEOUT_BIN}" "${timeout_secs}" "$@"
  else
    "$@"
  fi
}

refresh_aq_report_snapshot() {
  run_with_timeout "${AQ_REPORT_TIMEOUT_SECONDS}" \
    "${PYTHON_BIN}" "${REPO_ROOT}/scripts/ai/aq-report" --since=7d --format=json > "${AQ_REPORT_OUT}"
}

probe_hints_feedback_endpoint() {
  local endpoint="${HYBRID_URL%/}/hints/feedback"
  local payload response curl_args=()
  payload='{"hint_id":"health_probe_hint_feedback","helpful":true,"score":0.1,"comment":"post_deploy_probe","agent":"post-deploy-converge","task_id":"post-deploy-probe"}'
  curl_args=(--fail --silent --show-error --max-time 6 --connect-timeout 3 -H "Content-Type: application/json")
  if [[ -n "${HYBRID_API_KEY_FILE}" && -r "${HYBRID_API_KEY_FILE}" ]]; then
    local key
    key="$(tr -d '\r\n' < "${HYBRID_API_KEY_FILE}")"
    if [[ -n "${key}" ]]; then
      curl_args+=(-H "X-API-Key: ${key}")
    fi
  fi
  response="$(curl "${curl_args[@]}" -X POST "${endpoint}" -d "${payload}")"
  printf '%s' "${response}" | jq -e '.status == "recorded"' >/dev/null
}

declare -a STEP_RESULTS=()
START_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "${NPM_OUT_DIR}" "$(dirname "${AQ_REPORT_OUT}")"
mkdir -p "$(dirname "${CONVERGE_SUMMARY_OUT}")"
mkdir -p "$(dirname "${AI_TOOLING_SNAPSHOT_OUT}")"
mkdir -p "$(dirname "${HINT_FEEDBACK_SYNC_OUT}")"
mkdir -p "$(dirname "${AUTO_REMEDIATE_SUMMARY_OUT}")"

if [[ -x "${REPO_ROOT}/scripts/data/seed-routing-traffic.sh" ]]; then
  ready=false
  for ((i=1; i<=HYBRID_HEALTH_RETRIES; i++)); do
    if curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/health" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep "${HYBRID_HEALTH_RETRY_SECONDS}"
  done
  if [[ "${ready}" == true ]]; then
    run_step "routing_seed" run_with_timeout "${ROUTING_SEED_TIMEOUT_SECONDS}" \
      "${BASH_BIN}" "${REPO_ROOT}/scripts/data/seed-routing-traffic.sh" || true
  else
    log "Hybrid health unavailable after retries; skipping routing seed."
    STEP_RESULTS+=("routing_seed:skip")
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/data/seed-tool-audit-traffic.sh" ]]; then
  run_step "tool_audit_seed" run_with_timeout "${ROUTING_SEED_TIMEOUT_SECONDS}" \
    "${BASH_BIN}" "${REPO_ROOT}/scripts/data/seed-tool-audit-traffic.sh" || true
fi

if [[ -x "${REPO_ROOT}/scripts/security/npm-security-monitor.sh" ]]; then
  run_step "npm_security_report" env NPM_SECURITY_RESPONSE_MODE=report \
    "${BASH_BIN}" "${REPO_ROOT}/scripts/security/npm-security-monitor.sh" \
      --repo-root "${REPO_ROOT}" \
      --output-dir "${NPM_OUT_DIR}" || true
fi

if [[ -x "${REPO_ROOT}/scripts/data/rebuild-qdrant-collections.sh" ]]; then
  case "${QDRANT_REBUILD_MODE}" in
    never)
      log "Skipping full Qdrant rebuild (POST_DEPLOY_QDRANT_REBUILD_MODE=never)"
      STEP_RESULTS+=("qdrant_rebuild:skip")
      ;;
    always)
      run_step "qdrant_rebuild" run_with_timeout "${QDRANT_REBUILD_TIMEOUT_SECONDS}" \
        "${BASH_BIN}" "${REPO_ROOT}/scripts/data/rebuild-qdrant-collections.sh" || true
      ;;
    auto|*)
      # Auto mode: keep deploy-convergence fast by default.
      # Full collection rebuild remains available via mode=always.
      log "Skipping full Qdrant rebuild in auto mode (set POST_DEPLOY_QDRANT_REBUILD_MODE=always to force)."
      STEP_RESULTS+=("qdrant_rebuild:skip")
      ;;
  esac
fi

if [[ -x "${REPO_ROOT}/scripts/data/sync-hint-feedback-db.py" ]]; then
  run_step "hint_feedback_sync" run_with_timeout "${AQ_REPORT_TIMEOUT_SECONDS}" \
    "${PYTHON_BIN}" "${REPO_ROOT}/scripts/data/sync-hint-feedback-db.py" \
      --feedback-log "${HINT_FEEDBACK_LOG_PATH}" \
      --summary-out "${HINT_FEEDBACK_SYNC_OUT}" || true
fi

if [[ -x "${REPO_ROOT}/scripts/ai/aq-report" ]]; then
  run_step "aq_report_refresh" refresh_aq_report_snapshot || true
fi

if [[ -x "${REPO_ROOT}/scripts/automation/prime-ai-tooling-defaults.sh" ]]; then
  run_step "ai_tooling_prime" \
    env POST_DEPLOY_AI_TOOLING_SNAPSHOT_OUT="${AI_TOOLING_SNAPSHOT_OUT}" \
      "${BASH_BIN}" "${REPO_ROOT}/scripts/automation/prime-ai-tooling-defaults.sh" || true
fi

if [[ -x "${REPO_ROOT}/scripts/ai/aq-auto-remediate.py" ]]; then
  if [[ "${AUTO_REMEDIATE_ENABLE,,}" == "true" || "${AUTO_REMEDIATE_ENABLE}" == "1" ]]; then
    run_step "aq_auto_remediation" run_with_timeout "${AQ_REPORT_TIMEOUT_SECONDS}" \
      "${PYTHON_BIN}" "${REPO_ROOT}/scripts/ai/aq-auto-remediate.py" \
        --report-json "${AQ_REPORT_OUT}" \
        --summary-out "${AUTO_REMEDIATE_SUMMARY_OUT}" || true
  else
    log "Skipping aq auto-remediation (POST_DEPLOY_AUTO_REMEDIATE_ENABLE=${AUTO_REMEDIATE_ENABLE})"
    STEP_RESULTS+=("aq_auto_remediation:skip")
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/automation/run-intent-remediation-bounded.sh" ]]; then
  if [[ "${INTENT_BOUNDED_ENABLE,,}" == "true" || "${INTENT_BOUNDED_ENABLE}" == "1" ]]; then
    run_step "intent_remediation_bounded" run_with_timeout "${INTENT_BOUNDED_TIMEOUT_SECONDS}" \
      env \
        INTENT_REMEDIATION_TARGET_COVERAGE_PCT="${INTENT_BOUNDED_TARGET_COVERAGE_PCT}" \
        INTENT_REMEDIATION_RUNS_PER_PASS="${INTENT_BOUNDED_RUNS_PER_PASS}" \
        INTENT_REMEDIATION_MAX_TOTAL_RUNS="${INTENT_BOUNDED_MAX_TOTAL_RUNS}" \
        INTENT_REMEDIATION_MAX_PASSES="${INTENT_BOUNDED_MAX_PASSES}" \
        INTENT_REMEDIATION_SLEEP_SECONDS="${INTENT_BOUNDED_SLEEP_SECONDS}" \
        "${BASH_BIN}" "${REPO_ROOT}/scripts/automation/run-intent-remediation-bounded.sh" || true
  else
    log "Skipping bounded intent remediation (POST_DEPLOY_INTENT_BOUNDED_ENABLE=${INTENT_BOUNDED_ENABLE})"
    STEP_RESULTS+=("intent_remediation_bounded:skip")
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/automation/run-hint-adoption-remediation-bounded.sh" ]]; then
  if [[ "${HINT_BOUNDED_ENABLE,,}" == "true" || "${HINT_BOUNDED_ENABLE}" == "1" ]]; then
    run_step "hint_adoption_remediation_bounded" run_with_timeout "${HINT_BOUNDED_TIMEOUT_SECONDS}" \
      env \
        HINT_REMEDIATION_TARGET_ADOPTION_PCT="${HINT_BOUNDED_TARGET_ADOPTION_PCT}" \
        HINT_REMEDIATION_RUNS_PER_PASS="${HINT_BOUNDED_RUNS_PER_PASS}" \
        HINT_REMEDIATION_MAX_TOTAL_RUNS="${HINT_BOUNDED_MAX_TOTAL_RUNS}" \
        HINT_REMEDIATION_MAX_PASSES="${HINT_BOUNDED_MAX_PASSES}" \
        HINT_REMEDIATION_POLL_MAX_SECONDS="${HINT_BOUNDED_POLL_MAX_SECONDS}" \
        HINT_REMEDIATION_SLEEP_SECONDS="${HINT_BOUNDED_SLEEP_SECONDS}" \
        HINT_REMEDIATION_WORKSPACE="${HINT_BOUNDED_WORKSPACE}" \
        HINT_REMEDIATION_FILE="${HINT_BOUNDED_FILE}" \
        "${BASH_BIN}" "${REPO_ROOT}/scripts/automation/run-hint-adoption-remediation-bounded.sh" || true
  else
    log "Skipping bounded hint remediation (POST_DEPLOY_HINT_BOUNDED_ENABLE=${HINT_BOUNDED_ENABLE})"
    STEP_RESULTS+=("hint_adoption_remediation_bounded:skip")
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/ai/aq-report" ]]; then
  run_step "aq_report_refresh_post_bounded" refresh_aq_report_snapshot || true
fi

if [[ -x "${REPO_ROOT}/scripts/testing/check-aq-report-runtime-sections.sh" ]]; then
  run_step "aq_report_runtime_sections" \
    "${BASH_BIN}" "${REPO_ROOT}/scripts/testing/check-aq-report-runtime-sections.sh" || true
fi

run_step "hints_feedback_endpoint_probe" probe_hints_feedback_endpoint || true

END_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
{
  printf '{\n'
  printf '  "started_at": "%s",\n' "${START_TS}"
  printf '  "finished_at": "%s",\n' "${END_TS}"
  printf '  "steps": [\n'
  for idx in "${!STEP_RESULTS[@]}"; do
    step="${STEP_RESULTS[$idx]%:*}"
    status="${STEP_RESULTS[$idx]#*:}"
    comma=","
    if [[ "${idx}" -eq "$(( ${#STEP_RESULTS[@]} - 1 ))" ]]; then
      comma=""
    fi
    printf '    {"step":"%s","status":"%s"}%s\n' "${step}" "${status}" "${comma}"
  done
  printf '  ]\n'
  printf '}\n'
} > "${CONVERGE_SUMMARY_OUT}" || true

log "Convergence pass complete."
