#!/usr/bin/env bash
# Start the podman AI stack, dashboard services, and run a quick health check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
error() { echo "✗ $*"; }

# Pre-flight: Stop existing services to prevent port conflicts
info "Pre-flight: Stopping existing AI stack services..."
if [ -f "${SCRIPT_DIR}/stop-ai-stack.sh" ]; then
    "${SCRIPT_DIR}/stop-ai-stack.sh" || warn "Could not stop all services"
fi

# Pre-flight: Check for orphaned AI stack processes
info "Pre-flight: Checking for orphaned AI stack processes..."
orphaned_found=false
# Detect which port inspection tools are available
have_ss=false
have_lsof=false
if command -v ss >/dev/null 2>&1; then
    have_ss=true
fi
if command -v lsof >/dev/null 2>&1; then
    have_lsof=true
fi

port_in_use() {
    local port="$1"
    if [ "$have_ss" = true ]; then
        ss -tulpn 2>/dev/null | grep -q ":$port "
        return $?
    fi
    if [ "$have_lsof" = true ]; then
        lsof -i:$port >/dev/null 2>&1
        return $?
    fi
    return 1
}

# AI stack ports: 8091 (aidb), 8791 (aidb websocket), 8092 (hybrid-coordinator),
# 8094 (nixos-docs), 3001 (open-webui), 8098 (ralph-wiggum), 6333 (qdrant), 8080 (llama.cpp)
for port in 8091 8791 8092 8094 3001 8098 6333 8080; do
    if port_in_use "$port"; then
        pid=""
        if [ "$have_lsof" = true ]; then
            pid=$(lsof -ti:$port 2>/dev/null || echo "")
        fi
        if [ -n "$pid" ]; then
            process_info=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
            # Check if it's an AI stack process (not a regular system service)
            if echo "$process_info" | grep -qE "(python|uvicorn|server.py|podman)"; then
                warn "Found orphaned process on port $port (PID: $pid, $process_info)"
                orphaned_found=true
            fi
        fi
    fi
done

if [ "$orphaned_found" = true ]; then
    warn "Orphaned AI stack processes detected - attempting cleanup..."
    if [ -f "${SCRIPT_DIR}/stop-ai-stack.sh" ]; then
        "${SCRIPT_DIR}/stop-ai-stack.sh" || warn "Cleanup had issues"
    else
        error "stop-ai-stack.sh not found - manual cleanup required"
        exit 1
    fi
fi

info "Cleaning up any hanging podman-compose processes..."
if [ -x "${SCRIPT_DIR}/cleanup-hanging-compose.sh" ]; then
    "${SCRIPT_DIR}/cleanup-hanging-compose.sh" 5 || warn "Cleanup script had issues"
fi

info "Starting Hybrid AI stack (containers)..."
ai_stack_log="${HOME}/.cache/nixos-quick-deploy/logs/ai-stack-start-$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$ai_stack_log")" >/dev/null 2>&1 || true
stack_started=false

# Use timeout to prevent indefinite hanging (10 minutes max for entire startup)
if timeout 600 "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up >"$ai_stack_log" 2>&1; then
    success "Hybrid AI stack started (log: $ai_stack_log)"
    stack_started=true
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        error "Hybrid AI stack startup timed out after 10 minutes (log: $ai_stack_log)"
    else
        warn "Hybrid AI stack startup reported issues (log: $ai_stack_log)"
    fi
fi

if [ "$stack_started" = false ]; then
    warn "Skipping telemetry + health checks because stack startup failed."
    exit 1
fi

info "Starting dashboard services..."
systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api.service || warn "Dashboard services start failed"
success "Dashboard services started"

info "Running telemetry smoke test..."
"${PROJECT_ROOT}/scripts/telemetry-smoke-test.sh" || warn "Telemetry smoke test reported issues"

info "Running health checks..."
"${PROJECT_ROOT}/scripts/ai-stack-health.sh" || warn "Health checks reported issues"

success "Startup completed"
