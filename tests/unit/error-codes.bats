#!/usr/bin/env bats
#
# Unit tests for lib/error-codes.sh
#

load test_helper

setup() {
    source "$LIB_DIR/error-codes.sh"
}

# ============================================================================
# Error code constants
# ============================================================================

@test "ERR_SUCCESS is 0" {
    [[ "$ERR_SUCCESS" -eq 0 ]]
}

@test "ERR_GENERIC is 1" {
    [[ "$ERR_GENERIC" -eq 1 ]]
}

@test "ERR_NETWORK is 10" {
    [[ "$ERR_NETWORK" -eq 10 ]]
}

@test "ERR_NIXOS_REBUILD is 40" {
    [[ "$ERR_NIXOS_REBUILD" -eq 40 ]]
}

@test "ERR_K3S_DEPLOY is 50" {
    [[ "$ERR_K3S_DEPLOY" -eq 50 ]]
}

@test "ERR_SECRET_DECRYPT is 60" {
    [[ "$ERR_SECRET_DECRYPT" -eq 60 ]]
}

@test "ERR_TIMEOUT is 70" {
    [[ "$ERR_TIMEOUT" -eq 70 ]]
}

@test "ERR_USER_ABORT is 80" {
    [[ "$ERR_USER_ABORT" -eq 80 ]]
}

@test "ERR_BACKUP_FAILED is 90" {
    [[ "$ERR_BACKUP_FAILED" -eq 90 ]]
}

# ============================================================================
# error_code_name function
# ============================================================================

@test "error_code_name maps 0 to SUCCESS" {
    result=$(error_code_name 0)
    [[ "$result" == "SUCCESS" ]]
}

@test "error_code_name maps 10 to NETWORK_ERROR" {
    result=$(error_code_name 10)
    [[ "$result" == "NETWORK_ERROR" ]]
}

@test "error_code_name maps 40 to NIXOS_REBUILD_FAILED" {
    result=$(error_code_name 40)
    [[ "$result" == "NIXOS_REBUILD_FAILED" ]]
}

@test "error_code_name maps 71 to TIMEOUT_KUBECTL" {
    result=$(error_code_name 71)
    [[ "$result" == "TIMEOUT_KUBECTL" ]]
}

@test "error_code_name maps unknown code to UNKNOWN_ERROR(code)" {
    result=$(error_code_name 255)
    [[ "$result" == "UNKNOWN_ERROR(255)" ]]
}

# ============================================================================
# No collisions between error code ranges
# ============================================================================

@test "all error codes are unique" {
    local codes=(
        "$ERR_SUCCESS" "$ERR_GENERIC"
        "$ERR_NETWORK" "$ERR_DISK_SPACE" "$ERR_PERMISSION" "$ERR_NOT_NIXOS"
        "$ERR_RUNNING_AS_ROOT" "$ERR_MISSING_COMMAND"
        "$ERR_DEPENDENCY" "$ERR_PACKAGE_INSTALL" "$ERR_PACKAGE_REMOVE"
        "$ERR_CHANNEL_UPDATE" "$ERR_PROFILE_CONFLICT"
        "$ERR_CONFIG_INVALID" "$ERR_CONFIG_GENERATION"
        "$ERR_TEMPLATE_SUBSTITUTION" "$ERR_CONFIG_PATH_CONFLICT"
        "$ERR_NIXOS_REBUILD" "$ERR_HOME_MANAGER" "$ERR_FLAKE_LOCK" "$ERR_SYSTEM_SWITCH"
        "$ERR_K3S_DEPLOY" "$ERR_K3S_NOT_RUNNING" "$ERR_K3S_NAMESPACE"
        "$ERR_K3S_MANIFEST" "$ERR_IMAGE_BUILD" "$ERR_IMAGE_IMPORT"
        "$ERR_SECRET_DECRYPT" "$ERR_SECRET_MISSING" "$ERR_SECRET_INVALID" "$ERR_AGE_KEY_MISSING"
        "$ERR_TIMEOUT" "$ERR_TIMEOUT_KUBECTL" "$ERR_TIMEOUT_REBUILD" "$ERR_TIMEOUT_NETWORK"
        "$ERR_USER_ABORT" "$ERR_INVALID_INPUT"
        "$ERR_BACKUP_FAILED" "$ERR_ROLLBACK_FAILED" "$ERR_BACKUP_DIR"
    )

    local seen=()
    for code in "${codes[@]}"; do
        for s in "${seen[@]}"; do
            if [[ "$s" == "$code" ]]; then
                echo "Duplicate error code: $code" >&2
                return 1
            fi
        done
        seen+=("$code")
    done
}
