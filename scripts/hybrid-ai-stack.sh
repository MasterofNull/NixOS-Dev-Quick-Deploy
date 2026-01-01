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
    if [[ "$COMPOSE_CMD" == "podman-compose" ]]; then
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d llama-cpp || true
    fi
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build && success "Stack started" || error "Failed to start"
    cmd_status
}

cmd_down() {
    info "Stopping Hybrid AI Stack..."
    cd "$COMPOSE_DIR"
    require_compose
    $COMPOSE_CMD -f "$COMPOSE_FILE" down && success "Stack stopped" || error "Failed to stop"
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
    check_service "Ralph Wiggum Loop" 8098 "/health"
    echo ""
    echo "Agent Backends:"
    check_service "Aider" 8093 "/health"
    check_service "Continue" 8094 "/health"
    check_service "Goose" 8095 "/health"
    check_service "LangChain" 8096 "/health"
    check_service "AutoGPT" 8097 "/health"
    echo ""
    echo "User Interfaces:"
    check_service "Open WebUI" 3001 "/"
    check_service "MindsDB" 47334 "/"
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
