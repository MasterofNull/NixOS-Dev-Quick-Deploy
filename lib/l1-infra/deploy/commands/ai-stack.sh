#!/usr/bin/env bash
#
# Deploy CLI - AI Stack Command
# Manages AI stack services

# ============================================================================
# Help Text
# ============================================================================

help_ai_stack() {
  cat <<EOF
Command: deploy ai-stack

Deploy and manage AI stack services.

USAGE:
  deploy ai-stack [COMMAND] [OPTIONS]

COMMANDS:
  deploy                  Deploy/restart all AI stack services (default)
  status                  Show status of all services
  health                  Run comprehensive health checks
  restart                 Restart all services
  stop                    Stop all services
  start                   Start all services
  logs [SERVICE]          Show logs for service(s)

OPTIONS:
  --service NAME          Target specific service only
  --timeout SECONDS       Health check timeout (default: 30)
  --no-health-check       Skip health checks after deployment
  --help                  Show this help

EXAMPLES:
  deploy ai-stack                      # Deploy and health check all services
  deploy ai-stack status               # Show status of all services
  deploy ai-stack health               # Run health checks only
  deploy ai-stack restart --service aidb    # Restart specific service
  deploy ai-stack logs hybrid-coordinator   # Show service logs
  deploy ai-stack --dry-run            # Preview what would be deployed

DESCRIPTION:
  The 'ai-stack' command manages the entire AI stack including:
  - AI services (AIDB, hybrid-coordinator, Ralph Wiggum, switchboard)
  - LLM services (llama-cpp, llama-cpp-embed)
  - Data stores (Qdrant, PostgreSQL, Redis)
  - Monitoring (Prometheus, Grafana, OpenTelemetry)
  - Dashboard (API and SPA)

  In Phase 1.2, this command consolidates:
  - scripts/ai/ai-stack-health.sh (health checks)
  - systemctl management commands (service control)
  - journalctl log viewing (log aggregation)

SERVICES MANAGED:
  ai-stack.target                     # Main systemd target
  ai-aidb.service                     # AI database service
  ai-hybrid-coordinator.service       # Hybrid coordinator
  ai-ralph-wiggum.service             # Ralph Wiggum service
  ai-switchboard.service              # AI switchboard
  ai-otel-collector.service           # OpenTelemetry collector
  llama-cpp.service                   # LLM inference server
  llama-cpp-embed.service             # LLM embedding server
  qdrant.service                      # Vector database
  postgresql.service                  # Relational database
  redis-mcp.service                   # Redis cache
  prometheus.service                  # Metrics collection
  prometheus-node-exporter.service    # System metrics
  command-center-dashboard-api.service # Dashboard backend

LEGACY EQUIVALENTS:
  scripts/ai/ai-stack-health.sh           # Health checks
  systemctl status ai-stack.target        # Service status
  journalctl -u ai-aidb.service           # Service logs

RELATED COMMANDS:
  deploy system           Deploy entire system (includes AI stack)
  deploy health           Quick health check across all components
  deploy dashboard        Manage dashboard specifically

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
EOF
}

# ============================================================================
# Service Configuration
# ============================================================================

AI_STACK_SERVICES=(
  "ai-stack.target"
  "ai-aidb.service"
  "ai-hybrid-coordinator.service"
  "ai-ralph-wiggum.service"
  "ai-otel-collector.service"
  "ai-switchboard.service"
  "qdrant.service"
  "llama-cpp.service"
  "llama-cpp-embed.service"
  "postgresql.service"
  "redis-mcp.service"
  "prometheus.service"
  "prometheus-node-exporter.service"
  "command-center-dashboard-api.service"
)

# ============================================================================
# Helper Functions
# ============================================================================

check_service_status() {
  local service="$1"
  local quiet="${2:-0}"

  if systemctl is-active --quiet "$service" 2>/dev/null; then
    [[ $quiet -eq 0 ]] && log_success "$service: active"
    return 0
  else
    # Check if service exists
    if systemctl list-unit-files --type=service,target 2>/dev/null | grep -q "^${service}"; then
      [[ $quiet -eq 0 ]] && log_error "$service: inactive"
      return 1
    else
      [[ $quiet -eq 0 ]] && log_debug "$service: not installed (optional)"
      return 0
    fi
  fi
}

show_service_status() {
  local service="$1"

  printf "%-45s " "$service"

  if systemctl is-active --quiet "$service" 2>/dev/null; then
    echo -e "${GREEN}active${RESET}"
  elif systemctl list-unit-files --type=service,target 2>/dev/null | grep -q "^${service}"; then
    echo -e "${RED}inactive${RESET}"
  else
    echo -e "${CYAN}not-installed${RESET}"
  fi
}

# ============================================================================
# Command Implementations
# ============================================================================

cmd_ai_stack_status() {
  print_header "AI Stack Status"

  for service in "${AI_STACK_SERVICES[@]}"; do
    show_service_status "$service"
  done
}

cmd_ai_stack_health() {
  local timeout="${1:-30}"

  print_header "AI Stack Health Checks"

  log_step 1 2 "Checking service states..."

  local failed=0
  for service in "${AI_STACK_SERVICES[@]}"; do
    if ! check_service_status "$service" 1; then
      # Only count actual failures, not missing optional services
      if systemctl list-unit-files --type=service,target 2>/dev/null | grep -q "^${service}"; then
        failed=$((failed + 1))
      fi
    fi
  done

  if [[ $failed -gt 0 ]]; then
    log_error "$failed service(s) not running"
  else
    log_success "All services running"
  fi

  log_step 2 2 "Running health endpoint checks..."

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  if [[ -f "${script_dir}/scripts/ai/ai-stack-health.sh" ]]; then
    if bash "${script_dir}/scripts/ai/ai-stack-health.sh"; then
      log_success "Health checks passed"
      return 0
    else
      log_error "Health checks failed"
      return 1
    fi
  else
    log_warn "Health check script not found - skipping endpoint checks"
    return $failed
  fi
}

cmd_ai_stack_restart() {
  local service="${1:-}"

  print_header "AI Stack Restart"

  if [[ -n "$service" ]]; then
    log_info "Restarting service: $service"

    if would_run "systemctl restart $service"; then
      log_success "[DRY-RUN] Would restart $service"
      return 0
    fi

    if sudo systemctl restart "$service"; then
      log_success "Restarted $service"
    else
      die "Failed to restart $service"
    fi
  else
    log_info "Restarting AI stack target"

    if would_run "systemctl restart ai-stack.target"; then
      log_success "[DRY-RUN] Would restart ai-stack.target"
      return 0
    fi

    if sudo systemctl restart ai-stack.target; then
      log_success "Restarted ai-stack.target"
    else
      die "Failed to restart ai-stack.target"
    fi
  fi
}

cmd_ai_stack_start() {
  local service="${1:-}"

  print_header "AI Stack Start"

  if [[ -n "$service" ]]; then
    log_info "Starting service: $service"

    if would_run "systemctl start $service"; then
      log_success "[DRY-RUN] Would start $service"
      return 0
    fi

    if sudo systemctl start "$service"; then
      log_success "Started $service"
    else
      die "Failed to start $service"
    fi
  else
    log_info "Starting AI stack target"

    if would_run "systemctl start ai-stack.target"; then
      log_success "[DRY-RUN] Would start ai-stack.target"
      return 0
    fi

    if sudo systemctl start ai-stack.target; then
      log_success "Started ai-stack.target"
    else
      die "Failed to start ai-stack.target"
    fi
  fi
}

cmd_ai_stack_stop() {
  local service="${1:-}"

  print_header "AI Stack Stop"

  if [[ -n "$service" ]]; then
    log_info "Stopping service: $service"

    if would_run "systemctl stop $service"; then
      log_success "[DRY-RUN] Would stop $service"
      return 0
    fi

    if sudo systemctl stop "$service"; then
      log_success "Stopped $service"
    else
      die "Failed to stop $service"
    fi
  else
    log_warn "Stopping entire AI stack"

    if ! confirm_action "This will stop all AI stack services. Continue?"; then
      log_info "Operation cancelled"
      return 0
    fi

    if would_run "systemctl stop ai-stack.target"; then
      log_success "[DRY-RUN] Would stop ai-stack.target"
      return 0
    fi

    if sudo systemctl stop ai-stack.target; then
      log_success "Stopped ai-stack.target"
    else
      die "Failed to stop ai-stack.target"
    fi
  fi
}

cmd_ai_stack_logs() {
  local service="${1:-}"
  local lines="${2:-50}"

  if [[ -z "$service" ]]; then
    log_error "Service name required for logs command"
    echo ""
    echo "Usage: deploy ai-stack logs SERVICE [LINES]"
    echo ""
    echo "Available services:"
    for svc in "${AI_STACK_SERVICES[@]}"; do
      echo "  - ${svc%.service}"
    done
    return 1
  fi

  # Add .service suffix if not present
  if [[ "$service" != *.service ]] && [[ "$service" != *.target ]]; then
    service="${service}.service"
  fi

  print_header "Service Logs: $service"

  sudo journalctl -u "$service" -n "$lines" --no-pager
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_ai_stack() {
  local subcommand="${1:-deploy}"
  local specific_service=""
  local timeout=30
  local skip_health=0

  # Parse options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_ai_stack
        return 0
        ;;
      --service)
        specific_service="$2"
        shift 2
        ;;
      --timeout)
        timeout="$2"
        shift 2
        ;;
      --no-health-check)
        skip_health=1
        shift
        ;;
      status|health|restart|stop|start|logs|deploy)
        subcommand="$1"
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy ai-stack --help' for usage."
        return 1
        ;;
      *)
        # Positional argument (e.g., service name for logs)
        break
        ;;
    esac
  done

  # Dispatch to subcommand
  case "$subcommand" in
    status)
      cmd_ai_stack_status
      ;;
    health)
      cmd_ai_stack_health "$timeout"
      ;;
    restart)
      cmd_ai_stack_restart "$specific_service"
      if [[ $skip_health -eq 0 ]]; then
        sleep 3
        cmd_ai_stack_health "$timeout"
      fi
      ;;
    start)
      cmd_ai_stack_start "$specific_service"
      if [[ $skip_health -eq 0 ]]; then
        sleep 3
        cmd_ai_stack_health "$timeout"
      fi
      ;;
    stop)
      cmd_ai_stack_stop "$specific_service"
      ;;
    logs)
      cmd_ai_stack_logs "$@"
      ;;
    deploy)
      print_header "AI Stack Deployment"

      log_step 1 3 "Restarting AI stack services..."
      cmd_ai_stack_restart "$specific_service"

      log_step 2 3 "Waiting for services to stabilize..."
      sleep 5

      log_step 3 3 "Running health checks..."
      if cmd_ai_stack_health "$timeout"; then
        log_success "AI stack deployed successfully"

        print_section "Next Steps"
        echo "  • Run 'deploy ai-stack status' to check service states"
        echo "  • Run 'deploy ai-stack logs <service>' to view service logs"
        echo "  • Run 'deploy dashboard' to access monitoring dashboard"

        return 0
      else
        log_error "AI stack deployment completed with errors"

        print_section "Troubleshooting"
        echo "  • Run 'deploy ai-stack status' to identify failed services"
        echo "  • Run 'deploy ai-stack logs <service>' to check logs"
        echo "  • Run 'deploy health' for comprehensive diagnostics"

        return 1
      fi
      ;;
    *)
      log_error "Unknown subcommand: $subcommand"
      echo ""
      echo "Run 'deploy ai-stack --help' for usage."
      return 1
      ;;
  esac
}
