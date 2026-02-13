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
#   - LOG_LEVEL → Logging level (TRACE, DEBUG, INFO, WARNING, ERROR)
#   - ENABLE_DEBUG → Boolean flag for debug mode
#   - SCRIPT_VERSION → Version string for logging
#
# Exports:
#   - init_logging() → Initialize logging directory and file
#   - log() → Main logging function with level support
#
# ============================================================================

# Provide safe defaults when helper functions or variables are not defined by
# the caller. This keeps logging usable in minimal test harnesses.
: "${SCRIPT_VERSION:=0.0.0}"
: "${LOG_LEVEL:=INFO}"
: "${ENABLE_DEBUG:=false}"
: "${LOG_DIR:=${HOME:-/tmp}/.cache/nixos-quick-deploy}"
: "${LOG_FILE:=${LOG_DIR}/nixos-quick-deploy.log}"

if ! declare -F safe_mkdir >/dev/null 2>&1; then
    safe_mkdir() { mkdir -p "$1"; }
fi

if ! declare -F safe_chown_user_dir >/dev/null 2>&1; then
    safe_chown_user_dir() { return 0; }
fi

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
#   $1 - Log level (ERROR, WARNING, INFO, DEBUG, TRACE)
#   $* - Message to log (all remaining arguments)
# Returns: 0 on success
#
# Log Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
#
# Log Levels (in order of verbosity):
# - TRACE: Very detailed execution flow (function entry/exit, variable values)
# - DEBUG: Detailed diagnostic information (variable states, decisions)
# - INFO: General informational messages (phase start, operations)
# - WARNING: Warning conditions (non-critical issues, recoverable errors)
# - ERROR: Error conditions (failures, unexpected situations)
#
# How it works:
# 1. Extract level from first argument
# 2. Check if level should be logged based on LOG_LEVEL setting
# 3. Shift arguments so $* contains only the message
# 4. Generate ISO 8601-like timestamp
# 5. Write formatted message to log file
# 6. Handle special cases for ERROR, DEBUG, and TRACE levels
#
# Special handling:
# - ERROR: Includes calling function name for debugging
# - DEBUG: Only logs if LOG_LEVEL is DEBUG or TRACE
# - TRACE: Only logs if LOG_LEVEL is TRACE
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
    if [[ "$level" == "ERROR" && ! "$message" =~ ^ERR= ]]; then
        local fallback_code="${ERR_GENERIC:-1}"
        message="ERR=${fallback_code} ${message}"
    fi

    # Generate timestamp in human-readable format
    # Format: YYYY-MM-DD HH:MM:SS (24-hour clock)
    # Using '+%Y-%m-%d %H:%M:%S' format string
    # Note: Not using -Iseconds here for better readability
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Check if this log level should be written based on LOG_LEVEL setting
    # Log levels in order: TRACE < DEBUG < INFO < WARNING < ERROR
    # Only log if the message level is at or above the configured LOG_LEVEL
    local should_log=false
    case "$LOG_LEVEL" in
        TRACE)
            # TRACE level logs everything
            should_log=true
            ;;
        DEBUG)
            # DEBUG level logs DEBUG, INFO, WARNING, ERROR (not TRACE)
            case "$level" in
                TRACE) should_log=false ;;
                *) should_log=true ;;
            esac
            ;;
        INFO)
            # INFO level logs INFO, WARNING, ERROR (not TRACE or DEBUG)
            case "$level" in
                TRACE|DEBUG) should_log=false ;;
                *) should_log=true ;;
            esac
            ;;
        WARNING)
            # WARNING level logs WARNING and ERROR only
            case "$level" in
                TRACE|DEBUG|INFO) should_log=false ;;
                *) should_log=true ;;
            esac
            ;;
        ERROR)
            # ERROR level logs only ERROR messages
            [[ "$level" == "ERROR" ]] && should_log=true
            ;;
        *)
            # Default: log INFO, WARNING, ERROR (safe default)
            case "$level" in
                TRACE|DEBUG) should_log=false ;;
                *) should_log=true ;;
            esac
            ;;
    esac

    if [[ "$should_log" != true ]]; then
        return 0
    fi

    local caller="${FUNCNAME[2]:-}"

    if [[ "${LOG_FORMAT:-plain}" == "json" ]] && declare -F log_json_line >/dev/null 2>&1; then
        log_json_line "$level" "$message" "$caller" >> "$LOG_FILE"
        return 0
    fi

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
            if [[ -n "$caller" ]]; then
                # Write enriched error message with function context
                # This helps trace where errors originated in the code
                echo "[$timestamp] [$level] [${caller}] $message" >> "$LOG_FILE"
            fi
            ;;
        TRACE|DEBUG)
            # TRACE and DEBUG messages include additional context
            # Show calling function and variable values if available
            if [[ -n "$caller" ]]; then
                echo "[$timestamp] [$level] [${caller}] $message" >> "$LOG_FILE"
            fi
            ;;
        # Other levels (INFO, WARNING) fall through to default behavior
        # They are logged normally without special handling
    esac
}

# ============================================================================
# Log Rotation Function
# ============================================================================
# Purpose: Rotate log files when they become too large
# Parameters:
#   $1 - Maximum log file size in KB (default: 10240 = 10MB)
#   $2 - Number of backup files to keep (default: 5)
# Returns: 0 on success
# ============================================================================
rotate_logs() {
    local max_size_kb="${1:-10240}"
    local keep_backups="${2:-5}"
    
    if [[ ! -f "$LOG_FILE" ]]; then
        return 0
    fi
    
    # Get current file size in KB
    local size_kb
    size_kb=$(du -k "$LOG_FILE" 2>/dev/null | cut -f1 || echo "0")
    
    if [[ $size_kb -lt $max_size_kb ]]; then
        return 0  # No rotation needed
    fi
    
    log INFO "Log file size ($size_kb KB) exceeds maximum ($max_size_kb KB), rotating..."
    
    # Rotate existing backups
    local i
    for ((i=$keep_backups; i>=1; i--)); do
        if [[ $i -eq $keep_backups ]]; then
            rm -f "${LOG_FILE}.${i}" 2>/dev/null || true
        else
            mv "${LOG_FILE}.${i}" "${LOG_FILE}.$((i+1))" 2>/dev/null || true
        fi
    done
    
    # Move current log to backup.1
    mv "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null || true
    
    # Create new log file
    touch "$LOG_FILE" 2>/dev/null || true
    chmod 600 "$LOG_FILE" 2>/dev/null || true
    
    log INFO "Log rotated: previous log saved as ${LOG_FILE}.1"
    return 0
}

# ============================================================================
# Convenience Logging Helper Functions
# ============================================================================
# These wrappers provide shorter, more intuitive function names for common
# logging operations, making code more readable and maintainable.

log_info() {
    log INFO "$@"
}

log_warning() {
    log WARNING "$@"
}

log_error() {
    local first_arg="${1:-}"
    if [[ "$first_arg" =~ ^[0-9]+$ ]] && [[ $# -gt 1 ]]; then
        shift
        log ERROR "ERR=${first_arg} $*"
        return 0
    fi
    log ERROR "$@"
}

log_debug() {
    log DEBUG "$@"
}

log_trace() {
    log TRACE "$@"
}

log_success() {
    log INFO "$@"
}

# ============================================================================
# Error Aggregation
# ============================================================================
# Parses the deployment log file and returns error/warning counts.
# Outputs: DEPLOY_ERRORS DEPLOY_WARNINGS (global variables)
# Also populates DEPLOY_ERROR_SAMPLES (array of up to 10 sample error lines).

aggregate_deployment_errors() {
    DEPLOY_ERRORS=0
    DEPLOY_WARNINGS=0
    DEPLOY_ERROR_SAMPLES=()

    local log_file="${LOG_FILE:-}"
    if [[ -z "$log_file" || ! -f "$log_file" ]]; then
        return 0
    fi

    DEPLOY_ERRORS=$(grep -c '\[ERROR\]' "$log_file" 2>/dev/null || echo 0)
    DEPLOY_WARNINGS=$(grep -c '\[WARNING\]' "$log_file" 2>/dev/null || echo 0)

    # Collect up to 10 sample error lines (most recent first)
    local line
    while IFS= read -r line; do
        DEPLOY_ERROR_SAMPLES+=("$line")
    done < <(grep '\[ERROR\]' "$log_file" 2>/dev/null | tail -10)
}

# ============================================================================
# Why this logging approach?
# ============================================================================
# 1. Centralized: All logging goes through one function
# 2. Structured: Consistent format makes parsing and analysis easy
# 3. Timestamped: Every entry has a timestamp for debugging
# 4. Level-based: Can filter by severity (TRACE, DEBUG, INFO, WARNING, ERROR)
# 5. Context-aware: Errors include function names for debugging
# 6. Conditional: Logging level can be adjusted without code changes
# 7. Rotatable: Log files can be rotated to prevent disk space issues
#
# Best practices demonstrated:
# - Use of local variables to avoid polluting global scope
# - Parameter validation implicit in function design
# - Fail-safe defaults (empty string if FUNCNAME undefined)
# - Atomic operations (single echo per log entry)
# - Append mode (>>) to preserve history
# - Level filtering to reduce log noise
# ============================================================================
