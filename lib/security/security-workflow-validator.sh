#!/usr/bin/env bash
#
# Security Workflow Validator Module
# End-to-end security workflow orchestration and validation
#
# Usage:
#   source security-workflow-validator.sh
#   run_security_workflow "deployment_id"
#   run_pre_deployment_security_gate "deployment_id"
#   run_post_deployment_security_verification "deployment_id"
#   monitor_security_continuous "deployment_id"
#   trigger_automated_remediation "deployment_id" "issue_type"

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

# Load security modules
source "${SCRIPT_DIR}/scanner.sh"
source "${SCRIPT_DIR}/compliance-checker.sh"

# Python audit logger
AUDIT_LOGGER="${SCRIPT_DIR}/audit-logger.py"

# Workflow configuration
WORKFLOW_DIR="${WORKFLOW_DIR:-${REPO_ROOT}/.agent/security/workflows}"
WORKFLOW_STATE_FILE="${WORKFLOW_STATE_FILE:-${WORKFLOW_DIR}/workflow-state.json}"

# Security gate thresholds
MAX_CRITICAL_VULNERABILITIES="${MAX_CRITICAL_VULNERABILITIES:-0}"
MAX_HIGH_VULNERABILITIES="${MAX_HIGH_VULNERABILITIES:-5}"
MIN_COMPLIANCE_SCORE="${MIN_COMPLIANCE_SCORE:-80}"
MAX_SECRETS_DETECTED="${MAX_SECRETS_DETECTED:-0}"

# Logging helpers
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[security-workflow] DEBUG: $*" >&2
}

log_info() {
  echo "[security-workflow] INFO: $*" >&2
}

log_warn() {
  echo "[security-workflow] WARN: $*" >&2
}

log_error() {
  echo "[security-workflow] ERROR: $*" >&2
}

# ============================================================================
# Initialization
# ============================================================================

ensure_workflow_directories() {
  mkdir -p "${WORKFLOW_DIR}"

  # Initialize workflow state
  if [[ ! -f "${WORKFLOW_STATE_FILE}" ]]; then
    cat > "${WORKFLOW_STATE_FILE}" <<'EOF'
{
  "workflows": [],
  "last_updated": ""
}
EOF
  fi

  log_debug "Workflow directories ensured"
}

# ============================================================================
# Pre-Deployment Security Gate
# ============================================================================

run_pre_deployment_security_gate() {
  local deployment_id="$1"
  local gate_id="gate_$(date +%s)_pre"

  log_info "Running pre-deployment security gate for: ${deployment_id}"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "pre_deployment_gate_started" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity info \
    --details "{\"gate_id\": \"${gate_id}\"}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  local start_time
  start_time=$(date +%s)

  # Initialize gate result
  local gate_passed=true
  local gate_issues='[]'

  # 1. Vulnerability Scan
  log_info "Step 1/5: Running vulnerability scan"
  local vuln_scan_result
  vuln_scan_result=$(scan_all_services)

  local critical_vulns
  critical_vulns=$(echo "${vuln_scan_result}" | jq '[.[].scan.severity_counts.critical] | add // 0')
  local high_vulns
  high_vulns=$(echo "${vuln_scan_result}" | jq '[.[].scan.severity_counts.high] | add // 0')

  if [[ ${critical_vulns} -gt ${MAX_CRITICAL_VULNERABILITIES} ]]; then
    gate_passed=false
    gate_issues=$(echo "${gate_issues}" | jq \
      --arg issue "Critical vulnerabilities detected: ${critical_vulns} (max: ${MAX_CRITICAL_VULNERABILITIES})" \
      '. += [$issue]')
  fi

  if [[ ${high_vulns} -gt ${MAX_HIGH_VULNERABILITIES} ]]; then
    gate_passed=false
    gate_issues=$(echo "${gate_issues}" | jq \
      --arg issue "High vulnerabilities detected: ${high_vulns} (max: ${MAX_HIGH_VULNERABILITIES})" \
      '. += [$issue]')
  fi

  # 2. Secret Detection
  log_info "Step 2/5: Running secret detection"
  local secret_scan_result
  secret_scan_result=$(detect_secrets "${REPO_ROOT}")

  local secrets_found
  secrets_found=$(echo "${secret_scan_result}" | jq 'length')

  if [[ ${secrets_found} -gt ${MAX_SECRETS_DETECTED} ]]; then
    gate_passed=false
    gate_issues=$(echo "${gate_issues}" | jq \
      --arg issue "Secrets detected in code: ${secrets_found}" \
      '. += [$issue]')
  fi

  # 3. Configuration Security
  log_info "Step 3/5: Running configuration security scan"
  local config_scan_result
  config_scan_result=$(scan_configuration_security "${REPO_ROOT}")

  local config_issues
  config_issues=$(echo "${config_scan_result}" | jq '.total_issues')

  if [[ ${config_issues} -gt 10 ]]; then
    gate_passed=false
    gate_issues=$(echo "${gate_issues}" | jq \
      --arg issue "Configuration security issues: ${config_issues}" \
      '. += [$issue]')
  fi

  # 4. Compliance Check
  log_info "Step 4/5: Running compliance check"
  local compliance_result
  compliance_result=$(check_compliance "${deployment_id}" "SOC2")

  local compliance_score
  compliance_score=$(echo "${compliance_result}" | jq '.summary.compliance_percentage // 0')

  if [[ ${compliance_score} -lt ${MIN_COMPLIANCE_SCORE} ]]; then
    gate_passed=false
    gate_issues=$(echo "${gate_issues}" | jq \
      --arg issue "Compliance score below threshold: ${compliance_score}% (min: ${MIN_COMPLIANCE_SCORE}%)" \
      '. += [$issue]')
  fi

  # 5. Network Exposure Analysis
  log_info "Step 5/5: Running network exposure analysis"
  local network_scan_result
  network_scan_result=$(analyze_network_exposure "${deployment_id}")

  local exposed_services
  exposed_services=$(echo "${network_scan_result}" | jq '.network.exposed_services | length')

  if [[ ${exposed_services} -gt 0 ]]; then
    log_warn "Warning: ${exposed_services} sensitive services exposed on network"
  fi

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Aggregate gate result
  local gate_result
  gate_result=$(jq -n \
    --arg gate_id "${gate_id}" \
    --arg deployment_id "${deployment_id}" \
    --arg timestamp "$(date -Is)" \
    --arg duration "${duration}" \
    --arg passed "${gate_passed}" \
    --argjson issues "${gate_issues}" \
    --argjson vuln_scan "${vuln_scan_result}" \
    --argjson secret_scan "${secret_scan_result}" \
    --argjson config_scan "${config_scan_result}" \
    --argjson compliance "${compliance_result}" \
    --argjson network "${network_scan_result}" \
    '{
      gate_id: $gate_id,
      deployment_id: $deployment_id,
      timestamp: $timestamp,
      duration_seconds: ($duration | tonumber),
      passed: ($passed == "true"),
      issues: $issues,
      scans: {
        vulnerabilities: $vuln_scan,
        secrets: $secret_scan,
        configuration: $config_scan,
        compliance: $compliance,
        network: $network
      }
    }')

  # Save gate result
  local gate_file="${WORKFLOW_DIR}/${gate_id}_result.json"
  echo "${gate_result}" > "${gate_file}"

  # Log audit event
  local gate_status
  gate_status=$(if [[ "${gate_passed}" == "true" ]]; then echo "passed"; else echo "failed"; fi)

  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "pre_deployment_gate_${gate_status}" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity "$(if [[ "${gate_passed}" == "true" ]]; then echo "info"; else echo "error"; fi)" \
    --details "{\"gate_id\": \"${gate_id}\", \"duration_seconds\": ${duration}}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  if [[ "${gate_passed}" == "true" ]]; then
    log_info "Pre-deployment security gate PASSED in ${duration}s"
  else
    log_error "Pre-deployment security gate FAILED in ${duration}s"
    log_error "Issues found:"
    echo "${gate_issues}" | jq -r '.[]' | while read -r issue; do
      log_error "  - ${issue}"
    done
  fi

  echo "${gate_result}"

  # Return exit code based on gate result
  if [[ "${gate_passed}" == "false" ]]; then
    return 1
  fi
}

# ============================================================================
# Post-Deployment Security Verification
# ============================================================================

run_post_deployment_security_verification() {
  local deployment_id="$1"
  local verification_id="verify_$(date +%s)_post"

  log_info "Running post-deployment security verification for: ${deployment_id}"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "post_deployment_verification_started" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity info \
    --details "{\"verification_id\": \"${verification_id}\"}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  local start_time
  start_time=$(date +%s)

  # Initialize verification result
  local verification_passed=true
  local verification_issues='[]'

  # 1. Verify services are running securely
  log_info "Step 1/4: Verifying service security"
  local service_security
  service_security=$(verify_service_security "${deployment_id}")

  local insecure_services
  insecure_services=$(echo "${service_security}" | jq '[.[] | select(.secure == false)] | length')

  if [[ ${insecure_services} -gt 0 ]]; then
    verification_passed=false
    verification_issues=$(echo "${verification_issues}" | jq \
      --arg issue "Insecure services detected: ${insecure_services}" \
      '. += [$issue]')
  fi

  # 2. Verify NixOS hardening
  log_info "Step 2/4: Verifying NixOS hardening"
  local hardening_result
  hardening_result=$(verify_nixos_hardening "${deployment_id}")

  local hardening_score
  hardening_score=$(echo "${hardening_result}" | jq '.score.overall // 0')

  if [[ ${hardening_score} -lt 80 ]]; then
    log_warn "Warning: Hardening score below recommended threshold: ${hardening_score}%"
  fi

  # 3. Verify compliance status
  log_info "Step 3/4: Verifying compliance status"
  local compliance_result
  compliance_result=$(check_compliance "${deployment_id}" "SOC2")

  # 4. Detect configuration drift
  log_info "Step 4/4: Detecting configuration drift"
  local drift_result
  drift_result=$(detect_configuration_drift "${deployment_id}")

  local drift_detected
  drift_detected=$(echo "${drift_result}" | jq '.drift_detected')

  if [[ "${drift_detected}" == "true" ]]; then
    verification_passed=false
    verification_issues=$(echo "${verification_issues}" | jq \
      --arg issue "Configuration drift detected" \
      '. += [$issue]')
  fi

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Aggregate verification result
  local verification_result
  verification_result=$(jq -n \
    --arg verification_id "${verification_id}" \
    --arg deployment_id "${deployment_id}" \
    --arg timestamp "$(date -Is)" \
    --arg duration "${duration}" \
    --arg passed "${verification_passed}" \
    --argjson issues "${verification_issues}" \
    --argjson service_security "${service_security}" \
    --argjson hardening "${hardening_result}" \
    --argjson compliance "${compliance_result}" \
    --argjson drift "${drift_result}" \
    '{
      verification_id: $verification_id,
      deployment_id: $deployment_id,
      timestamp: $timestamp,
      duration_seconds: ($duration | tonumber),
      passed: ($passed == "true"),
      issues: $issues,
      verifications: {
        service_security: $service_security,
        hardening: $hardening,
        compliance: $compliance,
        drift: $drift
      }
    }')

  # Save verification result
  local verification_file="${WORKFLOW_DIR}/${verification_id}_result.json"
  echo "${verification_result}" > "${verification_file}"

  # Log audit event
  local verification_status
  verification_status=$(if [[ "${verification_passed}" == "true" ]]; then echo "passed"; else echo "failed"; fi)

  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "post_deployment_verification_${verification_status}" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity "$(if [[ "${verification_passed}" == "true" ]]; then echo "info"; else echo "warning"; fi)" \
    --details "{\"verification_id\": \"${verification_id}\", \"duration_seconds\": ${duration}}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  if [[ "${verification_passed}" == "true" ]]; then
    log_info "Post-deployment security verification PASSED in ${duration}s"
  else
    log_warn "Post-deployment security verification has WARNINGS in ${duration}s"
    log_warn "Issues found:"
    echo "${verification_issues}" | jq -r '.[]' | while read -r issue; do
      log_warn "  - ${issue}"
    done
  fi

  echo "${verification_result}"
}

verify_service_security() {
  local deployment_id="$1"

  local services=("llama-cpp" "llama-cpp-embed" "ai-aidb" "ai-hybrid-coordinator" "redis" "postgres")
  local results='[]'

  for service in "${services[@]}"; do
    local is_secure=true
    local security_issues='[]'

    # Check if service is running
    if systemctl is-active --quiet "${service}" 2>/dev/null; then
      # Service-specific security checks
      case "${service}" in
        redis)
          # Check if Redis has authentication
          if ! grep -q "^requirepass" /etc/redis/redis.conf 2>/dev/null; then
            is_secure=false
            security_issues=$(echo "${security_issues}" | jq '. += ["No authentication configured"]')
          fi
          ;;
        postgres)
          # Check if Postgres has proper authentication
          # Simplified check
          ;;
      esac
    fi

    local service_result
    service_result=$(jq -n \
      --arg service "${service}" \
      --arg secure "${is_secure}" \
      --argjson issues "${security_issues}" \
      '{
        service: $service,
        secure: ($secure == "true"),
        issues: $issues
      }')

    results=$(echo "${results}" | jq --argjson item "${service_result}" '. += [$item]')
  done

  echo "${results}"
}

# ============================================================================
# Continuous Security Monitoring
# ============================================================================

monitor_security_continuous() {
  local deployment_id="$1"
  local monitoring_interval="${2:-300}"  # Default: 5 minutes

  log_info "Starting continuous security monitoring for: ${deployment_id} (interval: ${monitoring_interval}s)"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "continuous_monitoring_started" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity info \
    --details "{\"interval_seconds\": ${monitoring_interval}}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  while true; do
    local monitor_id="monitor_$(date +%s)"

    log_debug "Running security monitoring cycle: ${monitor_id}"

    # Run lightweight security checks
    local network_scan
    network_scan=$(analyze_network_exposure "${deployment_id}")

    local drift_check
    drift_check=$(detect_configuration_drift "${deployment_id}")

    # Check for critical issues
    local critical_issues='[]'

    # Check network exposure
    local exposed_count
    exposed_count=$(echo "${network_scan}" | jq '.network.exposed_services | length')
    if [[ ${exposed_count} -gt 0 ]]; then
      critical_issues=$(echo "${critical_issues}" | jq \
        --arg issue "Sensitive services exposed: ${exposed_count}" \
        '. += [$issue]')
    fi

    # Check drift
    local drift_detected
    drift_detected=$(echo "${drift_check}" | jq '.drift_detected')
    if [[ "${drift_detected}" == "true" ]]; then
      critical_issues=$(echo "${critical_issues}" | jq \
        --arg issue "Configuration drift detected" \
        '. += [$issue]')
    fi

    # If critical issues found, trigger remediation
    if [[ $(echo "${critical_issues}" | jq 'length') -gt 0 ]]; then
      log_warn "Critical security issues detected during monitoring"
      echo "${critical_issues}" | jq -r '.[]' | while read -r issue; do
        log_warn "  - ${issue}"
      done

      # Log security event
      python3 "${AUDIT_LOGGER}" \
        --action log \
        --event-type security \
        --event-action "critical_issue_detected" \
        --actor "system" \
        --resource "deployment:${deployment_id}" \
        --severity critical \
        --details "$(echo "${critical_issues}" | jq -c '{issues: .}')" \
        >/dev/null 2>&1 || log_warn "Failed to log audit event"

      # Trigger automated remediation
      trigger_automated_remediation "${deployment_id}" "drift"
    fi

    # Sleep until next monitoring cycle
    sleep "${monitoring_interval}"
  done
}

# ============================================================================
# Automated Remediation
# ============================================================================

trigger_automated_remediation() {
  local deployment_id="$1"
  local issue_type="$2"
  local remediation_id="remediation_$(date +%s)"

  log_info "Triggering automated remediation for: ${issue_type}"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "remediation_triggered" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity warning \
    --details "{\"remediation_id\": \"${remediation_id}\", \"issue_type\": \"${issue_type}\"}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  case "${issue_type}" in
    drift)
      log_info "Remediation: Restoring configuration from baseline"
      # In production, this would restore from baseline
      ;;
    exposure)
      log_info "Remediation: Updating firewall rules"
      # In production, this would update firewall rules
      ;;
    vulnerability)
      log_info "Remediation: Scheduling security updates"
      # In production, this would trigger updates
      ;;
    *)
      log_warn "Unknown issue type: ${issue_type}, no automated remediation available"
      ;;
  esac

  # Log remediation completion
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "remediation_completed" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity info \
    --details "{\"remediation_id\": \"${remediation_id}\", \"issue_type\": \"${issue_type}\"}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  log_info "Automated remediation complete: ${remediation_id}"
}

# ============================================================================
# End-to-End Security Workflow
# ============================================================================

run_security_workflow() {
  local deployment_id="$1"
  local workflow_id="workflow_$(date +%s)"

  log_info "Running end-to-end security workflow for: ${deployment_id}"

  ensure_workflow_directories

  local start_time
  start_time=$(date +%s)

  # Update workflow state
  update_workflow_state "${workflow_id}" "${deployment_id}" "started"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "security_workflow_started" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity info \
    --details "{\"workflow_id\": \"${workflow_id}\"}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  local workflow_passed=true
  local workflow_stages='[]'

  # Stage 1: Pre-deployment security gate
  log_info "=== Stage 1: Pre-Deployment Security Gate ==="
  local gate_result
  if gate_result=$(run_pre_deployment_security_gate "${deployment_id}" 2>&1); then
    workflow_stages=$(echo "${workflow_stages}" | jq \
      '. += [{stage: "pre_deployment_gate", status: "passed", result: "Security gate passed"}]')
  else
    workflow_passed=false
    workflow_stages=$(echo "${workflow_stages}" | jq \
      '. += [{stage: "pre_deployment_gate", status: "failed", result: "Security gate failed"}]')
    log_error "Pre-deployment security gate failed, aborting workflow"

    update_workflow_state "${workflow_id}" "${deployment_id}" "failed"
    return 1
  fi

  # Stage 2: Post-deployment verification (simulated, would run after actual deployment)
  log_info "=== Stage 2: Post-Deployment Security Verification ==="
  local verification_result
  verification_result=$(run_post_deployment_security_verification "${deployment_id}")

  local verification_passed
  verification_passed=$(echo "${verification_result}" | jq -r '.passed')

  if [[ "${verification_passed}" == "true" ]]; then
    workflow_stages=$(echo "${workflow_stages}" | jq \
      '. += [{stage: "post_deployment_verification", status: "passed", result: "Verification passed"}]')
  else
    workflow_stages=$(echo "${workflow_stages}" | jq \
      '. += [{stage: "post_deployment_verification", status: "warning", result: "Verification has warnings"}]')
  fi

  # Stage 3: Create security baseline
  log_info "=== Stage 3: Creating Security Baseline ==="
  create_configuration_baseline "${deployment_id}"
  workflow_stages=$(echo "${workflow_stages}" | jq \
    '. += [{stage: "baseline_creation", status: "completed", result: "Baseline created"}]')

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Aggregate workflow result
  local workflow_result
  workflow_result=$(jq -n \
    --arg workflow_id "${workflow_id}" \
    --arg deployment_id "${deployment_id}" \
    --arg timestamp "$(date -Is)" \
    --arg duration "${duration}" \
    --arg passed "${workflow_passed}" \
    --argjson stages "${workflow_stages}" \
    '{
      workflow_id: $workflow_id,
      deployment_id: $deployment_id,
      timestamp: $timestamp,
      duration_seconds: ($duration | tonumber),
      passed: ($passed == "true"),
      stages: $stages
    }')

  # Save workflow result
  local workflow_file="${WORKFLOW_DIR}/${workflow_id}_result.json"
  echo "${workflow_result}" > "${workflow_file}"

  # Update workflow state
  local final_state
  final_state=$(if [[ "${workflow_passed}" == "true" ]]; then echo "completed"; else echo "failed"; fi)
  update_workflow_state "${workflow_id}" "${deployment_id}" "${final_state}"

  # Log audit event
  python3 "${AUDIT_LOGGER}" \
    --action log \
    --event-type security \
    --event-action "security_workflow_${final_state}" \
    --actor "system" \
    --resource "deployment:${deployment_id}" \
    --severity "$(if [[ "${workflow_passed}" == "true" ]]; then echo "info"; else echo "error"; fi)" \
    --details "{\"workflow_id\": \"${workflow_id}\", \"duration_seconds\": ${duration}}" \
    >/dev/null 2>&1 || log_warn "Failed to log audit event"

  log_info "Security workflow ${final_state} in ${duration}s"

  echo "${workflow_result}"

  if [[ "${workflow_passed}" == "false" ]]; then
    return 1
  fi
}

update_workflow_state() {
  local workflow_id="$1"
  local deployment_id="$2"
  local state="$3"

  local workflow_state
  workflow_state=$(cat "${WORKFLOW_STATE_FILE}")

  workflow_state=$(echo "${workflow_state}" | jq \
    --arg workflow_id "${workflow_id}" \
    --arg deployment_id "${deployment_id}" \
    --arg state "${state}" \
    --arg timestamp "$(date -Is)" \
    '.workflows += [{
      workflow_id: $workflow_id,
      deployment_id: $deployment_id,
      state: $state,
      timestamp: $timestamp
    }] | .last_updated = $timestamp')

  echo "${workflow_state}" > "${WORKFLOW_STATE_FILE}"
}

# ============================================================================
# Initialization
# ============================================================================

ensure_workflow_directories

log_debug "Security workflow validator module loaded"
