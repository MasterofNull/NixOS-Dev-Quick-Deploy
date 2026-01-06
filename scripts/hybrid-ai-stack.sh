#!/usr/bin/env bash
#
# Unified AI Stack Helper - Single Source of Truth
# Manages the complete NixOS Hybrid Learning AI Stack
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="${PROJECT_ROOT}/ai-stack/compose"
COMPOSE_FILE="docker-compose.yml"  # Single unified configuration
CONTAINER_RUNTIME=""
COMPOSE_CMD=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

check_podman_boot_id() {
    if [[ "$CONTAINER_RUNTIME" != "podman" ]]; then
        return 0
    fi

    local info_output=""
    info_output="$(podman info 2>&1 || true)"

    if echo "$info_output" | grep -q "current system boot ID differs"; then
        warning "Podman runtime boot ID mismatch detected."
        if [[ -x "${SCRIPT_DIR}/reset-podman-runtime.sh" ]]; then
            if "${SCRIPT_DIR}/reset-podman-runtime.sh"; then
                success "Podman runtime reset complete."
            else
                warning "Podman runtime reset required before starting containers."
                return 1
            fi
        else
            warning "Missing reset script: ${SCRIPT_DIR}/reset-podman-runtime.sh"
            warning "Run: sudo rm -rf /run/libpod /run/containers/storage"
            return 1
        fi
    fi
}

detect_runtime() {
    if command -v podman >/dev/null 2>&1; then
        CONTAINER_RUNTIME="podman"
    elif command -v docker >/dev/null 2>&1; then
        CONTAINER_RUNTIME="docker"
    else
        CONTAINER_RUNTIME=""
    fi

    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD=""
    fi
}

require_compose() {
    detect_runtime
    if [[ -z "$COMPOSE_CMD" ]]; then
        error "podman-compose or docker compose is required to manage the AI stack."
        exit 1
    fi
}

check_service() {
    local name=$1 port=$2 endpoint=${3:-/}
    if curl -sf --max-time 3 "http://localhost:$port$endpoint" &>/dev/null; then
        success "$name is running on port $port"
    else
        warning "$name not responding on port $port"
    fi
}

cmd_up() {
    info "Starting Hybrid AI Stack..."
    cd "$COMPOSE_DIR"
    require_compose
    check_podman_boot_id || return 1

    # Cleanup any hanging processes first
    if [[ -x "${SCRIPT_DIR}/cleanup-hanging-compose.sh" ]]; then
        "${SCRIPT_DIR}/cleanup-hanging-compose.sh" 5 || true
    fi

    if [[ "$COMPOSE_CMD" == "podman-compose" ]]; then
        timeout 60 $COMPOSE_CMD -f "$COMPOSE_FILE" up -d llama-cpp || true
    fi

    # Use timeout to prevent infinite hanging
    # Longer timeout (10 min) for --build to allow image building
    local timeout_seconds=600
    info "Starting containers (timeout: ${timeout_seconds}s to allow for image builds)..."

    if timeout $timeout_seconds $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build; then
        success "Stack started"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            warning "Stack start timed out after ${timeout_seconds}s, attempting clean restart..."
        else
            warning "Stack start failed, attempting clean restart..."
        fi

        local clean_script="${SCRIPT_DIR}/compose-clean-restart.sh"
        if [[ -x "$clean_script" ]]; then
            COMPOSE_FILE="${COMPOSE_DIR}/${COMPOSE_FILE}" "$clean_script" || true
        else
            warning "Clean restart script not found at $clean_script"
        fi

        # Second attempt with same timeout
        if timeout $timeout_seconds $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build; then
            success "Stack started after clean restart"
        else
            error "Failed to start (timed out after ${timeout_seconds}s)"
            warning "Some containers may still be starting - check with: podman ps"
            return 1
        fi
    fi

    # Start dashboard collector if not already running
    if command -v systemctl >/dev/null 2>&1; then
        if ! systemctl --user is-active --quiet dashboard-collector.timer 2>/dev/null; then
            info "Starting dashboard collector..."
            systemctl --user start dashboard-collector.timer 2>/dev/null && success "Dashboard collector started" || warning "Could not start dashboard collector"
        fi

        # Trigger initial data collection
        if [[ -x "${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" ]]; then
            info "Collecting initial dashboard metrics..."
            "${PROJECT_ROOT}/scripts/generate-dashboard-data.sh" >/dev/null 2>&1 || warning "Initial metrics collection had issues"
        fi
    fi

    # Only show status if explicitly requested
    if [[ "${SKIP_STATUS:-false}" != "true" ]]; then
        cmd_status_quick
    fi
}

cmd_down() {
    info "Stopping Hybrid AI Stack..."
    cd "$COMPOSE_DIR"
    require_compose
    $COMPOSE_CMD -f "$COMPOSE_FILE" down && success "Stack stopped" || error "Failed to stop"
}

cmd_status_quick() {
    info "Hybrid AI Stack v3.0 Status (quick check):"
    echo ""
    detect_runtime
    if [[ -n "$CONTAINER_RUNTIME" ]]; then
        $CONTAINER_RUNTIME ps --filter "label=nixos.quick-deploy.ai-stack=true" \
            --format "table {{.Names}}\t{{.Status}}"
    else
        warning "No container runtime detected (podman or docker)."
    fi
}

cmd_status() {
    info "Hybrid AI Stack v3.0 (Agentic Era) Status:"
    echo ""
    detect_runtime
    if [[ -n "$CONTAINER_RUNTIME" ]]; then
        $CONTAINER_RUNTIME ps --filter "label=nixos.quick-deploy.ai-stack=true" \
            --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        warning "No container runtime detected (podman or docker)."
    fi
    echo ""
    echo "Core Infrastructure:"
    check_service "Qdrant" 6333 "/healthz"
    check_service "llama.cpp" 8080 "/health"
    check_service "PostgreSQL" 5432 "/"
    check_service "Redis" 6379 "/"
    echo ""
    echo "MCP Servers:"
    check_service "AIDB MCP" 8091 "/health"
    check_service "Hybrid Coordinator" 8092 "/health"
    check_service "NixOS Docs MCP" 8094 "/health"
    echo ""
    echo "User Interfaces:"
    check_service "Open WebUI" 3000 "/"
    check_service "MindsDB" 47334 "/"
    echo ""
    info "Note: Some services may take 2-3 minutes to become healthy after startup"
}

cmd_logs() {
    cd "$COMPOSE_DIR"
    require_compose
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f "${1:-}"
}

cmd_help() {
    cat << EOF
Hybrid AI Stack Helper

USAGE:  $(basename "$0") COMMAND

COMMANDS:
    up       Start all containers
    down     Stop all containers
    restart  Restart all containers
    status   Show status and health
    logs     Show logs (add service name for specific service)
    ps       List containers
    help     Show this message

EXAMPLES:
    $(basename "$0") up
    $(basename "$0") status
    $(basename "$0") logs llama-cpp

DASHBOARD:
    Run ./scripts/serve-dashboard.sh and open http://localhost:8888/dashboard.html
EOF
}

case "${1:-help}" in
    up) cmd_up ;;
    down) cmd_down ;;
    restart) cmd_down && sleep 2 && cmd_up ;;
    status) cmd_status ;;
    logs) shift; cmd_logs "$@" ;;
    ps) require_compose; cd "$COMPOSE_DIR" && $COMPOSE_CMD -f "$COMPOSE_FILE" ps ;;
    *) cmd_help ;;
esac
