#!/usr/bin/env bash
# Fast rebuild script with BuildKit and parallel builds
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Rebuild containers with optimized settings for faster builds

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$PROJECT_ROOT/ai-stack/compose"

info() { echo "ℹ $*"; }
success() { echo "✓ $*"; }
error() { echo "✗ $*"; }

# Enable BuildKit for faster builds
export BUILDKIT_PROGRESS=plain
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Parallel build settings
export BUILDAH_MAX_JOBS=4

info "Fast rebuild with BuildKit enabled"
info "Build settings:"
echo "  - BuildKit: enabled"
echo "  - Parallel jobs: 4"
echo "  - Progress: plain (detailed)"

cd "$COMPOSE_DIR"

# Stop existing containers first
info "Stopping existing containers..."
podman-compose down 2>/dev/null || true

# Rebuild with cache and parallel builds
info "Rebuilding all containers (this will be faster with BuildKit)..."
podman-compose build \
    --parallel \
    --pull-always 2>&1 | grep -v "^WARN"

success "Rebuild complete!"

info "To start services, run:"
echo "  cd $COMPOSE_DIR && podman-compose up -d"
echo "Or use the full deployment:"
echo "  $PROJECT_ROOT/nixos-quick-deploy.sh"
