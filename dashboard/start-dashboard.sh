#!/usr/bin/env bash
# Launch the upgraded NixOS System Dashboard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    uvicorn api.main:app --host 0.0.0.0 --port 8889 --reload &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/dashboard-backend.pid
    echo "✅ Backend started (PID: $BACKEND_PID)"
}

# Start frontend dev server
start_frontend() {
    echo "🎨 Starting frontend on port 8890..."
    cd "$SCRIPT_DIR/frontend"
    pnpm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/dashboard-frontend.pid
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
}

# Cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down dashboard..."
    
    if [ -f /tmp/dashboard-backend.pid ]; then
        kill $(cat /tmp/dashboard-backend.pid) 2>/dev/null || true
        rm /tmp/dashboard-backend.pid
    fi
    
    if [ -f /tmp/dashboard-frontend.pid ]; then
        kill $(cat /tmp/dashboard-frontend.pid) 2>/dev/null || true
        rm /tmp/dashboard-frontend.pid
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
echo "  🔧 API URL:        http://localhost:8889"
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