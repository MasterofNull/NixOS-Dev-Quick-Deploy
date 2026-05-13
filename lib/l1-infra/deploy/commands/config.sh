#!/usr/bin/env bash
#
# Deploy CLI - Config Command
# Configuration management

# ============================================================================
# Help Text
# ============================================================================

help_config() {
  cat <<EOF
Command: deploy config

Manage deployment configuration.

USAGE:
  deploy config [OPERATION] [OPTIONS]

OPERATIONS:
  show                    Show current configuration
  edit                    Edit configuration file
  validate                Validate configuration
  reset                   Reset to defaults
  export PATH             Export configuration to file
  import PATH             Import configuration from file

OPTIONS:
  --key NAME              Show/edit specific configuration key
  --format FORMAT         Output format (yaml/json/env)
  --help                  Show this help

EXAMPLES:
  deploy config show                   # Show all configuration
  deploy config edit                   # Edit in \$EDITOR
  deploy config validate               # Validate current config
  deploy config show --key ai-stack    # Show specific section
  deploy config export /tmp/config.yaml # Export to file

DESCRIPTION:
  The 'config' command manages the unified deployment configuration
  defined in config/deploy.yaml. This configuration controls:

  - Deployment options and defaults
  - Service endpoints and ports
  - AI stack configuration
  - Dashboard settings
  - Security policies
  - Test suite settings

  Configuration Hierarchy:
  1. config/deploy.yaml (main config)
  2. Environment variables (overrides)
  3. Command-line flags (highest priority)

CONFIGURATION SECTIONS:

  deployment:
    - dry_run: boolean (default: false)
    - verbose: boolean (default: false)
    - confirm_actions: boolean (default: true)
    - parallel_services: integer (default: 4)

  ai_stack:
    - services: list of service names
    - health_check_timeout: seconds
    - restart_policy: string
    - startup_delay: seconds

  dashboard:
    - frontend_url: string
    - api_url: string
    - grafana_url: string
    - prometheus_url: string

  security:
    - auto_fix: boolean (default: false)
    - audit_level: string (basic/standard/strict)
    - tls_verify: boolean (default: true)

  testing:
    - smoke_timeout: seconds
    - parallel_tests: boolean
    - fail_fast: boolean

EXIT CODES:
  0    Operation successful
  1    Validation failed or configuration error
  2    Execution error

CONFIGURATION FILE:
  config/deploy.yaml

RELATED COMMANDS:
  deploy system           Uses deployment configuration
  deploy ai-stack         Uses ai_stack configuration
  deploy test             Uses testing configuration

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  config/deploy.yaml (once created in Phase 1.3)
EOF
}

# ============================================================================
# Configuration Operations
# ============================================================================

config_show() {
  local key="${1:-}"
  local format="${2:-yaml}"

  print_section "Current Configuration"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  if [[ ! -f "$config_file" ]]; then
    log_warn "Configuration file not found: $config_file"
    echo ""
    echo "Creating default configuration..."
    config_reset
    return $?
  fi

  if [[ -n "$key" ]]; then
    log_info "Showing configuration key: $key"

    # Simple grep-based extraction for now
    # In Phase 1.3, this will use proper YAML parsing
    grep -A 10 "^${key}:" "$config_file" || log_warn "Key not found: $key"
  else
    log_info "Configuration file: $config_file"
    echo ""
    cat "$config_file"
  fi

  return 0
}

config_edit() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  print_section "Edit Configuration"

  if [[ ! -f "$config_file" ]]; then
    log_warn "Configuration file not found: $config_file"
    echo ""

    if confirm_action "Create default configuration?"; then
      config_reset
    else
      return 0
    fi
  fi

  local editor="${EDITOR:-vi}"

  log_info "Opening configuration in: $editor"

  if $editor "$config_file"; then
    log_success "Configuration saved"

    # Validate after edit
    log_info "Validating configuration..."
    if config_validate; then
      log_success "Configuration is valid"
    else
      log_error "Configuration validation failed"
      return 1
    fi
  else
    log_error "Editor exited with error"
    return 2
  fi

  return 0
}

config_validate() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  print_section "Configuration Validation"

  if [[ ! -f "$config_file" ]]; then
    log_error "Configuration file not found: $config_file"
    return 1
  fi

  local issues=0

  # Basic YAML syntax check
  if command -v yamllint >/dev/null 2>&1; then
    log_info "Checking YAML syntax..."
    if yamllint "$config_file" >/dev/null 2>&1; then
      log_success "YAML syntax valid"
    else
      log_error "YAML syntax errors detected"
      yamllint "$config_file"
      issues=$((issues + 1))
    fi
  else
    log_debug "yamllint not available, skipping syntax check"
  fi

  # Check file permissions
  local perms
  perms=$(stat -c %a "$config_file" 2>/dev/null || stat -f %A "$config_file" 2>/dev/null)

  if [[ "$perms" =~ ^[0-7][0-7][0-7]$ ]]; then
    # Check if world-writable
    if [[ "${perms:2:1}" =~ [2367] ]]; then
      log_warn "Configuration file is world-writable"
      issues=$((issues + 1))
    else
      log_success "File permissions OK"
    fi
  fi

  # Validate required sections exist
  local required_sections=(
    "deployment"
    "ai_stack"
    "dashboard"
  )

  for section in "${required_sections[@]}"; do
    if grep -q "^${section}:" "$config_file"; then
      log_success "Section found: $section"
    else
      log_warn "Missing section: $section (optional)"
    fi
  done

  if [[ $issues -eq 0 ]]; then
    log_success "Configuration validation passed"
    return 0
  else
    log_error "$issues validation issue(s) found"
    return 1
  fi
}

config_reset() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  print_section "Reset Configuration"

  if [[ -f "$config_file" ]]; then
    log_warn "This will overwrite existing configuration"

    if ! confirm_action "Continue?"; then
      log_info "Operation cancelled"
      return 0
    fi

    # Backup existing config
    local backup="${config_file}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$config_file" "$backup"
    log_info "Backed up to: $backup"
  fi

  log_info "Creating default configuration..."

  # Create default config
  # This will be expanded in Phase 1.3
  cat > "$config_file" <<'EOF'
# Unified Deployment Configuration
# Generated by: deploy config reset

deployment:
  dry_run: false
  verbose: false
  confirm_actions: true
  parallel_services: 4

ai_stack:
  services:
    - ai-aidb.service
    - ai-hybrid-coordinator.service
    - ai-ralph-wiggum.service
    - ai-switchboard.service
    - llama-cpp.service
    - llama-cpp-embed.service
    - qdrant.service
    - postgresql.service
    - redis-mcp.service
  health_check_timeout: 30
  restart_policy: "on-failure"
  startup_delay: 5

dashboard:
  frontend_url: "http://localhost:3001"
  api_url: "http://localhost:8005"
  grafana_url: "http://localhost:3000"
  prometheus_url: "http://localhost:9090"

security:
  auto_fix: false
  audit_level: "standard"
  tls_verify: true

testing:
  smoke_timeout: 120
  parallel_tests: false
  fail_fast: false
EOF

  log_success "Default configuration created: $config_file"

  return 0
}

config_export() {
  local export_path="$1"

  if [[ -z "$export_path" ]]; then
    log_error "Export path required"
    echo ""
    echo "Usage: deploy config export PATH"
    return 2
  fi

  print_section "Export Configuration"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  if [[ ! -f "$config_file" ]]; then
    log_error "Configuration file not found: $config_file"
    return 1
  fi

  if cp "$config_file" "$export_path"; then
    log_success "Configuration exported to: $export_path"
    return 0
  else
    log_error "Export failed"
    return 1
  fi
}

config_import() {
  local import_path="$1"

  if [[ -z "$import_path" ]]; then
    log_error "Import path required"
    echo ""
    echo "Usage: deploy config import PATH"
    return 2
  fi

  if [[ ! -f "$import_path" ]]; then
    log_error "Import file not found: $import_path"
    return 1
  fi

  print_section "Import Configuration"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local config_file="${CONFIG_FILE:-${script_dir}/config/deploy.yaml}"

  log_warn "This will replace current configuration"

  if ! confirm_action "Continue?"; then
    log_info "Operation cancelled"
    return 0
  fi

  # Backup existing config if it exists
  if [[ -f "$config_file" ]]; then
    local backup="${config_file}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$config_file" "$backup"
    log_info "Backed up to: $backup"
  fi

  if cp "$import_path" "$config_file"; then
    log_success "Configuration imported from: $import_path"

    # Validate imported config
    log_info "Validating imported configuration..."
    if config_validate; then
      log_success "Imported configuration is valid"
      return 0
    else
      log_error "Imported configuration validation failed"
      return 1
    fi
  else
    log_error "Import failed"
    return 1
  fi
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_config() {
  local operation="show"
  local key=""
  local format="yaml"

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_config
        return 0
        ;;
      --key)
        key="$2"
        shift 2
        ;;
      --format)
        format="$2"
        shift 2
        ;;
      show|edit|validate|reset|export|import)
        operation="$1"
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy config --help' for usage."
        return 2
        ;;
      *)
        # Positional argument (path for export/import)
        break
        ;;
    esac
  done

  print_header "Configuration Management: $operation"

  # Dispatch to operation
  case "$operation" in
    show)
      config_show "$key" "$format"
      ;;
    edit)
      config_edit
      ;;
    validate)
      config_validate
      ;;
    reset)
      config_reset
      ;;
    export)
      config_export "$1"
      ;;
    import)
      config_import "$1"
      ;;
    *)
      log_error "Unknown operation: $operation"
      echo ""
      echo "Valid operations: show, edit, validate, reset, export, import"
      return 2
      ;;
  esac
}
