#!/usr/bin/env bash
# Unified Dashboard Startup Script
# Starts both the HTML dashboard (port 8888) and FastAPI backend (port 8889)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
DASHBOARD_API_BIND_ADDRESS="${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
BACKEND_LOG_FILE="${RUNTIME_DIR}/dashboard-backend.log"
FRONTEND_LOG_FILE="${RUNTIME_DIR}/dashboard-frontend.log"
BACKEND_PID_FILE="${RUNTIME_DIR}/dashboard-backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/dashboard-frontend.pid"
export DASHBOARD_BIND_ADDRESS DASHBOARD_API_BIND_ADDRESS

mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

echo "🚀 Starting Unified NixOS System Dashboard"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

# Check if ports are available
check_port() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        if ss -ltn "sport = :${port}" 2>/dev/null | grep -q ":${port}"; then
            return 1
        fi
    fi
    return 0
}

# Start FastAPI backend on port 8889
start_backend() {
    info "Starting FastAPI backend on port 8889..."

    if ! check_port 8889; then
        warn "Port 8889 already in use"
        info "Checking if it's our backend..."
        if curl -sf --max-time 2 http://${SERVICE_HOST:-localhost}:8889/api/health >/dev/null 2>&1; then
            success "FastAPI backend already running"
            return 0
        else
            warn "Port 8889 occupied by another process"
            return 1
        fi
    fi

    cd "$PROJECT_ROOT/dashboard/backend"

    # Setup venv if needed
    if [ ! -d "venv" ]; then
        info "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Install dependencies if needed
    if [ ! -f "venv/.installed" ]; then
        info "Installing backend dependencies..."
        pip install -q -r requirements.txt
        touch venv/.installed
    fi

    # Start backend
    nohup uvicorn api.main:app --host "$DASHBOARD_API_BIND_ADDRESS" --port 8889 \
        > "$BACKEND_LOG_FILE" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"

    # Wait for backend to be ready
    for i in {1..10}; do
        sleep 1
        if curl -sf --max-time 2 http://${SERVICE_HOST:-localhost}:8889/api/health >/dev/null 2>&1; then
            success "FastAPI backend started (PID: $(cat "$BACKEND_PID_FILE"))"
            return 0
        fi
    done

    warn "Backend may not be ready yet (check logs: tail -f $BACKEND_LOG_FILE)"
    return 0
}

# Start HTML dashboard on port 8888
start_frontend() {
    info "Starting HTML dashboard on port 8888..."

    if ! check_port 8888; then
        warn "Port 8888 already in use"
        info "Checking if it's our dashboard..."
        if curl -sf --max-time 2 http://${SERVICE_HOST:-localhost}:8888/dashboard.html >/dev/null 2>&1; then
            success "HTML dashboard already running"
            return 0
        else
            warn "Port 8888 occupied by another process"
            return 1
        fi
    fi

    cd "$PROJECT_ROOT"

    # Start dashboard server
    nohup "$SCRIPT_DIR/serve-dashboard.sh" \
        > "$FRONTEND_LOG_FILE" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"

    # Wait for frontend to be ready
    for i in {1..10}; do
        sleep 1
        if curl -sf --max-time 2 http://${SERVICE_HOST:-localhost}:8888/dashboard.html >/dev/null 2>&1; then
            success "HTML dashboard started (PID: $(cat "$FRONTEND_PID_FILE"))"
            return 0
        fi
    done

    warn "Dashboard may not be ready yet (check logs: tail -f $FRONTEND_LOG_FILE)"
    return 0
}

# Cleanup on exit
cleanup() {
    echo ""
    info "Shutting down dashboard..."

    if [ -f "$BACKEND_PID_FILE" ]; then
        kill "$(cat "$BACKEND_PID_FILE")" 2>/dev/null || true
        rm "$BACKEND_PID_FILE"
        success "Backend stopped"
    fi

    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null || true
        rm "$FRONTEND_PID_FILE"
        success "Frontend stopped"
    fi

    echo ""
    info "Dashboard stopped"
    exit 0
}

# Handle Ctrl+C
trap cleanup SIGINT SIGTERM

# Main
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Unified Dashboard Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start backend
start_backend || {
    warn "Failed to start backend, but continuing..."
}

echo ""

# Start frontend
start_frontend || {
    warn "Failed to start frontend"
    cleanup
    exit 1
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Unified Dashboard is Running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📊 Dashboard:     http://${SERVICE_HOST:-localhost}:8888/dashboard.html"
echo "  🔧 Backend API:   http://${SERVICE_HOST:-localhost}:8889"
echo "  📖 API Docs:      http://${SERVICE_HOST:-localhost}:8889/docs"
echo ""
echo "  📁 Backend logs:  tail -f $BACKEND_LOG_FILE"
echo "  📁 Frontend logs: tail -f $FRONTEND_LOG_FILE"
echo ""
echo "  Press Ctrl+C to stop both services"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Open browser if available
if command -v xdg-open >/dev/null 2>&1; then
    sleep 2
    xdg-open "http://${SERVICE_HOST:-localhost}:8888/dashboard.html" 2>/dev/null &
fi

# Keep script running
info "Dashboard running (Ctrl+C to stop)"
wait
