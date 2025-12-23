#!/usr/bin/env bash
# Start the podman AI stack, dashboard services, and run a quick health check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }

info "Starting Hybrid AI stack (containers)..."
"${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up

info "Starting dashboard services..."
systemctl --user start dashboard-collector.timer dashboard-server.service
success "Dashboard services started"

info "Running telemetry smoke test..."
"${PROJECT_ROOT}/scripts/telemetry-smoke-test.sh"

info "Running health checks..."
"${PROJECT_ROOT}/scripts/test-ai-stack-health.sh"

success "Startup completed"
