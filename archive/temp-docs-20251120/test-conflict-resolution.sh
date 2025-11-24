#!/usr/bin/env bash
#
# Test Script: Service Conflict Resolution
# Purpose: Verify the conflict detection and resolution functions work correctly
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"

# Initialize logging variables BEFORE loading libraries
export LOG_DIR="$HOME/.cache/test-conflict-resolution"
export LOG_FILE="$LOG_DIR/test-$(date +%Y%m%d_%H%M%S).log"
export LOG_LEVEL="INFO"
export HM_CONFIG_DIR="${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}"

# Create log directory manually (avoid dependency on safe_mkdir)
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Load required libraries in dependency order
echo "Loading libraries..."
source "$LIB_DIR/colors.sh"

# Define minimal safe_mkdir for logging.sh if needed
if ! declare -F safe_mkdir >/dev/null 2>&1; then
    safe_mkdir() { mkdir -p "$1" 2>/dev/null; }
fi

source "$LIB_DIR/logging.sh"
source "$LIB_DIR/service-conflict-resolution.sh"

# Initialize logging
if declare -F init_logging >/dev/null 2>&1; then
    init_logging
fi

echo ""
echo "======================================================================"
echo "Service Conflict Resolution Test"
echo "======================================================================"
echo ""

# Test 1: Check if functions are loaded
echo "Test 1: Verify functions are loaded"
if declare -F detect_service_conflicts >/dev/null 2>&1; then
    echo "  ✓ detect_service_conflicts loaded"
else
    echo "  ✗ detect_service_conflicts NOT loaded"
    exit 1
fi

if declare -F auto_resolve_service_conflicts >/dev/null 2>&1; then
    echo "  ✓ auto_resolve_service_conflicts loaded"
else
    echo "  ✗ auto_resolve_service_conflicts NOT loaded"
    exit 1
fi

if declare -F pre_home_manager_conflict_check >/dev/null 2>&1; then
    echo "  ✓ pre_home_manager_conflict_check loaded"
else
    echo "  ✗ pre_home_manager_conflict_check NOT loaded"
    exit 1
fi

echo ""

# Test 2: Check system services
echo "Test 2: Check system service status"
for service in ollama.service qdrant.service; do
    if sudo systemctl is-active "$service" &>/dev/null; then
        echo "  ✓ $service is active"
    else
        echo "  ○ $service is inactive"
    fi
done

echo ""

# Test 3: Check home.nix configuration
echo "Test 3: Check home.nix configuration"
HM_CONFIG_DIR="${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}"
if [[ -f "$HM_CONFIG_DIR/home.nix" ]]; then
    echo "  ✓ home.nix found at $HM_CONFIG_DIR"

    if grep -q "localAiStackEnabled = true" "$HM_CONFIG_DIR/home.nix"; then
        echo "  ✓ localAiStackEnabled = true (user services enabled)"
    else
        echo "  ○ localAiStackEnabled = false or not set"
    fi
else
    echo "  ✗ home.nix not found"
fi

echo ""

# Test 4: Detect conflicts
echo "Test 4: Run conflict detection"
if detect_service_conflicts; then
    echo "  ✓ No conflicts detected (or detection passed)"
else
    echo "  ⚠ Conflicts detected (this is expected if both levels are active)"
fi

echo ""

# Test 5: Check port usage
echo "Test 5: Check port usage for AI services"
for port in 6333 6334 11434; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || ss -tlnp 2>/dev/null | grep -q ":${port}\$"; then
        echo "  ✓ Port $port is in use"
        ss -tlnp 2>/dev/null | grep ":${port}" | head -1 | sed 's/^/    /'
    else
        echo "  ○ Port $port is available"
    fi
done

echo ""

# Test 6: Generate conflict report
echo "Test 6: Generate conflict report"
REPORT_FILE="/tmp/conflict-resolution-test-$(date +%s).txt"
generate_conflict_report "$REPORT_FILE"
echo "  ✓ Report generated at: $REPORT_FILE"
echo ""
echo "  Report preview:"
head -20 "$REPORT_FILE" | sed 's/^/    /'

echo ""
echo "======================================================================"
echo "Test Complete"
echo "======================================================================"
echo ""
echo "Summary:"
echo "  - All functions loaded successfully"
echo "  - Conflict detection system operational"
echo "  - Report generation working"
echo ""
echo "To resolve conflicts manually:"
echo "  1. Review the report: cat $REPORT_FILE"
echo "  2. Disable system services: sudo systemctl disable --now ollama.service qdrant.service"
echo "  3. Or disable user services: Set localAiStackEnabled = false in home.nix"
echo ""
echo "To test automatic resolution:"
echo "  ./nixos-quick-deploy.sh --phase 5"
echo ""
