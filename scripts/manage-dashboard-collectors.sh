#!/run/current-system/sw/bin/bash
# Dashboard Collectors Manager
# Manages both lite (2s) and full (60s) dashboard data collectors

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

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
    nohup bash "${PROJECT_ROOT}/scripts/run-dashboard-collector-lite.sh" </dev/null >/tmp/collector-lite.log 2>&1 &
    local lite_pid=$!
    success "Started lite collector - PID $lite_pid"

    # Wait a moment then start full collector to avoid lock conflicts
    sleep 3

    nohup bash "${PROJECT_ROOT}/scripts/run-dashboard-collector-full.sh" </dev/null >/tmp/collector-full.log 2>&1 &
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
            tail -20 /tmp/collector-lite.log 2>/dev/null || warning "No logs found"
            ;;
        full)
            info "Full collector logs:"
            tail -20 /tmp/collector-full.log 2>/dev/null || warning "No logs found"
            ;;
        *)
            info "Lite collector logs:"
            tail -10 /tmp/collector-lite.log 2>/dev/null || warning "No logs found"
            echo ""
            info "Full collector logs:"
            tail -10 /tmp/collector-full.log 2>/dev/null || warning "No logs found"
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
