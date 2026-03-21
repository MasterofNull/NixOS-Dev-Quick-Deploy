#!/usr/bin/env bash
#
# Deployment Hooks System
# Extensible hook registration and execution for deployment lifecycle events
#
# Usage:
#   source deployment-hooks.sh
#   register_hook "pre_deployment" "security_scan" "/path/to/hook.sh"
#   register_hook "post_deployment" "compliance_check" "/path/to/hook.sh"
#   execute_hooks "pre_deployment" "deployment_id"
#   execute_hooks "post_deployment" "deployment_id"
#   list_hooks "pre_deployment"
#   remove_hook "pre_deployment" "security_scan"

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

# Hook configuration
HOOKS_DIR="${HOOKS_DIR:-${REPO_ROOT}/.agent/deployment/hooks}"
HOOKS_REGISTRY_FILE="${HOOKS_REGISTRY_FILE:-${HOOKS_DIR}/registry.json}"

# Hook execution configuration
HOOK_TIMEOUT="${HOOK_TIMEOUT:-300}"  # 5 minutes default timeout
HOOK_FAIL_BEHAVIOR="${HOOK_FAIL_BEHAVIOR:-abort}"  # abort, warn, ignore

# Supported hook types
HOOK_TYPES=(
  "pre_deployment"
  "post_deployment"
  "pre_service_start"
  "post_service_start"
  "pre_rollback"
  "post_rollback"
)

# Logging helpers
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[deployment-hooks] DEBUG: $*" >&2
}

log_info() {
  echo "[deployment-hooks] INFO: $*" >&2
}

log_warn() {
  echo "[deployment-hooks] WARN: $*" >&2
}

log_error() {
  echo "[deployment-hooks] ERROR: $*" >&2
}

# ============================================================================
# Initialization
# ============================================================================

ensure_hooks_directories() {
  mkdir -p "${HOOKS_DIR}"
  mkdir -p "${HOOKS_DIR}/scripts"

  # Initialize hooks registry
  if [[ ! -f "${HOOKS_REGISTRY_FILE}" ]]; then
    cat > "${HOOKS_REGISTRY_FILE}" <<'EOF'
{
  "hooks": {
    "pre_deployment": [],
    "post_deployment": [],
    "pre_service_start": [],
    "post_service_start": [],
    "pre_rollback": [],
    "post_rollback": []
  },
  "last_updated": ""
}
EOF
  fi

  log_debug "Hooks directories ensured"
}

# ============================================================================
# Hook Registration
# ============================================================================

register_hook() {
  local hook_type="$1"
  local hook_name="$2"
  local hook_script="$3"
  local hook_priority="${4:-50}"  # Default priority: 50 (1-100, lower = earlier)

  # Validate hook type
  if ! is_valid_hook_type "${hook_type}"; then
    log_error "Invalid hook type: ${hook_type}"
    log_error "Valid types: ${HOOK_TYPES[*]}"
    return 1
  fi

  # Validate hook script exists
  if [[ ! -f "${hook_script}" ]]; then
    log_error "Hook script not found: ${hook_script}"
    return 1
  fi

  # Make script executable
  chmod +x "${hook_script}"

  log_info "Registering hook: ${hook_type}/${hook_name}"

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Check if hook already exists
  local existing_hook
  existing_hook=$(echo "${registry}" | jq -r \
    --arg type "${hook_type}" \
    --arg name "${hook_name}" \
    '.hooks[$type][] | select(.name == $name) | .name' 2>/dev/null || echo "")

  if [[ -n "${existing_hook}" ]]; then
    log_warn "Hook ${hook_type}/${hook_name} already registered, updating..."
    remove_hook "${hook_type}" "${hook_name}"
    registry=$(cat "${HOOKS_REGISTRY_FILE}")
  fi

  # Add hook to registry
  local hook_entry
  hook_entry=$(jq -n \
    --arg name "${hook_name}" \
    --arg script "${hook_script}" \
    --arg priority "${hook_priority}" \
    --arg registered "$(date -Is)" \
    '{
      name: $name,
      script: $script,
      priority: ($priority | tonumber),
      registered: $registered,
      enabled: true
    }')

  registry=$(echo "${registry}" | jq \
    --arg type "${hook_type}" \
    --argjson hook "${hook_entry}" \
    '.hooks[$type] += [$hook] | .hooks[$type] |= sort_by(.priority) | .last_updated = now | strftime("%Y-%m-%dT%H:%M:%S%z")')

  # Save registry
  echo "${registry}" > "${HOOKS_REGISTRY_FILE}"

  log_info "Hook registered successfully: ${hook_type}/${hook_name} (priority: ${hook_priority})"
}

remove_hook() {
  local hook_type="$1"
  local hook_name="$2"

  if ! is_valid_hook_type "${hook_type}"; then
    log_error "Invalid hook type: ${hook_type}"
    return 1
  fi

  log_info "Removing hook: ${hook_type}/${hook_name}"

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Remove hook
  registry=$(echo "${registry}" | jq \
    --arg type "${hook_type}" \
    --arg name "${hook_name}" \
    '.hooks[$type] = [.hooks[$type][] | select(.name != $name)] | .last_updated = now | strftime("%Y-%m-%dT%H:%M:%S%z")')

  # Save registry
  echo "${registry}" > "${HOOKS_REGISTRY_FILE}"

  log_info "Hook removed: ${hook_type}/${hook_name}"
}

enable_hook() {
  local hook_type="$1"
  local hook_name="$2"

  update_hook_status "${hook_type}" "${hook_name}" true
}

disable_hook() {
  local hook_type="$1"
  local hook_name="$2"

  update_hook_status "${hook_type}" "${hook_name}" false
}

update_hook_status() {
  local hook_type="$1"
  local hook_name="$2"
  local enabled="$3"

  if ! is_valid_hook_type "${hook_type}"; then
    log_error "Invalid hook type: ${hook_type}"
    return 1
  fi

  log_info "$(if [[ "${enabled}" == "true" ]]; then echo "Enabling"; else echo "Disabling"; fi) hook: ${hook_type}/${hook_name}"

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Update hook status
  registry=$(echo "${registry}" | jq \
    --arg type "${hook_type}" \
    --arg name "${hook_name}" \
    --argjson enabled "${enabled}" \
    '.hooks[$type] = [.hooks[$type][] | if .name == $name then .enabled = $enabled else . end] | .last_updated = now | strftime("%Y-%m-%dT%H:%M:%S%z")')

  # Save registry
  echo "${registry}" > "${HOOKS_REGISTRY_FILE}"
}

# ============================================================================
# Hook Execution
# ============================================================================

execute_hooks() {
  local hook_type="$1"
  local deployment_id="$2"
  shift 2
  local extra_args=("$@")

  if ! is_valid_hook_type "${hook_type}"; then
    log_error "Invalid hook type: ${hook_type}"
    return 1
  fi

  log_info "Executing ${hook_type} hooks for deployment: ${deployment_id}"

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Get hooks for this type (sorted by priority)
  local hooks
  hooks=$(echo "${registry}" | jq -r \
    --arg type "${hook_type}" \
    '.hooks[$type][] | select(.enabled == true) | @json')

  if [[ -z "${hooks}" ]]; then
    log_debug "No ${hook_type} hooks registered"
    return 0
  fi

  local total_hooks
  total_hooks=$(echo "${hooks}" | wc -l)
  local executed=0
  local failed=0

  log_info "Found ${total_hooks} ${hook_type} hook(s) to execute"

  # Execute each hook
  while IFS= read -r hook_json; do
    local hook_name
    hook_name=$(echo "${hook_json}" | jq -r '.name')
    local hook_script
    hook_script=$(echo "${hook_json}" | jq -r '.script')
    local hook_priority
    hook_priority=$(echo "${hook_json}" | jq -r '.priority')

    log_info "Executing hook: ${hook_name} (priority: ${hook_priority})"

    # Execute hook with timeout
    local hook_exit_code=0
    local hook_output
    local hook_start_time
    hook_start_time=$(date +%s)

    if hook_output=$(timeout "${HOOK_TIMEOUT}" "${hook_script}" "${deployment_id}" "${extra_args[@]}" 2>&1); then
      hook_exit_code=0
    else
      hook_exit_code=$?
    fi

    local hook_end_time
    hook_end_time=$(date +%s)
    local hook_duration=$((hook_end_time - hook_start_time))

    if [[ ${hook_exit_code} -eq 0 ]]; then
      log_info "Hook ${hook_name} completed successfully in ${hook_duration}s"
      executed=$((executed + 1))
    else
      failed=$((failed + 1))

      if [[ ${hook_exit_code} -eq 124 ]]; then
        log_error "Hook ${hook_name} timed out after ${HOOK_TIMEOUT}s"
      else
        log_error "Hook ${hook_name} failed with exit code ${hook_exit_code}"
      fi

      # Show hook output if verbose
      if [[ "${VERBOSE:-0}" == "1" ]] && [[ -n "${hook_output}" ]]; then
        log_debug "Hook output:"
        echo "${hook_output}" | while IFS= read -r line; do
          log_debug "  ${line}"
        done
      fi

      # Handle failure based on configured behavior
      case "${HOOK_FAIL_BEHAVIOR}" in
        abort)
          log_error "Aborting hook execution due to failure (HOOK_FAIL_BEHAVIOR=abort)"
          return 1
          ;;
        warn)
          log_warn "Continuing hook execution despite failure (HOOK_FAIL_BEHAVIOR=warn)"
          ;;
        ignore)
          log_debug "Ignoring hook failure (HOOK_FAIL_BEHAVIOR=ignore)"
          ;;
      esac
    fi
  done <<< "${hooks}"

  log_info "Hook execution complete: ${executed}/${total_hooks} succeeded, ${failed} failed"

  if [[ ${failed} -gt 0 ]] && [[ "${HOOK_FAIL_BEHAVIOR}" == "abort" ]]; then
    return 1
  fi

  return 0
}

execute_single_hook() {
  local hook_type="$1"
  local hook_name="$2"
  local deployment_id="$3"
  shift 3
  local extra_args=("$@")

  log_info "Executing single hook: ${hook_type}/${hook_name}"

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Get hook
  local hook
  hook=$(echo "${registry}" | jq -r \
    --arg type "${hook_type}" \
    --arg name "${hook_name}" \
    '.hooks[$type][] | select(.name == $name) | @json')

  if [[ -z "${hook}" ]]; then
    log_error "Hook not found: ${hook_type}/${hook_name}"
    return 1
  fi

  # Check if enabled
  local enabled
  enabled=$(echo "${hook}" | jq -r '.enabled')
  if [[ "${enabled}" != "true" ]]; then
    log_warn "Hook is disabled: ${hook_type}/${hook_name}"
    return 1
  fi

  # Execute hook
  local hook_script
  hook_script=$(echo "${hook}" | jq -r '.script')

  log_info "Executing: ${hook_script}"

  if timeout "${HOOK_TIMEOUT}" "${hook_script}" "${deployment_id}" "${extra_args[@]}"; then
    log_info "Hook completed successfully"
    return 0
  else
    local exit_code=$?
    log_error "Hook failed with exit code ${exit_code}"
    return ${exit_code}
  fi
}

# ============================================================================
# Hook Management
# ============================================================================

list_hooks() {
  local hook_type="${1:-all}"

  ensure_hooks_directories

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  if [[ "${hook_type}" == "all" ]]; then
    # List all hooks
    echo "Registered Hooks:"
    for type in "${HOOK_TYPES[@]}"; do
      echo ""
      echo "${type}:"
      echo "${registry}" | jq -r \
        --arg type "${type}" \
        '.hooks[$type][] | "  [\(.priority)] \(.name) - \(if .enabled then "enabled" else "disabled" end) - \(.script)"'
    done
  else
    # List hooks for specific type
    if ! is_valid_hook_type "${hook_type}"; then
      log_error "Invalid hook type: ${hook_type}"
      return 1
    fi

    echo "Registered ${hook_type} Hooks:"
    echo "${registry}" | jq -r \
      --arg type "${hook_type}" \
      '.hooks[$type][] | "  [\(.priority)] \(.name) - \(if .enabled then "enabled" else "disabled" end) - \(.script)"'
  fi
}

get_hook_info() {
  local hook_type="$1"
  local hook_name="$2"

  if ! is_valid_hook_type "${hook_type}"; then
    log_error "Invalid hook type: ${hook_type}"
    return 1
  fi

  # Load registry
  local registry
  registry=$(cat "${HOOKS_REGISTRY_FILE}")

  # Get hook
  local hook
  hook=$(echo "${registry}" | jq \
    --arg type "${hook_type}" \
    --arg name "${hook_name}" \
    '.hooks[$type][] | select(.name == $name)')

  if [[ -z "${hook}" ]] || [[ "${hook}" == "null" ]]; then
    log_error "Hook not found: ${hook_type}/${hook_name}"
    return 1
  fi

  echo "${hook}"
}

# ============================================================================
# Built-in Security Hooks
# ============================================================================

register_builtin_security_hooks() {
  local security_lib_dir="${REPO_ROOT}/lib/security"

  log_info "Registering built-in security hooks"

  # Pre-deployment security gate hook
  if [[ -f "${security_lib_dir}/security-workflow-validator.sh" ]]; then
    # Create wrapper script
    cat > "${HOOKS_DIR}/scripts/pre-deployment-security-gate.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${REPO_ROOT}/lib/security/security-workflow-validator.sh"

deployment_id="$1"

echo "[pre-deployment-security-gate] Running pre-deployment security gate"
run_pre_deployment_security_gate "${deployment_id}"
EOF

    chmod +x "${HOOKS_DIR}/scripts/pre-deployment-security-gate.sh"

    register_hook "pre_deployment" "security_gate" \
      "${HOOKS_DIR}/scripts/pre-deployment-security-gate.sh" 10
  fi

  # Post-deployment security verification hook
  if [[ -f "${security_lib_dir}/security-workflow-validator.sh" ]]; then
    # Create wrapper script
    cat > "${HOOKS_DIR}/scripts/post-deployment-security-verification.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${REPO_ROOT}/lib/security/security-workflow-validator.sh"

deployment_id="$1"

echo "[post-deployment-security-verification] Running post-deployment security verification"
run_post_deployment_security_verification "${deployment_id}"
EOF

    chmod +x "${HOOKS_DIR}/scripts/post-deployment-security-verification.sh"

    register_hook "post_deployment" "security_verification" \
      "${HOOKS_DIR}/scripts/post-deployment-security-verification.sh" 90
  fi

  # Pre-deployment audit logging hook
  cat > "${HOOKS_DIR}/scripts/pre-deployment-audit-log.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

deployment_id="$1"

echo "[pre-deployment-audit-log] Logging deployment start event"
python3 "${REPO_ROOT}/lib/security/audit-logger.py" \
  --action log \
  --event-type deployment \
  --event-action "started" \
  --actor "system" \
  --resource "deployment:${deployment_id}" \
  --severity info \
  --details "{\"phase\": \"pre_deployment\"}"
EOF

  chmod +x "${HOOKS_DIR}/scripts/pre-deployment-audit-log.sh"

  register_hook "pre_deployment" "audit_log" \
    "${HOOKS_DIR}/scripts/pre-deployment-audit-log.sh" 5

  # Post-deployment audit logging hook
  cat > "${HOOKS_DIR}/scripts/post-deployment-audit-log.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

deployment_id="$1"

echo "[post-deployment-audit-log] Logging deployment completion event"
python3 "${REPO_ROOT}/lib/security/audit-logger.py" \
  --action log \
  --event-type deployment \
  --event-action "completed" \
  --actor "system" \
  --resource "deployment:${deployment_id}" \
  --severity info \
  --details "{\"phase\": \"post_deployment\"}"
EOF

  chmod +x "${HOOKS_DIR}/scripts/post-deployment-audit-log.sh"

  register_hook "post_deployment" "audit_log" \
    "${HOOKS_DIR}/scripts/post-deployment-audit-log.sh" 95

  log_info "Built-in security hooks registered"
}

# ============================================================================
# Utilities
# ============================================================================

is_valid_hook_type() {
  local hook_type="$1"

  for valid_type in "${HOOK_TYPES[@]}"; do
    if [[ "${hook_type}" == "${valid_type}" ]]; then
      return 0
    fi
  done

  return 1
}

# ============================================================================
# Initialization
# ============================================================================

ensure_hooks_directories

log_debug "Deployment hooks system loaded"
