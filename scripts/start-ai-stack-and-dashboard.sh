#!/usr/bin/env bash
# Start the podman AI stack, dashboard services, and run a quick health check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

info "Starting Hybrid AI stack (containers)..."
ai_stack_log="${HOME}/.cache/nixos-quick-deploy/logs/ai-stack-start-$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$ai_stack_log")" >/dev/null 2>&1 || true
if "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up >"$ai_stack_log" 2>&1; then
    success "Hybrid AI stack started (log: $ai_stack_log)"
else
    warn "Hybrid AI stack startup reported issues (log: $ai_stack_log)"
fi

info "Starting dashboard services..."
systemctl --user start dashboard-collector.timer dashboard-server.service
success "Dashboard services started"

info "Running telemetry smoke test..."
"${PROJECT_ROOT}/scripts/telemetry-smoke-test.sh"

info "Running health checks..."
"${PROJECT_ROOT}/scripts/ai-stack-health.sh"

success "Startup completed"
