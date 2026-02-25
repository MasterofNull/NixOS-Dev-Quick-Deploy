#!/usr/bin/env bash
# Test: API Key Security Vulnerabilities
# Validates: API key storage, permissions, and handling

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TMP_ROOT="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test configuration
API_KEY_FILE="${PROJECT_ROOT}/ai-stack/secrets/generated/stack_api_key"
TEST_LOG="${TMP_ROOT}/chaos-test-api-key-security-$$.log"

ERRORS=0

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$TEST_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$TEST_LOG"
    ERRORS=$((ERRORS + 1))
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$TEST_LOG"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$TEST_LOG"
}

# Test 1: API key file permissions
test_file_permissions() {
    log "\n=== Test 1: API Key File Permissions ==="

    if [ ! -f "$API_KEY_FILE" ]; then
        error "API key file not found: $API_KEY_FILE"
        return 1
    fi

    # Check file permissions
    local perms
    perms=$(stat -c %a "$API_KEY_FILE" 2>/dev/null || stat -f %Lp "$API_KEY_FILE" 2>/dev/null)

    log "API key file permissions: $perms"

    # Critical: Should be 0400 (read-only by owner) or 0600 (read-write by owner)
    # NEVER 0444 (world-readable) or 0644 (world-readable)
    if [ "$perms" = "444" ] || [ "$perms" = "644" ]; then
        error "🚨 CRITICAL SECURITY VULNERABILITY!"
        error "API key file is world-readable (mode $perms)"
        error "ANY process on this system can read the API key!"
        error ""
        error "Attack scenario:"
        error "  1. Malicious user runs: cat $API_KEY_FILE"
        error "  2. Gets full API access"
        error "  3. Can query/modify all data"
        error ""
        error "Fix: chmod 400 $API_KEY_FILE"
        return 1
    elif [ "$perms" = "400" ] || [ "$perms" = "600" ]; then
        success "✓ API key permissions are secure ($perms)"
        return 0
    else
        warn "Unusual permissions: $perms"
        warn "Recommended: 400 (read-only by owner)"
        return 0
    fi
}

# Test 2: API key content validation
test_key_content() {
    log "\n=== Test 2: API Key Content Validation ==="

    local api_key
    if ! api_key=$(cat "$API_KEY_FILE" 2>/dev/null); then
        error "Cannot read API key file"
        return 1
    fi

    # Check if empty
    if [ -z "$api_key" ]; then
        error "API key is empty"
        return 1
    fi

    # Check for whitespace issues
    if [[ "$api_key" =~ ^[[:space:]] ]] || [[ "$api_key" =~ [[:space:]]$ ]]; then
        error "API key has leading/trailing whitespace"
        error "This will cause authentication failures"
        return 1
    fi

    # Check for newlines
    if [[ "$api_key" =~ $'\n' ]]; then
        error "API key contains newlines"
        error "This will cause authentication failures"
        return 1
    fi

    # Check key strength (should be at least 32 chars)
    if [ ${#api_key} -lt 32 ]; then
        warn "API key is weak (${#api_key} chars < 32 recommended)"
        warn "Consider regenerating with stronger key"
    fi

    success "✓ API key content is valid"
    return 0
}

# Test 3: Docker secrets configuration
test_k8s_secrets_config() {
    log "\n=== Test 3: Kubernetes Secrets Configuration ==="

    local secrets_file="${PROJECT_ROOT}/ai-stack/secrets/secrets.sops.yaml"

    if [ ! -f "$secrets_file" ]; then
        error "Kubernetes secrets file not found: $secrets_file"
        return 1
    fi

    # Ensure key names are present
    if ! rg -q "stack_api_key" "$secrets_file"; then
        error "Missing stack_api_key in sops secrets file"
        return 1
    fi

    success "✓ Kubernetes secrets configuration present"
    return 0
}

# Test 4: Key rotation capability
test_key_rotation() {
    log "\n=== Test 4: Key Rotation Capability ==="

    # Check if there's a key rotation script
    local rotation_script="${PROJECT_ROOT}/scripts/rotate-api-key.sh"

    if [ ! -f "$rotation_script" ]; then
        error "No API key rotation script found"
        error "Key rotation is MANUAL and will be forgotten"
        error ""
        error "Impact:"
        error "  - Same key used forever"
        error "  - If key leaks, no way to revoke"
        error "  - No audit trail of key changes"
        error ""
        error "Recommendation: Create ${rotation_script}"
        return 1
    fi

    success "✓ Key rotation script exists"
    return 0
}

# Test 5: Per-service key isolation
test_service_isolation() {
    log "\n=== Test 5: Per-Service Key Isolation ==="

    # Check if different services use different keys
    local secret_files
    secret_files=$(rg -l "api_key" "${PROJECT_ROOT}/ai-stack/secrets/secrets.sops.yaml" 2>/dev/null | wc -l)

    log "Found $secret_files API key files"

    if [ "$secret_files" -eq 1 ]; then
        error "Single API key shared across ALL services"
        error ""
        error "Security Impact:"
        error "  - If one service is compromised, ALL services compromised"
        error "  - Cannot revoke access to specific service"
        error "  - No audit trail per service"
        error "  - Violates principle of least privilege"
        error ""
        error "Recommendation: Use per-service API keys"
        error "  - aidb_api_key"
        error "  - embeddings_api_key"
        error "  - hybrid_api_key"
        return 1
    fi

    success "✓ Per-service key isolation implemented"
    return 0
}

# Test 6: API key in environment variables
test_env_var_exposure() {
    log "\n=== Test 6: Environment Variable Exposure ==="

    local configmap_file="${PROJECT_ROOT}/ai-stack/kompose/env-configmap.yaml"

    if [ -f "$configmap_file" ] && rg -q "API_KEY|STACK_API_KEY" "$configmap_file"; then
        error "🚨 API key exposed via configmap"
        error "Recommendation: Use Kubernetes secrets or _FILE suffix"
        return 1
    fi

    success "✓ API key not exposed via configmap"
    return 0
}

# Generate report
generate_report() {
    log "\n=== API Key Security Test Report ==="

    if [ $ERRORS -eq 0 ]; then
        success "\n✅ ALL API KEY SECURITY TESTS PASSED!"
        success "API key storage and handling is secure."
    else
        error "\n❌ API KEY SECURITY TESTS FAILED!"
        error "$ERRORS critical security vulnerability(ies) found."
        error ""
        error "🚨 THESE ARE PRODUCTION BLOCKERS!"
        error "Fix ALL issues before deploying to production."
    fi

    log "\nFull log: $TEST_LOG"
}

# Main execution
main() {
    log "=== API Key Security Torture Test ==="
    log "Testing for common API key vulnerabilities"
    log ""

    test_file_permissions || true
    test_key_content || true
    test_k8s_secrets_config || true
    test_key_rotation || true
    test_service_isolation || true
    test_env_var_exposure || true

    generate_report

    if [ $ERRORS -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
