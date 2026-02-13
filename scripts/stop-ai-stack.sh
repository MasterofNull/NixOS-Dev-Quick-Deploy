#!/usr/bin/env bash
# Stop all AI stack services (both host and containers)
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Clean stop of all AI stack components before redeployment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source container registry for complete container list
source "$PROJECT_ROOT/lib/ai-stack-containers.sh"

echo "🛑 Stopping AI Stack services..."

# Optional tools
have_lsof=false
have_pkill=false
if command -v lsof >/dev/null 2>&1; then
    have_lsof=true
fi
if command -v pkill >/dev/null 2>&1; then
    have_pkill=true
fi

if command -v kubectl >/dev/null 2>&1; then
    echo "  Stopping Kubernetes deployments..."
    kubectl --request-timeout=30s scale deploy -n ai-stack --replicas=0 --all 2>/dev/null || true
    kubectl --request-timeout=30s delete pod -n ai-stack --all 2>/dev/null || true
else
    echo "  kubectl not available; skipping Kubernetes stop"
fi

# Kill host processes on conflicting ports
echo "  Checking for port conflicts..."
# Use ports from the shared container registry
for port in "${AI_STACK_PORTS[@]}"; do
    if [ "$have_lsof" = true ]; then
        if lsof -ti:$port >/dev/null 2>&1; then
            pid=$(lsof -ti:$port)
            echo "    Killing process on port $port (PID: $pid)"
            kill -9 $pid 2>/dev/null || true
            sleep 1
        fi
    fi
done

# Check for orphaned AI stack processes by pattern
echo "  Checking for orphaned processes..."
if [ "$have_pkill" = true ]; then
    # AIDB server and tool discovery
    pkill -9 -f "python.*server.py.*config.*yaml" 2>/dev/null || true
    pkill -9 -f "start_with_discovery.sh" 2>/dev/null || true
    pkill -9 -f "tool_discovery_daemon.py" 2>/dev/null || true
    # Hybrid coordinator and continuous learning
    pkill -9 -f "start_with_learning.sh" 2>/dev/null || true
    pkill -9 -f "continuous_learning_daemon.py" 2>/dev/null || true
    # Open WebUI (uvicorn on port 3001)
    pkill -9 -f "uvicorn.*open_webui.main:app.*3001" 2>/dev/null || true
    # NixOS docs server
    pkill -9 -f "uvicorn.*nixos_docs" 2>/dev/null || true
    # Ralph Wiggum loop
    pkill -9 -f "ralph.*server.py" 2>/dev/null || true
    # Self-healing daemon
    pkill -9 -f "self_healing_daemon.py" 2>/dev/null || true
fi

# Wait a moment for processes to fully stop
sleep 2

# Verify ports are free
echo "  Verifying ports are free..."
all_clear=true
for port in "${AI_STACK_PORTS[@]}"; do
    if [ "$have_lsof" = true ]; then
        if lsof -ti:$port >/dev/null 2>&1; then
            pid=$(lsof -ti:$port 2>/dev/null || echo "unknown")
            echo "    ⚠️  Port $port is still in use! (PID: $pid)"
            all_clear=false
        fi
    fi
done

if [ "$all_clear" = true ]; then
    echo "✅ AI Stack stopped successfully"
    exit 0
else
    echo "⚠️  Some ports are still in use - manual intervention may be required"
    exit 1
fi
