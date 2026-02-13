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
  "health_checks": [],
  "metadata": {},
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
    local step="${1:-}"
    
    # Validate input
    if ! validate_non_empty "step" "$step" 2>/dev/null; then
        # Fallback if validation function not available
        if [[ -z "$step" ]]; then
            log WARNING "mark_step_complete called with empty step name"
            return 1
        fi
    fi

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
    elif command -v python3 &>/dev/null; then
        # ====================================================================
        # Fallback: use python3 when jq is unavailable
        # ====================================================================
        local tmp_file="${STATE_FILE}.tmp"
        if python3 - "$STATE_FILE" "$tmp_file" "$step" <<'PY'
import json
import sys
from datetime import datetime, timezone

src, dst, step = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src, "r", encoding="utf-8") as handle:
    data = json.load(handle)
data.setdefault("completed_steps", [])
data["completed_steps"].append({
    "step": step,
    "completed_at": datetime.now(timezone.utc).astimezone().isoformat()
})
with open(dst, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
        then
            if mv "$tmp_file" "$STATE_FILE" 2>/dev/null; then
                log INFO "Marked step complete: $step (python fallback)"
            else
                log WARNING "Failed to atomically update state file (python fallback)"
                rm -f "$tmp_file" 2>/dev/null || true
            fi
        else
            log WARNING "python3 failed to update state file"
            rm -f "$tmp_file" 2>/dev/null || true
        fi
    else
        # ====================================================================
        # Fallback: neither jq nor python3 available
        # ====================================================================
        log WARNING "jq not available, cannot update state file"
    fi
}

mark_phase_complete() {
    local identifier="$1"

    if [[ "$identifier" =~ ^[0-9]+$ ]]; then
        local formatted_step
        formatted_step="phase-$(printf '%02d' "$identifier")"
        mark_step_complete "$formatted_step"
    else
        mark_step_complete "$identifier"
    fi
}

# ============================================================================
# Record Health Check Result
# ============================================================================
# Purpose: Record inter-phase health check results in state file
# Parameters:
#   $1 - Phase number or name
#   $2 - Status (pass|warn|fail|skipped)
#   $3 - Message/details
# Returns: 0 on success, 1 on validation failure
# ============================================================================
record_health_check() {
    local phase="${1:-}"
    local status="${2:-}"
    local message="${3:-}"

    if [[ -z "$phase" || -z "$status" ]]; then
        log WARNING "record_health_check called with missing phase/status"
        return 1
    fi

    if [[ ! -f "$STATE_FILE" ]]; then
        init_state
    fi

    if command -v jq &>/dev/null; then
        if jq --arg phase "$phase" \
           --arg status "$status" \
           --arg message "$message" \
           --arg timestamp "$(date -Iseconds)" \
           '.health_checks = (.health_checks // []) | .health_checks += [{"phase": $phase, "status": $status, "message": $message, "checked_at": $timestamp}]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null; then
            if mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
                log INFO "Recorded health check: phase=${phase} status=${status}"
            else
                log WARNING "Failed to update state file with health check"
                rm -f "$STATE_FILE.tmp" 2>/dev/null || true
            fi
        else
            log WARNING "jq failed to record health check"
            rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        fi
    elif command -v python3 &>/dev/null; then
        local tmp_file="${STATE_FILE}.tmp"
        if python3 - "$STATE_FILE" "$tmp_file" "$phase" "$status" "$message" <<'PY'
import json
import sys
from datetime import datetime, timezone

src, dst, phase, status, message = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
with open(src, "r", encoding="utf-8") as handle:
    data = json.load(handle)
data.setdefault("health_checks", [])
data["health_checks"].append({
    "phase": phase,
    "status": status,
    "message": message,
    "checked_at": datetime.now(timezone.utc).astimezone().isoformat(),
})
with open(dst, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
        then
            if mv "$tmp_file" "$STATE_FILE" 2>/dev/null; then
                log INFO "Recorded health check: phase=${phase} status=${status} (python fallback)"
            else
                log WARNING "Failed to update state file with health check (python fallback)"
                rm -f "$tmp_file" 2>/dev/null || true
            fi
        else
            log WARNING "python3 failed to record health check"
            rm -f "$tmp_file" 2>/dev/null || true
        fi
    else
        log WARNING "jq not available, cannot record health check"
    fi

    return 0
}

# ============================================================================
# Metadata Helpers
# ============================================================================
# Store/retrieve lightweight deployment metadata (template digests, flags, etc.)
# ============================================================================
state_get_metadata() {
    local key="${1:-}"
    if [[ -z "$key" || ! -f "$STATE_FILE" ]]; then
        return 1
    fi

    if command -v jq &>/dev/null; then
        jq -r --arg key "$key" '.metadata[$key] // empty' "$STATE_FILE" 2>/dev/null
        return $?
    elif command -v python3 &>/dev/null; then
        if python3 - "$STATE_FILE" "$key" <<'PY'
import json
import sys

state_file, key = sys.argv[1], sys.argv[2]
with open(state_file, "r", encoding="utf-8") as handle:
    data = json.load(handle)
value = (data.get("metadata") or {}).get(key)
if value is None:
    sys.exit(1)
print(value)
PY
        then
            return 0
        fi
    fi

    return 1
}

state_set_metadata() {
    local key="${1:-}"
    local value="${2:-}"
    if [[ -z "$key" ]]; then
        log WARNING "state_set_metadata called with empty key"
        return 1
    fi

    if [[ ! -f "$STATE_FILE" ]]; then
        init_state
    fi

    if command -v jq &>/dev/null; then
        if jq --arg key "$key" \
           --arg value "$value" \
           '(.metadata // {}) as $meta | .metadata = $meta | .metadata[$key] = $value' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null; then
            if mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
                log INFO "Updated state metadata: ${key}"
                return 0
            fi
        fi
        rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        log WARNING "Failed to update state metadata via jq"
        return 1
    elif command -v python3 &>/dev/null; then
        local tmp_file="${STATE_FILE}.tmp"
        if python3 - "$STATE_FILE" "$tmp_file" "$key" "$value" <<'PY'
import json
import sys

src, dst, key, value = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(src, "r", encoding="utf-8") as handle:
    data = json.load(handle)
meta = data.get("metadata") or {}
meta[key] = value
data["metadata"] = meta
with open(dst, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
        then
            if mv "$tmp_file" "$STATE_FILE" 2>/dev/null; then
                log INFO "Updated state metadata: ${key} (python fallback)"
                return 0
            fi
        fi
        rm -f "$tmp_file" 2>/dev/null || true
        log WARNING "Failed to update state metadata via python"
        return 1
    fi

    log WARNING "state_set_metadata requires jq or python3"
    return 1
}

state_remove_steps() {
    if [[ ! -f "$STATE_FILE" ]]; then
        return 0
    fi
    if [[ "$#" -eq 0 ]]; then
        return 0
    fi

    if command -v jq &>/dev/null; then
        local jq_steps
        jq_steps=$(printf '%s\n' "$@" | jq -R . | jq -s .)
        if jq --argjson steps "$jq_steps" \
           '.completed_steps = [ .completed_steps[] | select(.step as $s | ($steps | index($s) | not)) ]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null; then
            if mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
                log INFO "Removed state steps: $*"
                return 0
            fi
        fi
        rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        log WARNING "Failed to remove state steps via jq"
        return 1
    elif command -v python3 &>/dev/null; then
        local tmp_file="${STATE_FILE}.tmp"
        if python3 - "$STATE_FILE" "$tmp_file" "$@" <<'PY'
import json
import sys

src, dst, *steps = sys.argv[1:]
with open(src, "r", encoding="utf-8") as handle:
    data = json.load(handle)
steps_set = set(steps)
completed = data.get("completed_steps", [])
data["completed_steps"] = [item for item in completed if item.get("step") not in steps_set]
with open(dst, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
        then
            if mv "$tmp_file" "$STATE_FILE" 2>/dev/null; then
                log INFO "Removed state steps: $* (python fallback)"
                return 0
            fi
        fi
        rm -f "$tmp_file" 2>/dev/null || true
        log WARNING "Failed to remove state steps via python"
        return 1
    fi

    log WARNING "state_remove_steps requires jq or python3"
    return 1
}

state_remove_phase_steps_from() {
    local start_phase="${1:-}"
    if [[ -z "$start_phase" || ! "$start_phase" =~ ^[0-9]+$ ]]; then
        log WARNING "state_remove_phase_steps_from requires numeric phase"
        return 1
    fi
    if [[ ! -f "$STATE_FILE" ]]; then
        return 0
    fi

    if command -v jq &>/dev/null; then
        if jq --argjson start "$start_phase" \
           '.completed_steps = [ .completed_steps[] |
             if (.step | test("^phase-[0-9]+$")) then
               (.step | capture("^phase-(?<num>[0-9]+)$").num | tonumber) as $num |
               if $num < $start then . else empty end
             else
               .
             end
           ]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null; then
            if mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null; then
                log INFO "Removed phase steps from phase ${start_phase} onward"
                return 0
            fi
        fi
        rm -f "$STATE_FILE.tmp" 2>/dev/null || true
        log WARNING "Failed to remove phase steps via jq"
        return 1
    elif command -v python3 &>/dev/null; then
        local tmp_file="${STATE_FILE}.tmp"
        if python3 - "$STATE_FILE" "$tmp_file" "$start_phase" <<'PY'
import json
import re
import sys

src, dst, start_phase = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(src, "r", encoding="utf-8") as handle:
    data = json.load(handle)
completed = data.get("completed_steps", [])
kept = []
for item in completed:
    step = item.get("step") or ""
    match = re.match(r"^phase-(\d+)$", step)
    if match:
        if int(match.group(1)) < start_phase:
            kept.append(item)
    else:
        kept.append(item)
data["completed_steps"] = kept
with open(dst, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
        then
            if mv "$tmp_file" "$STATE_FILE" 2>/dev/null; then
                log INFO "Removed phase steps from phase ${start_phase} onward (python fallback)"
                return 0
            fi
        fi
        rm -f "$tmp_file" 2>/dev/null || true
        log WARNING "Failed to remove phase steps via python"
        return 1
    fi

    log WARNING "state_remove_phase_steps_from requires jq or python3"
    return 1
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
    local step="${1:-}"
    
    # Validate input
    if [[ -z "$step" ]]; then
        # Empty step name means not complete
        return 1
    fi

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
    elif command -v python3 &>/dev/null; then
        if python3 - "$STATE_FILE" "$step" <<'PY'
import json
import sys

state_file, step = sys.argv[1], sys.argv[2]
with open(state_file, "r", encoding="utf-8") as handle:
    data = json.load(handle)
for item in data.get("completed_steps", []):
    if item.get("step") == step:
        sys.exit(0)
sys.exit(1)
PY
        then
            log DEBUG "Step already complete: $step (python fallback)"
            return 0
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
# Validate State File Version Function
# ============================================================================
# Purpose: Compare state file version with current script version
# Parameters:
#   $1 - Mode: "check" (warn only) or "enforce" (fail on mismatch)
# Returns:
#   0 - Versions match or check not applicable
#   1 - Versions differ and enforcement is active
#
# How it works:
# 1. Reads version from state file
# 2. Compares with current SCRIPT_VERSION
# 3. Either warns or fails based on mode
#
# Why version validation?
# - Prevents resuming deployment with incompatible state format
# - Alerts user to potential issues when script is upgraded
# - Maintains consistency between state and processing logic
# ============================================================================
validate_state_version() {
    local mode="${1:-check}"  # Default to "check" mode
    
    # Check if state file exists
    if [[ ! -f "$STATE_FILE" ]]; then
        return 0  # No state file, no version to validate
    fi

    local state_version=""
    
    # Try to get version from state file
    if command -v jq &>/dev/null; then
        state_version=$(jq -r '.version // empty' "$STATE_FILE" 2>/dev/null)
    elif command -v python3 &>/dev/null; then
        state_version=$(python3 -c "
import json
import sys
try:
    with open('$STATE_FILE', 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(data.get('version', ''), end='')
except:
    pass
" 2>/dev/null)
    fi

    # If we couldn't read the version, warn but continue
    if [[ -z "$state_version" ]]; then
        log WARNING "Could not read version from state file, skipping version validation"
        return 0
    fi

    # Compare versions
    if [[ "$state_version" != "$SCRIPT_VERSION" ]]; then
        if [[ "$mode" == "enforce" ]]; then
            log ERROR "State file version ($state_version) differs from script version ($SCRIPT_VERSION)"
            log ERROR "Use --reset-state to clear old state or --force-resume to bypass this check"
            return 1
        else
            log WARNING "State file version ($state_version) differs from script version ($SCRIPT_VERSION)"
            log WARNING "This may cause unexpected behavior. Consider using --reset-state to start fresh."
            return 0
        fi
    fi

    # Versions match
    return 0
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
