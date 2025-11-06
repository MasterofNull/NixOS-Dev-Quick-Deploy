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

# ============================================================================
# Logging Initialization Function
# ============================================================================
# Purpose: Set up logging directory, file, and write initial log entries
# Parameters: None (uses global variables)
# Returns: 0 on success
#
# How it works:
# 1. Creates log directory if it doesn't exist (mkdir -p is idempotent)
# 2. Creates log file with touch (also idempotent)
# 3. Sets restrictive permissions (600 = owner read/write only)
# 4. Writes initial session information to log
#
# Why restrictive permissions?
# Log files may contain sensitive information like:
# - System paths and configuration details
# - User names and home directories
# - Error messages that reveal system internals
# chmod 600 ensures only the file owner can read/write the log
# ============================================================================
init_logging() {
    # Create log directory with parents (-p flag)
    # -p = --parents: create parent directories as needed, no error if existing
    # This is safe to run multiple times (idempotent operation)
    if ! safe_mkdir "$LOG_DIR"; then
        echo "FATAL: Cannot create log directory: $LOG_DIR" >&2
        echo "Check permissions and available disk space" >&2
        exit 1
    fi

    # Set ownership of log directory
    safe_chown_user_dir "$LOG_DIR" || true

    # Create the log file if it doesn't exist
    # touch updates the timestamp if file exists, creates if it doesn't
    # Using touch instead of > to avoid truncating an existing file
    if ! touch "$LOG_FILE" 2>/dev/null; then
        echo "FATAL: Cannot create log file: $LOG_FILE" >&2
        echo "Check permissions on log directory: $LOG_DIR" >&2
        exit 1
    fi

    # Set secure permissions: owner read/write only (rw-------)
    # 6 = read(4) + write(2) for owner
    # 0 = no permissions for group
    # 0 = no permissions for others
    # This protects potentially sensitive deployment information
    if ! chmod 600 "$LOG_FILE" 2>/dev/null; then
        echo "WARNING: Cannot set log file permissions: $LOG_FILE" >&2
        # Don't fail - logging can still work
    fi

    # Write session header to log file
    # Using log() function to ensure consistent formatting
    log INFO "=== NixOS Quick Deploy v$SCRIPT_VERSION started ==="
    log INFO "Logging to: $LOG_FILE"

    # Record who is running the script and with what privileges
    # $USER = username (may not be set in some environments, fallback to whoami)
    # $EUID = effective user ID (0 = root)
    local current_user="${USER:-$(whoami 2>/dev/null || echo 'unknown')}"
    log INFO "Script executed by: $current_user (UID: ${EUID:-unknown})"

    # Record starting directory for context
    # $(pwd) is executed in a subshell and its output is logged
    log INFO "Working directory: $(pwd)"
}

# ============================================================================
# Main Logging Function
# ============================================================================
# Purpose: Write log messages to file with timestamp and level
# Parameters:
#   $1 - Log level (ERROR, WARNING, INFO, DEBUG)
#   $* - Message to log (all remaining arguments)
# Returns: 0 on success
#
# Log Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
#
# How it works:
# 1. Extract level from first argument
# 2. Shift arguments so $* contains only the message
# 3. Generate ISO 8601-like timestamp
# 4. Write formatted message to log file
# 5. Handle special cases for ERROR and DEBUG levels
#
# Special handling:
# - ERROR: Includes calling function name for debugging
# - DEBUG: Only logs if debug mode is enabled (respects LOG_LEVEL)
#
# Why shift?
# shift removes $1 from the argument list, so $* becomes the message
# This allows messages with spaces to be handled correctly
# Example: log INFO "Hello world" → $1=INFO, $*="Hello world"
# ============================================================================
log() {
    # Extract log level from first argument
    local level="$1"

    # Remove first argument (level) from argument list
    # After shift: $1 becomes old $2, $2 becomes old $3, etc.
    # Now $* contains only the message text
    shift

    # Capture all remaining arguments as the message
    # $* joins all arguments with spaces
    # Using "$*" preserves internal spaces in the message
    local message="$*"

    # Generate timestamp in human-readable format
    # Format: YYYY-MM-DD HH:MM:SS (24-hour clock)
    # Using '+%Y-%m-%d %H:%M:%S' format string
    # Note: Not using -Iseconds here for better readability
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Write to log file with formatted output
    # >> appends to file (vs > which overwrites)
    # Format: [timestamp] [level] message
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Handle special cases based on log level
    # case statement is more efficient than multiple if/elif for string matching
    case "$level" in
        ERROR)
            # For errors, include the calling function name for debugging
            # FUNCNAME is a bash array containing the call stack
            # FUNCNAME[0] = current function (log)
            # FUNCNAME[1] = direct caller (e.g., print_error)
            # FUNCNAME[2] = the actual function where error occurred
            # The ${var:-default} syntax provides a default if var is unset
            if [[ "${FUNCNAME[2]:-}" != "" ]]; then
                # Write enriched error message with function context
                # This helps trace where errors originated in the code
                echo "[$timestamp] [$level] [${FUNCNAME[2]}] $message" >> "$LOG_FILE"
            fi
            ;;
        DEBUG)
            # Debug messages are only logged if debug mode is explicitly enabled
            # This prevents log files from becoming cluttered with debug info
            # in normal operation, while allowing verbose logging when needed
            if [[ "$LOG_LEVEL" == "DEBUG" || "$ENABLE_DEBUG" == true ]]; then
                # Debug mode enabled: message was already written above
                # Just return success without additional console output
                return 0
            fi
            ;;
        # Other levels (INFO, WARNING) fall through to default behavior
        # They are logged normally without special handling
    esac
}

# ============================================================================
# Why this logging approach?
# ============================================================================
# 1. Centralized: All logging goes through one function
# 2. Structured: Consistent format makes parsing and analysis easy
# 3. Timestamped: Every entry has a timestamp for debugging
# 4. Level-based: Can filter by severity (ERROR, WARNING, INFO, DEBUG)
# 5. Context-aware: Errors include function names for debugging
# 6. Conditional: Debug logging can be toggled without code changes
#
# Best practices demonstrated:
# - Use of local variables to avoid polluting global scope
# - Parameter validation implicit in function design
# - Fail-safe defaults (empty string if FUNCNAME undefined)
# - Atomic operations (single echo per log entry)
# - Append mode (>>) to preserve history
# ============================================================================
