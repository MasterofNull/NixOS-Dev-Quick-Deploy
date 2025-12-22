#!/run/current-system/sw/bin/bash
# Quick Launcher for NixOS System Monitoring Dashboard
# This script starts data collection and dashboard server simultaneously

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${HOME}/.local/share/nixos-system-dashboard"
DASHBOARD_URL="http://localhost:8888/dashboard.html"
COLLECT_INTERVAL="${DASHBOARD_COLLECT_INTERVAL:-15}"

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
check_dependencies() {
    local missing_deps=()

    command -v python3 >/dev/null 2>&1 || missing_deps+=("python3")
    command -v jq >/dev/null 2>&1 || missing_deps+=("jq")
    command -v podman >/dev/null 2>&1 || missing_deps+=("podman")
    command -v curl >/dev/null 2>&1 || missing_deps+=("curl")

    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Missing dependencies: ${missing_deps[*]}${NC}"
        echo "Please install them first:"
        echo "  nix-env -iA nixpkgs.python3 nixpkgs.jq nixpkgs.podman nixpkgs.curl"
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
    echo -e "${CYAN}║  http://localhost:8888/data/                         ${CYAN}║${NC}"
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

    # Start services
    start_data_collection
    start_dashboard_server

    # Keep script running
    echo -e "${CYAN}Monitoring in progress... (Press Ctrl+C to stop)${NC}"
    wait
}

main "$@"
