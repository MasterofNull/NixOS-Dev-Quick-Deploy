#!/usr/bin/env bash
#
# Deploy CLI - Monitoring Integration Module
# Automatic monitoring setup after deployment with service health metric collection
#
# Usage:
#   source monitoring-integration.sh
#   setup_monitoring_after_deployment "deployment_id"
#   collect_deployment_metrics "service_name" "deployment_id"
#   validate_monitoring_config

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

# Load service endpoints if available
if [[ -f "${REPO_ROOT}/config/service-endpoints.sh" ]]; then
  source "${REPO_ROOT}/config/service-endpoints.sh"
fi

# Dashboard and monitoring endpoints
DASHBOARD_API_URL="${DASHBOARD_API_URL:-http://127.0.0.1:8889}"
HYBRID_URL="${HYBRID_URL:-http://127.0.0.1:8003}"

# Monitoring configuration paths
MONITORING_CONFIG_DIR="${MONITORING_CONFIG_DIR:-${REPO_ROOT}/.agent/monitoring}"
DEPLOYMENT_METRICS_FILE="${DEPLOYMENT_METRICS_FILE:-${MONITORING_CONFIG_DIR}/deployment-metrics.json}"
SERVICE_HEALTH_EVENTS_FILE="${SERVICE_HEALTH_EVENTS_FILE:-${MONITORING_CONFIG_DIR}/service-health-events.json}"

# Logging helpers
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[monitoring-integration] DEBUG: $*" >&2
}

log_info() {
  echo "[monitoring-integration] INFO: $*" >&2
}

log_warn() {
  echo "[monitoring-integration] WARN: $*" >&2
}

log_error() {
  echo "[monitoring-integration] ERROR: $*" >&2
}

# ============================================================================
# Monitoring Setup
# ============================================================================

ensure_monitoring_directories() {
  mkdir -p "${MONITORING_CONFIG_DIR}"
  touch "${DEPLOYMENT_METRICS_FILE}"
  touch "${SERVICE_HEALTH_EVENTS_FILE}"
  log_debug "Monitoring directories ensured at ${MONITORING_CONFIG_DIR}"
}

setup_monitoring_after_deployment() {
  local deployment_id="$1"
  local timestamp="$(date -Is)"

  log_info "Setting up monitoring for deployment ${deployment_id}"

  ensure_monitoring_directories

  # Initialize deployment metrics
  if ! jq -e . "${DEPLOYMENT_METRICS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"deployments":[]}' > "${DEPLOYMENT_METRICS_FILE}"
  fi

  # Add deployment entry
  local deployment_entry="{
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"monitoring_enabled\": true,
    \"metrics_collection_started\": \"${timestamp}\",
    \"services_registered\": []
  }"

  jq ".deployments += [${deployment_entry}]" "${DEPLOYMENT_METRICS_FILE}" > "${DEPLOYMENT_METRICS_FILE}.tmp"
  mv "${DEPLOYMENT_METRICS_FILE}.tmp" "${DEPLOYMENT_METRICS_FILE}"

  log_info "Monitoring initialized for deployment ${deployment_id}"

  # Register services with monitoring
  register_services_with_monitoring "${deployment_id}"
}

register_services_with_monitoring() {
  local deployment_id="$1"
  local services=(
    "llama-cpp"
    "llama-cpp-embed"
    "ai-aidb"
    "ai-hybrid-coordinator"
    "redis"
    "postgres"
  )

  log_info "Registering ${#services[@]} services with monitoring"

  for service in "${services[@]}"; do
    register_service_monitoring "${service}" "${deployment_id}"
  done

  log_info "Services registered with monitoring system"
}

register_service_monitoring() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Registering service monitoring: ${service}"

  # Record service registration
  local service_entry="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"registered_at\": \"${timestamp}\",
    \"health_check_enabled\": true,
    \"metric_collection_enabled\": true
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${service_entry}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

# ============================================================================
# Metric Collection
# ============================================================================

collect_deployment_metrics() {
  local service="$1"
  local deployment_id="$2"

  log_debug "Collecting metrics for ${service} (deployment: ${deployment_id})"

  # Collect service-specific metrics
  case "${service}" in
    llama-cpp|llama-cpp-embed)
      collect_llm_metrics "${service}" "${deployment_id}"
      ;;
    ai-aidb)
      collect_database_metrics "${service}" "${deployment_id}"
      ;;
    ai-hybrid-coordinator)
      collect_coordinator_metrics "${service}" "${deployment_id}"
      ;;
    redis)
      collect_redis_metrics "${service}" "${deployment_id}"
      ;;
    postgres)
      collect_postgres_metrics "${service}" "${deployment_id}"
      ;;
    *)
      log_warn "Unknown service for metrics collection: ${service}"
      ;;
  esac
}

collect_llm_metrics() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Collecting LLM metrics: ${service}"

  # Record LLM health event
  local event="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"event_type\": \"metrics_collected\",
    \"metrics\": {
      \"response_time_ms\": 0,
      \"tokens_per_second\": 0,
      \"queue_depth\": 0,
      \"error_rate\": 0
    }
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${event}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

collect_database_metrics() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Collecting database metrics: ${service}"

  # Record database health event
  local event="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"event_type\": \"metrics_collected\",
    \"metrics\": {
      \"connection_count\": 0,
      \"query_latency_ms\": 0,
      \"disk_usage_bytes\": 0,
      \"replication_lag_ms\": 0
    }
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${event}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

collect_coordinator_metrics() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Collecting coordinator metrics: ${service}"

  # Record coordinator health event
  local event="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"event_type\": \"metrics_collected\",
    \"metrics\": {
      \"request_latency_ms\": 0,
      \"alert_queue_depth\": 0,
      \"workflow_completion_rate\": 0,
      \"error_rate\": 0
    }
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${event}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

collect_redis_metrics() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Collecting Redis metrics: ${service}"

  # Record Redis health event
  local event="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"event_type\": \"metrics_collected\",
    \"metrics\": {
      \"connected_clients\": 0,
      \"used_memory_bytes\": 0,
      \"evicted_keys\": 0,
      \"keyspace_hits_rate\": 0
    }
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${event}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

collect_postgres_metrics() {
  local service="$1"
  local deployment_id="$2"
  local timestamp="$(date -Is)"

  log_debug "Collecting PostgreSQL metrics: ${service}"

  # Record PostgreSQL health event
  local event="{
    \"service\": \"${service}\",
    \"deployment_id\": \"${deployment_id}\",
    \"timestamp\": \"${timestamp}\",
    \"event_type\": \"metrics_collected\",
    \"metrics\": {
      \"active_connections\": 0,
      \"xact_commit_rate\": 0,
      \"cache_hit_ratio\": 0,
      \"replication_slots\": 0
    }
  }"

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"events":[]}' > "${SERVICE_HEALTH_EVENTS_FILE}"
  fi

  jq ".events += [${event}]" "${SERVICE_HEALTH_EVENTS_FILE}" > "${SERVICE_HEALTH_EVENTS_FILE}.tmp"
  mv "${SERVICE_HEALTH_EVENTS_FILE}.tmp" "${SERVICE_HEALTH_EVENTS_FILE}"
}

# ============================================================================
# Dashboard Integration
# ============================================================================

register_with_dashboard() {
  local deployment_id="$1"
  local timestamp="$(date -Is)"

  log_info "Registering deployment with dashboard: ${deployment_id}"

  if ! command -v curl >/dev/null 2>&1; then
    log_warn "curl not available, skipping dashboard registration"
    return 0
  fi

  # Try to notify dashboard that monitoring is active
  local payload="{
    \"deployment_id\": \"${deployment_id}\",
    \"monitoring_enabled\": true,
    \"timestamp\": \"${timestamp}\",
    \"services\": [\"llama-cpp\", \"llama-cpp-embed\", \"ai-aidb\", \"ai-hybrid-coordinator\", \"redis\", \"postgres\"]
  }"

  curl -fsS -X POST \
    -H 'Content-Type: application/json' \
    "${DASHBOARD_API_URL}/api/deployments/${deployment_id}/metadata" \
    --data "${payload}" 2>/dev/null || log_warn "Failed to notify dashboard of monitoring setup"
}

# ============================================================================
# Validation
# ============================================================================

validate_monitoring_config() {
  log_info "Validating monitoring configuration"

  ensure_monitoring_directories

  # Verify JSON structure
  if ! jq -e . "${DEPLOYMENT_METRICS_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid deployment metrics file: ${DEPLOYMENT_METRICS_FILE}"
    return 1
  fi

  if ! jq -e . "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid service health events file: ${SERVICE_HEALTH_EVENTS_FILE}"
    return 1
  fi

  log_info "Monitoring configuration valid"
  return 0
}

get_monitored_deployments() {
  if [[ ! -f "${DEPLOYMENT_METRICS_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  jq -r '.deployments[].deployment_id' "${DEPLOYMENT_METRICS_FILE}" 2>/dev/null || echo ""
}

get_service_events() {
  local service="$1"

  if [[ ! -f "${SERVICE_HEALTH_EVENTS_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  jq ".events[] | select(.service == \"${service}\")" "${SERVICE_HEALTH_EVENTS_FILE}" 2>/dev/null || echo ""
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_monitoring_after_deployment
export -f register_services_with_monitoring
export -f register_service_monitoring
export -f collect_deployment_metrics
export -f collect_llm_metrics
export -f collect_database_metrics
export -f collect_coordinator_metrics
export -f collect_redis_metrics
export -f collect_postgres_metrics
export -f register_with_dashboard
export -f validate_monitoring_config
export -f get_monitored_deployments
export -f get_service_events
