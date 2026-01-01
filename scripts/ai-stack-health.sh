#!/usr/bin/env bash
# Unified health check entry point for the local AI stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}"
LOG_FILE="${LOG_DIR}/ai-stack-health-$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR" >/dev/null 2>&1 || true

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

status=0

info "Running AI stack health check (v2)..."
if python3 "${PROJECT_ROOT}/scripts/check-ai-stack-health-v2.py" -v 2>&1 | tee "$LOG_FILE"; then
    success "AI stack service checks passed"
else
    status=1
    warn "AI stack service checks reported issues (log: $LOG_FILE)"
fi

info "Checking dashboard services..."
for unit in dashboard-collector.timer dashboard-server.service; do
    if systemctl --user is-active --quiet "$unit"; then
        success "$unit is active"
    else
        status=1
        warn "$unit is not active"
    fi
done

if [[ "$status" -eq 0 ]]; then
    success "All critical checks passed"
else
    warn "Some checks failed; inspect $LOG_FILE"
fi

exit "$status"
