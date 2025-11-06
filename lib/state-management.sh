#!/usr/bin/env bash
#
# State Management
# Purpose: Persistent state tracking for resume capability
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#
# Required Variables:
#   - STATE_DIR → Directory for state files
#   - STATE_FILE → Path to state JSON file
#   - SCRIPT_VERSION → Version string
#
# Exports:
#   - init_state() → Initialize state file
#   - mark_step_complete() → Mark a step as completed
#   - is_step_complete() → Check if step is already completed
#   - reset_state() → Reset state file (start fresh)
#
# ============================================================================

# ============================================================================
# Initialize State File Function
# ============================================================================
# Purpose: Create or reuse state file for tracking deployment progress
# Parameters: None (uses global variables)
# Returns: 0 on success
#
# State File Format: JSON with the following fields:
#   - version: Script version that created this state
#   - started_at: ISO 8601 timestamp of deployment start
#   - completed_steps: Array of completed step objects
#   - last_error: Last error message (null if no errors)
#   - last_exit_code: Last exit code (0 if no errors)
#
# How it works:
# 1. Creates state directory if it doesn't exist
# 2. Checks if state file already exists
# 3. If new: Creates fresh state file with initial values
# 4. If exists: Keeps existing state for resume capability
#
# Why JSON?
# - Structured data format, easy to parse and update
# - jq provides powerful command-line JSON manipulation
# - Human-readable for debugging
# - Version-controlled state tracking
# - Atomic updates via temp file pattern
#
# Resume capability:
# When script is re-run, existing state file allows skipping completed steps
# This is essential for long-running deployments that may fail partway through
# ============================================================================
init_state() {
    # Create state directory with parents if needed
    # -p flag makes this idempotent (safe to run multiple times)
    if ! safe_mkdir "$STATE_DIR"; then
        echo "FATAL: Cannot create state directory: $STATE_DIR" >&2
        exit 1
    fi

    # Set ownership of state directory
    safe_chown_user_dir "$STATE_DIR" || true

    # Check if state file already exists
    # -f tests for regular file (not directory or special file)
    # Using ! to negate: true if file does NOT exist
    if [[ ! -f "$STATE_FILE" ]]; then
        # ====================================================================
        # Create new state file with initial values
        # ====================================================================
        # Using heredoc (<<EOF) to create multi-line JSON
        # Benefits of heredoc:
        # - Readable multi-line strings
        # - Variable expansion works inside heredoc (unless <<'EOF')
        # - Proper indentation for JSON
        #
        # Why cat > instead of echo?
        # cat with heredoc preserves newlines and formatting
        # Makes the JSON human-readable in the file
        cat > "$STATE_FILE" <<EOF
{
  "version": "$SCRIPT_VERSION",
  "started_at": "$(date -Iseconds)",
  "completed_steps": [],
  "last_error": null,
  "last_exit_code": 0
}
EOF
        # Note: date -Iseconds produces ISO 8601 format: 2024-01-15T10:30:45-05:00
        # This is a standard, sortable, timezone-aware timestamp format

        log INFO "Initialized state file: $STATE_FILE"
    else
        # ====================================================================
        # State file exists - reuse it for resume capability
        # ====================================================================
        # This is a key feature: the script can pick up where it left off
        # After an error or interruption, re-running uses existing state
        # Completed steps are skipped, work resumes from next step
        log INFO "Using existing state file: $STATE_FILE"
    fi
}

# ============================================================================
# Why this state management approach?
# ============================================================================
# 1. Resume capability: Can recover from failures and continue
# 2. Idempotent operations: Safe to re-run multiple times
# 3. Audit trail: Track which steps completed and when
# 4. Error context: Save error info for debugging
# 5. Version tracking: Know which script version created the state
#
# Use cases:
# - Network failure during package download: resume from last step
# - User interrupts deployment: resume later without redoing work
# - Debugging: see exactly which steps completed before error
# - Automation: CI/CD can retry failed deployments intelligently
# ============================================================================

# ============================================================================
# Mark Step as Complete Function
# ============================================================================
# Purpose: Record a completed step in the state file
# Parameters:
#   $1 - Step name/identifier (e.g., "phase-01-preparation")
# Returns: 0 on success, continues even if jq unavailable
#
# How it works:
# 1. Ensures state file exists (creates if missing)
# 2. Uses jq to add step object to completed_steps array
# 3. Records step name and completion timestamp
# 4. Uses atomic write pattern (write to temp, then move)
#
# Step object format in JSON:
#   {"step": "phase-01-preparation", "completed_at": "2024-01-15T10:30:45-05:00"}
#
# Array append operation:
# The += operator in jq appends to an array
# Example: [1,2,3] += [4] → [1,2,3,4]
#
# Why atomic writes?
# Write to temp file, then move to actual file
# This ensures state file is never in a partial/corrupted state
# If script crashes during write, original file remains intact
# ============================================================================
mark_step_complete() {
    # Capture step name from parameter
    local step="$1"

    # Ensure state file exists before trying to update it
    # If somehow state wasn't initialized, initialize it now
    if [[ ! -f "$STATE_FILE" ]]; then
        init_state
    fi

    # Check if jq command is available
    # command -v returns path to command if found, empty if not
    # &>/dev/null redirects both stdout and stderr to null (silent check)
    if command -v jq &>/dev/null; then
        # ====================================================================
        # Use jq to update JSON state file
        # ====================================================================
        # jq command breakdown:
        # --arg step "$step" : Creates a jq variable $step with the step name
        # --arg timestamp "..." : Creates a jq variable $timestamp
        # '.completed_steps += [...]' : Appends to the completed_steps array
        # {"step": $step, ...} : Creates a new step object
        #
        # Atomic write pattern:
        # 1. Read from $STATE_FILE
        # 2. jq processes and outputs to $STATE_FILE.tmp
        # 3. && mv only runs if jq succeeds
        # 4. mv atomically replaces original file
        #
        # Why this is safe:
        # - If jq fails, original file is untouched
        # - mv is atomic on most filesystems (single inode update)
        # - No partial writes can corrupt the state file
        if jq --arg step "$step" \
           --arg timestamp "$(date -Iseconds)" \
           '.completed_steps += [{"step": $step, "completed_at": $timestamp}]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null; then
            # jq succeeded, now atomically move temp to actual file
            if mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
                # Log successful state update
                log INFO "Marked step complete: $step"
            else
                # mv failed - log warning and cleanup
                log WARNING "Failed to atomically update state file"
                rm -f "$STATE_FILE.tmp" 2>/dev/null || true
            fi
        else
            # jq failed - log warning and cleanup
            log WARNING "jq failed to update state file"
            rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        fi
    else
        # ====================================================================
        # Fallback: jq not available
        # ====================================================================
        # This shouldn't happen in normal operation (jq is a critical dependency)
        # But we handle it gracefully: log warning and continue
        # The deployment can still proceed, just without state tracking
        log WARNING "jq not available, cannot update state file"
    fi
}

# ============================================================================
# Check if Step is Complete Function
# ============================================================================
# Purpose: Query whether a step has already been completed
# Parameters:
#   $1 - Step name/identifier to check
# Returns:
#   0 - Step is complete (found in completed_steps array)
#   1 - Step is not complete (not found or state file missing)
#
# How it works:
# 1. Checks if state file exists
# 2. Uses jq to query completed_steps array
# 3. Returns success if step is found, failure otherwise
#
# Usage in deployment:
#   if is_step_complete "phase-01-preparation"; then
#       echo "Skipping phase 01, already completed"
#   else
#       run_phase_01
#   fi
#
# jq -e flag:
# -e = --exit-status: Sets exit code based on output
# Exit 0 if filter produces any output
# Exit 1 if filter produces no output (empty)
# This makes jq work naturally with bash conditionals
# ============================================================================
is_step_complete() {
    # Capture step name from parameter
    local step="$1"

    # Check if state file exists
    # If no state file exists, obviously no steps are complete
    if [[ ! -f "$STATE_FILE" ]]; then
        return 1  # Return failure: step is not complete
    fi

    # Check if jq command is available
    if command -v jq &>/dev/null; then
        # ====================================================================
        # Query state file with jq
        # ====================================================================
        # jq query breakdown:
        # --arg step "$step" : Pass step name as jq variable
        # '.completed_steps[]' : Iterate over completed_steps array
        # '| select(.step == $step)' : Filter for matching step
        # -e flag : Exit 0 if any output, 1 if no output
        #
        # How this works:
        # If step is found: jq outputs the step object and returns 0
        # If step not found: jq outputs nothing and returns 1
        # The if statement checks jq's exit code
        #
        # &>/dev/null : Suppress output (we only care about exit code)
        if jq -e --arg step "$step" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            # Step found in completed_steps array
            log DEBUG "Step already complete: $step"
            return 0  # Return success: step is complete
        fi
    fi

    # If we reach here, either:
    # - jq not available, or
    # - Step was not found in completed_steps
    # In either case, treat as incomplete
    return 1  # Return failure: step is not complete
}

# ============================================================================
# Reset State Function
# ============================================================================
# Purpose: Reset state file to start deployment from scratch
# Parameters: None
# Returns: 0 on success
#
# How it works:
# 1. Backs up existing state file (if present)
# 2. Creates fresh state file
#
# Why backup instead of delete?
# - Preserves history for debugging
# - Can analyze what completed before reset
# - Backup name includes timestamp for uniqueness
#
# Usage:
# - User wants to start over from beginning
# - After major script changes that invalidate old state
# - After manual intervention in system
# - For testing (ensure clean slate)
#
# Backup naming:
# Uses $(date +%s) to get Unix timestamp (seconds since epoch)
# Example: state.json.backup-1705334445
# Timestamp ensures unique names, enables sorting by age
# ============================================================================
reset_state() {
    # Check if state file exists before trying to back it up
    if [[ -f "$STATE_FILE" ]]; then
        # Create backup with timestamp
        # $(date +%s) produces Unix timestamp: seconds since 1970-01-01
        # This creates a unique filename that won't conflict with future backups
        mv "$STATE_FILE" "$STATE_FILE.backup-$(date +%s)"

        # Log the reset operation
        log INFO "Reset state file"
    fi

    # Create fresh state file
    # init_state is idempotent and will create a new state file
    init_state
}

# ============================================================================
# State Management Patterns Demonstrated
# ============================================================================
# 1. Idempotency: Operations can be run multiple times safely
# 2. Atomic updates: Use temp file + move pattern to avoid corruption
# 3. Fail-safe: Continue gracefully if jq unavailable
# 4. Query-based: Use jq queries instead of string parsing
# 5. Structured data: JSON enables rich state tracking
# 6. Timestamping: Track when each step completed
# 7. Backup before modify: Reset creates backup, never just deletes
# 8. Debug logging: Log state changes for troubleshooting
#
# Why jq instead of parsing JSON with bash?
# - jq is designed for JSON manipulation
# - Handles edge cases (escaping, encoding, etc.)
# - Type-safe (respects JSON data types)
# - Atomic operations (read + modify + write)
# - Query language more powerful than bash string manipulation
#
# Common jq patterns used here:
# - --arg: Pass bash variables to jq safely
# - += : Append to arrays
# - select(): Filter array elements
# - -e : Exit status based on output (for conditionals)
# ============================================================================
