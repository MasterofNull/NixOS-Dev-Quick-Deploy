#!/usr/bin/env bash
#
# Deploy CLI - Alert Configuration Module
# Alert rule configuration with threshold management and notification routing
#
# Usage:
#   source alert-config.sh
#   setup_alert_rules_for_deployment "deployment_id"
#   configure_threshold_alert "service" "metric" "threshold" "severity"
#   setup_notification_channels

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

# Alert configuration paths
ALERT_CONFIG_DIR="${ALERT_CONFIG_DIR:-${REPO_ROOT}/.agent/alerts}"
ALERT_RULES_FILE="${ALERT_RULES_FILE:-${ALERT_CONFIG_DIR}/alert-rules.json}"
ALERT_THRESHOLDS_FILE="${ALERT_THRESHOLDS_FILE:-${ALERT_CONFIG_DIR}/thresholds.json}"
NOTIFICATION_CONFIG_FILE="${NOTIFICATION_CONFIG_FILE:-${ALERT_CONFIG_DIR}/notifications.json}"

# Logging helpers
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[alert-config] DEBUG: $*" >&2
}

log_info() {
  echo "[alert-config] INFO: $*" >&2
}

log_warn() {
  echo "[alert-config] WARN: $*" >&2
}

log_error() {
  echo "[alert-config] ERROR: $*" >&2
}

# ============================================================================
# Alert Configuration Setup
# ============================================================================

ensure_alert_directories() {
  mkdir -p "${ALERT_CONFIG_DIR}"
  log_debug "Alert directories ensured at ${ALERT_CONFIG_DIR}"
}

setup_alert_rules_for_deployment() {
  local deployment_id="$1"
  local timestamp="$(date -Is)"

  log_info "Setting up alert rules for deployment ${deployment_id}"

  ensure_alert_directories

  # Initialize alert rules file
  if ! jq -e . "${ALERT_RULES_FILE}" 2>/dev/null >/dev/null; then
    echo '{"rules":[]}' > "${ALERT_RULES_FILE}"
  fi

  # Configure default alert rules for this deployment
  setup_service_health_alerts "${deployment_id}"
  setup_performance_alerts "${deployment_id}"
  setup_resource_alerts "${deployment_id}"
  setup_deployment_alerts "${deployment_id}"

  log_info "Alert rules configured for deployment ${deployment_id}"
}

setup_service_health_alerts() {
  local deployment_id="$1"

  log_debug "Setting up service health alert rules"

  # Service down alert
  add_alert_rule "service_down" \
    "service_health" \
    "critical" \
    "Service is not responding" \
    "immediate" \
    "${deployment_id}"

  # Service degraded alert
  add_alert_rule "service_degraded" \
    "service_health" \
    "warning" \
    "Service response time exceeds threshold" \
    "immediate" \
    "${deployment_id}"

  # Service restart required alert
  add_alert_rule "service_restart_required" \
    "service_health" \
    "warning" \
    "Service requires restart due to repeated failures" \
    "immediate" \
    "${deployment_id}"
}

setup_performance_alerts() {
  local deployment_id="$1"

  log_debug "Setting up performance alert rules"

  # High latency alert
  add_alert_rule "high_latency" \
    "performance" \
    "warning" \
    "Service latency exceeds threshold" \
    "immediate" \
    "${deployment_id}"

  # High error rate alert
  add_alert_rule "high_error_rate" \
    "performance" \
    "warning" \
    "Service error rate exceeds threshold" \
    "immediate" \
    "${deployment_id}"

  # Timeout alert
  add_alert_rule "request_timeout" \
    "performance" \
    "warning" \
    "Requests timing out" \
    "immediate" \
    "${deployment_id}"
}

setup_resource_alerts() {
  local deployment_id="$1"

  log_debug "Setting up resource alert rules"

  # High CPU alert
  add_alert_rule "high_cpu" \
    "resource" \
    "warning" \
    "CPU usage exceeds threshold" \
    "deferred" \
    "${deployment_id}"

  # High memory alert
  add_alert_rule "high_memory" \
    "resource" \
    "warning" \
    "Memory usage exceeds threshold" \
    "deferred" \
    "${deployment_id}"

  # Disk space alert
  add_alert_rule "low_disk_space" \
    "resource" \
    "critical" \
    "Available disk space below threshold" \
    "immediate" \
    "${deployment_id}"
}

setup_deployment_alerts() {
  local deployment_id="$1"

  log_debug "Setting up deployment alert rules"

  # Deployment failed alert
  add_alert_rule "deployment_failed" \
    "deployment" \
    "critical" \
    "Deployment failed" \
    "immediate" \
    "${deployment_id}"

  # Deployment slow alert
  add_alert_rule "deployment_slow" \
    "deployment" \
    "warning" \
    "Deployment taking longer than expected" \
    "deferred" \
    "${deployment_id}"

  # Post-deployment health check failed alert
  add_alert_rule "post_deploy_health_failed" \
    "deployment" \
    "critical" \
    "Post-deployment health checks failed" \
    "immediate" \
    "${deployment_id}"
}

# ============================================================================
# Alert Rule Management
# ============================================================================

add_alert_rule() {
  local name="$1"
  local category="$2"
  local severity="$3"
  local description="$4"
  local suppression="$5"
  local deployment_id="$6"

  log_debug "Adding alert rule: ${name}"

  local rule="{
    \"name\": \"${name}\",
    \"category\": \"${category}\",
    \"severity\": \"${severity}\",
    \"description\": \"${description}\",
    \"suppression_policy\": \"${suppression}\",
    \"deployment_id\": \"${deployment_id}\",
    \"enabled\": true,
    \"created_at\": \"$(date -Is)\"
  }"

  if ! jq -e . "${ALERT_RULES_FILE}" 2>/dev/null >/dev/null; then
    echo '{"rules":[]}' > "${ALERT_RULES_FILE}"
  fi

  jq ".rules += [${rule}]" "${ALERT_RULES_FILE}" > "${ALERT_RULES_FILE}.tmp"
  mv "${ALERT_RULES_FILE}.tmp" "${ALERT_RULES_FILE}"
}

# ============================================================================
# Threshold Configuration
# ============================================================================

setup_default_thresholds() {
  log_info "Setting up default alert thresholds"

  ensure_alert_directories

  # Initialize thresholds file
  if ! jq -e . "${ALERT_THRESHOLDS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"thresholds":{}}' > "${ALERT_THRESHOLDS_FILE}"
  fi

  # Service health thresholds
  configure_threshold_alert "llama-cpp" "response_time_ms" "5000" "warning"
  configure_threshold_alert "llama-cpp" "response_time_ms" "10000" "critical"

  # Resource thresholds
  configure_threshold_alert "system" "cpu_percent" "80" "warning"
  configure_threshold_alert "system" "cpu_percent" "95" "critical"
  configure_threshold_alert "system" "memory_percent" "85" "warning"
  configure_threshold_alert "system" "memory_percent" "95" "critical"
  configure_threshold_alert "system" "disk_percent" "80" "warning"
  configure_threshold_alert "system" "disk_percent" "90" "critical"

  # Error rate thresholds
  configure_threshold_alert "services" "error_rate_percent" "5" "warning"
  configure_threshold_alert "services" "error_rate_percent" "10" "critical"

  log_info "Default thresholds configured"
}

configure_threshold_alert() {
  local service="$1"
  local metric="$2"
  local threshold="$3"
  local severity="$4"

  log_debug "Configuring threshold: ${service}.${metric} = ${threshold} (${severity})"

  if ! jq -e . "${ALERT_THRESHOLDS_FILE}" 2>/dev/null >/dev/null; then
    echo '{"thresholds":{}}' > "${ALERT_THRESHOLDS_FILE}"
  fi

  local threshold_entry="{
    \"metric\": \"${metric}\",
    \"threshold\": ${threshold},
    \"severity\": \"${severity}\",
    \"configured_at\": \"$(date -Is)\"
  }"

  jq ".thresholds[\"${service}.${metric}.${severity}\"] = ${threshold_entry}" \
    "${ALERT_THRESHOLDS_FILE}" > "${ALERT_THRESHOLDS_FILE}.tmp"
  mv "${ALERT_THRESHOLDS_FILE}.tmp" "${ALERT_THRESHOLDS_FILE}"
}

# ============================================================================
# Notification Configuration
# ============================================================================

setup_notification_channels() {
  log_info "Setting up notification channels"

  ensure_alert_directories

  # Initialize notification config
  if ! jq -e . "${NOTIFICATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"channels":[]}' > "${NOTIFICATION_CONFIG_FILE}"
  fi

  # Dashboard channel
  add_notification_channel "dashboard" \
    "Push to dashboard alerts API" \
    "enabled"

  # Log channel
  add_notification_channel "syslog" \
    "Log alerts to system journal" \
    "enabled"

  # Webhook channel (configurable)
  add_notification_channel "webhook" \
    "Send alerts to configured webhook" \
    "disabled"

  log_info "Notification channels configured"
}

add_notification_channel() {
  local channel_name="$1"
  local description="$2"
  local status="$3"

  log_debug "Adding notification channel: ${channel_name}"

  local channel="{
    \"name\": \"${channel_name}\",
    \"description\": \"${description}\",
    \"status\": \"${status}\",
    \"created_at\": \"$(date -Is)\"
  }"

  if ! jq -e . "${NOTIFICATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"channels":[]}' > "${NOTIFICATION_CONFIG_FILE}"
  fi

  jq ".channels += [${channel}]" "${NOTIFICATION_CONFIG_FILE}" > "${NOTIFICATION_CONFIG_FILE}.tmp"
  mv "${NOTIFICATION_CONFIG_FILE}.tmp" "${NOTIFICATION_CONFIG_FILE}"
}

# ============================================================================
# Alert Suppression
# ============================================================================

setup_alert_suppression() {
  local deployment_id="$1"
  local suppress_for_seconds="${2:-300}"

  log_info "Setting up alert suppression for ${suppress_for_seconds}s (deployment: ${deployment_id})"

  # Create suppression record
  local suppression="{
    \"deployment_id\": \"${deployment_id}\",
    \"created_at\": \"$(date -Is)\",
    \"expires_at\": \"$(date -d "+${suppress_for_seconds} seconds" -Is)\",
    \"reason\": \"During deployment\"
  }"

  local suppress_file="${ALERT_CONFIG_DIR}/suppression.json"
  if ! jq -e . "${suppress_file}" 2>/dev/null >/dev/null; then
    echo '{"suppressions":[]}' > "${suppress_file}"
  fi

  jq ".suppressions += [${suppression}]" "${suppress_file}" > "${suppress_file}.tmp"
  mv "${suppress_file}.tmp" "${suppress_file}"
}

# ============================================================================
# Validation
# ============================================================================

validate_alert_config() {
  log_info "Validating alert configuration"

  ensure_alert_directories

  # Verify alert rules file
  if ! jq -e .rules "${ALERT_RULES_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid alert rules file: ${ALERT_RULES_FILE}"
    return 1
  fi

  # Verify thresholds file
  if ! jq -e .thresholds "${ALERT_THRESHOLDS_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid thresholds file: ${ALERT_THRESHOLDS_FILE}"
    return 1
  fi

  # Verify notification config
  if ! jq -e .channels "${NOTIFICATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid notification config file: ${NOTIFICATION_CONFIG_FILE}"
    return 1
  fi

  log_info "Alert configuration valid"
  return 0
}

get_alert_rules() {
  local deployment_id="${1:-}"

  if [[ ! -f "${ALERT_RULES_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  if [[ -n "${deployment_id}" ]]; then
    jq ".rules[] | select(.deployment_id == \"${deployment_id}\")" \
      "${ALERT_RULES_FILE}" 2>/dev/null || echo ""
  else
    jq '.rules[]' "${ALERT_RULES_FILE}" 2>/dev/null || echo ""
  fi
}

get_thresholds() {
  local metric_pattern="${1:-}"

  if [[ ! -f "${ALERT_THRESHOLDS_FILE}" ]]; then
    echo "{}"
    return 0
  fi

  if [[ -n "${metric_pattern}" ]]; then
    jq ".thresholds | with_entries(select(.key | contains(\"${metric_pattern}\")))" \
      "${ALERT_THRESHOLDS_FILE}" 2>/dev/null || echo "{}"
  else
    jq '.thresholds' "${ALERT_THRESHOLDS_FILE}" 2>/dev/null || echo "{}"
  fi
}

get_notification_channels() {
  if [[ ! -f "${NOTIFICATION_CONFIG_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  jq '.channels[]' "${NOTIFICATION_CONFIG_FILE}" 2>/dev/null || echo ""
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_alert_rules_for_deployment
export -f setup_service_health_alerts
export -f setup_performance_alerts
export -f setup_resource_alerts
export -f setup_deployment_alerts
export -f add_alert_rule
export -f setup_default_thresholds
export -f configure_threshold_alert
export -f setup_notification_channels
export -f add_notification_channel
export -f setup_alert_suppression
export -f validate_alert_config
export -f get_alert_rules
export -f get_thresholds
export -f get_notification_channels
