#!/usr/bin/env bash
#
# Build and Import Custom Images into K3s
# Purpose: Build all MCP server images and import them into K3s containerd
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_SERVERS_DIR="${SCRIPT_DIR}/ai-stack/mcp-servers"
DASHBOARD_API_DIR="${SCRIPT_DIR}/dashboard/backend"

# Ensure UID is exported for buildah storage config expansion.
if [[ -z "${UID:-}" ]]; then
    export UID="$(id -u)"
else
    export UID
fi
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${UID}}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Enforce rootless builds only.
if [[ $EUID -eq 0 ]]; then
    error "Refusing to run as root. Use rootless buildah instead."
    echo "Hint: run without sudo and publish via scripts/publish-local-registry.sh"
    exit 1
fi

# Default to build/export only; use publish-local-registry.sh to load into K3s.
SKIP_K3S_IMPORT="${SKIP_K3S_IMPORT:-true}"
if [[ "$SKIP_K3S_IMPORT" != "true" ]]; then
    error "Direct K3s import is disabled for rootless builds."
    echo "Use: ./scripts/publish-local-registry.sh to publish images."
    exit 1
fi

# Check for required tools (docker/nerdctl/buildah)
if ! command -v docker &>/dev/null && ! command -v nerdctl &>/dev/null && ! command -v buildah &>/dev/null; then
    error "No container build tool found. Install buildah, nerdctl, or docker."
    exit 1
fi

# Rootless build path does not touch k3s directly.

# Determine build tool (override via BUILD_TOOL env)
BUILD_TOOL="${BUILD_TOOL:-}"
if [[ -z "$BUILD_TOOL" ]]; then
    if command -v buildah &>/dev/null; then
        BUILD_TOOL="buildah"
    else
        error "buildah is required for rootless builds. Install buildah and retry."
        exit 1
    fi
else
    if [[ "$BUILD_TOOL" != "buildah" ]]; then
        error "Non-buildah build tool requested (${BUILD_TOOL}). Rootless builds require buildah."
        exit 1
    fi
fi

info "Using $BUILD_TOOL to build images (rootless)"

# Keep buildah non-interactive and compatible with local registry pushes.
export BUILDAH_SHORT_NAME_MODE="${BUILDAH_SHORT_NAME_MODE:-permissive}"
export BUILDAH_FORMAT="${BUILDAH_FORMAT:-docker}"
export BUILDAH_ISOLATION="${BUILDAH_ISOLATION:-chroot}"

# Image mappings (directory -> image name)
declare -A IMAGE_MAP=(
    ["aidb"]="localhost/ai-stack-aidb:latest"
    ["aider-wrapper"]="localhost/ai-stack-aider-wrapper:latest"
    ["container-engine"]="localhost/ai-stack-container-engine:latest"
    ["dashboard-api"]="localhost/ai-stack-dashboard-api:latest"
    ["embeddings-service"]="localhost/ai-stack-embeddings:latest"
    ["health-monitor"]="localhost/ai-stack-health-monitor:latest"
    ["hybrid-coordinator"]="localhost/ai-stack-hybrid-coordinator:latest"
    ["nixos-docs"]="localhost/ai-stack-nixos-docs:latest"
    ["ralph-wiggum"]="localhost/ai-stack-ralph-wiggum:latest"
)

declare -A IMAGE_CONTEXT_MAP=(
    ["dashboard-api"]="${DASHBOARD_API_DIR}"
)

declare -A IMAGE_DOCKERFILE_MAP=(
    ["dashboard-api"]="${DASHBOARD_API_DIR}/Dockerfile"
)

ONLY_IMAGES="${ONLY_IMAGES:-}"
SKIP_IMAGES="${SKIP_IMAGES:-}"
declare -A only_set=()
declare -A skip_set=()

if [[ -n "$ONLY_IMAGES" ]]; then
    IFS=',' read -r -a only_list <<< "$ONLY_IMAGES"
    for item in "${only_list[@]}"; do
        item="${item// /}"
        [[ -n "$item" ]] && only_set["$item"]=1
    done
fi

if [[ -n "$SKIP_IMAGES" ]]; then
    IFS=',' read -r -a skip_list <<< "$SKIP_IMAGES"
    for item in "${skip_list[@]}"; do
        item="${item// /}"
        [[ -n "$item" ]] && skip_set["$item"]=1
    done
fi

BUILD_TMP_BASE="${BUILD_TMP_BASE:-$HOME/.cache/nixos-quick-deploy/buildah}"
BUILD_TMP_MIN_FREE_GB="${BUILD_TMP_MIN_FREE_GB:-8}"

check_build_tmp_space() {
    local target="$1"
    local min_gb="$2"
    local avail_kb
    avail_kb=$(df -Pk "$target" 2>/dev/null | awk 'NR==2 {print $4}')
    if [[ -z "$avail_kb" ]]; then
        warn "Unable to determine free space for ${target}; continuing."
        return 0
    fi
    local avail_gb=$((avail_kb / 1024 / 1024))
    if (( avail_gb < min_gb )); then
        error "Insufficient free space in ${target} (${avail_gb}G < ${min_gb}G)."
        echo "Set BUILD_TMP_BASE to a path with more space or lower BUILD_TMP_MIN_FREE_GB." >&2
        return 1
    fi
    return 0
}
mkdir -p "$BUILD_TMP_BASE"
check_build_tmp_space "$BUILD_TMP_BASE" "$BUILD_TMP_MIN_FREE_GB"
export TMPDIR="$BUILD_TMP_BASE"
export BUILDAH_TMPDIR="$BUILD_TMP_BASE"

TEMP_DIR=$(mktemp -d -p "$BUILD_TMP_BASE")
trap 'rm -rf "$TEMP_DIR"' EXIT

build_and_import() {
    local dir_name="$1"
    local image_name="$2"
    local dockerfile_path="${IMAGE_DOCKERFILE_MAP[$dir_name]:-${MCP_SERVERS_DIR}/${dir_name}/Dockerfile}"
    local context_path="${IMAGE_CONTEXT_MAP[$dir_name]:-${MCP_SERVERS_DIR}}"
    local tar_path="${TEMP_DIR}/${dir_name}.tar"

    if [[ ! -f "$dockerfile_path" ]]; then
        warn "Dockerfile not found for $dir_name, skipping"
        return 0
    fi

    info "Building $image_name from $context_path"

    # Build the image
    if [[ "$BUILD_TOOL" == "buildah" ]]; then
        if ! buildah bud -f "$dockerfile_path" -t "$image_name" "$context_path" 2>&1; then
            error "Failed to build $image_name with buildah"
            return 1
        fi
    else
        if ! $BUILD_TOOL build -f "$dockerfile_path" -t "$image_name" "$context_path" 2>&1; then
            error "Failed to build $image_name"
            return 1
        fi
    fi

    info "Exporting $image_name to $tar_path"

    # Export to tar
    if [[ "$BUILD_TOOL" == "buildah" ]]; then
        if ! buildah push "$image_name" "docker-archive:${tar_path}" 2>&1; then
            error "Failed to export $image_name with buildah"
            return 1
        fi
    else
        if ! $BUILD_TOOL save -o "$tar_path" "$image_name" 2>&1; then
            error "Failed to export $image_name"
            return 1
        fi
    fi

    warn "Skipping k3s import for $image_name (rootless build)."
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
    image_short="${image_name#localhost/}"

    if [[ -n "$ONLY_IMAGES" ]]; then
        if [[ -z "${only_set[$dir_name]+x}" && -z "${only_set[$image_short]+x}" ]]; then
            warn "Skipping $dir_name (ONLY_IMAGES filter active)"
            continue
        fi
    fi

    if [[ -n "$SKIP_IMAGES" ]]; then
        if [[ -n "${skip_set[$dir_name]+x}" || -n "${skip_set[$image_short]+x}" ]]; then
            warn "Skipping $dir_name (SKIP_IMAGES filter active)"
            continue
        fi
    fi
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
    info "All images built and exported successfully."
    echo ""
    info "Next steps:"
    echo "  ./scripts/publish-local-registry.sh"
    echo "  kubectl rollout restart deployment -n ai-stack"
else
    error "$failed image(s) failed to build/import"
fi
echo "========================================"
