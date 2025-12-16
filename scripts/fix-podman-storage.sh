#!/usr/bin/env bash
#
# fix-podman-storage.sh - Manual Podman storage cleanup
# Run this before nixos-quick-deploy.sh if automated remediation fails
#

set -euo pipefail

echo "=========================================="
echo "  Podman Storage Cleanup Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() { echo -e "${GREEN}[STEP]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

# Step 1: Stop all Podman services
print_step "Stopping all Podman services..."

# System services
for svc in podman.service podman.socket podman-auto-update.service podman-auto-update.timer podman-restart.service; do
    sudo systemctl stop "$svc" 2>/dev/null || true
done

# User services
for svc in podman.service podman.socket podman-auto-update.service podman-auto-update.timer; do
    systemctl --user stop "$svc" 2>/dev/null || true
done

# Stop any quadlet-managed containers
systemctl --user list-units 'podman-*.service' --no-legend --no-pager 2>/dev/null | awk '{print $1}' | while read -r unit; do
    [[ -n "$unit" ]] && systemctl --user stop "$unit" 2>/dev/null || true
done

print_ok "Services stopped"

# Step 2: Kill any remaining Podman processes
print_step "Killing remaining Podman processes..."
pkill -9 podman 2>/dev/null || true
pkill -9 conmon 2>/dev/null || true
sudo pkill -9 podman 2>/dev/null || true
sudo pkill -9 conmon 2>/dev/null || true
sleep 2
print_ok "Processes terminated"

# Step 3: Unmount overlay filesystems
print_step "Unmounting overlay filesystems..."

# System overlays
if command -v findmnt >/dev/null 2>&1; then
    sudo findmnt -rn -t overlay -o TARGET 2>/dev/null | grep -E '^/var/lib/containers/storage/overlay/.+/merged$' | while read -r target; do
        if sudo umount -lf "$target" 2>/dev/null; then
            echo "  Unmounted: $target"
        fi
    done

    # User overlays
    findmnt -rn -t overlay -o TARGET 2>/dev/null | grep -E "^${HOME}/.local/share/containers/storage/overlay/.+/merged$" | while read -r target; do
        if umount -lf "$target" 2>/dev/null || sudo umount -lf "$target" 2>/dev/null; then
            echo "  Unmounted: $target"
        fi
    done

    # Fuse overlays
    findmnt -rn -t fuse.fuse-overlayfs -o TARGET 2>/dev/null | grep "/containers/storage/" | while read -r target; do
        if umount -lf "$target" 2>/dev/null || sudo umount -lf "$target" 2>/dev/null; then
            echo "  Unmounted: $target"
        fi
    done
fi
print_ok "Mounts detached"

# Step 4: Backup and remove storage.conf files
print_step "Backing up storage configuration files..."
timestamp=$(date +%Y%m%d-%H%M%S)

if [[ -f /etc/containers/storage.conf ]]; then
    sudo mv /etc/containers/storage.conf "/etc/containers/storage.conf.backup-$timestamp"
    echo "  Backed up /etc/containers/storage.conf"
fi

if [[ -f "${HOME}/.config/containers/storage.conf" ]]; then
    mv "${HOME}/.config/containers/storage.conf" "${HOME}/.config/containers/storage.conf.backup-$timestamp"
    echo "  Backed up user storage.conf"
fi
print_ok "Config files backed up"

# Step 5: Run podman system reset
print_step "Running podman system reset..."
timeout 30 podman system reset --force 2>/dev/null || print_warn "User reset had issues (continuing anyway)"
sudo timeout 30 podman system reset --force 2>/dev/null || print_warn "System reset had issues (continuing anyway)"
print_ok "Reset attempted"

# Step 6: Force delete storage directories
print_step "Removing storage directories..."

# User storage
if [[ -d "${HOME}/.local/share/containers/storage" ]]; then
    rm -rf "${HOME}/.local/share/containers/storage" 2>/dev/null || \
        sudo rm -rf "${HOME}/.local/share/containers/storage" 2>/dev/null || \
        print_warn "Could not remove user storage directory"
fi
rm -rf "${HOME}/.local/share/containers/cache" 2>/dev/null || true
rm -f "${HOME}/.local/share/containers/storage.lock" 2>/dev/null || true

# System storage
if sudo test -d /var/lib/containers/storage 2>/dev/null; then
    sudo rm -rf /var/lib/containers/storage 2>/dev/null || {
        print_warn "Standard removal failed, trying aggressive cleanup..."
        sudo find /var/lib/containers/storage -type f -delete 2>/dev/null || true
        sudo find /var/lib/containers/storage -type d -empty -delete 2>/dev/null || true
        sudo rm -rf /var/lib/containers/storage 2>/dev/null || print_fail "Could not remove system storage"
    }
fi
sudo rm -f /run/containers/storage.lock 2>/dev/null || true
sudo rm -f /var/lib/containers/storage.lock 2>/dev/null || true

print_ok "Storage directories cleaned"

# Step 7: Verify cleanup
print_step "Verifying cleanup..."
errors=0

if [[ -d "${HOME}/.local/share/containers/storage/overlay" ]] && \
   find "${HOME}/.local/share/containers/storage/overlay" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    print_fail "User overlay directory still has content"
    ls -la "${HOME}/.local/share/containers/storage/overlay" 2>/dev/null | head -5
    ((errors++))
else
    print_ok "User overlay directory is clean"
fi

if sudo test -d /var/lib/containers/storage/overlay 2>/dev/null && \
   sudo find /var/lib/containers/storage/overlay -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    print_fail "System overlay directory still has content"
    sudo ls -la /var/lib/containers/storage/overlay 2>/dev/null | head -5
    ((errors++))
else
    print_ok "System overlay directory is clean"
fi

echo ""
echo "=========================================="
if [[ $errors -eq 0 ]]; then
    echo -e "${GREEN}Cleanup completed successfully!${NC}"
    echo ""
    echo "You can now run:"
    echo "  ./nixos-quick-deploy.sh --resume"
else
    echo -e "${YELLOW}Cleanup completed with warnings.${NC}"
    echo ""
    echo "Some directories could not be cleaned. Try:"
    echo "  1. Reboot the system"
    echo "  2. Run this script again"
    echo "  3. Then run: ./nixos-quick-deploy.sh --resume"
fi
echo "=========================================="
