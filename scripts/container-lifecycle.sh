#!/usr/bin/env bash
# Safe container management with validation and rollback
# Usage: ./scripts/container-lifecycle.sh <service-name>

set -euo pipefail

SERVICE=$1
WORKDIR="/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy"

cd "$WORKDIR"

echo "════════════════════════════════════════════════════════════════"
echo "  Safe Container Deployment: ${SERVICE}"
echo "════════════════════════════════════════════════════════════════"

# Step 1: Validate Python syntax
echo ""
echo "→ Step 1: Validating Python syntax..."
if ! python3 -m py_compile "ai-stack/mcp-servers/${SERVICE}/server.py"; then
    echo "✗ Syntax validation failed"
    exit 1
fi
echo "✓ Syntax valid"

# Step 2: Build container image
echo ""
echo "→ Step 2: Building container image..."
if ! podman build \
    -f "ai-stack/mcp-servers/${SERVICE}/Dockerfile" \
    -t "${SERVICE}" \
    "ai-stack/mcp-servers/" 2>&1 | tail -10; then
    echo "✗ Build failed"
    exit 1
fi
echo "✓ Build successful"

# Step 3: Safe deployment with rollback
echo ""
echo "→ Step 3: Deploying container..."

# Check if old container exists
OLD_ID=$(podman ps -a --filter "name=local-ai-${SERVICE}" --format "{{.ID}}" || true)

if [[ -n "$OLD_ID" ]]; then
    echo "  Found existing container: $OLD_ID"
    echo "  Creating backup..."
    podman rename "local-ai-${SERVICE}" "local-ai-${SERVICE}-backup" || true
    podman stop "local-ai-${SERVICE}-backup" 2>/dev/null || true
fi

# Determine port mapping based on service
PORT_ARGS=""
case "${SERVICE}" in
    "ralph-wiggum")
        PORT_ARGS="-p 127.0.0.1:8098:8098"
        ;;
    "aider-wrapper")
        PORT_ARGS="--expose 8099"
        ;;
    *)
        PORT_ARGS="--expose 8099"
        ;;
esac

# Start new container
echo "  Starting new container with ports: ${PORT_ARGS}"
if ! podman run -d \
    --name "local-ai-${SERVICE}" \
    --hostname "${SERVICE}" \
    --network "local-ai" \
    ${PORT_ARGS} \
    --env-file "/home/hyperd/.config/nixos-ai-stack/.env" \
    -v "${WORKDIR}:/workspace:Z" \
    "${SERVICE}"; then
    echo "✗ Container failed to start"
    
    # Rollback
    if [[ -n "$OLD_ID" ]]; then
        echo "  Rolling back to previous container..."
        podman rename "local-ai-${SERVICE}-backup" "local-ai-${SERVICE}" 2>/dev/null || true
        podman start "local-ai-${SERVICE}" 2>/dev/null || true
    fi
    exit 1
fi

# Wait for container to initialize
echo "  Waiting for container to initialize..."
sleep 5

# Check if container is still running
if ! podman ps --filter "name=local-ai-${SERVICE}" --format "{{.Names}}" | grep -q "local-ai-${SERVICE}"; then
    echo "✗ Container exited unexpectedly"
    echo "  Logs:"
    podman logs "local-ai-${SERVICE}" 2>&1 | tail -20
    
    # Rollback
    podman rm -f "local-ai-${SERVICE}" 2>/dev/null || true
    if [[ -n "$OLD_ID" ]]; then
        echo "  Rolling back..."
        podman rename "local-ai-${SERVICE}-backup" "local-ai-${SERVICE}" 2>/dev/null || true
        podman start "local-ai-${SERVICE}" 2>/dev/null || true
    fi
    exit 1
fi

# Success - remove backup
if [[ -n "$OLD_ID" ]]; then
    echo "  Removing backup container..."
    podman rm -f "local-ai-${SERVICE}-backup" 2>/dev/null || true
fi

echo "✓ Deploy successful"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Deployment Complete: ${SERVICE}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Container status:"
podman ps --filter "name=local-ai-${SERVICE}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Recent logs:"
podman logs --tail 15 "local-ai-${SERVICE}" 2>&1 || true
