#!/usr/bin/env bash
# auto-remediate.sh — Autonomous failure remediation trigger
#
# Runs health-spider and aq-qa 0, parses failures, and queues remediation tasks via PRSI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
LOG_DIR="/var/log/nixos-ai-stack"
mkdir -p "$LOG_DIR"
REPORT_LOG="$LOG_DIR/remediation-loop.log"

log() {
  printf '[%s] [auto-remediate] %s
' "$(date +'%Y-%m-%dT%H:%M:%S')" "$*" | tee -a "$REPORT_LOG"
}

log "Starting remediation pass."

# 1. Run health-spider first. It catches dashboard semantic degradation and AppArmor
# denial debt that plain aq-qa phase 0 can miss.
HEALTH_SPIDER="${HEALTH_SPIDER:-${REPO_ROOT}/scripts/ai/aq-health-spider}"
SPIDER_LOG="$LOG_DIR/health-spider-remediation.log"
SPIDER_FAILED=0
if [[ -x "$HEALTH_SPIDER" ]]; then
  if "$HEALTH_SPIDER" --once > "$SPIDER_LOG" 2>&1; then
    log "Health spider pass clean."
  else
    SPIDER_FAILED=1
    log "Health spider detected anomalies. See $SPIDER_LOG"
  fi
else
  log "WARN: health spider not executable at $HEALTH_SPIDER"
fi

# 2. Run full health check, ignoring the remediation service itself in the failure report
# aq-qa not in service PATH; /run/current-system/sw/bin is the stable symlink.
AQ_QA="${AQ_QA:-/run/current-system/sw/bin/aq-qa}"
QA_LOG="$LOG_DIR/qa-failure.log"
if "$AQ_QA" 0 > "$QA_LOG" 2>&1 && ! grep -v "ai-auto-remediate" "$QA_LOG" | grep -E '✗|failed' > /dev/null; then
  QA_FAILED=0
else
  QA_FAILED=1
  log "Failures detected in aq-qa 0."
fi

if [[ "$SPIDER_FAILED" -eq 0 && "$QA_FAILED" -eq 0 ]]; then
  log "System healthy. No remediation required."
  exit 0
else
  log "Remediation required: health_spider=${SPIDER_FAILED} aq_qa=${QA_FAILED}"
fi

# 3. Extract failure context
FAILURES=$(
  {
    if [[ "$SPIDER_FAILED" -ne 0 ]]; then
      printf '[health-spider]\n'
      tail -n 40 "$SPIDER_LOG" 2>/dev/null || true
    fi
    if [[ "$QA_FAILED" -ne 0 ]]; then
      printf '[aq-qa]\n'
      grep -E '✗|failed' "$QA_LOG" 2>/dev/null | head -n 10 || true
    fi
  } | head -n 80
)
log "Extracted failures:
$FAILURES"

# 4. Trigger PRSI remediation
# Note: Uses Python interpreter directly since prsi-orchestrator wrapper is missing
if [[ -f "${REPO_ROOT}/scripts/automation/prsi-orchestrator.py" ]]; then
  log "Orchestrating remediation via PRSI..."
  # Queue remediation action based on failure log
  python3 "${REPO_ROOT}/scripts/automation/prsi-orchestrator.py" queue --type remediation --risk medium \
    --summary "Auto-remediate aq-qa 0 failure" \
    --details "$(printf '%s' "$FAILURES")"

  # Trigger execution
  python3 "${REPO_ROOT}/scripts/automation/prsi-orchestrator.py" execute --limit 1
  log "Remediation triggered."
else
  log "ERROR: prsi-orchestrator.py not found. Manual intervention required."
  exit 1
fi

exit 0
