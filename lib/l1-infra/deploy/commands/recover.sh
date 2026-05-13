#!/usr/bin/env bash
#
# Deploy CLI - Recover Command
# Recovery and troubleshooting operations

# ============================================================================
# Help Text
# ============================================================================

help_recover() {
  cat <<EOF
Command: deploy recover

Recovery operations and troubleshooting for failed deployments.

USAGE:
  deploy recover [OPERATION] [OPTIONS]

OPERATIONS:
  diagnose                Diagnose current system state
  rollback                Rollback to previous generation
  restart-services        Restart all critical services
  fix-permissions         Fix common permission issues
  clear-cache             Clear system caches
  rebuild                 Force rebuild and redeploy

OPTIONS:
  --component NAME        Focus on specific component
  --auto                  Attempt automatic recovery
  --safe-mode             Use safe recovery options only
  --help                  Show this help

EXAMPLES:
  deploy recover diagnose              # Diagnose issues
  deploy recover rollback              # Rollback deployment
  deploy recover restart-services      # Restart all services
  deploy recover --component ai-stack  # Focus on AI stack
  deploy recover --auto                # Auto-recovery attempt

DESCRIPTION:
  The 'recover' command provides recovery and troubleshooting operations
  for when deployments fail or systems become degraded:

  - Diagnose system state and identify issues
  - Rollback to previous working generation
  - Restart services with proper ordering
  - Fix common permission and configuration issues
  - Clear caches that may cause problems
  - Force rebuild and redeploy

  Recovery Strategies:
  1. Diagnose first to understand the problem
  2. Try non-destructive fixes (restart services, clear cache)
  3. Use rollback for deployment failures
  4. Force rebuild only as last resort

COMMON RECOVERY SCENARIOS:

  Deployment Failed:
  1. deploy recover diagnose           # Identify issue
  2. deploy recover rollback           # Go back to working state

  Services Not Starting:
  1. deploy recover diagnose
  2. deploy recover restart-services   # Restart in correct order

  Permission Errors:
  1. deploy recover fix-permissions    # Fix common issues

  Stuck State:
  1. deploy recover clear-cache
  2. deploy recover rebuild            # Fresh start

EXIT CODES:
  0    Recovery successful
  1    Recovery failed or issues remain
  2    Execution error

LEGACY EQUIVALENTS:
  nixos-rebuild switch --rollback      # Rollback
  systemctl restart SERVICE            # Restart services

RELATED COMMANDS:
  deploy system --rollback    System rollback
  deploy health               Health diagnostics
  deploy ai-stack restart     AI stack restart

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
EOF
}

# ============================================================================
# Recovery Operations
# ============================================================================

recover_diagnose() {
  print_section "System Diagnosis"

  local component="${1:-all}"
  local issues=0

  log_info "Diagnosing system state..."

  # Check systemd state
  log_step 1 5 "Checking systemd state..."

  if systemctl is-system-running >/dev/null 2>&1; then
    log_success "System state: $(systemctl is-system-running)"
  else
    local state
    state=$(systemctl is-system-running 2>/dev/null || echo "unknown")
    log_error "System state: $state"
    issues=$((issues + 1))
  fi

  # Check failed units
  log_step 2 5 "Checking for failed units..."

  local failed_count
  failed_count=$(systemctl list-units --failed --no-legend | wc -l)

  if [[ $failed_count -eq 0 ]]; then
    log_success "No failed systemd units"
  else
    log_error "$failed_count failed unit(s)"
    systemctl list-units --failed --no-legend
    issues=$((issues + 1))
  fi

  # Check disk space
  log_step 3 5 "Checking disk space..."

  local disk_usage
  disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

  if [[ $disk_usage -gt 90 ]]; then
    log_error "Critical disk space: ${disk_usage}% used"
    issues=$((issues + 1))
  elif [[ $disk_usage -gt 80 ]]; then
    log_warn "Low disk space: ${disk_usage}% used"
  else
    log_success "Disk space OK: ${disk_usage}% used"
  fi

  # Check AI stack if applicable
  if [[ "$component" == "all" || "$component" == "ai-stack" ]]; then
    log_step 4 5 "Checking AI stack..."

    if systemctl is-active --quiet ai-stack.target 2>/dev/null; then
      log_success "AI stack target active"
    else
      log_error "AI stack target inactive"
      issues=$((issues + 1))
    fi
  fi

  # Check recent errors in journal
  log_step 5 5 "Checking recent errors..."

  local recent_errors
  recent_errors=$(journalctl -p err --since "10 minutes ago" --no-pager | wc -l)

  if [[ $recent_errors -gt 0 ]]; then
    log_warn "$recent_errors error(s) in last 10 minutes"
    echo ""
    echo "Recent errors:"
    journalctl -p err --since "10 minutes ago" --no-pager | tail -10
  else
    log_success "No recent errors"
  fi

  echo ""

  if [[ $issues -eq 0 ]]; then
    log_success "No critical issues detected"

    print_section "Next Steps"
    echo "  • System appears healthy"
    echo "  • Run 'deploy health' for comprehensive check"

    return 0
  else
    log_error "$issues critical issue(s) detected"

    print_section "Recovery Options"
    echo "  • deploy recover restart-services    # Restart services"
    echo "  • deploy recover rollback            # Rollback deployment"
    echo "  • deploy recover fix-permissions     # Fix permissions"
    echo "  • deploy recover clear-cache         # Clear caches"

    return 1
  fi
}

recover_rollback() {
  print_section "System Rollback"

  log_warn "This will rollback to the previous NixOS generation"

  if ! confirm_action "Continue with rollback?"; then
    log_info "Rollback cancelled"
    return 0
  fi

  log_info "Rolling back system..."

  if would_run "nixos-rebuild switch --rollback"; then
    log_success "[DRY-RUN] Would rollback system"
    return 0
  fi

  if sudo nixos-rebuild switch --rollback; then
    log_success "System rolled back successfully"

    print_section "Next Steps"
    echo "  • Run 'deploy health' to verify system state"
    echo "  • Check what changed: nixos-rebuild list-generations"

    return 0
  else
    log_error "Rollback failed"

    print_section "Manual Recovery"
    echo "  • Reboot and select previous generation in boot menu"
    echo "  • Check system logs: journalctl -xe"

    return 1
  fi
}

recover_restart_services() {
  print_section "Restart Services"

  log_warn "This will restart all critical services"

  if ! confirm_action "Continue?"; then
    log_info "Operation cancelled"
    return 0
  fi

  local failed=0

  # Restart in dependency order
  local service_order=(
    "postgresql.service"
    "redis-mcp.service"
    "qdrant.service"
    "prometheus.service"
    "ai-stack.target"
  )

  for service in "${service_order[@]}"; do
    if systemctl list-unit-files --type=service,target 2>/dev/null | grep -q "^${service}"; then
      log_info "Restarting $service..."

      if would_run "systemctl restart $service"; then
        log_success "[DRY-RUN] Would restart $service"
      else
        if sudo systemctl restart "$service"; then
          log_success "Restarted $service"
          sleep 2  # Allow time to stabilize
        else
          log_error "Failed to restart $service"
          failed=$((failed + 1))
        fi
      fi
    else
      log_debug "$service not installed (skipping)"
    fi
  done

  echo ""

  if [[ $failed -eq 0 ]]; then
    log_success "All services restarted successfully"

    # Wait for services to stabilize
    log_info "Waiting for services to stabilize..."
    sleep 5

    # Run health check
    log_info "Running health check..."
    if cmd_health >/dev/null 2>&1; then
      log_success "Health check passed"
    else
      log_warn "Some health checks failed"
    fi

    return 0
  else
    log_error "$failed service(s) failed to restart"
    return 1
  fi
}

recover_fix_permissions() {
  print_section "Fix Permissions"

  log_warn "This will fix common permission issues"

  if ! confirm_action "Continue?"; then
    log_info "Operation cancelled"
    return 0
  fi

  local fixed=0

  # Fix /run/secrets permissions
  if [[ -d /run/secrets ]]; then
    log_info "Fixing /run/secrets permissions..."

    if would_run "chmod 755 /run/secrets"; then
      log_success "[DRY-RUN] Would fix /run/secrets permissions"
    else
      if sudo chmod 755 /run/secrets 2>/dev/null; then
        log_success "Fixed /run/secrets permissions"
        fixed=$((fixed + 1))
      fi

      # Fix individual secret files
      while IFS= read -r secret_file; do
        if sudo chmod 400 "$secret_file" 2>/dev/null; then
          log_success "Fixed $(basename "$secret_file")"
          fixed=$((fixed + 1))
        fi
      done < <(find /run/secrets -type f 2>/dev/null)
    fi
  fi

  # Fix common cache directories
  local cache_dirs=(
    "/var/cache/nginx"
    "/var/cache/prometheus"
  )

  for cache_dir in "${cache_dirs[@]}"; do
    if [[ -d "$cache_dir" ]]; then
      log_info "Fixing $cache_dir permissions..."

      if would_run "chmod 755 $cache_dir"; then
        log_success "[DRY-RUN] Would fix $cache_dir permissions"
      else
        if sudo chmod -R 755 "$cache_dir" 2>/dev/null; then
          log_success "Fixed $cache_dir"
          fixed=$((fixed + 1))
        fi
      fi
    fi
  done

  echo ""

  if [[ $fixed -gt 0 ]]; then
    log_success "Fixed $fixed permission issue(s)"
  else
    log_info "No permission issues found"
  fi

  return 0
}

recover_clear_cache() {
  print_section "Clear Caches"

  log_warn "This will clear system caches"

  if ! confirm_action "Continue?"; then
    log_info "Operation cancelled"
    return 0
  fi

  local cleared=0

  # Clear Nix store garbage
  log_info "Clearing Nix store garbage..."

  if would_run "nix-collect-garbage"; then
    log_success "[DRY-RUN] Would clear Nix garbage"
  else
    if nix-collect-garbage -d 2>/dev/null; then
      log_success "Cleared Nix garbage"
      cleared=$((cleared + 1))
    fi
  fi

  # Clear systemd failed units
  log_info "Resetting failed systemd units..."

  if would_run "systemctl reset-failed"; then
    log_success "[DRY-RUN] Would reset failed units"
  else
    if sudo systemctl reset-failed 2>/dev/null; then
      log_success "Reset failed units"
      cleared=$((cleared + 1))
    fi
  fi

  # Clear journal old entries
  log_info "Vacuuming journal..."

  if would_run "journalctl --vacuum-time=7d"; then
    log_success "[DRY-RUN] Would vacuum journal"
  else
    if sudo journalctl --vacuum-time=7d >/dev/null 2>&1; then
      log_success "Vacuumed journal"
      cleared=$((cleared + 1))
    fi
  fi

  echo ""
  log_success "Cleared $cleared cache(s)"

  return 0
}

recover_rebuild() {
  print_section "Force Rebuild"

  log_warn "This will force a complete system rebuild"
  log_warn "This operation may take several minutes"

  if ! confirm_action "Continue with force rebuild?"; then
    log_info "Operation cancelled"
    return 0
  fi

  log_info "Running force rebuild..."

  if would_run "nixos-rebuild switch"; then
    log_success "[DRY-RUN] Would force rebuild"
    return 0
  fi

  if sudo nixos-rebuild switch; then
    log_success "Rebuild completed successfully"

    log_info "Running post-rebuild health check..."
    if cmd_health >/dev/null 2>&1; then
      log_success "Health check passed"
    else
      log_warn "Some health checks failed"
    fi

    return 0
  else
    log_error "Rebuild failed"

    print_section "Recovery Options"
    echo "  • deploy recover rollback    # Rollback to previous state"
    echo "  • Check logs: journalctl -xe"

    return 1
  fi
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_recover() {
  local operation="diagnose"
  local component="all"
  local auto_mode=0
  local safe_mode=0

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_recover
        return 0
        ;;
      --component)
        component="$2"
        shift 2
        ;;
      --auto)
        auto_mode=1
        shift
        ;;
      --safe-mode)
        safe_mode=1
        shift
        ;;
      diagnose|rollback|restart-services|fix-permissions|clear-cache|rebuild)
        operation="$1"
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy recover --help' for usage."
        return 2
        ;;
      *)
        log_error "Unknown argument: $1"
        echo ""
        echo "Run 'deploy recover --help' for usage."
        return 2
        ;;
    esac
  done

  print_header "Recovery Operations: $operation"

  # Dispatch to operation
  case "$operation" in
    diagnose)
      recover_diagnose "$component"
      ;;
    rollback)
      recover_rollback
      ;;
    restart-services)
      recover_restart_services
      ;;
    fix-permissions)
      recover_fix_permissions
      ;;
    clear-cache)
      recover_clear_cache
      ;;
    rebuild)
      recover_rebuild
      ;;
    *)
      log_error "Unknown operation: $operation"
      echo ""
      echo "Valid operations: diagnose, rollback, restart-services, fix-permissions, clear-cache, rebuild"
      return 2
      ;;
  esac
}
