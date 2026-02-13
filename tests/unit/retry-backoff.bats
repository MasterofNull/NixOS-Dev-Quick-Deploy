#!/usr/bin/env bats
#
# Unit tests for lib/retry-backoff.sh
#

load test_helper

setup() {
    source "$LIB_DIR/retry-backoff.sh"
}

# ============================================================================
# retry_with_backoff - success cases
# ============================================================================

@test "retry_with_backoff: succeeds on first try" {
    run retry_with_backoff --attempts 3 --delay 0 -- true
    [[ "$status" -eq 0 ]]
}

@test "retry_with_backoff: returns 0 when command succeeds" {
    run retry_with_backoff -- echo "ok"
    [[ "$status" -eq 0 ]]
}

# ============================================================================
# retry_with_backoff - failure cases
# ============================================================================

@test "retry_with_backoff: fails after max attempts" {
    run retry_with_backoff --attempts 2 --delay 0 -- false
    [[ "$status" -ne 0 ]]
}

@test "retry_with_backoff: returns error when no command given" {
    run retry_with_backoff --attempts 1 --delay 0 --
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# retry_with_backoff - retry behavior
# ============================================================================

@test "retry_with_backoff: retries the correct number of times" {
    local counter_file
    counter_file=$(mktemp)
    echo "0" > "$counter_file"

    fail_twice() {
        local count
        count=$(cat "$counter_file")
        count=$((count + 1))
        echo "$count" > "$counter_file"
        [[ $count -ge 3 ]]
    }

    run retry_with_backoff --attempts 5 --delay 0 -- fail_twice
    [[ "$status" -eq 0 ]]

    local final_count
    final_count=$(cat "$counter_file")
    [[ "$final_count" -eq 3 ]]

    rm -f "$counter_file"
}

# ============================================================================
# Circuit breaker
# ============================================================================

@test "circuit_breaker_check: passes when no failures recorded" {
    run circuit_breaker_check "test_op"
    [[ "$status" -eq 0 ]]
}

@test "circuit_breaker_record_failure: increments failure count" {
    circuit_breaker_reset "test_op2"
    circuit_breaker_record_failure "test_op2"
    circuit_breaker_record_failure "test_op2"
    local count="${_CIRCUIT_BREAKER_FAILURES[test_op2]:-0}"
    [[ "$count" -eq 2 ]]
}

@test "circuit_breaker_check: trips after threshold failures" {
    CIRCUIT_BREAKER_THRESHOLD=3
    circuit_breaker_reset "test_op3"
    circuit_breaker_record_failure "test_op3"
    circuit_breaker_record_failure "test_op3"
    circuit_breaker_record_failure "test_op3"

    run circuit_breaker_check "test_op3"
    [[ "$status" -eq 1 ]]
}

@test "circuit_breaker_reset: clears failure count" {
    circuit_breaker_record_failure "test_op4"
    circuit_breaker_record_failure "test_op4"
    circuit_breaker_reset "test_op4"

    local count="${_CIRCUIT_BREAKER_FAILURES[test_op4]:-0}"
    [[ "$count" -eq 0 ]]
}
