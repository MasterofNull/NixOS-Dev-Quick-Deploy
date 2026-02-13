#!/usr/bin/env bash
#
# Error Codes - Standardized exit codes for deployment phases
# Purpose: Provide granular error identification for debugging
# Version: 6.1.0
#
# Usage:
#   source lib/error-codes.sh
#   return $ERR_NETWORK
#
# ============================================================================

# shellcheck disable=SC2034
readonly ERR_SUCCESS=0 \
    ERR_GENERIC=1 \
    ERR_NETWORK=10 \
    ERR_DISK_SPACE=11 \
    ERR_PERMISSION=12 \
    ERR_NOT_NIXOS=13 \
    ERR_RUNNING_AS_ROOT=14 \
    ERR_MISSING_COMMAND=15 \
    ERR_DEPENDENCY=20 \
    ERR_PACKAGE_INSTALL=21 \
    ERR_PACKAGE_REMOVE=22 \
    ERR_CHANNEL_UPDATE=23 \
    ERR_PROFILE_CONFLICT=24 \
    ERR_CONFIG_INVALID=30 \
    ERR_CONFIG_GENERATION=31 \
    ERR_TEMPLATE_SUBSTITUTION=32 \
    ERR_CONFIG_PATH_CONFLICT=33 \
    ERR_STATE_INVALID=34 \
    ERR_NIXOS_REBUILD=40 \
    ERR_HOME_MANAGER=41 \
    ERR_FLAKE_LOCK=42 \
    ERR_SYSTEM_SWITCH=43 \
    ERR_K3S_DEPLOY=50 \
    ERR_K3S_NOT_RUNNING=51 \
    ERR_K3S_NAMESPACE=52 \
    ERR_K3S_MANIFEST=53 \
    ERR_IMAGE_BUILD=54 \
    ERR_IMAGE_IMPORT=55 \
    ERR_SECRET_DECRYPT=60 \
    ERR_SECRET_MISSING=61 \
    ERR_SECRET_INVALID=62 \
    ERR_AGE_KEY_MISSING=63 \
    ERR_TIMEOUT=70 \
    ERR_TIMEOUT_KUBECTL=71 \
    ERR_TIMEOUT_REBUILD=72 \
    ERR_TIMEOUT_NETWORK=73 \
    ERR_USER_ABORT=80 \
    ERR_INVALID_INPUT=81 \
    ERR_BACKUP_FAILED=90 \
    ERR_ROLLBACK_FAILED=91 \
    ERR_BACKUP_DIR=92

# Maps error code to human-readable name
error_code_name() {
    local code="$1"
    case "$code" in
        0)  echo "SUCCESS" ;;
        1)  echo "GENERIC_ERROR" ;;
        10) echo "NETWORK_ERROR" ;;
        11) echo "DISK_SPACE" ;;
        12) echo "PERMISSION_DENIED" ;;
        13) echo "NOT_NIXOS" ;;
        14) echo "RUNNING_AS_ROOT" ;;
        15) echo "MISSING_COMMAND" ;;
        20) echo "DEPENDENCY_ERROR" ;;
        21) echo "PACKAGE_INSTALL_FAILED" ;;
        22) echo "PACKAGE_REMOVE_FAILED" ;;
        23) echo "CHANNEL_UPDATE_FAILED" ;;
        24) echo "PROFILE_CONFLICT" ;;
        30) echo "CONFIG_INVALID" ;;
        31) echo "CONFIG_GENERATION_FAILED" ;;
        32) echo "TEMPLATE_SUBSTITUTION_FAILED" ;;
        33) echo "CONFIG_PATH_CONFLICT" ;;
        34) echo "STATE_INVALID" ;;
        40) echo "NIXOS_REBUILD_FAILED" ;;
        41) echo "HOME_MANAGER_FAILED" ;;
        42) echo "FLAKE_LOCK_ERROR" ;;
        43) echo "SYSTEM_SWITCH_FAILED" ;;
        50) echo "K3S_DEPLOY_FAILED" ;;
        51) echo "K3S_NOT_RUNNING" ;;
        52) echo "K3S_NAMESPACE_ERROR" ;;
        53) echo "K3S_MANIFEST_ERROR" ;;
        54) echo "IMAGE_BUILD_FAILED" ;;
        55) echo "IMAGE_IMPORT_FAILED" ;;
        60) echo "SECRET_DECRYPT_FAILED" ;;
        61) echo "SECRET_MISSING" ;;
        62) echo "SECRET_INVALID" ;;
        63) echo "AGE_KEY_MISSING" ;;
        70) echo "TIMEOUT" ;;
        71) echo "TIMEOUT_KUBECTL" ;;
        72) echo "TIMEOUT_REBUILD" ;;
        73) echo "TIMEOUT_NETWORK" ;;
        80) echo "USER_ABORT" ;;
        81) echo "INVALID_INPUT" ;;
        90) echo "BACKUP_FAILED" ;;
        91) echo "ROLLBACK_FAILED" ;;
        92) echo "BACKUP_DIR_ERROR" ;;
        *)  echo "UNKNOWN_ERROR($code)" ;;
    esac
}
