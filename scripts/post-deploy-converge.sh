#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${POST_DEPLOY_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_DIR="${POST_DEPLOY_DATA_DIR:-/var/lib/ai-stack}"
HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
NPM_OUT_DIR="${POST_DEPLOY_NPM_OUT_DIR:-${DATA_DIR}/security/npm}"
AQ_REPORT_OUT="${POST_DEPLOY_AQ_REPORT_OUT:-${DATA_DIR}/hybrid/telemetry/latest-aq-report.json}"
HYBRID_HEALTH_RETRIES="${POST_DEPLOY_HYBRID_HEALTH_RETRIES:-12}"
HYBRID_HEALTH_RETRY_SECONDS="${POST_DEPLOY_HYBRID_HEALTH_RETRY_SECONDS:-5}"
BASH_BIN="${POST_DEPLOY_BASH_BIN:-bash}"
PYTHON_BIN="${POST_DEPLOY_PYTHON_BIN:-python3}"

log() {
  printf '[post-deploy-converge] %s\n' "$*"
}

mkdir -p "${NPM_OUT_DIR}" "$(dirname "${AQ_REPORT_OUT}")"

if [[ -x "${REPO_ROOT}/scripts/seed-routing-traffic.sh" ]]; then
  ready=false
  for ((i=1; i<=HYBRID_HEALTH_RETRIES; i++)); do
    if curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/health" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep "${HYBRID_HEALTH_RETRY_SECONDS}"
  done
  if [[ "${ready}" == true ]]; then
    log "Seeding routing traffic..."
    "${BASH_BIN}" "${REPO_ROOT}/scripts/seed-routing-traffic.sh" || log "routing seed failed; continuing"
  else
    log "Hybrid health unavailable after retries; skipping routing seed."
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/npm-security-monitor.sh" ]]; then
  log "Running npm security monitor (report mode)..."
  NPM_SECURITY_RESPONSE_MODE=report \
    "${BASH_BIN}" "${REPO_ROOT}/scripts/npm-security-monitor.sh" \
      --repo-root "${REPO_ROOT}" \
      --output-dir "${NPM_OUT_DIR}" \
      || log "npm security monitor failed; continuing"
fi

if [[ -x "${REPO_ROOT}/scripts/aq-report" ]]; then
  log "Refreshing aq-report snapshot..."
  "${PYTHON_BIN}" "${REPO_ROOT}/scripts/aq-report" --since=7d --format=json > "${AQ_REPORT_OUT}" \
    || log "aq-report refresh failed; continuing"
fi

log "Convergence pass complete."
