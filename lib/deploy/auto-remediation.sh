#!/usr/bin/env bash
#
# Deploy CLI - Automated Remediation Framework
# Remediation playbook registry with automatic execution and escalation
#
# Usage:
#   source auto-remediation.sh
#   setup_remediation_playbooks
#   execute_remediation_for_alert "alert_id" "service" "issue_type"
#   track_remediation_status "remediation_id"

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

# Remediation configuration paths
REMEDIATION_CONFIG_DIR="${REMEDIATION_CONFIG_DIR:-${REPO_ROOT}/.agent/remediation}"
PLAYBOOK_REGISTRY_FILE="${PLAYBOOK_REGISTRY_FILE:-${REMEDIATION_CONFIG_DIR}/playbooks.json}"
REMEDIATION_LOG_FILE="${REMEDIATION_LOG_FILE:-${REMEDIATION_CONFIG_DIR}/remediation-log.json}"
ESCALATION_CONFIG_FILE="${ESCALATION_CONFIG_FILE:-${REMEDIATION_CONFIG_DIR}/escalation-rules.json}"

# Enable/disable auto-remediation
AUTO_REMEDIATION_ENABLED="${AUTO_REMEDIATION_ENABLED:-true}"
AUTO_REMEDIATION_TIMEOUT="${AUTO_REMEDIATION_TIMEOUT:-300}"

# Logging helpers
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[auto-remediation] DEBUG: $*" >&2
}

log_info() {
  echo "[auto-remediation] INFO: $*" >&2
}

log_warn() {
  echo "[auto-remediation] WARN: $*" >&2
}

log_error() {
  echo "[auto-remediation] ERROR: $*" >&2
}

# ============================================================================
# Remediation Setup
# ============================================================================

ensure_remediation_directories() {
  mkdir -p "${REMEDIATION_CONFIG_DIR}"
  log_debug "Remediation directories ensured at ${REMEDIATION_CONFIG_DIR}"
}

setup_remediation_playbooks() {
  log_info "Setting up remediation playbooks"

  ensure_remediation_directories

  # Initialize playbook registry
  if ! jq -e . "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null >/dev/null; then
    echo '{"playbooks":[]}' > "${PLAYBOOK_REGISTRY_FILE}"
  fi

  # Register default playbooks
  register_service_restart_playbook
  register_service_health_check_playbook
  register_deployment_rollback_playbook
  register_resource_cleanup_playbook
  register_configuration_fix_playbook

  # Initialize remediation log
  if ! jq -e . "${REMEDIATION_LOG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"remediations":[]}' > "${REMEDIATION_LOG_FILE}"
  fi

  # Setup escalation rules
  setup_escalation_rules

  log_info "Remediation playbooks registered"
}

# ============================================================================
# Playbook Registry
# ============================================================================

register_service_restart_playbook() {
  log_debug "Registering service restart playbook"

  add_playbook_to_registry "service_restart" \
    "Restart unresponsive service" \
    "service_health" \
    "auto" \
    "restart_service"
}

register_service_health_check_playbook() {
  log_debug "Registering service health check playbook"

  add_playbook_to_registry "service_health_check" \
    "Run comprehensive service health checks" \
    "service_health" \
    "auto" \
    "run_health_checks"
}

register_deployment_rollback_playbook() {
  log_debug "Registering deployment rollback playbook"

  add_playbook_to_registry "deployment_rollback" \
    "Rollback to previous stable deployment" \
    "deployment_failure" \
    "manual" \
    "execute_rollback"
}

register_resource_cleanup_playbook() {
  log_debug "Registering resource cleanup playbook"

  add_playbook_to_registry "resource_cleanup" \
    "Clean up unused resources and cache" \
    "resource_exhaustion" \
    "auto" \
    "cleanup_resources"
}

register_configuration_fix_playbook() {
  log_debug "Registering configuration fix playbook"

  add_playbook_to_registry "config_fix" \
    "Apply known configuration fixes" \
    "configuration_error" \
    "manual" \
    "apply_config_fix"
}

add_playbook_to_registry() {
  local name="$1"
  local description="$2"
  local issue_type="$3"
  local execution_mode="$4"
  local action="$5"

  log_debug "Adding playbook to registry: ${name}"

  local playbook="{
    \"name\": \"${name}\",
    \"description\": \"${description}\",
    \"issue_type\": \"${issue_type}\",
    \"execution_mode\": \"${execution_mode}\",
    \"action\": \"${action}\",
    \"enabled\": true,
    \"registered_at\": \"$(date -Is)\"
  }"

  if ! jq -e . "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null >/dev/null; then
    echo '{"playbooks":[]}' > "${PLAYBOOK_REGISTRY_FILE}"
  fi

  jq ".playbooks += [${playbook}]" "${PLAYBOOK_REGISTRY_FILE}" > "${PLAYBOOK_REGISTRY_FILE}.tmp"
  mv "${PLAYBOOK_REGISTRY_FILE}.tmp" "${PLAYBOOK_REGISTRY_FILE}"
}

# ============================================================================
# Remediation Execution
# ============================================================================

execute_remediation_for_alert() {
  local alert_id="$1"
  local service="$2"
  local issue_type="$3"
  local remediation_id="remediation-${alert_id}-$(date +%s)"

  if [[ "${AUTO_REMEDIATION_ENABLED}" != "true" ]]; then
    log_warn "Auto-remediation disabled, skipping for alert ${alert_id}"
    return 0
  fi

  log_info "Executing remediation for alert ${alert_id} (service: ${service}, issue: ${issue_type})"

  # Find appropriate playbook
  local playbook
  playbook="$(find_playbook_for_issue "${issue_type}" "auto")" || true

  if [[ -z "${playbook}" ]]; then
    log_warn "No auto playbook found for issue type ${issue_type}, escalating"
    escalate_alert "${alert_id}" "${service}" "${issue_type}"
    return 1
  fi

  # Extract action from playbook
  local action
  action="$(echo "${playbook}" | jq -r '.action')"

  # Log remediation start
  record_remediation_start "${remediation_id}" "${alert_id}" "${service}" "${action}"

  # Execute remediation based on action type
  local result="failed"
  case "${action}" in
    restart_service)
      result=$(restart_service_remediation "${service}" "${remediation_id}")
      ;;
    run_health_checks)
      result=$(run_health_checks_remediation "${service}" "${remediation_id}")
      ;;
    cleanup_resources)
      result=$(cleanup_resources_remediation "${service}" "${remediation_id}")
      ;;
    *)
      log_warn "Unknown remediation action: ${action}"
      result="skipped"
      ;;
  esac

  # Log remediation result
  record_remediation_result "${remediation_id}" "${result}"

  if [[ "${result}" == "success" ]]; then
    log_info "Remediation succeeded: ${remediation_id}"
    return 0
  else
    log_warn "Remediation failed or skipped: ${remediation_id}, escalating"
    escalate_alert "${alert_id}" "${service}" "${issue_type}"
    return 1
  fi
}

find_playbook_for_issue() {
  local issue_type="$1"
  local execution_mode="${2:-}"

  if [[ ! -f "${PLAYBOOK_REGISTRY_FILE}" ]]; then
    return 1
  fi

  local query=".playbooks[] | select(.issue_type == \"${issue_type}\" and .enabled == true"
  if [[ -n "${execution_mode}" ]]; then
    query="${query} and .execution_mode == \"${execution_mode}\""
  fi
  query="${query})"

  jq -e "${query}" "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null || return 1
}

# ============================================================================
# Remediation Actions
# ============================================================================

restart_service_remediation() {
  local service="$1"
  local remediation_id="$2"

  log_info "Attempting service restart: ${service} (${remediation_id})"

  # Record action
  record_remediation_action "${remediation_id}" "restart_service" "started"

  # Use systemctl to restart if available
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl restart "${service}" 2>&1 | tee -a "${REMEDIATION_CONFIG_DIR}/${remediation_id}.log"; then
      record_remediation_action "${remediation_id}" "restart_service" "success"
      sleep 2
      echo "success"
      return 0
    else
      record_remediation_action "${remediation_id}" "restart_service" "failed"
      echo "failed"
      return 1
    fi
  else
    log_warn "systemctl not available, cannot restart ${service}"
    echo "skipped"
    return 1
  fi
}

run_health_checks_remediation() {
  local service="$1"
  local remediation_id="$2"

  log_info "Running health checks: ${service} (${remediation_id})"

  record_remediation_action "${remediation_id}" "health_check" "started"

  # Run health check
  if [[ -f "${REPO_ROOT}/lib/deploy/parallel-health-checks.sh" ]]; then
    if bash -c "source ${REPO_ROOT}/lib/deploy/parallel-health-checks.sh; wait_for_service_ready '${service}' 'http://localhost:8080/health'" 2>&1 | tee -a "${REMEDIATION_CONFIG_DIR}/${remediation_id}.log"; then
      record_remediation_action "${remediation_id}" "health_check" "success"
      echo "success"
      return 0
    fi
  fi

  record_remediation_action "${remediation_id}" "health_check" "failed"
  echo "failed"
  return 1
}

cleanup_resources_remediation() {
  local service="$1"
  local remediation_id="$2"

  log_info "Cleaning up resources: ${service} (${remediation_id})"

  record_remediation_action "${remediation_id}" "resource_cleanup" "started"

  # Clear caches and temporary data
  local cleanup_dirs=(
    "/tmp"
    "${REPO_ROOT}/.cache"
  )

  for dir in "${cleanup_dirs[@]}"; do
    if [[ -d "${dir}" ]]; then
      log_debug "Cleaning up: ${dir}"
      find "${dir}" -type f -atime +7 -delete 2>/dev/null || true
    fi
  done

  record_remediation_action "${remediation_id}" "resource_cleanup" "success"
  echo "success"
  return 0
}

# ============================================================================
# Escalation
# ============================================================================

setup_escalation_rules() {
  log_debug "Setting up escalation rules"

  ensure_remediation_directories

  if ! jq -e . "${ESCALATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"rules":[]}' > "${ESCALATION_CONFIG_FILE}"
  fi

  # Add escalation rule for critical issues
  add_escalation_rule "critical_immediate" \
    "critical" \
    "immediate" \
    "Log alert and notify operators"

  # Add escalation rule for failed remediations
  add_escalation_rule "remediation_failed" \
    "warning" \
    "deferred" \
    "Manual review required"
}

add_escalation_rule() {
  local rule_name="$1"
  local severity="$2"
  local timing="$3"
  local action="$4"

  local rule="{
    \"name\": \"${rule_name}\",
    \"severity\": \"${severity}\",
    \"escalation_timing\": \"${timing}\",
    \"action\": \"${action}\",
    \"created_at\": \"$(date -Is)\"
  }"

  if ! jq -e . "${ESCALATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"rules":[]}' > "${ESCALATION_CONFIG_FILE}"
  fi

  jq ".rules += [${rule}]" "${ESCALATION_CONFIG_FILE}" > "${ESCALATION_CONFIG_FILE}.tmp"
  mv "${ESCALATION_CONFIG_FILE}.tmp" "${ESCALATION_CONFIG_FILE}"
}

escalate_alert() {
  local alert_id="$1"
  local service="$2"
  local issue_type="$3"

  log_warn "Escalating alert ${alert_id} (service: ${service}, issue: ${issue_type})"

  local escalation="{
    \"alert_id\": \"${alert_id}\",
    \"service\": \"${service}\",
    \"issue_type\": \"${issue_type}\",
    \"escalated_at\": \"$(date -Is)\",
    \"requires_manual_intervention\": true
  }"

  local escalation_file="${REMEDIATION_CONFIG_DIR}/escalations.json"
  if ! jq -e . "${escalation_file}" 2>/dev/null >/dev/null; then
    echo '{"escalations":[]}' > "${escalation_file}"
  fi

  jq ".escalations += [${escalation}]" "${escalation_file}" > "${escalation_file}.tmp"
  mv "${escalation_file}.tmp" "${escalation_file}"

  # Log escalation in syslog if available
  if command -v logger >/dev/null 2>&1; then
    logger -t "auto-remediation" -p "user.warning" "Escalated alert ${alert_id}: ${issue_type} on ${service}"
  fi
}

# ============================================================================
# Status Tracking
# ============================================================================

record_remediation_start() {
  local remediation_id="$1"
  local alert_id="$2"
  local service="$3"
  local action="$4"

  log_debug "Recording remediation start: ${remediation_id}"

  local entry="{
    \"remediation_id\": \"${remediation_id}\",
    \"alert_id\": \"${alert_id}\",
    \"service\": \"${service}\",
    \"action\": \"${action}\",
    \"started_at\": \"$(date -Is)\",
    \"status\": \"in_progress\"
  }"

  if ! jq -e . "${REMEDIATION_LOG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"remediations":[]}' > "${REMEDIATION_LOG_FILE}"
  fi

  jq ".remediations += [${entry}]" "${REMEDIATION_LOG_FILE}" > "${REMEDIATION_LOG_FILE}.tmp"
  mv "${REMEDIATION_LOG_FILE}.tmp" "${REMEDIATION_LOG_FILE}"
}

record_remediation_result() {
  local remediation_id="$1"
  local result="$2"

  log_debug "Recording remediation result: ${remediation_id} = ${result}"

  if ! jq -e . "${REMEDIATION_LOG_FILE}" 2>/dev/null >/dev/null; then
    echo '{"remediations":[]}' > "${REMEDIATION_LOG_FILE}"
  fi

  jq ".remediations[] |= if .remediation_id == \"${remediation_id}\" then .status = \"${result}\" | .completed_at = \"$(date -Is)\" else . end" \
    "${REMEDIATION_LOG_FILE}" > "${REMEDIATION_LOG_FILE}.tmp"
  mv "${REMEDIATION_LOG_FILE}.tmp" "${REMEDIATION_LOG_FILE}"
}

record_remediation_action() {
  local remediation_id="$1"
  local action="$2"
  local status="$3"

  log_debug "Recording action: ${remediation_id}: ${action} = ${status}"

  local action_log="${REMEDIATION_CONFIG_DIR}/${remediation_id}.actions"
  echo "$(date -Is) - ${action}: ${status}" >> "${action_log}"
}

track_remediation_status() {
  local remediation_id="$1"

  if [[ ! -f "${REMEDIATION_LOG_FILE}" ]]; then
    echo "not_found"
    return 1
  fi

  jq -r ".remediations[] | select(.remediation_id == \"${remediation_id}\") | .status" \
    "${REMEDIATION_LOG_FILE}" 2>/dev/null || echo "not_found"
}

# ============================================================================
# Validation
# ============================================================================

validate_remediation_config() {
  log_info "Validating remediation configuration"

  ensure_remediation_directories

  if ! jq -e .playbooks "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid playbook registry: ${PLAYBOOK_REGISTRY_FILE}"
    return 1
  fi

  if ! jq -e .rules "${ESCALATION_CONFIG_FILE}" 2>/dev/null >/dev/null; then
    log_error "Invalid escalation config: ${ESCALATION_CONFIG_FILE}"
    return 1
  fi

  log_info "Remediation configuration valid"
  return 0
}

get_playbooks() {
  local issue_type="${1:-}"

  if [[ ! -f "${PLAYBOOK_REGISTRY_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  if [[ -n "${issue_type}" ]]; then
    jq ".playbooks[] | select(.issue_type == \"${issue_type}\")" \
      "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null || echo ""
  else
    jq '.playbooks[]' "${PLAYBOOK_REGISTRY_FILE}" 2>/dev/null || echo ""
  fi
}

get_remediation_log() {
  local alert_id="${1:-}"

  if [[ ! -f "${REMEDIATION_LOG_FILE}" ]]; then
    echo "[]"
    return 0
  fi

  if [[ -n "${alert_id}" ]]; then
    jq ".remediations[] | select(.alert_id == \"${alert_id}\")" \
      "${REMEDIATION_LOG_FILE}" 2>/dev/null || echo ""
  else
    jq '.remediations[]' "${REMEDIATION_LOG_FILE}" 2>/dev/null || echo ""
  fi
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_remediation_playbooks
export -f execute_remediation_for_alert
export -f find_playbook_for_issue
export -f restart_service_remediation
export -f run_health_checks_remediation
export -f cleanup_resources_remediation
export -f setup_escalation_rules
export -f escalate_alert
export -f track_remediation_status
export -f validate_remediation_config
export -f get_playbooks
export -f get_remediation_log
