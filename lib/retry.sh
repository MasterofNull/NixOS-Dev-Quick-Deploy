#!/usr/bin/env bash
#
# Retry Logic & Progress Indicators
# Purpose: Retry with exponential backoff and progress spinners
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/user-interaction.sh → print_* functions
#   - lib/logging.sh → log() function
#
# Required Variables:
#   - RETRY_MAX_ATTEMPTS → Maximum retry attempts
#   - RETRY_BACKOFF_MULTIPLIER → Backoff multiplier for delays
#
# Exports:
#   - retry_with_backoff() → Retry command with exponential backoff
#   - with_progress() → Run command with progress spinner
#
# ============================================================================

# Retry function with exponential backoff
retry_with_backoff() {
    local max_attempts=$RETRY_MAX_ATTEMPTS
    local timeout=2
    local attempt=1
    local exit_code=0

    while (( attempt <= max_attempts )); do
        if "$@"; then
            return 0
        fi

        exit_code=$?

        if (( attempt < max_attempts )); then
            print_warning "Attempt $attempt/$max_attempts failed, retrying in ${timeout}s..."
            log WARNING "Retry attempt $attempt failed for command: $*"
            sleep $timeout
            timeout=$((timeout * RETRY_BACKOFF_MULTIPLIER))
            attempt=$((attempt + 1))
        else
            log ERROR "All retry attempts failed for command: $*"
            return $exit_code
        fi
    done

    return $exit_code
}

# Progress indicator
with_progress() {
    local message="$1"
    shift
    local command=("$@")

    print_info "$message"
    log INFO "Running with progress: ${command[*]}"

    # Run command in background
    "${command[@]}" &
    local pid=$!

    # Show spinner while running
    local spin='-\|/'
    local i=0
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) %4 ))
        printf "\r  [${spin:$i:1}] Please wait..."
        sleep 0.1
    done

    wait $pid
    local exit_code=$?

    if (( exit_code == 0 )); then
        printf "\r  [✓] Complete!     \n"
        log INFO "Command completed successfully"
    else
        printf "\r  [✗] Failed!      \n"
        log ERROR "Command failed with exit code $exit_code"
    fi

    return $exit_code
}
