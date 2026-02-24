#!/usr/bin/env bash
#
# Retry with Exponential Backoff + Circuit Breaker
# Purpose: Handle transient failures gracefully
# Version: 6.1.0
#
# ============================================================================

# Default retry settings - override via config/settings.sh or env vars
: "${MAX_RETRY_ATTEMPTS:=3}"
: "${RETRY_BASE_DELAY:=2}"
: "${RETRY_MAX_DELAY:=60}"
: "${CIRCUIT_BREAKER_THRESHOLD:=5}"

# Circuit breaker state (tracks consecutive failures per operation)
declare -A _CIRCUIT_BREAKER_FAILURES 2>/dev/null || true

# ============================================================================
# Retry a command with exponential backoff
# ============================================================================
# Usage: retry_with_backoff [options] -- <command> [args...]
#   Options:
#     --attempts N     Max attempts (default: MAX_RETRY_ATTEMPTS)
#     --delay N        Base delay seconds (default: RETRY_BASE_DELAY)
#     --max-delay N    Max delay seconds (default: RETRY_MAX_DELAY)
#     --on-retry CMD   Command to run between retries (e.g., cleanup)
#
# Returns: Exit code of the last attempt
# ============================================================================
retry_with_backoff() {
    local max_attempts="$MAX_RETRY_ATTEMPTS"
    local base_delay="$RETRY_BASE_DELAY"
    local max_delay="$RETRY_MAX_DELAY"
    local on_retry_cmd=""

    # Parse options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --attempts)   max_attempts="$2"; shift 2 ;;
            --delay)      base_delay="$2"; shift 2 ;;
            --max-delay)  max_delay="$2"; shift 2 ;;
            --on-retry)   on_retry_cmd="$2"; shift 2 ;;
            --)           shift; break ;;
            *)            break ;;
        esac
    done

    if [[ $# -eq 0 ]]; then
        if declare -F log >/dev/null 2>&1; then
            log ERROR "retry_with_backoff: no command specified"
        fi
        return 1
    fi

    local attempt=1
    local delay="$base_delay"
    local exit_code=0

    while [[ $attempt -le $max_attempts ]]; do
        # Execute the command
        "$@"
        exit_code=$?

        if [[ $exit_code -eq 0 ]]; then
            # Success - reset circuit breaker for this operation
            local op_key="${1}${2:-}"
            _CIRCUIT_BREAKER_FAILURES["$op_key"]=0 2>/dev/null || true
            return 0
        fi

        # Failure
        if [[ $attempt -ge $max_attempts ]]; then
            if declare -F log >/dev/null 2>&1; then
                log ERROR "All $max_attempts attempts failed for: $* (last exit: $exit_code)"
            fi
            break
        fi

        # Log retry
        local remaining=$((max_attempts - attempt))
        if declare -F print_warning >/dev/null 2>&1; then
            print_warning "Attempt $attempt/$max_attempts failed (exit: $exit_code). Retrying in ${delay}s... ($remaining remaining)"
        fi

        # Execute on-retry hook if specified
        if [[ -n "$on_retry_cmd" ]]; then
            $on_retry_cmd 2>/dev/null || true
        fi

        sleep "$delay"

        # Exponential backoff with jitter
        local jitter=$((RANDOM % 3))
        delay=$(( (delay * 2) + jitter ))
        if [[ $delay -gt $max_delay ]]; then
            delay=$max_delay
        fi

        attempt=$((attempt + 1))
    done

    return $exit_code
}

# ============================================================================
# Circuit breaker - prevents retrying known-broken operations
# ============================================================================
# Usage: circuit_breaker_check <operation_name>
# Returns: 0 if circuit is closed (ok to proceed), 1 if open (should skip)
# ============================================================================
circuit_breaker_check() {
    local operation="${1:?operation name required}"
    local failures="${_CIRCUIT_BREAKER_FAILURES[$operation]:-0}"

    if [[ $failures -ge $CIRCUIT_BREAKER_THRESHOLD ]]; then
        if declare -F print_error >/dev/null 2>&1; then
            print_error "Circuit breaker OPEN for '$operation' ($failures consecutive failures)"
            print_info "Reset with: circuit_breaker_reset '$operation'"
        fi
        return 1
    fi

    return 0
}

# ============================================================================
# Record a failure for circuit breaker tracking
# ============================================================================
circuit_breaker_record_failure() {
    local operation="${1:?operation name required}"
    local current="${_CIRCUIT_BREAKER_FAILURES[$operation]:-0}"
    _CIRCUIT_BREAKER_FAILURES["$operation"]=$((current + 1)) 2>/dev/null || true
}

# ============================================================================
# Reset circuit breaker for an operation
# ============================================================================
circuit_breaker_reset() {
    local operation="${1:?operation name required}"
    _CIRCUIT_BREAKER_FAILURES["$operation"]=0 2>/dev/null || true
}

# ============================================================================
# Convenience: retry kubectl commands
# ============================================================================
retry_kubectl() {
    if ! circuit_breaker_check "kubectl"; then
        return "${ERR_TIMEOUT_KUBECTL:-71}"
    fi

    retry_with_backoff --attempts 3 --delay 2 --max-delay 30 -- kubectl_safe "$@"
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        circuit_breaker_record_failure "kubectl"
    fi

    return $exit_code
}

# ============================================================================
# Convenience: retry network operations
# ============================================================================
retry_network() {
    if ! circuit_breaker_check "network"; then
        return "${ERR_TIMEOUT_NETWORK:-73}"
    fi

    retry_with_backoff --attempts 3 --delay 5 --max-delay 60 -- "$@"
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        circuit_breaker_record_failure "network"
    fi

    return $exit_code
}
