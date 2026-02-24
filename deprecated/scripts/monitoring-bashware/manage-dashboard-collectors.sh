#!/run/current-system/sw/bin/bash
# Dashboard Collectors Manager
# Manages both lite (2s) and full (60s) dashboard data collectors

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
COLLECTOR_LITE_LOG="${RUNTIME_DIR}/collector-lite.log"
COLLECTOR_FULL_LOG="${RUNTIME_DIR}/collector-full.log"

mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

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
    if command -v kubectl >/dev/null 2>&1; then
        if [[ -n "${KUBECONFIG:-}" ]] || [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
            echo "k8s"
            return
        fi
    fi
    if command -v podman >/dev/null 2>&1; then
        echo "podman"
        return
    fi
    if command -v docker >/dev/null 2>&1; then
        echo "docker"
        return
    fi
    echo ""
}

status() {
    info "Dashboard Collectors Status:"
    echo ""

    local lite_pid=$(pgrep -f "run-dashboard-collector-lite" || echo "")
    local full_pid=$(pgrep -f "run-dashboard-collector-full" || echo "")

    if [[ -n "$lite_pid" ]]; then
        success "Lite collector (system+network) running - PID $lite_pid"
        echo "   Updates every ~2.5 seconds"
    else
        warning "Lite collector not running"
    fi

    if [[ -n "$full_pid" ]]; then
        success "Full collector (all metrics) running - PID $full_pid"
        echo "   Updates every ~69 seconds"
    else
        warning "Full collector not running"
    fi

    echo ""
    if [[ -f ~/.local/share/nixos-system-dashboard/system.json ]]; then
        local age=$(( $(date +%s) - $(stat -c %Y ~/.local/share/nixos-system-dashboard/system.json) ))
        echo "Last system.json update: ${age}s ago"
    fi
}

start() {
    info "Starting dashboard collectors..."
    local runtime
    runtime=$(detect_runtime)

    # Stop any existing collectors first
    stop

    # Ensure scripts exist
    if [[ ! -f "${PROJECT_ROOT}/scripts/run-dashboard-collector-lite.sh" ]]; then
        error "Lite collector script not found"
        return 1
    fi
    if [[ ! -f "${PROJECT_ROOT}/scripts/run-dashboard-collector-full.sh" ]]; then
        error "Full collector script not found"
        return 1
    fi

    # Start lite collector
    DASHBOARD_MODE="${runtime}" AI_STACK_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}" \
        nohup bash "${PROJECT_ROOT}/scripts/run-dashboard-collector-lite.sh" </dev/null >"$COLLECTOR_LITE_LOG" 2>&1 &
    local lite_pid=$!
    success "Started lite collector - PID $lite_pid"

    # Wait a moment then start full collector to avoid lock conflicts
    sleep 3

    DASHBOARD_MODE="${runtime}" AI_STACK_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}" \
        nohup bash "${PROJECT_ROOT}/scripts/run-dashboard-collector-full.sh" </dev/null >"$COLLECTOR_FULL_LOG" 2>&1 &
    local full_pid=$!
    success "Started full collector - PID $full_pid"

    echo ""
    info "Dashboard will update:"
    echo "  - Graphs (CPU, memory, network): Every 2 seconds"
    echo "  - Static data (LLM, database, security): Every 60 seconds"
}

stop() {
    info "Stopping dashboard collectors..."

    pkill -f "run-dashboard-collector-lite" 2>/dev/null && success "Stopped lite collector" || warning "Lite collector not running"
    pkill -f "run-dashboard-collector-full" 2>/dev/null && success "Stopped full collector" || warning "Full collector not running"

    # Clean up lock files
    rm -f ~/.local/share/nixos-system-dashboard/.lock 2>/dev/null || true
}

logs() {
    local which="${1:-both}"

    case "$which" in
        lite)
            info "Lite collector logs:"
            tail -20 "$COLLECTOR_LITE_LOG" 2>/dev/null || warning "No logs found"
            ;;
        full)
            info "Full collector logs:"
            tail -20 "$COLLECTOR_FULL_LOG" 2>/dev/null || warning "No logs found"
            ;;
        *)
            info "Lite collector logs:"
            tail -10 "$COLLECTOR_LITE_LOG" 2>/dev/null || warning "No logs found"
            echo ""
            info "Full collector logs:"
            tail -10 "$COLLECTOR_FULL_LOG" 2>/dev/null || warning "No logs found"
            ;;
    esac
}

case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-both}"
        ;;
    *)
        cat << EOF
Dashboard Collectors Manager

USAGE: $(basename "$0") COMMAND

COMMANDS:
    start    Start both collectors
    stop     Stop both collectors
    restart  Restart both collectors
    status   Show collector status (default)
    logs     Show logs (add 'lite' or 'full' for specific collector)

EXAMPLES:
    $(basename "$0") start
    $(basename "$0") status
    $(basename "$0") logs lite

COLLECTORS:
    Lite:  Updates system + network every ~2.5 seconds
    Full:  Updates all metrics every ~69 seconds
EOF
        ;;
esac
