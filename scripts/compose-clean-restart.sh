#!/usr/bin/env bash
# Clean restart of AI stack containers
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Stop, clean, and prepare for fresh container startup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="${COMPOSE_FILE:-$PROJECT_ROOT/ai-stack/compose}"

# Source container registry for complete container list
source "$PROJECT_ROOT/lib/ai-stack-containers.sh"

# If COMPOSE_FILE is a file path, extract directory
if [[ -f "$COMPOSE_DIR" ]]; then
    COMPOSE_DIR="$(dirname "$COMPOSE_DIR")"
fi

echo "==> Clean restart: stopping existing containers..."

# Determine compose command
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "Warning: No compose command found, skipping compose down"
    COMPOSE_CMD=""
fi

# Stop via compose if available
if [[ -n "$COMPOSE_CMD" && -f "$COMPOSE_DIR/docker-compose.yml" ]]; then
    cd "$COMPOSE_DIR"
    $COMPOSE_CMD down --remove-orphans 2>/dev/null || true
fi

# Force stop and remove any lingering containers
if command -v podman >/dev/null 2>&1; then
    for container in "${AI_STACK_CONTAINERS[@]}"; do
        if podman ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            echo "  Removing $container..."
            podman stop "$container" 2>/dev/null || true
            podman rm -f "$container" 2>/dev/null || true
        fi
    done

    # Clean up any orphaned containers with our label
    orphans=$(podman ps -a --filter "label=nixos.quick-deploy.ai-stack=true" --format '{{.Names}}' 2>/dev/null || true)
    if [[ -n "$orphans" ]]; then
        echo "  Removing orphaned containers..."
        echo "$orphans" | while read -r name; do
            podman rm -f "$name" 2>/dev/null || true
        done
    fi
fi

echo "==> Clean restart complete"
