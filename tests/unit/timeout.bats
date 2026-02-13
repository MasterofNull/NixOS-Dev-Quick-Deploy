#!/usr/bin/env bats
#
# Unit tests for lib/timeout.sh
#

load test_helper

setup() {
    source "$LIB_DIR/timeout.sh"
}

# ============================================================================
# run_with_timeout
# ============================================================================

@test "run_with_timeout: completes fast command successfully" {
    run run_with_timeout 10 echo "hello"
    [[ "$status" -eq 0 ]]
    [[ "$output" == "hello" ]]
}

@test "run_with_timeout: times out slow command with exit 124" {
    run run_with_timeout 1 sleep 30
    [[ "$status" -eq 124 ]]
}

@test "run_with_timeout: passes through command exit code" {
    run run_with_timeout 10 bash -c 'exit 42'
    [[ "$status" -eq 42 ]]
}

# ============================================================================
# Default timeout variables
# ============================================================================

@test "KUBECTL_TIMEOUT has a default value" {
    [[ -n "$KUBECTL_TIMEOUT" ]]
    [[ "$KUBECTL_TIMEOUT" -gt 0 ]]
}

@test "CURL_TIMEOUT has a default value" {
    [[ -n "$CURL_TIMEOUT" ]]
    [[ "$CURL_TIMEOUT" -gt 0 ]]
}

@test "NIXOS_REBUILD_TIMEOUT has a default value" {
    [[ -n "$NIXOS_REBUILD_TIMEOUT" ]]
    [[ "$NIXOS_REBUILD_TIMEOUT" -gt 0 ]]
}

@test "HOME_MANAGER_TIMEOUT has a default value" {
    [[ -n "$HOME_MANAGER_TIMEOUT" ]]
    [[ "$HOME_MANAGER_TIMEOUT" -gt 0 ]]
}

# ============================================================================
# curl_safe (stub test - curl may not be in test env)
# ============================================================================

@test "curl_safe: returns error code when curl missing" {
    if command -v curl >/dev/null 2>&1; then
        skip "curl is available, cannot test missing-command path"
    fi
    run curl_safe --version
    [[ "$status" -ne 0 ]]
}

# ============================================================================
# kubectl_safe (stub test - kubectl may not be in test env)
# ============================================================================

@test "kubectl_safe: returns error code when kubectl missing" {
    if command -v kubectl >/dev/null 2>&1; then
        skip "kubectl is available, cannot test missing-command path"
    fi
    run kubectl_safe version
    [[ "$status" -ne 0 ]]
}
