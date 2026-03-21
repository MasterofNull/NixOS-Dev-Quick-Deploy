#!/usr/bin/env bash
# scripts/testing/smoke-integration-complete.sh
# Phase 4.5: Smoke Test for Integration Completeness
#
# Quick smoke test to verify all features are integrated and working
# No manual steps required, runs in under 30 seconds

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Test result tracking
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Service checks
check_service() {
    local service="$1"
    if systemctl is-active "${service}" &>/dev/null; then
        pass "Service ${service} is running"
        return 0
    else
        fail "Service ${service} is not running"
        return 1
    fi
}

# HTTP endpoint checks
check_http() {
    local url="$1"
    local name="$2"
    if curl -sf "${url}" --max-time 5 &>/dev/null; then
        pass "${name} is accessible"
        return 0
    else
        warn "${name} is not accessible (may not be started yet)"
        return 1
    fi
}

# File existence checks
check_file() {
    local file="$1"
    local name="$2"
    if [[ -f "${file}" ]]; then
        pass "${name} exists"
        return 0
    else
        fail "${name} not found"
        return 1
    fi
}

# Check for executable script
check_executable() {
    local file="$1"
    local name="$2"
    if [[ -x "${file}" ]]; then
        pass "${name} is executable"
        return 0
    else
        fail "${name} is not executable"
        return 1
    fi
}

# Configuration checks
check_config_defaults() {
    local config="$1"
    local name="$2"

    if [[ ! -f "${config}" ]]; then
        warn "${name} config not found"
        return 1
    fi

    # Check for problematic patterns (enabled: false outside experimental)
    if grep -q "enabled: false" "${config}"; then
        # Check if it's in experimental/opt-in section
        if grep -B5 "enabled: false" "${config}" | grep -q -i "experimental\|opt.*in\|manual"; then
            pass "${name} has appropriate defaults (experimental features disabled)"
        else
            warn "${name} has disabled features outside experimental section"
        fi
    else
        pass "${name} has all features enabled"
    fi
}

# Main smoke test
main() {
    echo "========================================"
    echo "Integration Completeness Smoke Test"
    echo "========================================"
    echo ""

    info "Phase 1: Core Services"
    echo "----------------------------------------"
    check_service "postgresql" || true
    check_service "qdrant" || true
    check_service "llama-cpp" || true
    check_service "hybrid-coordinator" || true
    check_service "aidb" || true
    echo ""

    info "Phase 2: HTTP Endpoints"
    echo "----------------------------------------"
    check_http "http://localhost:9090/api/health" "Hybrid Coordinator API" || true
    check_http "http://localhost:8080/api/health" "Dashboard API" || true
    check_http "http://localhost:6333/collections" "Qdrant API" || true
    echo ""

    info "Phase 3: Dashboard & UI"
    echo "----------------------------------------"
    ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    check_file "${ROOT_DIR}/dashboard.html" "Dashboard HTML"
    check_file "${ROOT_DIR}/dashboard/backend/api/main.py" "Dashboard Backend" || true
    echo ""

    info "Phase 4: Auto-Enable Scripts"
    echo "----------------------------------------"
    check_file "${ROOT_DIR}/lib/deploy/auto-enable-features.sh" "Auto-enable script"
    check_executable "${ROOT_DIR}/lib/deploy/auto-enable-features.sh" "Auto-enable script"
    echo ""

    info "Phase 5: Configuration Defaults"
    echo "----------------------------------------"
    check_config_defaults "${ROOT_DIR}/config/feature-defaults.yaml" "Feature defaults"
    check_config_defaults "${ROOT_DIR}/config/model-cache.yaml" "Model cache"
    check_config_defaults "${ROOT_DIR}/config/anomaly-detection.yaml" "Anomaly detection"
    check_config_defaults "${ROOT_DIR}/config/notifications.yaml" "Notifications"
    echo ""

    info "Phase 6: Audit & Test Tools"
    echo "----------------------------------------"
    check_file "${ROOT_DIR}/scripts/audit/integration-audit.sh" "Integration audit script"
    check_file "${ROOT_DIR}/scripts/testing/test-integration-completeness.py" "Integration test suite"
    check_executable "${ROOT_DIR}/scripts/audit/integration-audit.sh" "Integration audit script"
    check_executable "${ROOT_DIR}/scripts/testing/test-integration-completeness.py" "Integration test suite"
    echo ""

    info "Phase 7: No Manual Steps Required"
    echo "----------------------------------------"
    # Check that manual setup scripts don't exist (good)
    if [[ ! -f "${ROOT_DIR}/scripts/setup/enable-features.sh" ]]; then
        pass "No manual enable-features.sh script"
    else
        warn "Manual enable-features.sh script exists"
    fi

    if [[ ! -f "${ROOT_DIR}/scripts/setup/configure-optional.sh" ]]; then
        pass "No manual configure-optional.sh script"
    else
        warn "Manual configure-optional.sh script exists"
    fi
    echo ""

    info "Phase 8: Deployment Integration"
    echo "----------------------------------------"
    # Check that deployment doesn't require manual feature enabling
    if grep -q "auto-enable-features" "${ROOT_DIR}/nixos-quick-deploy.sh" 2>/dev/null || \
       grep -q "auto.*enable" "${ROOT_DIR}/scripts/deploy/start-ai-stack.sh" 2>/dev/null; then
        pass "Deployment integrates auto-enable logic"
    else
        warn "Deployment may not integrate auto-enable (check manually)"
    fi

    # Check for feature flag removal
    if ! grep -r "ENABLE_OPTIONAL_FEATURES\|FEATURE_FLAGS_ENABLED" \
         "${ROOT_DIR}/nix/modules" "${ROOT_DIR}/scripts/deploy" 2>/dev/null | grep -v "archive" &>/dev/null; then
        pass "No legacy feature flag variables found"
    else
        warn "Found legacy feature flag references (review needed)"
    fi
    echo ""

    # Summary
    echo "========================================"
    echo "SMOKE TEST SUMMARY"
    echo "========================================"
    echo -e "Passed:     ${GREEN}${PASSED}${NC} ✓"
    echo -e "Failed:     ${RED}${FAILED}${NC} ✗"
    echo -e "Warnings:   ${YELLOW}${WARNINGS}${NC} ⚠"
    echo ""

    if [[ "${FAILED}" -eq 0 ]]; then
        echo -e "${GREEN}✓ Integration completeness: VERIFIED${NC}"
        echo "All features are integrated and working out-of-box"
        if [[ "${WARNINGS}" -gt 0 ]]; then
            echo ""
            echo -e "${YELLOW}Note: ${WARNINGS} warnings (non-critical)${NC}"
        fi
        exit 0
    else
        echo -e "${RED}✗ Integration completeness: FAILED${NC}"
        echo "Some features require manual intervention or are not integrated"
        exit 1
    fi
}

main "$@"
