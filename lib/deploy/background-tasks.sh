#!/usr/bin/env bash
#
# Deploy CLI - Background Task Management
# Non-blocking background task execution and monitoring
#
# Usage:
#   source background-tasks.sh
#   spawn_background_tasks
#   wait_for_background_tasks
#   get_background_task_status

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

declare -gA BACKGROUND_TASKS
declare -gA TASK_PIDS
declare -g BACKGROUND_TASK_LOG="/tmp/background-tasks-$$.log"

# Priority levels for task scheduling
declare -g TASK_PRIORITY_HIGH=10
declare -g TASK_PRIORITY_NORMAL=5
declare -g TASK_PRIORITY_LOW=1

# ============================================================================
# Task Registration
# ============================================================================

register_background_task() {
  local task_name="$1"
  local task_command="$2"
  local priority="${3:-$TASK_PRIORITY_NORMAL}"

  BACKGROUND_TASKS["$task_name"]="$task_command"

  log_debug "Registered background task: $task_name (priority: $priority)"
}

# ============================================================================
# Task Execution
# ============================================================================

spawn_background_tasks() {
  log_info "Spawning non-critical background tasks..."

  > "$BACKGROUND_TASK_LOG"

  local task_count=0
  local started_count=0

  # Task 1: Cache prewarm
  if [[ -x "${REPO_ROOT:-$(pwd)}/scripts/data/seed-routing-traffic.sh" ]]; then
    task_count=$(( task_count + 1 ))

    (
      sleep 1  # Stagger start
      log_info "Background: Starting cache prewarm..."
      {
        nice -n 15 "${REPO_ROOT:-$(pwd)}/scripts/data/seed-routing-traffic.sh" \
          --count "${CACHE_PREWARM_COUNT:-100}" 2>&1
      } >> "$BACKGROUND_TASK_LOG" 2>&1 || {
        echo "Cache prewarm failed with exit code: $?" >> "$BACKGROUND_TASK_LOG"
      }
    ) &

    local cache_pid=$!
    TASK_PIDS["cache-prewarm"]=$cache_pid
    started_count=$(( started_count + 1 ))

    log_debug "  Cache prewarm started (pid $cache_pid, priority: low)"
  fi

  # Task 2: Dashboard health check
  if [[ -x "${REPO_ROOT:-$(pwd)}/scripts/testing/check-mcp-health.sh" ]]; then
    task_count=$(( task_count + 1 ))

    (
      sleep 2  # Stagger start further
      log_info "Background: Checking dashboard health..."
      {
        "${REPO_ROOT:-$(pwd)}/scripts/testing/check-mcp-health.sh" --optional 2>&1
      } >> "$BACKGROUND_TASK_LOG" 2>&1 || {
        echo "Dashboard health check failed with exit code: $?" >> "$BACKGROUND_TASK_LOG"
      }
    ) &

    local dashboard_pid=$!
    TASK_PIDS["dashboard-health"]=$dashboard_pid
    started_count=$(( started_count + 1 ))

    log_debug "  Dashboard health check started (pid $dashboard_pid, priority: low)"
  fi

  # Task 3: Prometheus restart (if configured)
  if systemctl is-enabled prometheus 2>/dev/null; then
    task_count=$(( task_count + 1 ))

    (
      sleep 3
      log_info "Background: Restarting Prometheus..."
      {
        systemctl restart prometheus 2>&1 || true
      } >> "$BACKGROUND_TASK_LOG" 2>&1
    ) &

    local prom_pid=$!
    TASK_PIDS["prometheus-restart"]=$prom_pid
    started_count=$(( started_count + 1 ))

    log_debug "  Prometheus restart queued (pid $prom_pid, priority: low)"
  fi

  log_info "Background tasks spawned: $started_count / $task_count (main thread unblocked)"
  log_debug "Background task log: $BACKGROUND_TASK_LOG"

  # Don't wait - return immediately to unblock main thread
  return 0
}

# ============================================================================
# Task Monitoring
# ============================================================================

wait_for_background_tasks() {
  local timeout="${1:-180}"  # Default 3 minute timeout
  local start_time
  local wait_pids=()

  start_time="$(date +%s)"

  log_debug "Waiting for background tasks (timeout: ${timeout}s)..."

  # Collect all pids
  for task in "${!TASK_PIDS[@]}"; do
    wait_pids+=("${TASK_PIDS[$task]}")
  done

  if [[ ${#wait_pids[@]} -eq 0 ]]; then
    log_debug "No background tasks to wait for"
    return 0
  fi

  # Wait for all with timeout
  for pid in "${wait_pids[@]}"; do
    # Check if we've exceeded timeout
    local elapsed=$(( $(date +%s) - start_time ))
    if (( elapsed > timeout )); then
      log_warn "Background task timeout exceeded (${timeout}s)"
      return 1
    fi

    # Wait for this pid
    if wait "$pid" 2>/dev/null; then
      log_debug "Background task completed (pid $pid)"
    else
      local exit_code=$?
      if [[ $exit_code -ne 127 ]]; then  # 127 = process not found
        log_debug "Background task exited with code $exit_code (pid $pid)"
      fi
    fi
  done

  local total_elapsed=$(( $(date +%s) - start_time ))
  log_info "All background tasks completed in ${total_elapsed}s"

  return 0
}

wait_for_background_tasks_optional() {
  # Wait for background tasks but don't block on failure
  wait_for_background_tasks 180 || true
  return 0
}

# ============================================================================
# Task Status and Reporting
# ============================================================================

get_background_task_status() {
  local task_name="$1"
  local pid="${TASK_PIDS[$task_name]:-}"

  if [[ -z "$pid" ]]; then
    echo "not-registered"
    return 1
  fi

  if kill -0 "$pid" 2>/dev/null; then
    echo "running"
    return 0
  else
    echo "completed"
    return 0
  fi
}

list_background_tasks() {
  log_info "Background Tasks:"

  for task in "${!TASK_PIDS[@]}"; do
    local pid="${TASK_PIDS[$task]}"
    local status
    status="$(get_background_task_status "$task")"

    case "$status" in
      running)
        log_info "  ○ $task (pid $pid, running)"
        ;;
      completed)
        log_success "  ✓ $task (pid $pid, completed)"
        ;;
      *)
        log_debug "  ? $task (pid $pid, unknown status)"
        ;;
    esac
  done
}

report_background_task_results() {
  log_info "Background Task Results:"

  if [[ ! -f "$BACKGROUND_TASK_LOG" ]]; then
    log_debug "No background task log found"
    return 0
  fi

  log_info "Output from background tasks:"
  sed 's/^/  /' "$BACKGROUND_TASK_LOG" | tail -20

  return 0
}

# ============================================================================
# Task Control
# ============================================================================

cancel_background_tasks() {
  log_warn "Canceling background tasks..."

  for task in "${!TASK_PIDS[@]}"; do
    local pid="${TASK_PIDS[$task]}"

    if kill -0 "$pid" 2>/dev/null; then
      log_info "  Terminating $task (pid $pid)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  log_info "Background tasks canceled"
}

# ============================================================================
# Deferred Task Execution
# ============================================================================

defer_task() {
  local task_name="$1"
  local task_command="$2"

  log_debug "Deferring task: $task_name"

  (
    sleep 5  # Defer by 5 seconds
    eval "$task_command"
  ) &

  local defer_pid=$!
  log_debug "Task deferred (pid $defer_pid)"

  return 0
}

# ============================================================================
# Performance Optimization
# ============================================================================

enable_background_tasks() {
  export DEPLOY_ENABLE_BACKGROUND_TASKS=true
  log_debug "Background task execution enabled"
}

disable_background_tasks() {
  export DEPLOY_ENABLE_BACKGROUND_TASKS=false
  log_debug "Background task execution disabled"
}

are_background_tasks_enabled() {
  [[ "${DEPLOY_ENABLE_BACKGROUND_TASKS:-true}" == "true" ]]
}

smart_spawn_background_tasks() {
  if are_background_tasks_enabled; then
    spawn_background_tasks
  else
    log_debug "Background tasks disabled"
  fi
}

# ============================================================================
# Export Functions
# ============================================================================

export -f register_background_task
export -f spawn_background_tasks
export -f wait_for_background_tasks
export -f wait_for_background_tasks_optional
export -f get_background_task_status
export -f list_background_tasks
export -f report_background_task_results
export -f cancel_background_tasks
export -f defer_task
export -f enable_background_tasks
export -f disable_background_tasks
export -f are_background_tasks_enabled
export -f smart_spawn_background_tasks
