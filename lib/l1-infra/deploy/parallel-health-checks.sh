#!/usr/bin/env bash
#
# Deploy CLI - Parallel Health Checks Module
# Concurrent health check execution with smart timeouts and retry logic
#
# Usage:
#   source parallel-health-checks.sh
#   setup_service_endpoints
#   check_health_parallel
#   wait_for_service_ready "llama-cpp" "http://localhost:8080/health"

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

# Default service timeouts (seconds) - adjusted for expected startup times
declare -gA SERVICE_TIMEOUTS=(
  [llama-cpp]=40               # 5-10s startup + 15-20s warmup
  [llama-cpp-embed]=40         # Same as llama-cpp
  [ai-aidb]=50                 # Slower due to postgres init
  [ai-hybrid-coordinator]=30
  [redis]=25
  [postgres]=30
)

# Health check polling intervals (seconds)
declare -gA SERVICE_CHECK_INTERVALS=(
  [llama-cpp]=2
  [llama-cpp-embed]=2
  [ai-aidb]=3
  [ai-hybrid-coordinator]=2
  [redis]=1
  [postgres]=2
)

# Service health endpoints configuration
declare -gA SERVICE_HEALTH_URLS
declare -g _health_check_start_time

# ============================================================================
# Service Endpoint Configuration
# ============================================================================

setup_service_endpoints() {
  # Load from config if available
  if [[ -f "${REPO_ROOT:-$(pwd)}/config/service-endpoints.sh" ]]; then
    source "${REPO_ROOT}/config/service-endpoints.sh" || true
  fi

  # Set defaults if not already defined
  SERVICE_HEALTH_URLS[llama-cpp]="${LLAMA_URL:-http://localhost:8080}/health"
  SERVICE_HEALTH_URLS[llama-cpp-embed]="${EMBEDDINGS_URL:-http://localhost:8001}/health"
  SERVICE_HEALTH_URLS[ai-aidb]="${AIDB_URL:-http://localhost:8002}/health"
  SERVICE_HEALTH_URLS[ai-hybrid-coordinator]="${HYBRID_URL:-http://localhost:8003}/health"
  SERVICE_HEALTH_URLS[redis]="${REDIS_URL:-redis://localhost:6379}"
  SERVICE_HEALTH_URLS[postgres]="${POSTGRES_URL:-postgresql://localhost:5432}"

  log_debug "Service endpoints configured"
}

# ============================================================================
# Single Service Health Check
# ============================================================================

wait_for_service_ready() {
  local service="$1"
  local url="$2"
  local timeout="${SERVICE_TIMEOUTS[$service]:-30}"
  local interval="${SERVICE_CHECK_INTERVALS[$service]:-2}"

  local elapsed=0
  local attempt=0
  local max_attempts=$(( timeout / interval ))

  while (( attempt < max_attempts )); do
    attempt=$(( attempt + 1 ))
    elapsed=$(( attempt * interval ))

    # Try to reach health endpoint
    if curl -sf \
      --connect-timeout 2 \
      --max-time 5 \
      "$url" >/dev/null 2>&1; then
      log_success "  ✓ $service ready ($elapsed s, $attempt checks)"
      return 0
    fi

    # Don't sleep on the last iteration
    if (( attempt < max_attempts )); then
      sleep "$interval"
    fi
  done

  log_warn "  ⚠ $service unresponsive (timeout ${timeout}s after $attempt checks)"
  return 1
}

# ============================================================================
# Parallel Health Check Execution
# ============================================================================

check_health_parallel() {
  local -a pids=()
  local -a services=()
  local -a failed_services=()
  local any_failed=0

  log_info "Checking service health (parallel, max timeout: 50s)..."
  _health_check_start_time="$(date +%s)"

  setup_service_endpoints

  # Start background health checks for each service
  for service in "${!SERVICE_HEALTH_URLS[@]}"; do
    local url="${SERVICE_HEALTH_URLS[$service]}"

    (
      # Each check runs in its own subshell to allow parallelization
      if ! wait_for_service_ready "$service" "$url" 2>&1; then
        echo "FAILED:$service" >> /tmp/health-check-failures-$$.txt
      fi
    ) &

    local pid=$!
    pids+=("$pid")
    services+=("$service")

    log_debug "  Health check started for $service (pid $pid)"
  done

  # Wait for all checks with overall timeout
  local overall_timeout=55
  local start_wait="$(date +%s)"
  local failed_count=0

  for i in "${!pids[@]}"; do
    local pid="${pids[$i]}"
    local service="${services[$i]}"
    local elapsed=$(( $(date +%s) - start_wait ))

    if (( elapsed > overall_timeout )); then
      log_warn "  Overall health check timeout exceeded"
      any_failed=1
      break
    fi

    # Wait for this specific check with timeout
    if wait "$pid" 2>/dev/null; then
      log_debug "  Health check completed for $service"
    else
      log_warn "  Health check failed for $service"
      failed_services+=("$service")
      failed_count=$(( failed_count + 1 ))
      any_failed=1
    fi
  done

  local check_elapsed=$(( $(date +%s) - _health_check_start_time ))
  log_info "Health checks completed in ${check_elapsed}s"

  if [[ $any_failed -eq 0 ]]; then
    log_success "All services healthy"
    return 0
  else
    log_warn "Some services not yet healthy (will continue monitoring)"
    return 1
  fi
}

# ============================================================================
# Selective Health Checks
# ============================================================================

check_health_critical_services() {
  # Check only critical services that block others
  local critical_services=(
    "llama-cpp"
    "ai-aidb"
  )

  log_info "Checking critical service health..."

  local -a pids=()
  for service in "${critical_services[@]}"; do
    local url="${SERVICE_HEALTH_URLS[$service]}"
    (wait_for_service_ready "$service" "$url") &
    pids+=($!)
  done

  for pid in "${pids[@]}"; do
    wait "$pid" || return 1
  done

  log_success "Critical services healthy"
  return 0
}

check_health_optional_services() {
  # Check services that don't block deployment
  local optional_services=(
    "llama-cpp-embed"
    "ai-hybrid-coordinator"
    "redis"
  )

  log_info "Checking optional service health (non-blocking)..."

  for service in "${optional_services[@]}"; do
    local url="${SERVICE_HEALTH_URLS[$service]}"
    if wait_for_service_ready "$service" "$url"; then
      log_debug "  Optional service healthy: $service"
    else
      log_debug "  Optional service not yet ready: $service (will continue)"
    fi
  done

  return 0
}

# ============================================================================
# Health Status Reporting
# ============================================================================

get_service_health_status() {
  local service="$1"
  local url="${SERVICE_HEALTH_URLS[$service]}"

  if curl -sf --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
    echo "healthy"
    return 0
  else
    echo "unhealthy"
    return 1
  fi
}

report_health_status() {
  log_info "Service Health Status:"

  setup_service_endpoints

  for service in "${!SERVICE_HEALTH_URLS[@]}"; do
    local status
    status="$(get_service_health_status "$service")"

    if [[ "$status" == "healthy" ]]; then
      log_success "  ✓ $service"
    else
      log_warn "  ✗ $service"
    fi
  done
}

# ============================================================================
# Timeout Configuration
# ============================================================================

set_service_timeout() {
  local service="$1"
  local timeout="$2"

  SERVICE_TIMEOUTS["$service"]="$timeout"
  log_debug "Service timeout updated: $service = ${timeout}s"
}

set_service_interval() {
  local service="$1"
  local interval="$2"

  SERVICE_CHECK_INTERVALS["$service"]="$interval"
  log_debug "Service check interval updated: $service = ${interval}s"
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_service_endpoints
export -f wait_for_service_ready
export -f check_health_parallel
export -f check_health_critical_services
export -f check_health_optional_services
export -f get_service_health_status
export -f report_health_status
export -f set_service_timeout
export -f set_service_interval
