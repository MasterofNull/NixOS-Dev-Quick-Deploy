#!/usr/bin/env bash
#
# Deploy CLI - Dashboard Command
# Monitoring dashboard management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [[ -f "${REPO_ROOT}/config/service-endpoints.sh" ]]; then
  # shellcheck source=config/service-endpoints.sh
  source "${REPO_ROOT}/config/service-endpoints.sh"
fi

# ============================================================================
# Help Text
# ============================================================================

help_dashboard() {
  cat <<EOF
Command: deploy dashboard

Manage the monitoring and control dashboard.

USAGE:
  deploy dashboard [OPERATION] [OPTIONS]

OPERATIONS:
  start                   Start dashboard services (default)
  stop                    Stop dashboard services
  restart                 Restart dashboard services
  status                  Show dashboard status
  logs                    Show dashboard logs
  open                    Open dashboard in browser
  setup                   Run dashboard setup

OPTIONS:
  --port PORT             Dashboard port (default: from config)
  --api-port PORT         API backend port (default: from config)
  --no-browser            Don't open browser automatically
  --help                  Show this help

EXAMPLES:
  deploy dashboard                     # Start dashboard
  deploy dashboard status              # Check dashboard status
  deploy dashboard open                # Open in browser
  deploy dashboard restart             # Restart services
  deploy dashboard logs                # View logs

DESCRIPTION:
  The 'dashboard' command manages the monitoring and control dashboard
  that provides:
  - Real-time system and AI stack monitoring
  - Service status visualization
  - Metrics and performance graphs
  - Deployment history
  - Log aggregation
  - Control actions (restart, stop services)

  Dashboard Components:
  - Frontend: Command Center SPA served by the backend
  - Backend API: FastAPI served on the same operator port in production
  - Monitoring: Grafana (port 3000)
  - Metrics: Prometheus (port 9090)

  In Phase 2, the dashboard will be fully integrated with:
  - Real-time deployment progress tracking
  - Automated health monitoring
  - Alert visualization
  - Deployment history with semantic search

DASHBOARD SERVICES:
  command-center-dashboard-api.service    # Backend API
  grafana.service                         # Grafana dashboard
  prometheus.service                      # Metrics collection
  prometheus-node-exporter.service        # Node metrics

URLS (default):
  Dashboard:    ${DASHBOARD_URL}
  API:          ${DASHBOARD_API_URL}
  Grafana:      ${GRAFANA_URL}
  Prometheus:   ${PROMETHEUS_URL}

EXIT CODES:
  0    Operation successful
  1    Operation failed
  2    Execution error

LEGACY EQUIVALENT:
  dashboard/start-dashboard.sh

RELATED COMMANDS:
  deploy health           Health checks (data source for dashboard)
  deploy ai-stack         AI stack management (monitored by dashboard)
  deploy system           System deployment (tracked in dashboard)

DOCUMENTATION:
  dashboard/README.md
  dashboard/INTEGRATION-WITH-AI-STACK.md
  .agents/designs/unified-deploy-cli-architecture.md
EOF
}

# ============================================================================
# Dashboard Configuration
# ============================================================================

DASHBOARD_SERVICES=(
  "command-center-dashboard-api.service"
  "grafana.service"
  "prometheus.service"
  "prometheus-node-exporter.service"
)

# Default URLs (can be overridden by env/config/service-endpoints.sh)
DASHBOARD_URL="${DASHBOARD_URL:-http://127.0.0.1:8889}"
DASHBOARD_API_URL="${DASHBOARD_API_URL:-${DASHBOARD_URL}}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"

# ============================================================================
# Dashboard Operations
# ============================================================================

dashboard_start() {
  print_section "Starting Dashboard"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  # Check if dashboard directory exists
  if [[ ! -d "${script_dir}/dashboard" ]]; then
    log_error "Dashboard directory not found"
    echo ""
    echo "The dashboard may not be installed. To set it up:"
    echo "  • Check dashboard/README.md for installation instructions"
    echo "  • Run 'deploy dashboard setup' for guided setup"
    return 2
  fi

  # Start dashboard services
  log_step 1 3 "Starting dashboard services..."

  local failed=0
  for service in "${DASHBOARD_SERVICES[@]}"; do
    if systemctl list-unit-files --type=service 2>/dev/null | grep -q "^${service}"; then
      if would_run "systemctl start $service"; then
        log_success "[DRY-RUN] Would start $service"
      else
        if sudo systemctl start "$service" 2>/dev/null; then
          log_success "Started $service"
        else
          log_warn "Could not start $service (may not be installed)"
        fi
      fi
    else
      log_debug "$service not installed (optional)"
    fi
  done

  # Run start script if available
  if [[ -f "${script_dir}/dashboard/start-dashboard.sh" ]]; then
    log_step 2 3 "Running dashboard startup script..."

    if would_run "bash ${script_dir}/dashboard/start-dashboard.sh"; then
      log_success "[DRY-RUN] Would run dashboard startup script"
    else
      if bash "${script_dir}/dashboard/start-dashboard.sh" >/dev/null 2>&1 &
      then
        log_success "Dashboard startup script launched"
      else
        log_warn "Dashboard startup script failed (check logs)"
      fi
    fi
  fi

  # Wait for services to be ready
  log_step 3 3 "Waiting for dashboard to be ready..."
  sleep 3

  # Check if dashboard is accessible
  if curl -fsS --max-time 3 "${DASHBOARD_API_URL}/api/health" >/dev/null 2>&1; then
    log_success "Dashboard API is ready"
  else
    log_warn "Dashboard API not responding yet (may still be starting)"
  fi

  echo ""
  log_success "Dashboard services started"

  print_section "Dashboard Access"
  echo "  • Dashboard UI:  ${DASHBOARD_URL}"
  echo "  • API Backend:   ${DASHBOARD_API_URL}"
  echo "  • Grafana:       ${GRAFANA_URL}"
  echo "  • Prometheus:    ${PROMETHEUS_URL}"
  echo ""
  echo "Run 'deploy dashboard open' to open in browser"

  return 0
}

dashboard_stop() {
  print_section "Stopping Dashboard"

  log_warn "This will stop all dashboard services"

  if ! confirm_action "Continue?"; then
    log_info "Operation cancelled"
    return 0
  fi

  local failed=0
  for service in "${DASHBOARD_SERVICES[@]}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
      if would_run "systemctl stop $service"; then
        log_success "[DRY-RUN] Would stop $service"
      else
        if sudo systemctl stop "$service"; then
          log_success "Stopped $service"
        else
          log_error "Failed to stop $service"
          failed=$((failed + 1))
        fi
      fi
    fi
  done

  if [[ $failed -eq 0 ]]; then
    log_success "Dashboard services stopped"
    return 0
  else
    log_error "$failed service(s) failed to stop"
    return 1
  fi
}

dashboard_restart() {
  print_section "Restarting Dashboard"

  dashboard_stop
  sleep 2
  dashboard_start
}

dashboard_status() {
  print_section "Dashboard Status"

  local all_running=1

  for service in "${DASHBOARD_SERVICES[@]}"; do
    printf "%-45s " "$service"

    if systemctl is-active --quiet "$service" 2>/dev/null; then
      echo -e "${GREEN}active${RESET}"
    elif systemctl list-unit-files --type=service 2>/dev/null | grep -q "^${service}"; then
      echo -e "${RED}inactive${RESET}"
      all_running=0
    else
      echo -e "${CYAN}not-installed${RESET}"
    fi
  done

  echo ""

  # Check HTTP endpoints
  print_section "Endpoint Status"

  printf "%-45s " "Dashboard UI (${DASHBOARD_URL})"
  if curl -fsS --max-time 3 "${DASHBOARD_URL}" >/dev/null 2>&1; then
    echo -e "${GREEN}responding${RESET}"
  else
    echo -e "${RED}not responding${RESET}"
    all_running=0
  fi

  printf "%-45s " "API Backend (${DASHBOARD_API_URL})"
  if curl -fsS --max-time 3 "${DASHBOARD_API_URL}/api/health" >/dev/null 2>&1; then
    echo -e "${GREEN}responding${RESET}"
  else
    echo -e "${RED}not responding${RESET}"
    all_running=0
  fi

  printf "%-45s " "Grafana (${GRAFANA_URL})"
  if curl -fsS --max-time 3 "${GRAFANA_URL}/api/health" >/dev/null 2>&1; then
    echo -e "${GREEN}responding${RESET}"
  else
    echo -e "${RED}not responding${RESET}"
  fi

  printf "%-45s " "Prometheus (${PROMETHEUS_URL})"
  if curl -fsS --max-time 3 "${PROMETHEUS_URL}/-/ready" >/dev/null 2>&1; then
    echo -e "${GREEN}responding${RESET}"
  else
    echo -e "${RED}not responding${RESET}"
  fi

  echo ""

  if [[ $all_running -eq 1 ]]; then
    log_success "Dashboard is fully operational"
    return 0
  else
    log_warn "Some dashboard components are not running"
    echo ""
    echo "To start dashboard: deploy dashboard start"
    return 1
  fi
}

dashboard_logs() {
  local service="${1:-command-center-dashboard-api.service}"
  local lines="${2:-50}"

  print_section "Dashboard Logs: $service"

  if systemctl list-unit-files --type=service 2>/dev/null | grep -q "^${service}"; then
    sudo journalctl -u "$service" -n "$lines" --no-pager
  else
    log_error "Service not found: $service"
    echo ""
    echo "Available dashboard services:"
    for svc in "${DASHBOARD_SERVICES[@]}"; do
      echo "  - $svc"
    done
    return 1
  fi
}

dashboard_open() {
  print_section "Opening Dashboard"

  # Check if dashboard is running
  if ! curl -fsS --max-time 3 "${DASHBOARD_URL}" >/dev/null 2>&1; then
    log_warn "Dashboard UI not responding"
    echo ""
    echo "Starting dashboard first..."
    dashboard_start
    sleep 3
  fi

  # Try to open in browser
  local opened=0

  if command -v xdg-open >/dev/null 2>&1; then
    log_info "Opening dashboard in browser..."
    xdg-open "${DASHBOARD_URL}" 2>/dev/null &
    opened=1
  elif command -v open >/dev/null 2>&1; then
    log_info "Opening dashboard in browser..."
    open "${DASHBOARD_URL}" 2>/dev/null &
    opened=1
  fi

  if [[ $opened -eq 1 ]]; then
    log_success "Dashboard opened in browser"
  else
    log_warn "Could not detect browser command"
  fi

  echo ""
  echo "Dashboard URLs:"
  echo "  • Dashboard UI:  ${DASHBOARD_URL}"
  echo "  • API Backend:   ${DASHBOARD_API_URL}"
  echo "  • Grafana:       ${GRAFANA_URL}"
  echo "  • Prometheus:    ${PROMETHEUS_URL}"

  return 0
}

dashboard_setup() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "Dashboard Setup"

  log_info "Dashboard setup wizard"

  # Check if dashboard directory exists
  if [[ ! -d "${script_dir}/dashboard" ]]; then
    log_error "Dashboard directory not found at: ${script_dir}/dashboard"
    return 2
  fi

  # Show setup documentation
  if [[ -f "${script_dir}/dashboard/README.md" ]]; then
    log_info "Setup documentation available at: dashboard/README.md"
  fi

  if [[ -f "${script_dir}/dashboard/INTEGRATION-WITH-AI-STACK.md" ]]; then
    log_info "Integration guide: dashboard/INTEGRATION-WITH-AI-STACK.md"
  fi

  # Check for setup scripts
  if [[ -f "${script_dir}/dashboard/start-dashboard.sh" ]]; then
    log_success "Dashboard startup script found"

    if confirm_action "Run dashboard startup script now?"; then
      bash "${script_dir}/dashboard/start-dashboard.sh"
    fi
  fi

  echo ""
  log_info "For complete setup instructions, see: dashboard/README.md"

  return 0
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_dashboard() {
  local operation="start"
  local port=""
  local api_port=""
  local no_browser=0

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_dashboard
        return 0
        ;;
      --port)
        port="$2"
        DASHBOARD_URL="http://localhost:${port}"
        shift 2
        ;;
      --api-port)
        api_port="$2"
        DASHBOARD_API_URL="http://localhost:${api_port}"
        shift 2
        ;;
      --no-browser)
        no_browser=1
        shift
        ;;
      start|stop|restart|status|logs|open|setup)
        operation="$1"
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy dashboard --help' for usage."
        return 2
        ;;
      *)
        # Positional argument (e.g., service name for logs)
        break
        ;;
    esac
  done

  print_header "Dashboard Management: $operation"

  # Dispatch to operation
  case "$operation" in
    start)
      dashboard_start
      ;;
    stop)
      dashboard_stop
      ;;
    restart)
      dashboard_restart
      ;;
    status)
      dashboard_status
      ;;
    logs)
      dashboard_logs "$@"
      ;;
    open)
      dashboard_open
      ;;
    setup)
      dashboard_setup
      ;;
    *)
      log_error "Unknown operation: $operation"
      echo ""
      echo "Valid operations: start, stop, restart, status, logs, open, setup"
      return 2
      ;;
  esac
}
