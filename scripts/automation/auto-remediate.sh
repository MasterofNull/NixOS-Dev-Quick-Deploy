#!/usr/bin/env bash
# auto-remediate.sh — Autonomous failure remediation trigger
#
# Runs aq-qa 0, parses failures, and queues remediation tasks via PRSI.

set -euo pipefail

LOG_DIR="/var/log/nixos-ai-stack"
mkdir -p "$LOG_DIR"
REPORT_LOG="$LOG_DIR/remediation-loop.log"

log() {
  printf '[%s] [auto-remediate] %s
' "$(date +'%Y-%m-%dT%H:%M:%S')" "$*" | tee -a "$REPORT_LOG"
}

log "Starting remediation pass."

# 1. Run full health check, ignoring the remediation service itself in the failure report
# aq-qa not in service PATH; /run/current-system/sw/bin is the stable symlink.
AQ_QA="${AQ_QA:-/run/current-system/sw/bin/aq-qa}"
if "$AQ_QA" 0 | grep -v "ai-auto-remediate" | grep -E '✗|failed' > /dev/null; then
  log "Failures detected in aq-qa 0."
  # ... rest of remediation logic ...
else
  log "System healthy. No remediation required."
  exit 0
fi

# 2. Extract failure context
FAILURES=$(grep -E '✗|failed' "$LOG_DIR/qa-failure.log" | head -n 5)
log "Extracted failures:
$FAILURES"

# 3. Trigger PRSI remediation
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
