#!/usr/bin/env bash
# AI Stack Automatic Startup Script
# Starts all AI containers, MCP services, and monitoring on system boot
# Author: Claude Code (Vibe Coding System)
# Date: 2025-12-31

set -euo pipefail

# Ensure /run/wrappers/bin is in PATH for setuid helpers (newuidmap/newgidmap)
export PATH="/run/wrappers/bin:${PATH:-/run/current-system/sw/bin}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${HOME}/.cache/nixos-quick-deploy/logs"
LOG_FILE="${LOG_DIR}/ai-stack-startup-$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

info() {
    log "ℹ INFO: $*"
}

success() {
    log "✓ SUCCESS: $*"
}

error() {
    log "✗ ERROR: $*"
}

warn() {
    log "⚠ WARNING: $*"
}

# Wait for network to be ready
wait_for_network() {
    info "Waiting for network connectivity..."
    local retries=30
    local count=0

    while [ $count -lt $retries ]; do
        if ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then
            success "Network is ready"
            return 0
        fi
        count=$((count + 1))
        sleep 2
    done

    warn "Network check timeout - proceeding anyway"
    return 0
}

# Wait for Podman socket to be ready
wait_for_podman() {
    info "Waiting for Podman to be ready..."
    local retries=30
    local count=0

    while [ $count -lt $retries ]; do
        local info_output=""
        info_output="$(podman info 2>&1 || true)"
        if echo "$info_output" | grep -q "current system boot ID differs"; then
            warn "Podman runtime boot ID mismatch detected."
            if [[ -x "${PROJECT_ROOT}/scripts/reset-podman-runtime.sh" ]]; then
                if "${PROJECT_ROOT}/scripts/reset-podman-runtime.sh"; then
                    info "Retesting Podman after runtime reset..."
                    continue
                else
                    warn "Podman runtime reset required before startup."
                    return 1
                fi
            else
                warn "Missing reset script: ${PROJECT_ROOT}/scripts/reset-podman-runtime.sh"
                return 1
            fi
        fi

        if podman info >/dev/null 2>&1; then
            success "Podman is ready"
            return 0
        fi
        count=$((count + 1))
        sleep 2
    done

    error "Podman not ready after 60 seconds"
    return 1
}

# Wait for containers to become healthy
# Uses podman health checks instead of arbitrary sleep delays
wait_for_containers_healthy() {
    local max_wait=180  # 3 minutes max
    local check_interval=5
    local elapsed=0

    info "Waiting for containers to pass health checks: $*"

    while [ $elapsed -lt $max_wait ]; do
        local all_healthy=true
        local status_summary=""

        for container_short_name in "$@"; do
            local container_name="local-ai-${container_short_name}"
            local health_status=$(podman inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")

            # Handle containers without health checks (consider them healthy if running)
            if [ "$health_status" = "none" ] || [ "$health_status" = "" ]; then
                local is_running=$(podman ps --filter "name=^${container_name}$" --format "{{.Names}}" 2>/dev/null)
                if [ -n "$is_running" ]; then
                    health_status="running"
                else
                    health_status="not_running"
                fi
            fi

            status_summary="$status_summary $container_short_name:$health_status"

            if [ "$health_status" != "healthy" ] && [ "$health_status" != "running" ]; then
                all_healthy=false
            fi
        done

        if [ "$all_healthy" = true ]; then
            success "All containers are healthy:$status_summary"
            return 0
        fi

        info "Container status (${elapsed}s):$status_summary"
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done

    warn "Timeout waiting for containers to become healthy after ${max_wait}s"
    return 1
}

# Ensure services are running without recreating existing containers.
ensure_services_running() {
    local services=("$@")
    for service in "${services[@]}"; do
        local container_name="local-ai-${service}"
        if podman container exists "$container_name" 2>/dev/null; then
            if podman ps --filter "name=^${container_name}$" --format "{{.Names}}" | grep -q "$container_name"; then
                info "Service already running: $service"
            else
                info "Starting existing container: $service"
                podman start "$container_name" 2>&1 | tee -a "$LOG_FILE" || {
                    error "Failed to start existing container: $service"
                    return 1
                }
            fi
        else
            info "Creating service container: $service"
            if podman-compose up -d "$service" 2>&1 | tee -a "$LOG_FILE"; then
                true
            else
                error "Failed to create/start service: $service"
                return 1
            fi
        fi
    done
}

# Start core AI infrastructure
start_core_infrastructure() {
    info "Starting core AI infrastructure (postgres, redis, qdrant, embeddings, llama-cpp, mindsdb)..."

    cd "$PROJECT_ROOT/ai-stack/compose"

    ensure_services_running postgres redis qdrant embeddings llama-cpp mindsdb
    success "Core infrastructure started"

    # Wait for services to be healthy (using docker health checks)
    info "Waiting for core services to become healthy..."
    wait_for_containers_healthy "postgres" "redis" "qdrant" "embeddings" "llama-cpp" "mindsdb"
}

# Check service health
check_service_health() {
    local service_name="$1"
    local health_url="$2"
    local max_retries="${3:-10}"

    info "Checking $service_name health..."
    local count=0

    while [ $count -lt $max_retries ]; do
        if curl -sf --max-time 2 "$health_url" >/dev/null 2>&1; then
            success "$service_name is healthy"
            return 0
        fi
        count=$((count + 1))
        sleep 3
    done

    warn "$service_name health check timeout"
    return 1
}

# Start MCP services
start_mcp_services() {
    info "Starting MCP services (AIDB, Hybrid Coordinator, Health Monitor)..."

    cd "$PROJECT_ROOT/ai-stack/compose"

    # Use existing images (no --build flag to avoid rebuilding on every boot)
    ensure_services_running aidb hybrid-coordinator health-monitor
    success "MCP services started"

    # Wait for MCP services to become healthy
    info "Waiting for MCP services to become healthy..."
    wait_for_containers_healthy "aidb" "hybrid-coordinator" "health-monitor"

    # Verify endpoints are responding
    check_service_health "AIDB" "http://localhost:8091/health" 5
    check_service_health "Hybrid Coordinator" "http://localhost:8092/health" 5
}

# Initialize Qdrant collections if needed
initialize_qdrant_collections() {
    info "Checking Qdrant collections..."

    # Check if collections exist
    local collection_count=$(curl -sf http://localhost:6333/collections 2>/dev/null | jq -r '.result.collections | length' 2>/dev/null || echo "0")

    if [ "$collection_count" -lt 5 ]; then
        info "Initializing Qdrant collections..."
        if bash "$PROJECT_ROOT/scripts/initialize-qdrant-collections.sh" 2>&1 | tee -a "$LOG_FILE"; then
            success "Qdrant collections initialized"
        else
            warn "Qdrant collection initialization had issues"
        fi
    else
        success "Qdrant collections already exist ($collection_count collections)"
    fi
}

# Start dashboard services
start_dashboard_services() {
    info "Starting dashboard services..."

    # Check if dashboard server is already running
    if systemctl --user is-active --quiet dashboard-server.service; then
        info "Dashboard server already running"
    else
        systemctl --user start dashboard-server.service 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard server start failed"
    fi

    # Check if dashboard API is already running
    if systemctl --user is-active --quiet dashboard-api.service; then
        info "Dashboard API already running"
    else
        systemctl --user start dashboard-api.service 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard API start failed"
    fi

    # Start dashboard collector timer
    if systemctl --user is-active --quiet dashboard-collector.timer; then
        info "Dashboard collector already running"
    else
        systemctl --user start dashboard-collector.timer 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard collector start failed"
    fi

    # Force initial metrics collection
    info "Collecting initial dashboard metrics..."
    bash "$PROJECT_ROOT/scripts/collect-ai-metrics.sh" 2>&1 | tee -a "$LOG_FILE" || warn "Initial metrics collection failed"
    bash "$PROJECT_ROOT/scripts/generate-dashboard-data-lite.sh" 2>&1 | tee -a "$LOG_FILE" || warn "Dashboard data generation failed"

    success "Dashboard services started"
}

# Run health checks
run_health_checks() {
    info "Running comprehensive health checks..."

    local failed_checks=0

    # Check container status
    info "Checking container status..."
    local expected_containers=(
        "local-ai-postgres"
        "local-ai-redis"
        "local-ai-qdrant"
        "local-ai-embeddings"
        "local-ai-llama-cpp"
        "local-ai-mindsdb"
        "local-ai-aidb"
        "local-ai-hybrid-coordinator"
        "local-ai-health-monitor"
    )

    for container in "${expected_containers[@]}"; do
        if podman ps --format "{{.Names}}" | grep -q "^${container}$"; then
            success "Container running: $container"
        else
            error "Container not running: $container"
            failed_checks=$((failed_checks + 1))
        fi
    done

    # Check service endpoints
    info "Checking service endpoints..."

    if curl -sf http://localhost:8091/health >/dev/null 2>&1; then
        success "AIDB endpoint healthy"
    else
        error "AIDB endpoint failed"
        failed_checks=$((failed_checks + 1))
    fi

    if curl -sf http://localhost:8092/health >/dev/null 2>&1; then
        success "Hybrid Coordinator endpoint healthy"
    else
        error "Hybrid Coordinator endpoint failed"
        failed_checks=$((failed_checks + 1))
    fi

    if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
        success "Qdrant endpoint healthy"
    else
        error "Qdrant endpoint failed"
        failed_checks=$((failed_checks + 1))
    fi

    if curl -sf http://localhost:8081/health >/dev/null 2>&1; then
        success "Embeddings service endpoint healthy"
    else
        error "Embeddings service endpoint failed"
        failed_checks=$((failed_checks + 1))
    fi

    if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        success "llama.cpp endpoint healthy"
    else
        error "llama.cpp endpoint failed"
        failed_checks=$((failed_checks + 1))
    fi

    # Report results
    if [ $failed_checks -eq 0 ]; then
        success "All health checks passed!"
        return 0
    else
        warn "$failed_checks health check(s) failed"
        return 1
    fi
}

# Generate startup report
generate_startup_report() {
    local status="$1"
    local report_file="${HOME}/.local/share/nixos-ai-stack/startup-report-$(date +%Y%m%d_%H%M%S).txt"

    mkdir -p "$(dirname "$report_file")"

    cat > "$report_file" <<EOF
AI Stack Startup Report
=======================
Date: $(date)
Status: $status
Log: $LOG_FILE

Container Status:
$(podman ps --format "table {{.Names}}\t{{.Status}}" | grep local-ai || echo "No containers running")

Service Health:
- AIDB: $(curl -sf http://localhost:8091/health 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unreachable")
- Hybrid Coordinator: $(curl -sf http://localhost:8092/health 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unreachable")
- Qdrant: $(curl -sf http://localhost:6333/healthz 2>/dev/null || echo "unreachable")
- Embeddings: $(curl -sf http://localhost:8081/health 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unreachable")
- llama.cpp: $(curl -sf http://localhost:8080/health 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unreachable")

Dashboard:
- Server: $(systemctl --user is-active dashboard-server.service || echo "inactive")
- API: $(systemctl --user is-active dashboard-api.service || echo "inactive")
- Collector: $(systemctl --user is-active dashboard-collector.timer || echo "inactive")
- URL: http://localhost:8888/dashboard.html
- API URL: http://localhost:8889

Resource Usage:
$(podman stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}" 2>/dev/null | grep local-ai || echo "Stats unavailable")
EOF

    info "Startup report saved to: $report_file"
}

# Main startup sequence
main() {
    info "=== AI Stack Startup Beginning ==="
    info "Log file: $LOG_FILE"

    # Pre-flight checks
    wait_for_network
    wait_for_podman || {
        error "Podman not available - cannot start AI stack"
        exit 1
    }

    # Start services in order
    start_core_infrastructure || {
        error "Core infrastructure failed to start"
        generate_startup_report "FAILED"
        exit 1
    }

    start_mcp_services || {
        error "MCP services failed to start"
        generate_startup_report "PARTIAL"
        exit 1
    }

    initialize_qdrant_collections || warn "Qdrant initialization had issues"

    start_dashboard_services || warn "Dashboard services had issues"

    # Final health check (no sleep needed - containers already healthy)
    if run_health_checks; then
        success "=== AI Stack Startup Complete ==="
        generate_startup_report "SUCCESS"

        # Display summary
        echo ""
        echo "╔══════════════════════════════════════════════════════════╗"
        echo "║          AI Stack Started Successfully                   ║"
        echo "╠══════════════════════════════════════════════════════════╣"
        echo "║  Dashboard:   http://localhost:8888/dashboard.html      ║"
        echo "║  AIDB MCP:    http://localhost:8091/health              ║"
        echo "║  Hybrid:      http://localhost:8092/health              ║"
        echo "║  Qdrant:      http://localhost:6333/dashboard           ║"
        echo "║  Embeddings:  http://localhost:8081/health              ║"
        echo "║  llama.cpp:   http://localhost:8080                     ║"
        echo "║  Log:         $LOG_FILE"
        echo "╚══════════════════════════════════════════════════════════╝"
        echo ""

        exit 0
    else
        warn "=== AI Stack Startup Completed with Warnings ==="
        generate_startup_report "WARNING"
        exit 0
    fi
}

# Run main function
main "$@"
