#!/usr/bin/env bash
#
# PyTorch Download Fix Verification Script
# Purpose: Verify that the PyTorch download hang fixes are working correctly
#

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PyTorch Download Fix Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

pass_count=0
fail_count=0

check() {
    local description="$1"
    local test_result="$2"

    if [ "$test_result" = "0" ]; then
        echo -e "${GREEN}✓${NC} $description"
        ((pass_count++))
        return 0
    else
        echo -e "${RED}✗${NC} $description"
        ((fail_count++))
        return 1
    fi
}

info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

error() {
    echo -e "${RED}✗${NC} $*"
}

success() {
    echo -e "${GREEN}✓${NC} $*"
}

echo "Checking modified files..."
echo ""

# Check 1: Verify requirements.txt has the correct PyTorch version
if grep -q "torch==2.5.1+cpu" "$PROJECT_ROOT/ai-stack/mcp-servers/aidb/requirements.txt"; then
    check "PyTorch version updated to 2.5.1+cpu" 0
else
    check "PyTorch version updated to 2.5.1+cpu" 1
    warn "  Expected: torch==2.5.1+cpu"
    warn "  Found: $(grep "^torch==" "$PROJECT_ROOT/ai-stack/mcp-servers/aidb/requirements.txt" || echo "NOT FOUND")"
fi

# Check 2: Verify deploy-aidb-mcp-server.sh has timeout configuration
if grep -q "PIP_DEFAULT_TIMEOUT=300" "$PROJECT_ROOT/scripts/deploy-aidb-mcp-server.sh"; then
    check "deploy-aidb-mcp-server.sh has PIP_DEFAULT_TIMEOUT" 0
else
    check "deploy-aidb-mcp-server.sh has PIP_DEFAULT_TIMEOUT" 1
fi

if grep -q -- "--timeout 300" "$PROJECT_ROOT/scripts/deploy-aidb-mcp-server.sh"; then
    check "deploy-aidb-mcp-server.sh has --timeout flag" 0
else
    check "deploy-aidb-mcp-server.sh has --timeout flag" 1
fi

# Check 3: Verify setup-hybrid-learning-auto.sh has timeout configuration
if grep -q "PIP_DEFAULT_TIMEOUT=300" "$PROJECT_ROOT/scripts/setup-hybrid-learning-auto.sh"; then
    check "setup-hybrid-learning-auto.sh has timeout configuration" 0
else
    check "setup-hybrid-learning-auto.sh has timeout configuration" 1
fi

# Check 4: Verify setup-hybrid-learning.sh has timeout configuration
if grep -q "PIP_DEFAULT_TIMEOUT=300" "$PROJECT_ROOT/scripts/setup-hybrid-learning.sh"; then
    check "setup-hybrid-learning.sh has timeout configuration" 0
else
    check "setup-hybrid-learning.sh has timeout configuration" 1
fi

# Check 5: Verify dashboard/start-dashboard.sh has timeout configuration
if grep -q "PIP_DEFAULT_TIMEOUT=300" "$PROJECT_ROOT/dashboard/start-dashboard.sh"; then
    check "dashboard/start-dashboard.sh has timeout configuration" 0
else
    check "dashboard/start-dashboard.sh has timeout configuration" 1
fi

# Check 6: Verify download-llama-cpp-models.sh has timeout
if grep -q "timeout 1800 python3" "$PROJECT_ROOT/scripts/download-llama-cpp-models.sh"; then
    check "download-llama-cpp-models.sh has model download timeout" 0
else
    check "download-llama-cpp-models.sh has model download timeout" 1
fi

echo ""
echo "Testing network connectivity..."
echo ""

# Check 7: Test PyPI connectivity
if timeout 10 curl -sI https://pypi.org >/dev/null 2>&1; then
    check "PyPI connectivity" 0
else
    check "PyPI connectivity" 1
    warn "  Cannot reach PyPI - downloads may fail"
fi

# Check 8: Test PyTorch CDN connectivity
if timeout 10 curl -sI https://download.pytorch.org >/dev/null 2>&1; then
    check "PyTorch CDN connectivity" 0
else
    check "PyTorch CDN connectivity" 1
    warn "  Cannot reach PyTorch CDN - downloads may be slower"
fi

# Check 9: Test if PyTorch 2.5.1+cpu is available
info "Checking if PyTorch 2.5.1+cpu is available (this may take a moment)..."
if timeout 30 python3 -m pip index versions torch --index-url https://download.pytorch.org/whl/cpu 2>/dev/null | grep -q "2.5.1+cpu"; then
    check "PyTorch 2.5.1+cpu is available in index" 0
else
    check "PyTorch 2.5.1+cpu is available in index" 1
    warn "  May need to check PyTorch repository status"
fi

# Check 10: Verify Python and pip are available
if command -v python3 >/dev/null 2>&1; then
    check "Python3 is available" 0
    info "  Python version: $(python3 --version)"
else
    check "Python3 is available" 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Verification Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Passed: ${pass_count}"
echo "  Failed: ${fail_count}"
echo ""

if [ $fail_count -eq 0 ]; then
    success "All verification checks passed!"
    echo ""
    echo "  The PyTorch download hang fixes are properly applied."
    echo "  You can now run the deployment script:"
    echo ""
    echo "    ./nixos-quick-deploy.sh"
    echo ""
    exit 0
else
    error "Some verification checks failed!"
    echo ""
    echo "  Please review the failed checks above and ensure all fixes are applied."
    echo "  See PYTORCH-DOWNLOAD-FIX-2025-12-31.md for details."
    echo ""
    exit 1
fi
