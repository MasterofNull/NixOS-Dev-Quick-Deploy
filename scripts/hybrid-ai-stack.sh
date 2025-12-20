#!/usr/bin/env bash
#
# Hybrid AI Stack Helper - Manages docker-compose.hybrid.yml
# Quick management for NixOS Hybrid Learning AI Stack
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="${PROJECT_ROOT}/ai-stack/compose"
COMPOSE_FILE="docker-compose.hybrid.yml"

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
    podman-compose -f "$COMPOSE_FILE" up -d && success "Stack started" || error "Failed to start"
    cmd_status
}

cmd_down() {
    info "Stopping Hybrid AI Stack..."
    cd "$COMPOSE_DIR"
    podman-compose -f "$COMPOSE_FILE" down && success "Stack stopped" || error "Failed to stop"
}

cmd_status() {
    info "Hybrid AI Stack Status:"
    echo ""
    podman ps --filter "name=nixos-ai" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    check_service "Qdrant" 6333 "/healthz"
    check_service "Ollama" 11434 "/api/tags"
    check_service "Lemonade" 8000 "/api/v1/health"
    check_service "Lemonade Coder" 8001 "/api/v1/health"
    check_service "Lemonade DeepSeek" 8003 "/api/v1/health"
    check_service "Open WebUI" 3000 "/"
}

cmd_logs() {
    cd "$COMPOSE_DIR"
    podman-compose -f "$COMPOSE_FILE" logs -f "${1:-}"
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
    $(basename "$0") logs lemonade

DASHBOARD:
    Open ai-stack/dashboard/index.html in browser
EOF
}

case "${1:-help}" in
    up) cmd_up ;;
    down) cmd_down ;;
    restart) cmd_down && sleep 2 && cmd_up ;;
    status) cmd_status ;;
    logs) shift; cmd_logs "$@" ;;
    ps) cd "$COMPOSE_DIR" && podman-compose -f "$COMPOSE_FILE" ps ;;
    *) cmd_help ;;
esac
