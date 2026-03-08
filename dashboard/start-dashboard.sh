#!/usr/bin/env bash
# Launch the upgraded NixOS System Dashboard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_API_BIND_ADDRESS="${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1}"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
BACKEND_PID_FILE="${RUNTIME_DIR}/dashboard-backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/dashboard-frontend.pid"
export DASHBOARD_API_BIND_ADDRESS

mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

echo "🚀 Starting NixOS System Dashboard v2.0..."
echo ""

# Check dependencies
check_dependencies() {
    local missing=()
    
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v node >/dev/null 2>&1 || missing+=("node")
    command -v pnpm >/dev/null 2>&1 || missing+=("pnpm")
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ Missing dependencies: ${missing[*]}"
        exit 1
    fi
}

# Install backend dependencies
setup_backend() {
    echo "📦 Setting up backend..."
    cd "$SCRIPT_DIR/backend"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    # Set pip timeout to prevent hanging on slow connections
    export PIP_DEFAULT_TIMEOUT=300
    pip install --timeout 300 --retries 3 -q -r requirements.txt

    echo "✅ Backend ready"
}

# Install frontend dependencies
setup_frontend() {
    echo "📦 Setting up frontend..."
    cd "$SCRIPT_DIR/frontend"
    
    if [ ! -d "node_modules" ]; then
        pnpm install
    fi
    
    echo "✅ Frontend ready"
}

# Start backend API
start_backend() {
    echo "🔧 Starting backend API on port 8889..."
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate
    uvicorn api.main:app --host "$DASHBOARD_API_BIND_ADDRESS" --port 8889 --reload &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    echo "✅ Backend started (PID: $BACKEND_PID)"
}

# Start frontend dev server
start_frontend() {
    echo "🎨 Starting frontend on port 8890..."
    cd "$SCRIPT_DIR/frontend"
    pnpm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
}

# Cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down dashboard..."
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        kill "$(cat "$BACKEND_PID_FILE")" 2>/dev/null || true
        rm "$BACKEND_PID_FILE"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null || true
        rm "$FRONTEND_PID_FILE"
    fi
    
    echo "👋 Dashboard stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Main
check_dependencies
setup_backend
setup_frontend

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎯 Dashboard Starting..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

start_backend
sleep 2
start_frontend
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Dashboard is now running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📊 Dashboard URL:  http://localhost:8890"
echo "  🔧 API URL:        http://127.0.0.1:8889 (dev-only)"
echo ""
echo "  Press Ctrl+C to stop"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Open browser
if command -v xdg-open >/dev/null 2>&1; then
    sleep 2
    xdg-open "http://localhost:8890" 2>/dev/null &
fi

# Keep script running
wait
