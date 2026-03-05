#!/run/current-system/sw/bin/bash
# Enable COSMIC Power Profile Manager
# Disables TLP and enables power-profiles-daemon

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

CONFIG_FILE="/etc/nixos/nixos-improvements/mobile-workstation.nix"
BACKUP_FILE="${CONFIG_FILE}.backup-$(date +%Y%m%d-%H%M%S)"

if [[ ! -f "$CONFIG_FILE" ]]; then
    error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)"
    exit 1
fi

info "Switching from TLP to power-profiles-daemon for COSMIC integration"
echo ""

# Create backup
info "Creating backup: $BACKUP_FILE"
cp "$CONFIG_FILE" "$BACKUP_FILE"
success "Backup created"

# Make the changes
info "Disabling TLP..."
sed -i 's/services\.tlp = {$/services.tlp = {/' "$CONFIG_FILE"
sed -i 's/^    enable = lib\.mkDefault true;$/    enable = lib.mkDefault false;  # Disabled in favor of power-profiles-daemon for COSMIC integration/' "$CONFIG_FILE"
success "TLP disabled"

info "Enabling power-profiles-daemon..."
sed -i 's/services\.power-profiles-daemon\.enable = lib\.mkForce false;$/services.power-profiles-daemon.enable = lib.mkDefault true;  # Enabled for COSMIC power profile GUI/' "$CONFIG_FILE"
success "power-profiles-daemon enabled"

echo ""
info "Configuration updated. Changes made:"
echo "  - TLP: enabled → disabled"
echo "  - power-profiles-daemon: disabled → enabled"
echo ""

warning "You must rebuild NixOS for changes to take effect:"
echo ""
echo "  sudo nixos-rebuild switch"
echo ""
info "After rebuild, the COSMIC power profile manager will work"
echo ""
info "Backup saved at: $BACKUP_FILE"
