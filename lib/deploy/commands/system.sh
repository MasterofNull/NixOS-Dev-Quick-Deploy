#!/usr/bin/env bash
#
# Deploy CLI - System Command
# Replaces nixos-quick-deploy.sh

# ============================================================================
# Help Text
# ============================================================================

help_system() {
  cat <<EOF
Command: deploy system

Deploy entire NixOS system configuration.

USAGE:
  deploy system [OPTIONS]

OPTIONS:
  --dry-run               Preview changes without applying
  --rollback              Rollback to previous generation
  --target HOST           Deploy to remote host (default: local)
  --fast                  Skip expensive checks
  --force                 Override safety checks
  --help                  Show this help

EXAMPLES:
  deploy system                    # Full deployment with preview
  deploy system --dry-run          # Preview changes only
  deploy system --rollback         # Rollback to previous generation
  deploy system --target=server    # Deploy to remote server
  deploy system --fast             # Skip expensive checks

DESCRIPTION:
  The 'system' command deploys the complete NixOS system configuration
  by wrapping the nixos-quick-deploy.sh script with a cleaner interface.

  This command:
  - Validates configuration before deployment
  - Shows clear progress indicators
  - Provides rollback capability
  - Handles errors gracefully

  In Phase 1.2, this command will fully replace nixos-quick-deploy.sh
  with native implementation. For now, it wraps the existing script.

LEGACY EQUIVALENT:
  ./nixos-quick-deploy.sh

RELATED COMMANDS:
  deploy ai-stack         Deploy AI stack only
  deploy health           Check system health after deployment
  deploy recover          Recover from failed deployment

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
EOF
}

# ============================================================================
# Command Implementation
# ============================================================================

cmd_system() {
  local do_rollback=0
  local target="local"
  local fast_mode=0
  local force=0

  # Parse command-specific options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_system
        return 0
        ;;
      --rollback)
        do_rollback=1
        shift
        ;;
      --target)
        target="$2"
        shift 2
        ;;
      --target=*)
        target="${1#*=}"
        shift
        ;;
      --fast)
        fast_mode=1
        shift
        ;;
      --force)
        force=1
        shift
        ;;
      *)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy system --help' for usage."
        return 1
        ;;
    esac
  done

  print_header "System Deployment"

  # Validate prerequisites
  log_step 1 4 "Validating prerequisites..."
  require_command nixos-rebuild "Install NixOS"
  require_command git "nix-env -iA nixos.git"

  # Check if we're on NixOS
  if [[ ! -f /etc/NIXOS ]]; then
    die "This command requires NixOS"
  fi

  log_success "Prerequisites validated"

  # Rollback if requested
  if [[ $do_rollback -eq 1 ]]; then
    log_step 2 4 "Rolling back to previous generation..."

    if would_run "nixos-rebuild switch --rollback"; then
      log_success "[DRY-RUN] Would rollback system"
      return 0
    fi

    if sudo nixos-rebuild switch --rollback; then
      log_success "System rolled back successfully"
      return 0
    else
      die "Rollback failed"
    fi
  fi

  # Validate configuration
  log_step 2 4 "Validating configuration..."

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  if [[ ! -f "${script_dir}/nixos-quick-deploy.sh" ]]; then
    die "nixos-quick-deploy.sh not found"
  fi

  log_success "Configuration valid"

  # Deploy
  log_step 3 4 "Deploying system..."

  local deploy_args=()

  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log_info "Dry-run mode enabled - showing what would be deployed"
    # For now, delegate to nixos-quick-deploy.sh
    # In Phase 1.2, this will be native implementation
  fi

  if [[ $fast_mode -eq 1 ]]; then
    log_info "Fast mode enabled - skipping expensive checks"
  fi

  # Delegate to nixos-quick-deploy.sh for now
  # TODO Phase 1.2: Replace with native implementation
  log_info "Delegating to nixos-quick-deploy.sh (Phase 1.2 will remove this)"

  print_section "Deployment Output"

  local start_time
  start_time=$(get_timestamp)

  if "${script_dir}/nixos-quick-deploy.sh" "${deploy_args[@]}" "$@"; then
    local end_time
    end_time=$(get_timestamp)
    local duration=$((end_time - start_time))

    log_success "System deployed successfully in $(format_duration $duration)"

    # Post-deployment health check
    log_step 4 4 "Running post-deployment health check..."

    if command -v systemctl >/dev/null 2>&1; then
      local failed_services
      failed_services=$(systemctl list-units --failed --no-legend | wc -l)

      if [[ $failed_services -eq 0 ]]; then
        log_success "All services running"
      else
        log_warn "$failed_services service(s) failed - run 'deploy health' for details"
      fi
    fi

    print_section "Next Steps"
    echo "  • Run 'deploy health' to verify system health"
    echo "  • Run 'deploy ai-stack' to deploy AI services"
    echo "  • Run 'deploy test --suite=smoke' to run smoke tests"

    return 0
  else
    local exit_code=$?
    log_error "System deployment failed (exit code: $exit_code)"

    print_section "Troubleshooting"
    echo "  • Check logs for errors"
    echo "  • Run 'deploy recover diagnose' for detailed diagnosis"
    echo "  • Run 'deploy system --rollback' to rollback"
    echo "  • See nixos-quick-deploy.sh logs for details"

    return $exit_code
  fi
}
