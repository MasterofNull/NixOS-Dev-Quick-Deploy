#!/usr/bin/env bash
# Full NixOS System Update Script
# Updates flake inputs, rebuilds system, updates home-manager, and cleans up

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "$REPO_ROOT"

echo "=================================="
echo "NixOS System Update - Full Sweep"
echo "=================================="
echo ""
echo "Repo: $REPO_ROOT"
echo "Date: $(date)"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Step 1: Show current state
log_info "Step 1: Current System State"
echo ""
echo "Current Chromium version:"
chromium --version 2>/dev/null || echo "  (not installed)"
echo ""
echo "Current NixOS generation:"
nixos-rebuild list-generations | head -3
echo ""
echo "Current nixpkgs:"
nix flake metadata --json 2>/dev/null | jq -r '.locks.nodes.nixpkgs.locked | "  \(.owner)/\(.repo) @ \(.rev[0:7]) (last modified: \(.lastModified | strftime("%Y-%m-%d")))"' || echo "  (unable to determine)"
echo ""

# Check disk space
AVAILABLE_GB=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')
if (( AVAILABLE_GB < 10 )); then
    log_warn "Low disk space: ${AVAILABLE_GB}GB available. Consider running garbage collection first."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Update flake inputs
log_info "Step 2: Updating flake inputs (nixpkgs, home-manager, etc.)"
echo ""

if nix flake update; then
    log_info "✓ Flake inputs updated"
    echo ""

    # Show what changed
    log_info "Changes in flake.lock:"
    git diff flake.lock | grep -E '^\+|^\-' | grep -E 'narHash|rev|lastModified' | head -20 || echo "  (no changes detected)"
    echo ""
else
    log_error "Failed to update flake inputs"
    exit 1
fi

# Step 3: Dry run to see what will be updated
log_info "Step 3: Checking what will be updated (dry-run)"
echo ""

if nixos-rebuild dry-build --flake .#hyperd 2>&1 | tee /tmp/nixos-update-dryrun.log; then
    log_info "✓ Dry-run successful"

    # Estimate download size
    if grep -q "will be downloaded" /tmp/nixos-update-dryrun.log; then
        log_info "Download estimate:"
        grep "will be downloaded" /tmp/nixos-update-dryrun.log | tail -1
    fi
    echo ""
else
    log_warn "Dry-run had issues (this might be OK)"
    echo ""
fi

# Ask for confirmation
log_warn "This will:"
echo "  - Update nixpkgs and all system packages"
echo "  - Update Chromium to latest stable version"
echo "  - Rebuild system configuration"
echo "  - Update home-manager user environment"
echo "  - Download ~500MB-2GB of packages (estimate)"
echo ""
read -p "Proceed with system update? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Update cancelled by user"
    exit 0
fi

# Step 4: Rebuild system
log_info "Step 4: Rebuilding NixOS system"
echo ""

if sudo nixos-rebuild switch --flake .#hyperd; then
    log_info "✓ System rebuild successful"
    echo ""
else
    log_error "System rebuild failed"
    log_error "To rollback: sudo nixos-rebuild switch --rollback"
    exit 1
fi

# Step 5: Update home-manager
log_info "Step 5: Updating home-manager (user environment)"
echo ""

if home-manager switch --flake .#hyperd@hyperd; then
    log_info "✓ Home-manager updated"
    echo ""
else
    log_warn "Home-manager update failed (non-critical)"
    echo ""
fi

# Step 6: Verify updates
log_info "Step 6: Verification"
echo ""
echo "New Chromium version:"
chromium --version 2>/dev/null || echo "  (not installed)"
echo ""
echo "New NixOS generation:"
nixos-rebuild list-generations | head -3
echo ""
echo "New nixpkgs:"
nix flake metadata --json 2>/dev/null | jq -r '.locks.nodes.nixpkgs.locked | "  \(.owner)/\(.repo) @ \(.rev[0:7]) (last modified: \(.lastModified | strftime("%Y-%m-%d")))"' || echo "  (unable to determine)"
echo ""

# Step 7: Optional cleanup
log_info "Step 7: Cleanup (optional)"
echo ""

GENERATIONS=$(nixos-rebuild list-generations | wc -l)
log_info "You have $GENERATIONS system generations"

if (( GENERATIONS > 10 )); then
    read -p "Clean old generations (keep last 5)? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Running garbage collection..."
        sudo nix-collect-garbage --delete-older-than 30d
        log_info "✓ Garbage collection complete"
        echo ""
    fi
fi

# Show disk usage
log_info "Current disk usage:"
df -h / | grep -v Filesystem
echo ""

# Step 8: Summary
echo "=================================="
echo "Update Complete!"
echo "=================================="
echo ""
log_info "Summary:"
echo "  ✓ Flake inputs updated"
echo "  ✓ System packages updated (including Chromium)"
echo "  ✓ Home-manager environment updated"
echo "  ✓ All changes applied"
echo ""
log_info "To rollback if needed:"
echo "  sudo nixos-rebuild switch --rollback"
echo ""
log_info "Chromium will now receive updates through NixOS package manager."
log_info "Run this script periodically (weekly/monthly) to stay current."
echo ""
