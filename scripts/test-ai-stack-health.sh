#!/usr/bin/env bash
# Basic health checks for the local AI stack + dashboard services.

set -euo pipefail

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; }

check_url() {
    local name="$1"
    local url="$2"
    if curl -sf --max-time 3 "$url" >/dev/null; then
        success "$name is healthy"
        return 0
    fi
    fail "$name is not responding at $url"
    return 1
}

check_service() {
    local name="$1"
    if systemctl --user is-active --quiet "$name"; then
        success "$name service is active"
        return 0
    fi
    warn "$name service is not active"
    return 1
}

status=0

info "Checking AI stack HTTP endpoints..."
check_url "Qdrant" "http://localhost:6333/healthz" || status=1
check_url "llama.cpp" "http://localhost:8080/health" || status=1
check_url "Open WebUI" "http://localhost:3001/" || status=1
check_url "AIDB MCP" "http://localhost:8091/health" || status=1
check_url "Hybrid Coordinator" "http://localhost:8092/health" || status=1

info "Checking dashboard services..."
check_service "dashboard-collector.timer" || status=1
check_service "dashboard-server.service" || status=1

if [[ "$status" -eq 0 ]]; then
    success "All critical checks passed"
else
    warn "Some checks failed; inspect logs and service status"
fi

exit "$status"
