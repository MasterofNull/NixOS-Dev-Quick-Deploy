#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${POST_DEPLOY_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATA_DIR="${POST_DEPLOY_DATA_DIR:-/var/lib/ai-stack}"
HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"
NPM_OUT_DIR="${POST_DEPLOY_NPM_OUT_DIR:-${DATA_DIR}/security/npm}"
AQ_REPORT_OUT="${POST_DEPLOY_AQ_REPORT_OUT:-${DATA_DIR}/hybrid/telemetry/latest-aq-report.json}"

log() {
  printf '[post-deploy-converge] %s\n' "$*"
}

mkdir -p "${NPM_OUT_DIR}" "$(dirname "${AQ_REPORT_OUT}")"

if curl -fsS --max-time 5 --connect-timeout 3 "${HYBRID_URL%/}/health" >/dev/null 2>&1; then
  if [[ -x "${REPO_ROOT}/scripts/seed-routing-traffic.sh" ]]; then
    log "Seeding routing traffic..."
    "${REPO_ROOT}/scripts/seed-routing-traffic.sh" || log "routing seed failed; continuing"
  fi
else
  log "Hybrid health unavailable; skipping routing seed."
fi

if [[ -x "${REPO_ROOT}/scripts/npm-security-monitor.sh" ]]; then
  log "Running npm security monitor (report mode)..."
  NPM_SECURITY_RESPONSE_MODE=report \
    "${REPO_ROOT}/scripts/npm-security-monitor.sh" \
      --repo-root "${REPO_ROOT}" \
      --output-dir "${NPM_OUT_DIR}" \
      || log "npm security monitor failed; continuing"
fi

if [[ -x "${REPO_ROOT}/scripts/aq-report" ]]; then
  log "Refreshing aq-report snapshot..."
  "${REPO_ROOT}/scripts/aq-report" --since=7d --format=json > "${AQ_REPORT_OUT}" \
    || log "aq-report refresh failed; continuing"
fi

log "Convergence pass complete."
