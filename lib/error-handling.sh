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

# ============================================================================
# Comprehensive Error Handler Function
# ============================================================================
# Purpose: Handle script errors, log details, save state, and offer recovery
# Parameters:
#   $1 - Line number where error occurred (passed by trap)
# Global Variables Used:
#   $? - Exit code of failed command (captured immediately)
#   BASH_LINENO - Array of line numbers in call stack
#   FUNCNAME - Array of function names in call stack
#   BASH_COMMAND - The command that was executing when error occurred
# Returns: Does not return (exits with error code)
#
# How it works:
# 1. Captures error context (line, function, exit code, command)
# 2. Logs detailed error information to log file
# 3. Displays user-friendly error message to console
# 4. Saves error state to STATE_FILE for potential resume
# 5. Offers rollback option if available
# 6. Exits with the original error code
#
# Why this approach?
# - Provides maximum debugging information for troubleshooting
# - Enables resume capability by saving state
# - Offers user clear next steps (check log, resume, or rollback)
# - Preserves original exit code for calling scripts/CI systems
# ============================================================================
error_handler() {
    # Capture the exit code of the failed command IMMEDIATELY
    # Must be first line in function, before any other command runs
    # $? contains exit code of last command, gets overwritten easily
    local exit_code=$?

    # Get line number from trap parameter
    # The trap passes $LINENO as argument: trap 'error_handler $LINENO' ERR
    local line_number=$1

    # Get line number from bash call stack (alternative source)
    # BASH_LINENO[0] contains the line number of the current call
    # Useful for cross-referencing with $line_number
    local bash_lineno=${BASH_LINENO[0]}

    # Get function name where error occurred
    # FUNCNAME is an array of the call stack:
    #   FUNCNAME[0] = "error_handler" (this function)
    #   FUNCNAME[1] = the function that was running when error occurred
    # ${var:-default} provides "main" if no function name (top-level code)
    local function_name=${FUNCNAME[1]:-"main"}

    # Log detailed error information to log file
    # This creates a permanent record for debugging
    log ERROR "Script failed at line $line_number (function: $function_name) with exit code $exit_code"

    # Log the actual command that failed
    # BASH_COMMAND contains the command string that was executing
    # This is invaluable for debugging: you see exactly what failed
    log ERROR "Command: ${BASH_COMMAND}"

    # Display user-friendly error message to console
    # Using print_error() for colored output (defined in user-interaction.sh)
    print_error "Deployment failed at line $line_number"
    print_error "Function: $function_name"
    print_error "Exit code: $exit_code"

    # ========================================================================
    # Save failure state for resume capability
    # ========================================================================
    # Check if state file exists before trying to update it
    # Using -f test to check for regular file (not directory or special file)
    if [[ -f "$STATE_FILE" ]]; then
        # Update state file with error information using jq
        # jq is a JSON processor that safely modifies JSON files
        #
        # How this jq command works:
        # --arg error "..." : Defines a jq variable $error with the error message
        # --arg exit_code "..." : Defines a jq variable $exit_code
        # '.last_error = $error' : Sets the last_error field in JSON
        # '| .last_exit_code = $exit_code' : Pipes to set exit_code field
        #
        # Why redirect through temp file?
        # jq can't safely write to the same file it's reading from
        # Pattern: read input file → write to temp → move temp to original
        #
        # Improved error handling: Log failures but don't let error handler fail
        # If jq fails, we don't want error_handler itself to fail
        # This prevents infinite error loops
        if jq --arg error "Failed at line $line_number: ${BASH_COMMAND}" \
           --arg exit_code "$exit_code" \
           '.last_error = $error | .last_exit_code = $exit_code' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null && mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
            : # Success - state saved for resume capability
        else
            # Log warning but don't fail (we're in error handler handling an error)
            echo "[WARNING] Failed to save error state to file" >&2 || true
            rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        fi
    fi

    # Print blank line for visual separation
    echo ""

    # ========================================================================
    # Provide user guidance for next steps
    # ========================================================================
    # Point user to log file for detailed debugging information
    print_info "Check the log file for details: $LOG_FILE"

    # Inform user about resume capability
    # The script can resume from the last completed step using state file
    print_info "To resume from this point, re-run the script"
    echo ""

    # Attempt to record the failure in AIDB logs if available
    local aidb_log="${AIDB_LOG_PATH:-$HOME/.local/share/aidb/logs/deploy.log}"
    local aidb_log_dir
    aidb_log_dir="$(dirname "$aidb_log")"
    if [[ -d "$aidb_log_dir" ]] || safe_mkdir "$aidb_log_dir"; then
        if touch "$aidb_log" >/dev/null 2>&1; then
            local ts
            ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
            {
                echo "timestamp=$ts phase=${CURRENT_PHASE_NUM:-unknown} func=${function_name:-unknown} line=$line_number exit=$exit_code"
                echo "command=${BASH_COMMAND}"
                echo "---"
            } >>"$aidb_log" 2>/dev/null || print_warning "Unable to append to AIDB log at $aidb_log"
        else
            print_warning "AIDB log location not writable ($aidb_log); error not recorded to AIDB."
        fi
    else
        print_warning "AIDB log directory missing/unwritable ($aidb_log_dir); error not recorded to AIDB."
    fi

    # ========================================================================
    # Rollback data notice (automatic rollback disabled)
    # ========================================================================
    if [[ -f "$ROLLBACK_INFO_FILE" ]]; then
        echo ""
        if [[ "${AUTO_ROLLBACK_ENABLED:-false}" == true && "${ROLLBACK_IN_PROGRESS:-false}" != true && "${AUTO_ROLLBACK_SUPPRESSED:-false}" != true ]]; then
            # Skip automatic rollback for the final health check (Phase 8) or when phase context is unknown.
            local current_phase="${CURRENT_PHASE_NUM:-}"
            if [[ -n "$current_phase" && "$current_phase" -lt 8 ]]; then
                print_info "Attempting automatic rollback to last known good state (phase $current_phase failed)."
                trap - ERR  # avoid recursive traps during rollback
                AUTO_ROLLBACK_REQUESTED=true
                ROLLBACK_IN_PROGRESS=true
                export AUTO_ROLLBACK_REQUESTED ROLLBACK_IN_PROGRESS
                if ! perform_rollback; then
                    print_warning "Automatic rollback encountered issues; manual intervention may be required."
                fi
            else
                print_info "Rollback information recorded at $ROLLBACK_INFO_FILE"
                print_info "Automatic rollback skipped (final health check or unknown phase)."
            fi
        else
            print_info "Rollback information recorded at $ROLLBACK_INFO_FILE"
            print_info "Automatic rollback not enabled for this run."
        fi
        echo ""
    fi

    # Exit with the original error code
    # This preserves the exit code for calling scripts or CI/CD systems
    # Important: allows automation to detect and react to failures properly
    exit "$exit_code"
}

# ============================================================================
# Set up ERR trap
# ============================================================================
# The trap command sets up signal handlers for the shell
# Format: trap 'commands' SIGNAL
#
# ERR signal: Triggered when a command returns non-zero exit code
# This works with: set -e (exit on error)
#
# Why pass $LINENO?
# $LINENO is expanded at trap execution time (when error occurs)
# This gives us the exact line number where the error happened
#
# Single quotes vs double quotes:
# Using single quotes prevents immediate expansion of $LINENO
# It's expanded later when the trap fires, giving the correct line number
# ============================================================================
trap 'error_handler $LINENO' ERR

# ============================================================================
# Cleanup on Exit Function
# ============================================================================
# Purpose: Perform cleanup tasks when script exits (normal or error)
# Parameters: None (captures $? automatically)
# Returns: Original exit code (transparent to caller)
#
# Why EXIT trap?
# EXIT trap runs when the shell exits for ANY reason:
# - Normal completion (exit 0)
# - Error exit (exit 1, exit 2, etc.)
# - Explicit exit command
# - Receiving SIGTERM or SIGINT (with some caveats)
#
# Use cases:
# - Remove temporary files
# - Release locks
# - Close file descriptors
# - Log script completion
# - Cleanup background processes
#
# Important: Keep this function fast and simple
# Don't perform complex operations that could fail
# If this function fails, you lose control of cleanup
# ============================================================================
cleanup_on_exit() {
    # Capture exit code immediately
    # This is the exit code of the script (or last command before exit)
    local exit_code=$?

    # Log script exit with code for audit trail
    # This helps track whether deployments completed successfully
    log INFO "Script exiting with code: $exit_code"

    # ========================================================================
    # Cleanup temporary files (placeholder)
    # ========================================================================
    # Add cleanup logic here, for example:
    # - rm -f /tmp/nixos-deploy-*.tmp
    # - rm -f "$STATE_DIR"/*.lock
    # - kill background processes if any
    #
    # Best practice: Use a trap-safe cleanup approach
    # - Check if files exist before removing them
    # - Use || true to prevent cleanup failures from masking real errors
    # - Don't rely on external commands that might not be available
    # ========================================================================

    # Return the original exit code
    # This makes the cleanup transparent to the caller
    # The script exits with the same code it would have without cleanup
    return $exit_code
}

# ============================================================================
# Set up EXIT trap
# ============================================================================
# Registers cleanup_on_exit to run when shell exits
# This ensures cleanup happens regardless of how the script terminates
#
# Order matters: EXIT trap runs AFTER ERR trap
# If error occurs: ERR trap runs → error_handler → exit → EXIT trap → cleanup
# If success: normal exit → EXIT trap → cleanup
#
# Why this matters:
# Cleanup runs whether deployment succeeds or fails
# State is saved before cleanup (in error_handler)
# ============================================================================
trap cleanup_on_exit EXIT

# ============================================================================
# Error Handling Best Practices Demonstrated Here
# ============================================================================
# 1. Capture exit codes immediately (before any other command)
# 2. Log both to file and display to user (different audiences)
# 3. Save state for resume capability (enables recovery)
# 4. Provide clear next steps to user (reduce support burden)
# 5. Preserve exit codes (enables automation and CI/CD integration)
# 6. Use trap for automatic error handling (don't rely on manual checks)
# 7. Separate error handling from cleanup (single responsibility)
# 8. Make cleanup safe and idempotent (can run multiple times safely)
# 9. Use fail-safe operators (|| true) where appropriate
# 10. Provide rollback option (enable undo of partial deployments)
#
# Why set -e is important:
# The script should have 'set -e' enabled (exit on error)
# This makes the ERR trap fire on any command failure
# Without set -e, only explicit 'exit' commands trigger EXIT trap
# ============================================================================
