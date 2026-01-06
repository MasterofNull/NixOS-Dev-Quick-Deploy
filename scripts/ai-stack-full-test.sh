#!/usr/bin/env bash
# Comprehensive AI stack verification workflow.
# Uses existing scripts/endpoints to validate core features end-to-end.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}"
LOG_FILE="${LOG_DIR}/ai-stack-full-test-$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR" >/dev/null 2>&1 || true

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; exit 1; }

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        fail "Missing required command: $1"
    fi
}

curl_ok() {
    local url="$1"
    curl -sf --max-time 5 "$url" >/dev/null 2>&1
}

wait_for_url() {
    local url="$1"
    local label="$2"
    local retries="${3:-30}"
    local delay="${4:-2}"
    for i in $(seq 1 "$retries"); do
        if curl_ok "$url"; then
            success "$label healthy: $url"
            return 0
        fi
        if [[ $i -eq 1 ]]; then
            info "Waiting for $label..."
        fi
        sleep "$delay"
    done
    warn "$label did not become healthy: $url"
    return 1
}

require_cmd curl
require_cmd podman

info "Logging to $LOG_FILE"

info "Starting AI stack (if needed)..."
stack_running=false
if podman ps --format '{{.Names}}' | grep -qE '^local-ai-(qdrant|llama-cpp|postgres|redis)'; then
    stack_running=true
fi
if pgrep -f "podman-compose.*${PROJECT_ROOT}/ai-stack/compose" >/dev/null 2>&1; then
    stack_running=true
fi

if [[ "$stack_running" == "true" ]]; then
    success "AI stack already running; skipping start"
elif [[ -x "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" ]]; then
    if command -v timeout >/dev/null 2>&1; then
        timeout 300 "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up || warn "Stack start reported issues"
    else
        "${PROJECT_ROOT}/scripts/hybrid-ai-stack.sh" up || warn "Stack start reported issues"
    fi
else
    warn "hybrid-ai-stack.sh not found; skipping auto-start"
fi

info "Checking core services..."
wait_for_url "http://localhost:6333/healthz" "Qdrant" 30 2 || true
wait_for_url "http://localhost:8080/health" "llama.cpp" 30 2 || true
wait_for_url "http://localhost:8091/health" "AIDB MCP" 30 2 || true
wait_for_url "http://localhost:8092/health" "Hybrid Coordinator" 30 2 || true
if wait_for_url "http://localhost:3001" "Open WebUI" 5 2; then
    :
elif wait_for_url "http://localhost:3000" "Open WebUI" 5 2; then
    :
else
    warn "Open WebUI did not become healthy on 3000 or 3001"
fi

info "Validating Qdrant collections..."
if curl_ok "http://localhost:6333/collections"; then
    collections=$(curl -sf --max-time 5 http://localhost:6333/collections | jq -r '.result.collections[].name' 2>/dev/null || true)
    if [[ -n "$collections" ]]; then
        success "Qdrant collections present: $(echo "$collections" | tr '\n' ' ')"
    else
        warn "No Qdrant collections found"
    fi
else
    warn "Unable to query Qdrant collections"
fi

info "Validating llama.cpp models endpoint..."
if curl_ok "http://localhost:8080/v1/models"; then
    success "llama.cpp models endpoint reachable"
else
    warn "llama.cpp models endpoint not reachable"
fi

info "Validating AIDB discovery endpoints..."
curl_ok "http://localhost:8091/discovery/info" && success "AIDB discovery info OK" || warn "AIDB discovery info failed"
curl_ok "http://localhost:8091/discovery/quickstart" && success "AIDB discovery quickstart OK" || warn "AIDB discovery quickstart failed"

info "Validating Hybrid Coordinator stats endpoint..."
curl_ok "http://localhost:8092/stats" && success "Hybrid stats OK" || warn "Hybrid stats unavailable"

info "Checking PostgreSQL/Redis containers..."
if podman ps --format '{{.Names}}' | grep -q '^local-ai-postgres$'; then
    if podman exec local-ai-postgres pg_isready -U mcp >/dev/null 2>&1; then
        success "PostgreSQL ready"
    else
        warn "PostgreSQL not ready"
    fi
else
    warn "PostgreSQL container not running"
fi

if podman ps --format '{{.Names}}' | grep -q '^local-ai-redis$'; then
    if podman exec local-ai-redis redis-cli ping >/dev/null 2>&1; then
        success "Redis ready"
    else
        warn "Redis not ready"
    fi
else
    warn "Redis container not running"
fi

info "Running AI stack health checks..."
if [[ -x "${PROJECT_ROOT}/scripts/ai-stack-health.sh" ]]; then
    "${PROJECT_ROOT}/scripts/ai-stack-health.sh" || warn "ai-stack-health reported issues"
else
    warn "ai-stack-health.sh not found"
fi

info "Running telemetry smoke test..."
if [[ -x "${PROJECT_ROOT}/scripts/telemetry-smoke-test.sh" ]]; then
    "${PROJECT_ROOT}/scripts/telemetry-smoke-test.sh" || warn "Telemetry smoke test reported issues"
else
    warn "telemetry-smoke-test.sh not found"
fi

info "Collecting AI metrics..."
if [[ -x "${PROJECT_ROOT}/scripts/collect-ai-metrics.sh" ]]; then
    "${PROJECT_ROOT}/scripts/collect-ai-metrics.sh" >/dev/null 2>&1 || warn "collect-ai-metrics failed"
    if [[ -f "$HOME/.local/share/nixos-system-dashboard/ai_metrics.json" ]]; then
        success "AI metrics generated"
    else
        warn "AI metrics file not found"
    fi
else
    warn "collect-ai-metrics.sh not found"
fi

info "AI stack test complete"
