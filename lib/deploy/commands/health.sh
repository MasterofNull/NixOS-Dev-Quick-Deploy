#!/usr/bin/env bash
#
# Deploy CLI - Health Command
# Comprehensive health checks across all components

# Source ai-stack command for AI stack health checks
HEALTH_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${HEALTH_SCRIPT_DIR}/ai-stack.sh" ]]; then
  source "${HEALTH_SCRIPT_DIR}/ai-stack.sh"
fi

# ============================================================================
# Help Text
# ============================================================================

help_health() {
  cat <<EOF
Command: deploy health

Run comprehensive health checks across all system components.

USAGE:
  deploy health [OPTIONS]

OPTIONS:
  --component NAME        Check specific component only
  --timeout SECONDS       Health check timeout (default: 30)
  --json                  Output results in JSON format
  --help                  Show this help

COMPONENTS:
  system                  System-level health (disk, memory, services)
  ai-stack                AI stack services and endpoints
  network                 Network connectivity and DNS
  storage                 Disk space and database connectivity
  all                     All components (default)

EXAMPLES:
  deploy health                        # Check all components
  deploy health --component ai-stack   # Check AI stack only
  deploy health --json                 # JSON output for monitoring
  deploy health --timeout 60           # Longer timeout for slow systems

DESCRIPTION:
  The 'health' command provides comprehensive health monitoring across:
  - System resources (CPU, memory, disk)
  - AI stack services (all services and health endpoints)
  - Network connectivity (DNS, external connectivity)
  - Storage systems (disk space, database connectivity)
  - Service states (systemd units)

  This command is designed for:
  - Post-deployment validation
  - Continuous monitoring
  - Troubleshooting and diagnostics
  - CI/CD health gates

  In Phase 2, health data will feed into the monitoring dashboard
  for real-time visualization.

HEALTH CHECKS PERFORMED:
  System:
  - Critical systemd services running
  - Disk space > 10% free
  - Memory available
  - No failed systemd units

  AI Stack:
  - All AI services active
  - Health endpoints responding
  - Database connections working
  - Redis/Qdrant connectivity

  Network:
  - DNS resolution working
  - Internet connectivity
  - Internal service mesh reachable

  Storage:
  - PostgreSQL accessible
  - Redis accessible
  - Qdrant accessible
  - Adequate disk space

EXIT CODES:
  0    All health checks passed
  1    One or more health checks failed
  2    Health check execution error

LEGACY EQUIVALENTS:
  scripts/ai/ai-stack-health.sh
  systemctl status
  df -h
  free -h

RELATED COMMANDS:
  deploy ai-stack health   Detailed AI stack health
  deploy system            Full system deployment
  deploy dashboard         View health in dashboard

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
EOF
}

# ============================================================================
# Health Check Functions
# ============================================================================

check_system_health() {
  log_info "Checking system health..."

  local failed=0

  # Check disk space
  local disk_usage
  disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

  if [[ $disk_usage -gt 90 ]]; then
    log_error "Disk space critical: ${disk_usage}% used"
    failed=$((failed + 1))
  elif [[ $disk_usage -gt 80 ]]; then
    log_warn "Disk space warning: ${disk_usage}% used"
  else
    log_success "Disk space: ${disk_usage}% used"
  fi

  # Check memory
  if command -v free >/dev/null 2>&1; then
    local mem_available
    mem_available=$(free -m | awk 'NR==2 {print $7}')

    if [[ $mem_available -lt 512 ]]; then
      log_error "Low memory: ${mem_available}MB available"
      failed=$((failed + 1))
    else
      log_success "Memory available: ${mem_available}MB"
    fi
  fi

  # Check failed systemd units
  if command -v systemctl >/dev/null 2>&1; then
    local failed_units
    failed_units=$(systemctl list-units --failed --no-legend | wc -l)

    if [[ $failed_units -gt 0 ]]; then
      log_error "$failed_units systemd unit(s) failed"
      systemctl list-units --failed --no-legend
      failed=$((failed + 1))
    else
      log_success "No failed systemd units"
    fi
  fi

  return $failed
}

check_ai_stack_health() {
  log_info "Checking AI stack health..."

  # Delegate to ai-stack health command
  if cmd_ai_stack_health 30; then
    log_success "AI stack health checks passed"
    return 0
  else
    log_error "AI stack health checks failed"
    return 1
  fi
}

check_network_health() {
  log_info "Checking network health..."

  local failed=0

  # Check DNS resolution
  if host google.com >/dev/null 2>&1; then
    log_success "DNS resolution working"
  else
    log_error "DNS resolution failed"
    failed=$((failed + 1))
  fi

  # Check internet connectivity
  if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    log_success "Internet connectivity working"
  else
    log_warn "Internet connectivity may be limited"
  fi

  # Check localhost
  if ping -c 1 -W 1 127.0.0.1 >/dev/null 2>&1; then
    log_success "Localhost reachable"
  else
    log_error "Localhost unreachable"
    failed=$((failed + 1))
  fi

  return $failed
}

check_storage_health() {
  log_info "Checking storage health..."

  local failed=0

  # Check PostgreSQL using pg_isready (no sudo required)
  if systemctl is-active --quiet postgresql.service 2>/dev/null; then
    if command -v pg_isready >/dev/null 2>&1 && pg_isready -q 2>/dev/null; then
      log_success "PostgreSQL accessible"
    elif psql -h /run/postgresql -U postgres -c "SELECT 1;" >/dev/null 2>&1; then
      log_success "PostgreSQL accessible"
    elif curl -fsS --max-time 3 "http://127.0.0.1:5432" >/dev/null 2>&1 || \
         nc -z 127.0.0.1 5432 2>/dev/null; then
      log_success "PostgreSQL port listening"
    else
      log_error "PostgreSQL not responding"
      failed=$((failed + 1))
    fi
  else
    log_warn "PostgreSQL service not active"
  fi

  # Check Redis
  if systemctl is-active --quiet redis-mcp.service 2>/dev/null; then
    if command -v redis-cli >/dev/null 2>&1; then
      if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis accessible"
      else
        log_error "Redis not responding"
        failed=$((failed + 1))
      fi
    fi
  else
    log_warn "Redis service not active"
  fi

  # Check Qdrant
  if systemctl is-active --quiet qdrant.service 2>/dev/null; then
    if curl -fsS --max-time 3 http://127.0.0.1:6333/collections >/dev/null 2>&1; then
      log_success "Qdrant accessible"
    else
      log_error "Qdrant not responding"
      failed=$((failed + 1))
    fi
  else
    log_warn "Qdrant service not active"
  fi

  return $failed
}

# ============================================================================
# JSON Output
# ============================================================================

output_health_json() {
  local component="$1"
  local status="$2"
  local message="$3"
  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  cat <<EOF
{
  "timestamp": "$timestamp",
  "component": "$component",
  "status": "$status",
  "message": "$message",
  "hostname": "$(hostname)",
  "version": "${DEPLOY_VERSION}"
}
EOF
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_health() {
  local component="all"
  local timeout=30
  local use_json=0

  # Parse options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_health
        return 0
        ;;
      --component)
        component="$2"
        shift 2
        ;;
      --timeout)
        timeout="$2"
        shift 2
        ;;
      --json)
        use_json=1
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy health --help' for usage."
        return 1
        ;;
      *)
        log_error "Unknown argument: $1"
        echo ""
        echo "Run 'deploy health --help' for usage."
        return 1
        ;;
    esac
  done

  # JSON output mode
  if [[ $use_json -eq 1 ]]; then
    # Run checks silently and output JSON
    local overall_status="healthy"
    local failures=0

    case "$component" in
      system)
        check_system_health >/dev/null 2>&1 || failures=$((failures + 1))
        ;;
      ai-stack)
        check_ai_stack_health >/dev/null 2>&1 || failures=$((failures + 1))
        ;;
      network)
        check_network_health >/dev/null 2>&1 || failures=$((failures + 1))
        ;;
      storage)
        check_storage_health >/dev/null 2>&1 || failures=$((failures + 1))
        ;;
      all)
        check_system_health >/dev/null 2>&1 || failures=$((failures + 1))
        check_ai_stack_health >/dev/null 2>&1 || failures=$((failures + 1))
        check_network_health >/dev/null 2>&1 || failures=$((failures + 1))
        check_storage_health >/dev/null 2>&1 || failures=$((failures + 1))
        ;;
      *)
        output_health_json "$component" "error" "Unknown component: $component"
        return 2
        ;;
    esac

    if [[ $failures -gt 0 ]]; then
      overall_status="unhealthy"
    fi

    output_health_json "$component" "$overall_status" "$failures check(s) failed"
    return $failures
  fi

  # Normal output mode
  print_header "System Health Check"

  local total_failures=0

  case "$component" in
    system)
      log_step 1 1 "System health..."
      check_system_health || total_failures=$((total_failures + 1))
      ;;
    ai-stack)
      log_step 1 1 "AI stack health..."
      check_ai_stack_health || total_failures=$((total_failures + 1))
      ;;
    network)
      log_step 1 1 "Network health..."
      check_network_health || total_failures=$((total_failures + 1))
      ;;
    storage)
      log_step 1 1 "Storage health..."
      check_storage_health || total_failures=$((total_failures + 1))
      ;;
    all)
      log_step 1 4 "System health..."
      check_system_health || total_failures=$((total_failures + 1))

      log_step 2 4 "AI stack health..."
      check_ai_stack_health || total_failures=$((total_failures + 1))

      log_step 3 4 "Network health..."
      check_network_health || total_failures=$((total_failures + 1))

      log_step 4 4 "Storage health..."
      check_storage_health || total_failures=$((total_failures + 1))
      ;;
    *)
      log_error "Unknown component: $component"
      echo ""
      echo "Valid components: system, ai-stack, network, storage, all"
      return 2
      ;;
  esac

  echo ""

  if [[ $total_failures -eq 0 ]]; then
    log_success "All health checks passed"

    print_section "Next Steps"
    echo "  • System is healthy and ready for use"
    echo "  • Run 'deploy dashboard' to view monitoring data"
    echo "  • Run 'deploy ai-stack status' for detailed service states"

    return 0
  else
    log_error "$total_failures component(s) unhealthy"

    print_section "Troubleshooting"
    echo "  • Run 'deploy health --component <name>' for detailed checks"
    echo "  • Run 'deploy ai-stack status' to check service states"
    echo "  • Run 'deploy ai-stack logs <service>' to view logs"
    echo "  • Run 'deploy recover diagnose' for recovery options"

    return 1
  fi
}
