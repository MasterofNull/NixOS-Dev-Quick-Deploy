#!/usr/bin/env bash
# Reset AI stack volume permissions and clear corrupted state
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Fix volume permission issues and corrupted state files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_STACK_DATA="${AI_STACK_DATA:-${HOME}/.local/share/nixos-ai-stack}"

echo "🔧 Resetting AI stack volumes..."

# Stop containers first
if [ -f "$SCRIPT_DIR/stop-ai-stack.sh" ]; then
    echo "  Stopping AI stack first..."
    "$SCRIPT_DIR/stop-ai-stack.sh" || true
fi

# Reset Qdrant volume (most common issue - exit code 101)
if [ -d "$AI_STACK_DATA/qdrant" ]; then
    echo "  Resetting Qdrant volume..."
    chmod -R u+rwX "$AI_STACK_DATA/qdrant" 2>/dev/null || true

    # Remove potentially corrupted state (will be regenerated)
    if [ -f "$AI_STACK_DATA/qdrant/raft_state.json" ]; then
        echo "    Removing potentially corrupted raft_state.json..."
        rm -f "$AI_STACK_DATA/qdrant/raft_state.json"
    fi

    # Reset ownership to current user (if running with sudo/different user)
    chown -R $(id -u):$(id -g) "$AI_STACK_DATA/qdrant" 2>/dev/null || true
fi

# Reset other MCP server volumes
for vol in aidb hybrid-coordinator nixos-docs health-monitor ralph-wiggum; do
    if [ -d "$AI_STACK_DATA/$vol" ]; then
        echo "  Resetting $vol volume..."
        chmod -R u+rwX "$AI_STACK_DATA/$vol" 2>/dev/null || true
        chown -R $(id -u):$(id -g) "$AI_STACK_DATA/$vol" 2>/dev/null || true

        # Clear any lock files
        find "$AI_STACK_DATA/$vol" -name "*.lock" -delete 2>/dev/null || true
        find "$AI_STACK_DATA/$vol" -name "*.pid" -delete 2>/dev/null || true
    fi
done

# Reset telemetry volume
if [ -d "$AI_STACK_DATA/telemetry" ]; then
    echo "  Resetting telemetry volume..."
    chmod -R u+rwX "$AI_STACK_DATA/telemetry" 2>/dev/null || true
    chown -R $(id -u):$(id -g) "$AI_STACK_DATA/telemetry" 2>/dev/null || true
fi

# Create missing directories with correct permissions
echo "  Ensuring all required directories exist..."
for dir in qdrant llama-cpp-models open-webui postgres redis mindsdb \
           aidb aidb-cache hybrid-coordinator nixos-docs nixos-repos \
           health-monitor telemetry fine-tuning workspace; do
    mkdir -p "$AI_STACK_DATA/$dir"
    chmod 755 "$AI_STACK_DATA/$dir"
done

echo "✅ Volumes reset successfully"
echo ""
echo "Next steps:"
echo "  1. Start AI stack: podman-compose up -d"
echo "  2. Or run full deployment: ./nixos-quick-deploy.sh"
