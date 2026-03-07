#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# update-llama-cpp.sh — Update llama.cpp version pin to latest release
#
# Phase 20.1 — Declarative llama.cpp version tracking
#
# This script:
#   1. Queries GitHub API for the latest llama.cpp release tag
#   2. Computes the nix hash for the new version
#   3. Updates nix/pins/llama-cpp.json (current → fallback rotation)
#   4. Optionally tests the build before committing
#
# Usage:
#   update-llama-cpp.sh [OPTIONS]
#
# Options:
#   --check         Check for updates without applying
#   --test-build    Build llama-cpp after updating to verify
#   --force         Update even if already at latest
#   --to-version X  Pin to specific version (e.g., b8200)
#   --help          Show this help
#
# Environment:
#   GITHUB_TOKEN    Optional: GitHub API token for higher rate limits
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PIN_FILE="$REPO_ROOT/nix/pins/llama-cpp.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
    sed -n '2,/^# ─/p' "$0" | grep '^#' | sed 's/^# //'
    exit 0
}

# Parse arguments
CHECK_ONLY=false
TEST_BUILD=false
FORCE=false
TARGET_VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --check)      CHECK_ONLY=true; shift ;;
        --test-build) TEST_BUILD=true; shift ;;
        --force)      FORCE=true; shift ;;
        --to-version) TARGET_VERSION="$2"; shift 2 ;;
        --help|-h)    usage ;;
        *)            log_error "Unknown option: $1"; usage ;;
    esac
done

# Ensure dependencies
for cmd in curl jq nix-prefetch-url; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Required command not found: $cmd"
        exit 1
    fi
done

# Read current pin
if [[ ! -f "$PIN_FILE" ]]; then
    log_error "Pin file not found: $PIN_FILE"
    exit 1
fi

CURRENT_VERSION=$(jq -r '.current.version' "$PIN_FILE")
CURRENT_REV=$(jq -r '.current.rev' "$PIN_FILE")
log_info "Current pinned version: $CURRENT_REV (build $CURRENT_VERSION)"

# Get latest release from GitHub
get_latest_release() {
    local auth_header=""
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        auth_header="Authorization: token $GITHUB_TOKEN"
    fi

    local releases
    releases=$(curl -sS -H "$auth_header" \
        "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10")

    # Find latest non-prerelease with b* tag
    echo "$releases" | jq -r '
        [.[] | select(.prerelease == false and (.tag_name | startswith("b")))]
        | first | .tag_name // empty
    '
}

# Compute nix hash for a version
compute_hash() {
    local version="$1"
    local url="https://github.com/ggml-org/llama.cpp/archive/refs/tags/${version}.tar.gz"

    log_info "Computing hash for $version..."
    local nix32_hash
    nix32_hash=$(nix-prefetch-url --unpack "$url" 2>&1 | tail -1)

    # Convert to SRI format
    nix hash convert --hash-algo sha256 --to sri "$nix32_hash" 2>/dev/null ||
        nix hash to-sri --type sha256 "$nix32_hash" 2>/dev/null |
        grep -v '^warning'
}

# Determine target version
if [[ -n "$TARGET_VERSION" ]]; then
    # Use specified version
    if [[ ! "$TARGET_VERSION" =~ ^b[0-9]+$ ]]; then
        log_error "Invalid version format: $TARGET_VERSION (expected bNNNN)"
        exit 1
    fi
    LATEST_REV="$TARGET_VERSION"
    log_info "Targeting specified version: $LATEST_REV"
else
    # Query latest from GitHub
    log_info "Checking GitHub for latest release..."
    LATEST_REV=$(get_latest_release)

    if [[ -z "$LATEST_REV" ]]; then
        log_error "Failed to fetch latest release from GitHub"
        log_warn "Try setting GITHUB_TOKEN if rate limited"
        exit 1
    fi
fi

LATEST_VERSION="${LATEST_REV#b}"
log_info "Latest available: $LATEST_REV (build $LATEST_VERSION)"

# Compare versions
if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]] && [[ "$FORCE" != "true" ]]; then
    log_ok "Already at latest version: $CURRENT_REV"
    exit 0
fi

# Calculate version delta
VERSION_DELTA=$((LATEST_VERSION - CURRENT_VERSION))
if [[ $VERSION_DELTA -gt 0 ]]; then
    log_info "Update available: +$VERSION_DELTA builds"
elif [[ $VERSION_DELTA -lt 0 ]]; then
    log_warn "Target version is older than current (-$((VERSION_DELTA * -1)) builds)"
fi

# Check-only mode
if [[ "$CHECK_ONLY" == "true" ]]; then
    if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
        echo ""
        echo "Update available:"
        echo "  Current: $CURRENT_REV"
        echo "  Latest:  $LATEST_REV"
        echo "  Delta:   $VERSION_DELTA builds"
        echo ""
        echo "Run without --check to apply update"
        exit 0
    fi
    exit 0
fi

# Compute hash for new version
LATEST_HASH=$(compute_hash "$LATEST_REV")
if [[ -z "$LATEST_HASH" ]]; then
    log_error "Failed to compute hash for $LATEST_REV"
    exit 1
fi
log_ok "Hash computed: $LATEST_HASH"

# Update pin file (rotate current → fallback)
log_info "Updating pin file..."
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_STAMP=$(date +"%Y-%m-%d")

# Read current values for fallback
FALLBACK_JSON=$(jq '.current' "$PIN_FILE")

# Create updated pin file
jq --arg ver "$LATEST_VERSION" \
   --arg rev "$LATEST_REV" \
   --arg hash "$LATEST_HASH" \
   --arg date "$DATE_STAMP" \
   --arg ts "$TIMESTAMP" \
   --argjson fb "$FALLBACK_JSON" \
   '
   .fallback = $fb |
   .current = {
     version: $ver,
     rev: $rev,
     hash: $hash,
     date: $date
   } |
   ._meta.lastUpdated = $ts |
   ._meta.updatedBy = "scripts/ai/update-llama-cpp.sh"
   ' "$PIN_FILE" > "${PIN_FILE}.tmp"

mv "${PIN_FILE}.tmp" "$PIN_FILE"
log_ok "Pin file updated: $CURRENT_REV → $LATEST_REV"

# Show the changes
echo ""
echo "Updated nix/pins/llama-cpp.json:"
echo "  current:  $LATEST_REV ($LATEST_HASH)"
echo "  fallback: $CURRENT_REV (previous current)"
echo ""

# Optional: test build
if [[ "$TEST_BUILD" == "true" ]]; then
    log_info "Testing build..."
    if nix build "$REPO_ROOT#nixosConfigurations.nixos-ai-dev.config.system.build.toplevel" \
         --no-link --print-out-paths 2>&1 | head -5; then
        log_ok "Build test passed"
    else
        log_error "Build test failed — consider using --force to revert"
        log_warn "Fallback available: set mySystem.aiStack.llamaCpp.useFallback = true"
        exit 1
    fi
fi

# Summary
echo ""
log_ok "llama.cpp pin updated successfully"
echo ""
echo "Next steps:"
echo "  1. Review: git diff nix/pins/llama-cpp.json"
echo "  2. Rebuild: sudo nixos-rebuild switch --flake ."
echo "  3. If issues: set mySystem.aiStack.llamaCpp.useFallback = true"
echo ""
echo "Changelog: https://github.com/ggml-org/llama.cpp/releases/tag/$LATEST_REV"
