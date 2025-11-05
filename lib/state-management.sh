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

# Initialize state file
init_state() {
    mkdir -p "$STATE_DIR"

    if [[ ! -f "$STATE_FILE" ]]; then
        cat > "$STATE_FILE" <<EOF
{
  "version": "$SCRIPT_VERSION",
  "started_at": "$(date -Iseconds)",
  "completed_steps": [],
  "last_error": null,
  "last_exit_code": 0
}
EOF
        log INFO "Initialized state file: $STATE_FILE"
    else
        log INFO "Using existing state file: $STATE_FILE"
    fi
}

# Mark step as complete
mark_step_complete() {
    local step="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        init_state
    fi

    if command -v jq &>/dev/null; then
        jq --arg step "$step" \
           --arg timestamp "$(date -Iseconds)" \
           '.completed_steps += [{"step": $step, "completed_at": $timestamp}]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"

        log INFO "Marked step complete: $step"
    else
        log WARNING "jq not available, cannot update state file"
    fi
}

# Check if step is complete
is_step_complete() {
    local step="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi

    if command -v jq &>/dev/null; then
        if jq -e --arg step "$step" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            log DEBUG "Step already complete: $step"
            return 0
        fi
    fi

    return 1
}

# Reset state (start fresh)
reset_state() {
    if [[ -f "$STATE_FILE" ]]; then
        mv "$STATE_FILE" "$STATE_FILE.backup-$(date +%s)"
        log INFO "Reset state file"
    fi
    init_state
}
