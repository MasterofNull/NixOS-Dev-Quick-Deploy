#!/usr/bin/env bash
# Verification script for flatpak-managed-install timeout fix

set -euo pipefail

echo "=== Flatpak Service Timeout Fix Verification ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_check() {
    echo -e "${BLUE}[CHECK]${NC} $*"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $*"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $*"
}

# Check 1: Verify X-SwitchMethod is in the new config
print_check "Checking if X-SwitchMethod is in templates/home.nix..."
if grep -q "X-SwitchMethod.*keep-old" templates/home.nix; then
    print_pass "X-SwitchMethod = \"keep-old\" found in templates/home.nix"
    grep -A2 -B2 "X-SwitchMethod" templates/home.nix | sed 's/^/  /'
else
    print_fail "X-SwitchMethod not found in templates/home.nix"
fi
echo ""

# Check 2: Verify cleanup function removes condition file
print_check "Checking if cleanup function removes condition file..."
if grep -q "rm -f.*allow-flatpak-managed-install" nixos-quick-deploy.sh; then
    print_pass "Cleanup removes condition file"
    grep -B2 -A2 "rm -f.*allow-flatpak-managed-install" nixos-quick-deploy.sh | head -10 | sed 's/^/  /'
else
    print_fail "Cleanup doesn't remove condition file"
fi
echo ""

# Check 3: Verify cleanup function masks service
print_check "Checking if cleanup function masks the service..."
if grep -q "systemctl --user mask.*flatpak-managed-install" nixos-quick-deploy.sh; then
    print_pass "Cleanup masks the service"
    grep -B1 -A1 "systemctl --user mask.*flatpak-managed-install" nixos-quick-deploy.sh | sed 's/^/  /'
else
    print_fail "Cleanup doesn't mask the service"
fi
echo ""

# Check 4: Verify ensure function unmasks service
print_check "Checking if ensure function unmasks the service..."
if grep -q "systemctl --user unmask.*flatpak-managed-install" nixos-quick-deploy.sh; then
    print_pass "Ensure function unmasks the service"
    grep -B1 -A1 "systemctl --user unmask.*flatpak-managed-install" nixos-quick-deploy.sh | sed 's/^/  /'
else
    print_fail "Ensure function doesn't unmask the service"
fi
echo ""

# Check 5: Current service status
print_check "Checking current service status..."
if systemctl --user list-unit-files flatpak-managed-install.service &>/dev/null; then
    print_info "Service exists in current system"

    # Check if masked
    if systemctl --user is-enabled flatpak-managed-install.service 2>&1 | grep -q "masked"; then
        print_info "Service is currently MASKED (this is normal during activation)"
    else
        print_info "Service is NOT masked (this is normal after activation completes)"
    fi

    # Check service state
    STATE=$(systemctl --user is-active flatpak-managed-install.service 2>/dev/null || echo "inactive")
    print_info "Service state: $STATE"

    # Check if it has X-SwitchMethod in current deployment
    if systemctl --user show flatpak-managed-install.service 2>/dev/null | grep -q "X-SwitchMethod"; then
        print_pass "Service has X-SwitchMethod in current deployment"
    else
        print_info "Service doesn't have X-SwitchMethod yet (will be added on next home-manager switch)"
    fi
else
    print_info "Service not yet deployed to user systemd"
fi
echo ""

# Check 6: Condition file status
print_check "Checking condition file status..."
CONDITION_FILE="/run/user/$(id -u)/allow-flatpak-managed-install"
if [[ -f "$CONDITION_FILE" ]]; then
    print_info "Condition file EXISTS (service is allowed to run)"
else
    print_info "Condition file MISSING (service won't run - normal during activation)"
fi
echo ""

# Check 7: Git commits
print_check "Checking git commits on current branch..."
CURRENT_BRANCH=$(git branch --show-current)
print_info "Current branch: $CURRENT_BRANCH"

if git log --oneline -5 | grep -q "X-SwitchMethod"; then
    print_pass "Found commit with X-SwitchMethod fix"
    git log --oneline -5 | grep "X-SwitchMethod" | sed 's/^/  /'
fi

if git log --oneline -5 | grep -q "masking"; then
    print_pass "Found commit with masking fix"
    git log --oneline -5 | grep "masking" | sed 's/^/  /'
fi
echo ""

# Summary
echo "=== VERIFICATION SUMMARY ==="
echo ""
echo "To test the complete fix:"
echo ""
echo "1. Before running home-manager switch, check:"
echo "   systemctl --user is-enabled flatpak-managed-install.service"
echo "   ls -la $CONDITION_FILE"
echo ""
echo "2. During deployment, the script should show:"
echo "   - 'Removing flatpak condition file to prevent activation...'"
echo "   - 'Temporarily masking flatpak-managed-install.service...'"
echo "   - 'Services cleaned up and masked - safe to run home-manager switch'"
echo ""
echo "3. home-manager switch should complete WITHOUT the error:"
echo "   'timed out waiting on channel'"
echo ""
echo "4. After home-manager switch succeeds, it should show:"
echo "   - 'Unmasking flatpak-managed-install.service...'"
echo "   - Service should start normally"
echo ""
echo "5. Verify final state:"
echo "   systemctl --user is-enabled flatpak-managed-install.service  # Should NOT be masked"
echo "   systemctl --user status flatpak-managed-install.service"
echo "   ls -la $CONDITION_FILE  # Should exist if service ran"
echo ""
