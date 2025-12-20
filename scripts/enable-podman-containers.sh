#!/usr/bin/env bash
#
# Enable Podman Containers - Quick Fix Script
# Purpose: Enable LOCAL_AI_STACK_ENABLED and rebuild Home Manager configuration
#
# Usage: ./scripts/enable-podman-containers.sh [--hf-token TOKEN]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

print_success() {
    echo -e "${GREEN}✓${NC} $*"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
}

print_error() {
    echo -e "${RED}✗${NC} $*"
}

# Parse arguments
HF_TOKEN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --hf-token)
            HF_TOKEN="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--hf-token TOKEN]"
            echo ""
            echo "Enable Podman containers by setting LOCAL_AI_STACK_ENABLED=true"
            echo "and rebuilding the Home Manager configuration."
            echo ""
            echo "Options:"
            echo "  --hf-token TOKEN    Set Hugging Face API token"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

print_info "Enabling Podman containers..."

# Step 1: Set preference file
PREF_DIR="$HOME/.config/nixos-quick-deploy"
PREF_FILE="$PREF_DIR/local-ai-stack.env"
HF_PREF_FILE="$PREF_DIR/huggingface-token.env"

mkdir -p "$PREF_DIR"

# Set LOCAL_AI_STACK_ENABLED
echo "LOCAL_AI_STACK_ENABLED=true" > "$PREF_FILE"
print_success "Set LOCAL_AI_STACK_ENABLED=true in $PREF_FILE"

# Set Hugging Face token if provided
if [[ -n "$HF_TOKEN" ]]; then
    echo "HUGGINGFACEHUB_API_TOKEN=$HF_TOKEN" > "$HF_PREF_FILE"
    export HUGGINGFACEHUB_API_TOKEN="$HF_TOKEN"
    print_success "Set Hugging Face token"
elif [[ -f "$HF_PREF_FILE" ]]; then
    # Load existing token if available
    source "$HF_PREF_FILE" 2>/dev/null || true
    if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        print_info "Using existing Hugging Face token from $HF_PREF_FILE"
    fi
fi

# Step 2: Export environment variables
export LOCAL_AI_STACK_ENABLED=true

# Step 3: Check if we need to regenerate configuration
CONFIG_DIR="${HOME_MANAGER_CONFIG_DIR:-$HOME/.config/home-manager}"
HOME_NIX="$CONFIG_DIR/home.nix"

if [[ ! -f "$HOME_NIX" ]]; then
    print_error "Home Manager configuration not found at $HOME_NIX"
    print_info "You may need to run the full deployment script first"
    exit 1
fi

# Check if containers are already enabled
if grep -q "LOCAL_AI_STACK_ENABLED_PLACEHOLDER" "$HOME_NIX" 2>/dev/null; then
    print_warning "Configuration still contains placeholder - needs regeneration"
    print_info "You may need to re-run the deployment script or regenerate config"
elif grep -q "services.podman.*=.*lib.mkIf.*true" "$HOME_NIX" 2>/dev/null; then
    print_success "Containers appear to be enabled in configuration"
else
    print_warning "Could not verify container configuration in $HOME_NIX"
fi

# Step 4: Rebuild Home Manager
print_info "Rebuilding Home Manager configuration..."
print_info "This will apply the container definitions to your system"

HOSTNAME=$(hostname)
if command -v home-manager >/dev/null 2>&1; then
    if home-manager switch --flake "$CONFIG_DIR#$HOSTNAME"; then
        print_success "Home Manager rebuild complete"
    else
        print_error "Home Manager rebuild failed"
        exit 1
    fi
else
    print_error "home-manager command not found"
    print_info "Make sure Home Manager is installed and in your PATH"
    exit 1
fi

# Step 5: Verify installation
print_info "Verifying installation..."

if [[ -f "$HOME/.local/bin/podman-ai-stack" ]]; then
    print_success "podman-ai-stack helper installed"
else
    print_warning "podman-ai-stack helper not found (may need to rebuild again)"
fi

# Check for systemd services
if systemctl --user list-units --type=service --all | grep -q "podman-.*\.service"; then
    print_success "Podman systemd services found"
else
    print_warning "No Podman systemd services found yet"
    print_info "Services will be created when you first run 'podman-ai-stack up'"
fi

# Step 6: Instructions
echo ""
print_success "Podman containers are now enabled!"
echo ""
print_info "Next steps:"
echo "  1. Start the containers:"
echo "     ${GREEN}podman-ai-stack up${NC}"
echo ""
echo "  2. Check container status:"
echo "     ${GREEN}podman-ai-stack status${NC}"
echo ""
echo "  3. View logs:"
echo "     ${GREEN}podman-ai-stack logs${NC}"
echo ""
print_info "Containers will be created and started when you run 'podman-ai-stack up'"
print_info "Data will be stored in: $HOME/.local/share/podman-ai-stack/"

