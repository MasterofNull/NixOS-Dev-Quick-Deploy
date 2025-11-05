#!/usr/bin/env bash
#
# Logging Framework
# Purpose: Centralized logging with levels and file output
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - None (standalone - must be loaded early)
#
# Required Variables:
#   - LOG_DIR → Directory for log files
#   - LOG_FILE → Path to current log file
#   - LOG_LEVEL → Logging level (DEBUG, INFO, WARNING, ERROR)
#   - ENABLE_DEBUG → Boolean flag for debug mode
#   - SCRIPT_VERSION → Version string for logging
#
# Exports:
#   - init_logging() → Initialize logging directory and file
#   - log() → Main logging function with level support
#
# ============================================================================

# Initialize logging
init_logging() {
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
    chmod 600 "$LOG_FILE"

    log INFO "=== NixOS Quick Deploy v$SCRIPT_VERSION started ==="
    log INFO "Logging to: $LOG_FILE"
    log INFO "Script executed by: $USER (UID: $EUID)"
    log INFO "Working directory: $(pwd)"
}

# Main logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Write to log file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Also print to console based on log level
    case "$level" in
        ERROR)
            if [[ "${FUNCNAME[2]:-}" != "" ]]; then
                echo "[$timestamp] [$level] [${FUNCNAME[2]}] $message" >> "$LOG_FILE"
            fi
            ;;
        DEBUG)
            if [[ "$LOG_LEVEL" == "DEBUG" || "$ENABLE_DEBUG" == true ]]; then
                # Only show debug in verbose mode
                return 0
            fi
            ;;
    esac
}
