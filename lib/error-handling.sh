#!/usr/bin/env bash
#
# Error Handling Framework
# Purpose: Comprehensive error handling with trap setup
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/colors.sh → Color codes for output
#
# Required Variables:
#   - STATE_FILE → Path to state file for error recording
#   - LOG_FILE → Path to log file for user reference
#   - ROLLBACK_INFO_FILE → Path to rollback info
#   - SCRIPT_DIR → Script directory for rollback command
#
# Exports:
#   - error_handler() → Comprehensive error handler
#   - cleanup_on_exit() → Cleanup function for normal/error exit
#   - Trap setup for ERR and EXIT signals
#
# ============================================================================

# Comprehensive error handler
error_handler() {
    local exit_code=$?
    local line_number=$1
    local bash_lineno=${BASH_LINENO[0]}
    local function_name=${FUNCNAME[1]:-"main"}

    log ERROR "Script failed at line $line_number (function: $function_name) with exit code $exit_code"
    log ERROR "Command: ${BASH_COMMAND}"

    print_error "Deployment failed at line $line_number"
    print_error "Function: $function_name"
    print_error "Exit code: $exit_code"

    # Save failure state
    if [[ -f "$STATE_FILE" ]]; then
        jq --arg error "Failed at line $line_number: ${BASH_COMMAND}" \
           --arg exit_code "$exit_code" \
           '.last_error = $error | .last_exit_code = $exit_code' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null && mv "$STATE_FILE.tmp" "$STATE_FILE" || true
    fi

    echo ""
    print_info "Check the log file for details: $LOG_FILE"
    print_info "To resume from this point, re-run the script"
    echo ""

    # Offer rollback if available
    if [[ -f "$ROLLBACK_INFO_FILE" ]]; then
        echo ""
        print_warning "A rollback point is available. To rollback:"
        echo "  $SCRIPT_DIR/nixos-quick-deploy.sh --rollback"
        echo ""
    fi

    exit "$exit_code"
}

# Set up error trap
trap 'error_handler $LINENO' ERR

# Cleanup on exit (normal or error)
cleanup_on_exit() {
    local exit_code=$?
    log INFO "Script exiting with code: $exit_code"

    # Remove temporary files if any
    # Add cleanup logic here

    return $exit_code
}

trap cleanup_on_exit EXIT
