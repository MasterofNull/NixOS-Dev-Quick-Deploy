#!/run/current-system/sw/bin/bash
# Quick Launcher for NixOS System Monitoring Dashboard
# This script starts data collection and dashboard server simultaneously

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${HOME}/.local/share/nixos-system-dashboard"

# Source centralized service endpoints (optional)
# shellcheck source=config/service-endpoints.sh
if [[ -f "${PROJECT_DIR}/config/service-endpoints.sh" ]]; then
    source "${PROJECT_DIR}/config/service-endpoints.sh"
fi

DASHBOARD_HOST="${SERVICE_HOST:-localhost}"
DASHBOARD_URL="http://${DASHBOARD_HOST}:${DASHBOARD_PORT:-8888}/dashboard.html"
COLLECT_INTERVAL="${DASHBOARD_COLLECT_INTERVAL:-15}"
API_PORT="${DASHBOARD_API_PORT:-8889}"

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ███╗   ██╗██╗██╗  ██╗ ██████╗ ███████╗                    ║
║   ████╗  ██║██║╚██╗██╔╝██╔═══██╗██╔════╝                    ║
║   ██╔██╗ ██║██║ ╚███╔╝ ██║   ██║███████╗                    ║
║   ██║╚██╗██║██║ ██╔██╗ ██║   ██║╚════██║                    ║
║   ██║ ╚████║██║██╔╝ ██╗╚██████╔╝███████║                    ║
║   ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝                    ║
║                                                               ║
║          SYSTEM COMMAND CENTER - DASHBOARD LAUNCHER          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check dependencies
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

check_dependencies() {
    local missing_deps=()

    command -v python3 >/dev/null 2>&1 || missing_deps+=("python3")
    command -v jq >/dev/null 2>&1 || missing_deps+=("jq")
    command -v curl >/dev/null 2>&1 || missing_deps+=("curl")

    local runtime
    runtime=$(detect_runtime)
    if [[ "$runtime" == "k8s" ]]; then
        command -v kubectl >/dev/null 2>&1 || missing_deps+=("kubectl")
    elif [[ "$runtime" == "podman" ]]; then
        command -v podman >/dev/null 2>&1 || missing_deps+=("podman")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Missing dependencies: ${missing_deps[*]}${NC}"
        echo "Please install them first:"
        echo "  nix-env -iA nixpkgs.python3 nixpkgs.jq nixpkgs.curl"
        echo "  # plus nixpkgs.kubectl for K3s or nixpkgs.podman for Podman runtime"
        exit 1
    fi
}

# Generate initial data
generate_initial_data() {
    echo -e "${GREEN}📊 Generating initial dashboard data...${NC}"
    "$PROJECT_DIR/scripts/generate-dashboard-data.sh"
    echo -e "${GREEN}✅ Data collection complete${NC}"
    echo ""
}

# Start background data collection
start_data_collection() {
    echo -e "${GREEN}🔄 Starting background data collection (every ${COLLECT_INTERVAL}s)...${NC}"

    # Kill existing collection process if any
    pkill -f "generate-dashboard-data.sh" 2>/dev/null || true

    # Start collection loop in background
    (
        while true; do
            "$PROJECT_DIR/scripts/generate-dashboard-data.sh" >/dev/null 2>&1
            sleep "$COLLECT_INTERVAL"
        done
    ) &

    echo -e "${GREEN}✅ Background collector started (PID: $!)${NC}"
    echo "$!" > "$DATA_DIR/collector.pid"
    echo ""
}

# Start dashboard server
start_dashboard_server() {
    echo -e "${GREEN}🌐 Starting dashboard server...${NC}"
    echo ""

    # Start server in background
    "$PROJECT_DIR/scripts/serve-dashboard.sh" &
    local SERVER_PID=$!
    echo "$SERVER_PID" > "$DATA_DIR/server.pid"

    # Wait for server to start
    sleep 2

    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                       ║${NC}"
    echo -e "${CYAN}║  ${GREEN}✅ Dashboard is now running!${CYAN}                        ║${NC}"
    echo -e "${CYAN}║                                                       ║${NC}"
    echo -e "${CYAN}║  ${YELLOW}Dashboard URL:${NC}                                    ${CYAN}║${NC}"
    echo -e "${CYAN}║  ${DASHBOARD_URL}            ${CYAN}║${NC}"
    echo -e "${CYAN}║                                                       ║${NC}"
    echo -e "${CYAN}║  ${YELLOW}Data API:${NC}                                         ${CYAN}║${NC}"
    echo -e "${CYAN}║  http://${DASHBOARD_HOST}:${DASHBOARD_PORT:-8888}/data/                         ${CYAN}║${NC}"
    echo -e "${CYAN}║                                                       ║${NC}"
    echo -e "${CYAN}║  ${YELLOW}Controls:${NC}                                         ${CYAN}║${NC}"
    echo -e "${CYAN}║  • Press Ctrl+C to stop all services                 ${CYAN}║${NC}"
    echo -e "${CYAN}║  • Data updates every ${COLLECT_INTERVAL}s automatically        ${CYAN}║${NC}"
    echo -e "${CYAN}║                                                       ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Try to open in browser
    if command -v xdg-open >/dev/null 2>&1; then
        echo -e "${GREEN}🌍 Opening dashboard in browser...${NC}"
        sleep 1
        xdg-open "$DASHBOARD_URL" 2>/dev/null &
    fi
}

# Start port-forward for the Dashboard API (K3s/Kubernetes)
start_dashboard_api_proxy() {
    local runtime
    runtime=$(detect_runtime)
    if [[ "$runtime" == "k8s" ]] && command -v kubectl >/dev/null 2>&1; then
        echo -e "${GREEN}🔌 Starting Dashboard API port-forward (${API_PORT})...${NC}"
        kubectl port-forward -n ai-stack svc/dashboard-api "${API_PORT}:8889" >/dev/null 2>&1 &
        echo "$!" > "$DATA_DIR/api.pid"
        sleep 1
    fi
}

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping dashboard services...${NC}"

    # Stop data collector
    if [ -f "$DATA_DIR/collector.pid" ]; then
        kill "$(cat "$DATA_DIR/collector.pid")" 2>/dev/null || true
        rm "$DATA_DIR/collector.pid"
        echo -e "${GREEN}✅ Data collector stopped${NC}"
    fi

    # Stop server
    if [ -f "$DATA_DIR/server.pid" ]; then
        kill "$(cat "$DATA_DIR/server.pid")" 2>/dev/null || true
        rm "$DATA_DIR/server.pid"
        echo -e "${GREEN}✅ Dashboard server stopped${NC}"
    fi

    # Stop API port-forward
    if [ -f "$DATA_DIR/api.pid" ]; then
        kill "$(cat "$DATA_DIR/api.pid")" 2>/dev/null || true
        rm "$DATA_DIR/api.pid"
        echo -e "${GREEN}✅ Dashboard API proxy stopped${NC}"
    fi

    echo -e "${CYAN}👋 Goodbye!${NC}"
    exit 0
}

# Main execution
main() {
    # Set up trap for cleanup
    trap cleanup SIGINT SIGTERM EXIT

    # Create data directory
    mkdir -p "$DATA_DIR"

    # Check dependencies
    check_dependencies

    # Generate initial data
    generate_initial_data

    local runtime
    runtime=$(detect_runtime)
    if [[ "$runtime" == "k8s" ]]; then
        export DASHBOARD_MODE="k8s"
    fi
    export AI_STACK_NAMESPACE="${AI_STACK_NAMESPACE:-ai-stack}"
    export DASHBOARD_API_PORT="${API_PORT}"
    export AI_METRICS_ENDPOINT="${DASHBOARD_API_URL:-http://${DASHBOARD_HOST}:${API_PORT}}/api/ai/metrics"

    # Start services
    start_data_collection
    start_dashboard_api_proxy
    start_dashboard_server

    # Keep script running
    echo -e "${CYAN}Monitoring in progress... (Press Ctrl+C to stop)${NC}"
    wait
}

main "$@"
