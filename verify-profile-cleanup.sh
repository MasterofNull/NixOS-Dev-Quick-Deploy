#!/usr/bin/env bash
#
# Verification Script for Home Manager Profile Cleanup Fix
# This script helps verify that the profile cleanup is working correctly
#

set -euo pipefail

echo "=========================================================================="
echo "Home Manager Profile Cleanup Verification"
echo "=========================================================================="
echo ""

HM_PROFILE="${HOME}/.local/state/nix/profiles/home-manager"

# Check if nix command is available
if ! command -v nix >/dev/null 2>&1; then
    echo "✗ nix command not found"
    exit 1
fi

echo "✓ nix command available"
echo ""

# Check if home-manager profile exists
if [[ ! -e "$HM_PROFILE" ]]; then
    echo "ℹ Home-manager profile not yet initialized"
    echo "  Profile will be created during home-manager switch"
    echo "  Location: $HM_PROFILE"
    exit 0
fi

echo "✓ Home-manager profile exists: $HM_PROFILE"
echo ""

# List profile contents
echo "Current home-manager profile contents:"
echo "----------------------------------------------------------------------"
if nix profile list --profile "$HM_PROFILE" 2>/dev/null; then
    echo "----------------------------------------------------------------------"
    echo ""
else
    echo "✗ Could not list profile contents"
    exit 1
fi

# Check for conflicting packages
echo "Checking for conflicting packages..."
CONFLICTS=$(nix profile list --profile "$HM_PROFILE" 2>/dev/null | grep -iE 'python3|huggingface-hub|shellcheck|slirp4netns|fuse3|^[[:space:]]*[0-9]+[[:space:]]+git[[:space:]]' || true)

if [[ -n "$CONFLICTS" ]]; then
    echo "✗ FOUND CONFLICTING PACKAGES:"
    echo "$CONFLICTS" | sed 's/^/  /'
    echo ""
    echo "These packages will cause file collisions during home-manager switch."
    echo "The deployment script will automatically remove them before the switch."
    echo ""
    echo "To manually remove them now:"
    echo "  nix profile list --profile $HM_PROFILE"
    echo "  nix profile remove <index> --profile $HM_PROFILE"
    exit 1
else
    echo "✓ No conflicting packages detected"
    echo ""
    echo "The home-manager profile is clean and ready for deployment."
fi

echo ""
echo "=========================================================================="
echo "Verification Complete"
echo "=========================================================================="
