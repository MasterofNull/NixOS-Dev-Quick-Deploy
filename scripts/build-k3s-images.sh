#!/usr/bin/env bash
#
# Build and Import Custom Images into K3s
# Purpose: Build all MCP server images and import them into K3s containerd
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_SERVERS_DIR="${SCRIPT_DIR}/ai-stack/mcp-servers"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if running as root (needed for k3s ctr)
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (for k3s ctr images import)"
    echo "Usage: sudo $0"
    exit 1
fi

# Check for required tools
if ! command -v docker &>/dev/null && ! command -v nerdctl &>/dev/null; then
    error "Neither docker nor nerdctl found. Install one to build images."
    exit 1
fi

if ! command -v k3s &>/dev/null; then
    error "k3s not found. Is K3s installed?"
    exit 1
fi

# Determine build tool
BUILD_TOOL=""
if command -v nerdctl &>/dev/null; then
    BUILD_TOOL="nerdctl"
elif command -v docker &>/dev/null; then
    BUILD_TOOL="docker"
fi

info "Using $BUILD_TOOL to build images"

# Image mappings (directory -> image name)
declare -A IMAGE_MAP=(
    ["aidb"]="localhost/compose_aidb:latest"
    ["aider-wrapper"]="localhost/compose_aider-wrapper:latest"
    ["container-engine"]="localhost/compose_container-engine:latest"
    ["embeddings-service"]="localhost/compose_embeddings:latest"
    ["health-monitor"]="localhost/compose_health-monitor:latest"
    ["hybrid-coordinator"]="localhost/compose_hybrid-coordinator:latest"
    ["nixos-docs"]="localhost/compose_nixos-docs:latest"
    ["ralph-wiggum"]="localhost/compose_ralph-wiggum:latest"
)

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

build_and_import() {
    local dir_name="$1"
    local image_name="$2"
    local dockerfile_path="${MCP_SERVERS_DIR}/${dir_name}/Dockerfile"
    local context_path="${MCP_SERVERS_DIR}/${dir_name}"
    local tar_path="${TEMP_DIR}/${dir_name}.tar"

    if [[ ! -f "$dockerfile_path" ]]; then
        warn "Dockerfile not found for $dir_name, skipping"
        return 0
    fi

    info "Building $image_name from $context_path"

    # Build the image
    if ! $BUILD_TOOL build -t "$image_name" "$context_path" 2>&1; then
        error "Failed to build $image_name"
        return 1
    fi

    info "Exporting $image_name to $tar_path"

    # Export to tar
    if ! $BUILD_TOOL save -o "$tar_path" "$image_name" 2>&1; then
        error "Failed to export $image_name"
        return 1
    fi

    info "Importing $image_name into K3s"

    # Import into K3s containerd
    if ! k3s ctr images import "$tar_path" 2>&1; then
        error "Failed to import $image_name into K3s"
        return 1
    fi

    info "Successfully imported $image_name"
    return 0
}

echo ""
echo "========================================"
echo "  K3s Custom Image Builder"
echo "========================================"
echo ""

# Build and import each image
failed=0
for dir_name in "${!IMAGE_MAP[@]}"; do
    image_name="${IMAGE_MAP[$dir_name]}"
    echo ""
    info "Processing: $dir_name -> $image_name"
    echo "----------------------------------------"

    if ! build_and_import "$dir_name" "$image_name"; then
        error "Failed to process $dir_name"
        ((failed++))
    fi
done

echo ""
echo "========================================"
if [[ $failed -eq 0 ]]; then
    info "All images built and imported successfully!"
    echo ""
    info "Restart failing pods with:"
    echo "  kubectl rollout restart deployment -n ai-stack"
else
    error "$failed image(s) failed to build/import"
fi
echo "========================================"
