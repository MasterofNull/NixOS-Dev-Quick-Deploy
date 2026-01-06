#!/usr/bin/env bash
# Stop all AI stack services (both host and containers)
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Clean stop of all AI stack components before redeployment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

# Stop containers via compose
cd "$PROJECT_ROOT/ai-stack/compose"
if command -v podman-compose >/dev/null 2>&1; then
    if [ -f docker-compose.yml ]; then
        echo "  Stopping containers via podman-compose..."
        podman-compose down 2>/dev/null || true
        podman-compose down --remove-orphans 2>/dev/null || true
    fi
fi

# Force stop specific containers if they're still running
echo "  Force stopping containers..."
for container in local-ai-qdrant local-ai-llama-cpp local-ai-open-webui \
                 local-ai-postgres local-ai-redis local-ai-mindsdb \
                 local-ai-health-monitor local-ai-nixos-docs \
                 local-ai-aidb local-ai-hybrid-coordinator \
                 local-ai-ralph-wiggum local-ai-aider local-ai-autogpt; do
    if podman ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "    Stopping $container..."
        podman stop "$container" 2>/dev/null || true
    fi
done

# Remove stopped containers to avoid name conflicts on next start
echo "  Removing stale containers..."
for container in local-ai-qdrant local-ai-llama-cpp local-ai-open-webui \
                 local-ai-postgres local-ai-redis local-ai-mindsdb \
                 local-ai-health-monitor local-ai-nixos-docs \
                 local-ai-aidb local-ai-hybrid-coordinator \
                 local-ai-ralph-wiggum local-ai-aider local-ai-autogpt; do
    if podman ps -a --format '{{.Names}} {{.Status}}' | grep -q "^${container} "; then
        if ! podman ps --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "    Removing $container..."
            podman rm -f "$container" 2>/dev/null || true
        fi
    fi
done

# Kill host processes on conflicting ports
echo "  Checking for port conflicts..."
# AI stack ports: 8091 (aidb), 8791 (aidb websocket), 8092 (hybrid-coordinator),
# 8094 (nixos-docs), 3001 (open-webui), 8098 (ralph-wiggum)
for port in 8091 8791 8092 8094 3001 8098; do
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
for port in 8091 8791 8092 8094 3001 8098; do
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
