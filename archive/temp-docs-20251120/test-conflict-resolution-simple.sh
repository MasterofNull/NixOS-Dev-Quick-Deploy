#!/usr/bin/env bash
#
# Simple Test Script: Service Conflict Resolution
# Purpose: Verify conflict detection works without full library dependencies
#

set -euo pipefail

echo "======================================================================"
echo "Service Conflict Resolution - Simple Test"
echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine if sudo is available without prompting (CI-safe)
SUDO_AVAILABLE=false
if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    SUDO_AVAILABLE=true
fi

run_sudo() {
    if [[ "$SUDO_AVAILABLE" == "true" ]]; then
        sudo -n "$@"
    else
        return 1
    fi
}

print_info() { echo -e "${BLUE}ℹ${NC} $*"; }
print_success() { echo -e "${GREEN}✓${NC} $*"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $*"; }
print_error() { echo -e "${RED}✗${NC} $*"; }

# Test 1: Check System Services
echo "Test 1: Check system service status"
echo "----------------------------------------------------------------------"
declare -A SYSTEM_STATUS
declare -A SYSTEM_ENABLED

if [[ "$SUDO_AVAILABLE" != "true" ]]; then
    print_warning "sudo is unavailable without a password; system service checks are best-effort only"
fi

for service in ollama.service qdrant.service; do
    if run_sudo systemctl is-active "$service" &>/dev/null; then
        status="active"
        print_success "$service is $status"
    elif [[ "$SUDO_AVAILABLE" != "true" ]]; then
        status="unknown (no sudo)"
        print_warning "Unable to query $service (sudo not available); assuming inactive for conflict checks"
    else
        status="inactive"
        print_info "$service is $status"
    fi

    if [[ "$SUDO_AVAILABLE" == "true" ]]; then
        if run_sudo systemctl is-enabled "$service" &>/dev/null 2>&1; then
            enabled="enabled"
        elif run_sudo systemctl is-enabled "$service" 2>&1 | grep -q "masked"; then
            enabled="masked"
        else
            enabled="disabled"
        fi
    else
        enabled="unknown"
    fi

    SYSTEM_STATUS["$service"]="$status"
    SYSTEM_ENABLED["$service"]="$enabled"
    echo "  Status: ${SYSTEM_STATUS[$service]}, Enabled: ${SYSTEM_ENABLED[$service]}"
done
echo ""

# Test 2: Check home.nix Configuration
echo "Test 2: Check home.nix configuration"
echo "----------------------------------------------------------------------"
HM_CONFIG="${HOME}/.dotfiles/home-manager/home.nix"
if [[ -f "$HM_CONFIG" ]]; then
    print_success "home.nix found"

    if grep -q "localAiStackEnabled = true" "$HM_CONFIG"; then
        print_success "localAiStackEnabled = true (user services enabled)"
        USER_SERVICES_ENABLED=true
    else
        print_info "localAiStackEnabled = false or not set"
        USER_SERVICES_ENABLED=false
    fi
else
    print_error "home.nix not found at $HM_CONFIG"
    USER_SERVICES_ENABLED=false
fi
echo ""

# Test 3: Check Port Usage
echo "Test 3: Check port usage for AI services"
echo "----------------------------------------------------------------------"
CONFLICT_FOUND=false
for port in 6333 6334 11434; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || ss -tlnp 2>/dev/null | grep -q ":${port}\$"; then
        print_warning "Port $port is in use"
        ss -tlnp 2>/dev/null | grep ":${port}" | head -1 | sed 's/^/  /'
        CONFLICT_FOUND=true
    else
        print_info "Port $port is available"
    fi
done
echo ""

# Test 4: Detect Conflicts
echo "Test 4: Conflict detection"
echo "----------------------------------------------------------------------"
CONFLICTS=0

# Check ollama conflict
if [[ "${SYSTEM_STATUS[ollama.service]}" == "active" && "$USER_SERVICES_ENABLED" == "true" ]]; then
    print_warning "Conflict: ollama.service (system) vs podman-local-ai-ollama.service (user)"
    ((CONFLICTS++))
fi

# Check qdrant conflict
if [[ "${SYSTEM_STATUS[qdrant.service]}" == "active" && "$USER_SERVICES_ENABLED" == "true" ]]; then
    print_warning "Conflict: qdrant.service (system) vs podman-local-ai-qdrant.service (user)"
    ((CONFLICTS++))
fi

if (( CONFLICTS == 0 )); then
    print_success "No conflicts detected"
else
    print_warning "Found $CONFLICTS conflict(s)"
fi
echo ""

# Test 5: Test Masking (if conflicts exist)
if (( CONFLICTS > 0 )); then
    echo "Test 5: Test service masking capability"
    echo "----------------------------------------------------------------------"
    if [[ "$SUDO_AVAILABLE" == "true" ]]; then
        print_info "Testing if masking works on this system..."
        # Test with a dummy service name (won't actually mask anything)
        if run_sudo systemctl mask --dry-run ollama.service &>/dev/null; then
            print_success "systemctl mask command is available (NixOS compatible)"
        else
            print_warning "systemctl mask may have limitations"
        fi
    else
        print_warning "Skipping mask dry-run (sudo not available without a password)"
    fi
    echo ""
fi

# Summary
echo "======================================================================"
echo "Test Summary"
echo "======================================================================"
echo ""
echo "System Services:"
if [[ "$SUDO_AVAILABLE" == "true" ]]; then
    run_sudo systemctl status ollama.service --no-pager 2>&1 | head -3 | sed 's/^/  /' || true
    echo ""
    run_sudo systemctl status qdrant.service --no-pager 2>&1 | head -3 | sed 's/^/  /' || true
    echo ""
else
    echo "  sudo not available; skipped detailed systemd status"
    echo ""
fi

echo "User Services Configuration:"
if [[ "$USER_SERVICES_ENABLED" == "true" ]]; then
    echo "  localAiStackEnabled = true in home.nix"
    echo "  User-level AI stack will be deployed"
else
    echo "  localAiStackEnabled = false or not configured"
    echo "  User-level AI stack will NOT be deployed"
fi
echo ""

if (( CONFLICTS > 0 )); then
    echo "⚠ Conflicts Detected: $CONFLICTS"
    echo ""
    echo "Resolution Options:"
    echo "  1. Automatic (via deployment script):"
    echo "     ./nixos-quick-deploy.sh"
    echo "     (will mask system services automatically)"
    echo ""
    echo "  2. Manual masking:"
    echo "     sudo systemctl stop ollama.service qdrant.service"
    echo "     sudo systemctl mask ollama.service qdrant.service"
    echo ""
    echo "  3. Permanent fix (edit /etc/nixos/configuration.nix):"
    echo "     services.ollama.enable = false;"
    echo "     services.qdrant.enable = false;"
    echo "     Then: sudo nixos-rebuild switch"
    echo ""
else
    echo "✓ No conflicts - Ready for deployment"
    echo ""
fi

echo "======================================================================"
echo "Test Complete"
echo "======================================================================"
