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

# ============================================================================
# Retry with Exponential Backoff Function
# ============================================================================
# Purpose: Retry a command multiple times with increasing wait time
# Parameters:
#   $@ - Command and arguments to retry
# Returns:
#   0 - Command succeeded (on any attempt)
#   Exit code - Command failed on all attempts (returns last exit code)
#
# How exponential backoff works:
# - Attempt 1: Run immediately (0s wait)
# - Attempt 2: Wait 2s, then run
# - Attempt 3: Wait 4s, then run (2 * 2)
# - Attempt 4: Wait 8s, then run (4 * 2)
# Total: ~14 seconds for 4 attempts
#
# Why exponential backoff?
# 1. Transient errors: Many failures are temporary (network glitches, etc.)
# 2. Avoid overwhelming: Don't hammer a failing service with rapid retries
# 3. Give time to recover: Services may need time to become available
# 4. Standard pattern: Used by AWS, Google Cloud, and other cloud services
#
# Use cases:
# - Network operations (curl, wget, ssh)
# - Service health checks
# - Database connections
# - API calls
# - Package downloads
#
# NOTE: retry_with_backoff() is defined in lib/retry-backoff.sh (canonical location).
# Duplicate removed in Phase 17.2.4 — retry-backoff.sh is loaded after retry.sh and
# provides a more capable implementation (configurable backoff, jitter, on-retry hook).

# ============================================================================
# With Progress Spinner Function
# ============================================================================
# Purpose: Run a command with animated progress spinner
# Parameters:
#   $1 - Message to display
#   $@ - Command and arguments to run
# Returns:
#   Exit code of command
#
# Visual effect:
#   ℹ Message
#   [-] Please wait...  (spinner animates: - \ | / - \ | /)
#   [✓] Complete!       (on success)
#   [✗] Failed!         (on failure)
#
# How it works:
# 1. Runs command in background
# 2. Displays animated spinner while command runs
# 3. Uses kill -0 to check if process still alive
# 4. Waits for command to complete
# 5. Shows result (✓ or ✗)
#
# Why run in background?
# - Allows us to show progress while command runs
# - Can't show spinner if we wait synchronously
# - Background + spinner = better user experience
#
# kill -0 explained:
# - Sends signal 0 (null signal) to process
# - Doesn't actually kill the process
# - Returns 0 if process exists, 1 if doesn't
# - Standard way to check if process is still running
# ============================================================================
with_progress() {
    # Extract message from first argument
    local message="$1"

    # Remove first argument, leaving command and its arguments
    # After shift: $1 becomes old $2, $2 becomes old $3, etc.
    shift

    # Capture remaining arguments as command array
    # Using array preserves arguments correctly (spaces, special chars, etc.)
    local command=("$@")

    # Display info message to user
    print_info "$message"

    # Log what we're running for debugging
    # ${command[*]} expands all array elements as single string
    log INFO "Running with progress: ${command[*]}"

    # ========================================================================
    # Run command in background
    # ========================================================================
    # & at end runs command in background
    # "${command[@]}" expands array as separate words (correct handling)
    "${command[@]}" &

    # Capture PID of background process
    # $! = PID of last background process
    # We need this to check if process is still running
    local pid=$!

    # ========================================================================
    # Show animated spinner while command runs
    # ========================================================================
    # Spinner characters: - \ | /
    # These create visual rotation effect when displayed rapidly
    local spin='-\|/'

    # Index into spinner string (0-3)
    local i=0

    # Loop while process is still running
    # kill -0 checks process existence without killing it
    # 2>/dev/null suppresses error message if process finished
    while kill -0 $pid 2>/dev/null; do
        # Calculate next spinner character index (cycles 0→1→2→3→0...)
        # (i+1) %4 gives modulo (remainder) to wrap around at 4
        # Example: (0+1)%4=1, (1+1)%4=2, (2+1)%4=3, (3+1)%4=0
        i=$(( (i+1) %4 ))

        # Print spinner character with message
        # \r = carriage return (move cursor to start of line)
        # ${spin:$i:1} = extract 1 character at position $i from $spin
        # printf (not echo) to avoid newline and enable \r
        printf "\r  [${spin:$i:1}] Please wait..."

        # Brief sleep to control animation speed
        # 0.1 second = 10 frames per second
        # Smooth animation without excessive CPU usage
        sleep 0.1
    done

    # ========================================================================
    # Command finished, wait for it and get exit code
    # ========================================================================
    # wait blocks until process completes and returns its exit code
    # Even though process already finished (kill -0 returned false),
    # we must call wait to:
    # 1. Reap the zombie process
    # 2. Get the exit code
    wait $pid
    local exit_code=$?

    # ========================================================================
    # Display result based on exit code
    # ========================================================================
    if (( exit_code == 0 )); then
        # Success: print checkmark
        # \r moves to start of line (overwrites spinner)
        # Spaces after "Complete!" clear any remaining spinner text
        printf "\r  [✓] Complete!     \n"
        log INFO "Command completed successfully"
    else
        # Failure: print X mark
        # \r moves to start of line (overwrites spinner)
        # Spaces after "Failed!" clear any remaining spinner text
        printf "\r  [✗] Failed!      \n"
        log ERROR "Command failed with exit code $exit_code"
    fi

    # Return the command's exit code
    # This allows caller to handle success/failure appropriately
    return $exit_code
}

# ============================================================================
# Retry and Progress Best Practices
# ============================================================================
# 1. Exponential backoff: Prevents overwhelming failing services
# 2. Informative feedback: Tell user what's happening and why
# 3. Configurable retries: Use global config for max attempts
# 4. Preserve exit codes: Return actual error code, not generic failure
# 5. Log all attempts: Track retries for debugging
# 6. User-friendly UX: Spinner shows activity, checkmark shows completion
# 7. Proper backgrounding: Use & and wait correctly
# 8. Process management: Use kill -0 to check process status
# 9. Clean display: Use \r to overwrite spinner with result
# 10. Argument preservation: Use "$@" and arrays correctly
#
# Why these patterns matter:
# - Reliability: Retries handle transient failures automatically
# - User experience: Progress indicators reduce perceived wait time
# - Debugging: Logs help diagnose intermittent failures
# - Maintainability: Centralized retry logic, don't repeat throughout code
# - Standards: Follow industry-standard exponential backoff pattern
# ============================================================================
