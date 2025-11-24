#!/usr/bin/env bash
#
# Fix Stuck NixOS Rebuild
# This script fixes a stuck nixos-rebuild-switch-to-configuration service
# and broken sudo binary that can occur during incomplete system rebuilds.
#
# Usage: Run this directly from a terminal (it will use the working sudo wrapper):
#   bash /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/fix-stuck-rebuild.sh
#
# The script will prompt for your password when needed.

set -euo pipefail

# Use the working sudo wrapper from /run/wrappers/bin
SUDO="/run/wrappers/bin/sudo"

if [[ ! -x "$SUDO" ]]; then
    echo "ERROR: Working sudo not found at $SUDO"
    echo "Please run the commands manually as root"
    exit 1
fi

echo "=== NixOS Rebuild Recovery Script ==="
echo ""
echo "This script will use sudo and may prompt for your password."
echo ""

echo "Step 1: Stopping stuck nixos-rebuild-switch-to-configuration service..."
if systemctl is-active --quiet nixos-rebuild-switch-to-configuration.service 2>/dev/null; then
    echo "  Service is running, stopping it..."
    if $SUDO systemctl stop nixos-rebuild-switch-to-configuration.service 2>/dev/null; then
        echo "  ✓ Service stopped gracefully"
    else
        echo "  Failed to stop gracefully, force killing..."
        $SUDO systemctl kill -s SIGKILL nixos-rebuild-switch-to-configuration.service
        sleep 2
        echo "  ✓ Service killed"
    fi
else
    echo "  Service is not running (skipping)"
fi

echo ""
echo "Step 2: Resetting failed systemd units..."
$SUDO systemctl reset-failed 2>/dev/null || echo "  No failed units to reset"

echo ""
echo "Step 3: Checking sudo binary..."
SUDO_PATH="/run/current-system/sw/bin/sudo"
if [[ -L "$SUDO_PATH" ]]; then
    SUDO_TARGET=$(readlink -f "$SUDO_PATH")
    echo "  Sudo symlink: $SUDO_PATH -> $SUDO_TARGET"

    if [[ -f "$SUDO_TARGET" ]]; then
        SUDO_PERMS=$(stat -c '%a' "$SUDO_TARGET")
        echo "  Sudo permissions: $SUDO_PERMS"

        # Check if setuid bit is set (should be 4xxx)
        if [[ "$SUDO_PERMS" =~ ^4 ]]; then
            echo "  ✓ Sudo has correct permissions"
        else
            echo "  ✗ Sudo missing setuid bit!"
            echo "  Note: /nix/store is immutable, cannot fix this directly"
            echo "  This will be fixed by completing nixos-rebuild"
        fi
    fi
fi

echo ""
echo "Step 4: Finding a working sudo binary..."
WORKING_SUDO=""
for sudo_candidate in /run/wrappers/bin/sudo /nix/store/*/bin/sudo; do
    if [[ -f "$sudo_candidate" ]] && [[ -u "$sudo_candidate" ]]; then
        WORKING_SUDO="$sudo_candidate"
        echo "  ✓ Found working sudo: $WORKING_SUDO"
        break
    fi
done

if [[ -z "$WORKING_SUDO" ]]; then
    echo "  ⚠ No working sudo found with setuid bit"
    echo "  This will be fixed after completing nixos-rebuild"
fi

echo ""
echo "Step 5: Daemon reload..."
$SUDO systemctl daemon-reload
echo "  ✓ Systemd daemon reloaded"

echo ""
echo "=== Recovery Complete ==="
echo ""
echo "The stuck service has been stopped and systemd has been reloaded."
echo ""
echo "Next step: Retry nixos-rebuild switch"
echo "  Run this command:"
echo "  $SUDO nixos-rebuild switch --flake ~/.config/home-manager#\$(hostname)"
echo ""
echo "Or run the deployment script:"
echo "  cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy"
echo "  ./nixos-quick-deploy.sh"
echo ""
