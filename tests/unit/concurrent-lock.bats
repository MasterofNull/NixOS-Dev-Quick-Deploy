#!/usr/bin/env bats
#
# Unit tests for deployment lock handling (Phase 14.1.5)
#
# Verifies:
#   - Concurrent invocations are safely serialized via flock
#   - Stale locks from crashed processes are detected and cleared
#   - Lock timeout enforced when another instance holds the lock
#   - Lock released on exit (trap cleanup)

load test_helper

TEST_LOCK_DIR=""

setup() {
    TEST_LOCK_DIR=$(mktemp -d)
    export TEST_LOCK_FILE="$TEST_LOCK_DIR/deploy.lock"
}

teardown() {
    rm -rf "$TEST_LOCK_DIR" 2>/dev/null || true
}

# ============================================================================
# Helper: minimal lock-acquire script matching nixos-quick-deploy.sh logic
# ============================================================================
_lock_script() {
    cat <<'SCRIPT'
#!/usr/bin/env bash
set -uo pipefail
lock_file="$TEST_LOCK_FILE"
lock_fd=200
lock_timeout_sec="${DEPLOY_LOCK_TIMEOUT_SEC:-5}"
lock_acquired=false
lock_start_time=$(date +%s)
lock_warned=false

while true; do
    eval "exec ${lock_fd}>\"${lock_file}\""
    if flock -n "$lock_fd"; then
        printf '%s\n' "$$" > "$lock_file"
        lock_acquired=true
        break
    fi

    # Stale PID detection
    lock_pid=$(cat "$lock_file" 2>/dev/null || true)
    if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
        rm -f "$lock_file" 2>/dev/null || true
        continue
    fi

    now=$(date +%s)
    elapsed=$((now - lock_start_time))
    if (( lock_timeout_sec > 0 && elapsed >= lock_timeout_sec )); then
        echo "LOCK_TIMEOUT"
        exit 1
    fi

    sleep 0.2
done

trap "flock -u ${lock_fd} 2>/dev/null || true; rm -f \"$lock_file\" 2>/dev/null || true" EXIT

# Simulate work: hold lock for duration given as $1 (default 0)
sleep "${1:-0}"
echo "LOCK_ACQUIRED"
SCRIPT
}

# ============================================================================
# Basic lock acquisition
# ============================================================================

@test "lock: single instance acquires lock successfully" {
    script=$(_lock_script)
    run bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' bash <(echo '$script') 0"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"LOCK_ACQUIRED"* ]]
}

@test "lock: lock file is removed after clean exit" {
    script=$(_lock_script)
    bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' bash <(echo '$script') 0"
    # Lock file should be cleaned up by trap
    [[ ! -f "$TEST_LOCK_FILE" ]]
}

# ============================================================================
# Concurrent access: second instance waits then acquires
# ============================================================================

@test "lock: second instance waits and acquires after first releases" {
    script=$(_lock_script)

    # First instance holds lock for 1 second
    bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' DEPLOY_LOCK_TIMEOUT_SEC=10 bash <(echo '$script') 1" &
    pid1=$!
    sleep 0.3  # Let first instance acquire

    # Second instance should wait and eventually succeed
    run bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' DEPLOY_LOCK_TIMEOUT_SEC=10 bash <(echo '$script') 0"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"LOCK_ACQUIRED"* ]]

    wait "$pid1" 2>/dev/null || true
}

# ============================================================================
# Timeout: second instance gives up after timeout
# ============================================================================

@test "lock: second instance times out when first holds lock too long" {
    script=$(_lock_script)

    # First instance holds lock for 10 seconds
    bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' DEPLOY_LOCK_TIMEOUT_SEC=30 bash <(echo '$script') 10" &
    pid1=$!
    sleep 0.3  # Let first instance acquire

    # Second instance with short timeout should fail
    run bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' DEPLOY_LOCK_TIMEOUT_SEC=2 bash <(echo '$script') 0"
    [[ "$status" -ne 0 ]]
    [[ "$output" == *"LOCK_TIMEOUT"* ]]

    kill "$pid1" 2>/dev/null || true
    wait "$pid1" 2>/dev/null || true
}

# ============================================================================
# Stale lock detection
# ============================================================================

@test "lock: stale lock from dead PID is cleared automatically" {
    # Create a lock file with a non-existent PID
    echo "99999999" > "$TEST_LOCK_FILE"

    script=$(_lock_script)
    run bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' bash <(echo '$script') 0"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"LOCK_ACQUIRED"* ]]
}

@test "lock: stale lock with empty PID is cleared automatically" {
    # Create an empty lock file
    touch "$TEST_LOCK_FILE"

    script=$(_lock_script)
    run bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' bash <(echo '$script') 0"
    [[ "$status" -eq 0 ]]
    [[ "$output" == *"LOCK_ACQUIRED"* ]]
}

# ============================================================================
# Serialization: multiple concurrent instances run sequentially
# ============================================================================

@test "lock: three concurrent instances serialize correctly" {
    script=$(_lock_script)
    local results_file="$TEST_LOCK_DIR/results.txt"
    touch "$results_file"

    # Launch 3 instances each holding for 0.3s
    for i in 1 2 3; do
        bash -c "TEST_LOCK_FILE='$TEST_LOCK_FILE' DEPLOY_LOCK_TIMEOUT_SEC=15 bash <(echo '$script') 0.3 && echo 'done_$i' >> '$results_file'" &
    done

    # Wait for all to complete
    wait

    # All three should have completed
    local count
    count=$(wc -l < "$results_file")
    [[ "$count" -eq 3 ]]
}
