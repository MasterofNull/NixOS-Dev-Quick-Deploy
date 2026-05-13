#!/usr/bin/env bash
#
# Deploy CLI - Parallel Service Startup Module
# Smart parallel service startup with dependency management
#
# Usage:
#   source parallel-service-start.sh
#   build_service_dependency_graph
#   start_services_parallel
#   stop_services_parallel

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Services that can start independently (no hard startup dependencies)
declare -ga INDEPENDENT_SERVICES=(
  "ai-aidb"
  "ai-hybrid-coordinator"
)

# Services that depend on model fetch completion
declare -ga MODEL_DEPENDENT_SERVICES=(
  "llama-cpp"
  "llama-cpp-embed"
)

# All AI stack services
declare -ga AI_STACK_SERVICES=(
  "llama-cpp-model-fetch.service"
  "llama-cpp.service"
  "llama-cpp-embed-model-fetch.service"
  "llama-cpp-embed.service"
  "ai-aidb.service"
  "ai-hybrid-coordinator.service"
)

# ============================================================================
# Dependency Graph Management
# ============================================================================

declare -gA SERVICE_DEPENDENCIES
declare -gA SERVICE_SOFT_DEPENDENCIES

build_service_dependency_graph() {
  # Map of which services must complete before others start
  SERVICE_DEPENDENCIES=(
    [llama-cpp]="llama-cpp-model-fetch.service"
    [llama-cpp-embed]="llama-cpp-embed-model-fetch.service"
    [ai-hybrid-coordinator]="ai-aidb ai-hybrid-coordinator"
  )

  # Services that can start in parallel but have ordering preference
  SERVICE_SOFT_DEPENDENCIES=(
    [ai-aidb]=""                    # No dependencies
    [ai-hybrid-coordinator]="ai-aidb"  # Prefer aidb first, but can overlap
  )

  log_debug "Service dependency graph built"
}

# ============================================================================
# Parallel Service Startup
# ============================================================================

start_services_parallel() {
  log_info "Starting AI stack services in parallel..."

  build_service_dependency_graph

  local -a pids=()
  local -a services=()
  local -a service_names=()

  # Start independent services (no dependencies)
  for svc in "${INDEPENDENT_SERVICES[@]}"; do
    if systemctl is-enabled --quiet "${svc}.service" 2>/dev/null; then
      (
        systemctl restart "${svc}.service" >/dev/null 2>&1
      ) &

      local pid=$!
      pids+=("$pid")
      services+=("${svc}.service")
      service_names+=("$svc")

      log_debug "  Started $svc (pid $pid)"
    fi
  done

  # Start model-dependent services
  for svc in "${MODEL_DEPENDENT_SERVICES[@]}"; do
    if systemctl is-enabled --quiet "${svc}.service" 2>/dev/null; then
      (
        systemctl restart "${svc}.service" >/dev/null 2>&1
      ) &

      local pid=$!
      pids+=("$pid")
      services+=("${svc}.service")
      service_names+=("$svc")

      log_debug "  Started $svc (pid $pid)"
    fi
  done

  # Wait for all services with per-service monitoring
  local timeout=120
  local start_time="$(date +%s)"
  local failed=0

  for i in "${!pids[@]}"; do
    local pid="${pids[$i]}"
    local svc="${services[$i]}"
    local svc_name="${service_names[$i]}"

    # Check overall timeout
    local elapsed=$(( $(date +%s) - start_time ))
    if (( elapsed > timeout )); then
      log_warn "Service startup timeout exceeded (${timeout}s)"
      failed=1
      break
    fi

    # Wait for this specific service with per-service timeout
    if wait "$pid" 2>/dev/null; then
      log_success "  ✓ Service started: $svc_name"
    else
      log_warn "  ⚠ Service start failed: $svc_name"
      failed=1
    fi
  done

  local total_elapsed=$(( $(date +%s) - start_time ))
  log_info "Service startup completed in ${total_elapsed}s"

  if [[ $failed -eq 0 ]]; then
    log_success "All services started successfully"
    return 0
  else
    log_warn "Some services may not have started correctly"
    return 1
  fi
}

# ============================================================================
# Serial Service Startup (Fallback)
# ============================================================================

start_services_serial() {
  log_info "Starting AI stack services (serial mode)..."

  build_service_dependency_graph

  for svc in "${AI_STACK_SERVICES[@]}"; do
    local svc_name="${svc%.service}"

    log_debug "Starting $svc_name..."

    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
      if systemctl restart "$svc" >/dev/null 2>&1; then
        log_success "  ✓ Started $svc_name"
      else
        log_warn "  ⚠ Failed to start $svc_name"
      fi
    fi

    sleep 1  # Small delay between sequential starts
  done

  log_info "Serial service startup complete"
}

# ============================================================================
# Parallel Service Stop
# ============================================================================

stop_services_parallel() {
  log_info "Stopping AI stack services (parallel)..."

  local -a pids=()
  local -a services=()

  # Reverse order for stops
  for svc in "${AI_STACK_SERVICES[@]}"; do
    local svc_name="${svc%.service}"

    if systemctl is-active --quiet "$svc" 2>/dev/null; then
      (
        systemctl stop "$svc" >/dev/null 2>&1 || true
      ) &

      pids+=($!)
      services+=("$svc_name")

      log_debug "  Stop signal sent to $svc_name (pid $!)"
    fi
  done

  # Wait for all stops
  local timeout=30
  local start_time="$(date +%s)"

  for i in "${!pids[@]}"; do
    local pid="${pids[$i]}"
    local svc="${services[$i]}"

    if wait "$pid" 2>/dev/null; then
      log_success "  ✓ Stopped $svc"
    else
      log_debug "  Stopped $svc (with exit code)"
    fi

    # Check overall timeout
    local elapsed=$(( $(date +%s) - start_time ))
    if (( elapsed > timeout )); then
      log_warn "Service stop timeout"
      break
    fi
  done

  log_info "Service stop completed"
}

# ============================================================================
# Service Status Monitoring
# ============================================================================

get_service_status() {
  local svc="$1"

  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "active"
    return 0
  elif systemctl is-enabled --quiet "$svc" 2>/dev/null; then
    echo "enabled"
    return 0
  else
    echo "inactive"
    return 1
  fi
}

report_service_status() {
  log_info "AI Stack Service Status:"

  for svc in "${AI_STACK_SERVICES[@]}"; do
    local svc_name="${svc%.service}"
    local status
    status="$(get_service_status "$svc")"

    case "$status" in
      active)
        log_success "  ✓ $svc_name (active)"
        ;;
      enabled)
        log_info "  ○ $svc_name (enabled, not active)"
        ;;
      *)
        log_warn "  ✗ $svc_name (inactive)"
        ;;
    esac
  done
}

# ============================================================================
# Selective Service Control
# ============================================================================

restart_critical_services() {
  log_info "Restarting critical services..."

  local critical=(
    "llama-cpp.service"
    "ai-aidb.service"
  )

  for svc in "${critical[@]}"; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
      if systemctl restart "$svc" >/dev/null 2>&1; then
        log_success "  ✓ Restarted ${svc%.service}"
      else
        log_warn "  ⚠ Failed to restart ${svc%.service}"
      fi
    fi
  done
}

restart_optional_services() {
  log_info "Restarting optional services (non-blocking)..."

  local optional=(
    "llama-cpp-embed.service"
    "ai-hybrid-coordinator.service"
  )

  for svc in "${optional[@]}"; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
      (
        if systemctl restart "$svc" >/dev/null 2>&1; then
          log_debug "  ✓ Restarted ${svc%.service}"
        else
          log_debug "  ⚠ Failed to restart ${svc%.service}"
        fi
      ) &
    fi
  done

  # Don't wait for optional services
  log_info "Optional service restarts queued (non-blocking)"
}

# ============================================================================
# Optimization Control
# ============================================================================

use_parallel_startup() {
  export DEPLOY_PARALLEL_SERVICES=true
}

use_serial_startup() {
  export DEPLOY_PARALLEL_SERVICES=false
}

is_parallel_startup_enabled() {
  [[ "${DEPLOY_PARALLEL_SERVICES:-true}" == "true" ]]
}

smart_start_services() {
  if is_parallel_startup_enabled; then
    start_services_parallel
  else
    start_services_serial
  fi
}

# ============================================================================
# Export Functions
# ============================================================================

export -f build_service_dependency_graph
export -f start_services_parallel
export -f start_services_serial
export -f stop_services_parallel
export -f get_service_status
export -f report_service_status
export -f restart_critical_services
export -f restart_optional_services
export -f use_parallel_startup
export -f use_serial_startup
export -f is_parallel_startup_enabled
export -f smart_start_services
