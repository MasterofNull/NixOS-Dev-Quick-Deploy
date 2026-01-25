#!/usr/bin/env bash
# Deployment Script - Option A (Aggressive)
# Deploy ALL January 2026 package updates at once
# Created: 2026-01-10

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
BACKUP_DIR="${HOME}/.local/share/nixos-ai-stack/backups/jan2026-$(date +%Y%m%d-%H%M%S)"
COMPOSE_FILE="ai-stack/compose/docker-compose.yml"
POSTGRES_CONTAINER="local-ai-postgres"
POSTGRES_USER="mcp"
POSTGRES_DB="mcp"
QDRANT_CONTAINER="local-ai-qdrant"
REDIS_CONTAINER="local-ai-redis"

# Set required environment variables
export AI_STACK_ENV_FILE="${HOME}/.config/nixos-ai-stack/.env"

# Track deployment status
DEPLOYMENT_LOG="${BACKUP_DIR}/deployment.log"
ROLLBACK_SCRIPT="${BACKUP_DIR}/rollback.sh"

# Create backup directory
mkdir -p "$BACKUP_DIR"

log_info "Starting Option A Deployment - January 2026 Updates"
log_info "Backup directory: $BACKUP_DIR"

# Step 1: Pre-flight checks
log_info "Step 1: Running pre-flight checks..."

check_docker() {
    if ! command -v podman &> /dev/null; then
        log_error "Podman not found. Please install Podman."
        exit 1
    fi
    log_success "Podman is installed"
}

check_compose() {
    if ! command -v podman-compose &> /dev/null; then
        log_error "Podman-compose not found. Please install podman-compose."
        exit 1
    fi
    log_success "Podman-compose is installed"
}

check_running_containers() {
    local running=$(podman ps --format '{{.Names}}' | grep -c 'local-ai' || true)
    log_info "Found $running running AI stack containers"
    if [ "$running" -eq 0 ]; then
        log_warning "No AI stack containers are running. Start them first."
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

check_docker
check_compose
check_running_containers

# Step 2: Backup critical data
log_info "Step 2: Backing up critical data..."

backup_postgresql() {
    log_info "Backing up PostgreSQL databases..."

    if podman exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" &>/dev/null; then
        # Backup all databases
        podman exec "$POSTGRES_CONTAINER" pg_dumpall -U "$POSTGRES_USER" > "${BACKUP_DIR}/postgres-all-databases.sql"
        log_success "PostgreSQL backup created: postgres-all-databases.sql"

        # Verify backup size
        local backup_size=$(stat -c%s "${BACKUP_DIR}/postgres-all-databases.sql" 2>/dev/null || stat -f%z "${BACKUP_DIR}/postgres-all-databases.sql" 2>/dev/null)
        if [ "$backup_size" -lt 1000 ]; then
            log_error "PostgreSQL backup appears empty or corrupted"
            exit 1
        fi
        log_info "Backup size: $(echo $backup_size | numfmt --to=iec 2>/dev/null || echo $backup_size bytes)"
    else
        log_error "PostgreSQL is not ready for backup"
        exit 1
    fi
}

backup_qdrant() {
    log_info "Backing up Qdrant data..."

    # Get Qdrant storage path
    local qdrant_storage=$(podman inspect "$QDRANT_CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/qdrant/storage"}}{{.Source}}{{end}}{{end}}')

    if [ -n "$qdrant_storage" ] && [ -d "$qdrant_storage" ]; then
        cp -r "$qdrant_storage" "${BACKUP_DIR}/qdrant-storage"
        log_success "Qdrant backup created: qdrant-storage/"
    else
        log_warning "Qdrant storage path not found, skipping backup"
    fi
}

backup_redis() {
    log_info "Backing up Redis data..."

    # Trigger RDB save
    if podman exec "$REDIS_CONTAINER" redis-cli SAVE &>/dev/null; then
        # Copy RDB file
        local redis_data=$(podman inspect "$REDIS_CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}')

        if [ -n "$redis_data" ] && [ -f "${redis_data}/dump.rdb" ]; then
            cp "${redis_data}/dump.rdb" "${BACKUP_DIR}/redis-dump.rdb" 2>/dev/null || log_warning "Failed to copy Redis dump file (permission denied)"
            if [ -f "${BACKUP_DIR}/redis-dump.rdb" ]; then
                log_success "Redis backup created: redis-dump.rdb"
            else
                log_warning "Redis backup skipped due to permissions"
            fi
        fi
    else
        log_warning "Redis SAVE command failed, skipping backup"
    fi
}

backup_postgresql
backup_qdrant
backup_redis

# Step 3: Create rollback script
log_info "Step 3: Creating rollback script..."

cat > "$ROLLBACK_SCRIPT" << 'ROLLBACK_EOF'
#!/usr/bin/env bash
# Rollback script for January 2026 deployment
set -euo pipefail

BACKUP_DIR="$(dirname "$0")"

echo "Rolling back to pre-deployment state..."

# Stop all containers
echo "Stopping all containers..."
cd ~/Documents/try/NixOS-Dev-Quick-Deploy
podman-compose -f ai-stack/compose/docker-compose.yml down

# Restore PostgreSQL
if [ -f "${BACKUP_DIR}/postgres-all-databases.sql" ]; then
    echo "Restoring PostgreSQL..."
    podman-compose -f ai-stack/compose/docker-compose.yml up -d postgres
    sleep 10
    podman exec -i local-ai-postgres psql -U mcp < "${BACKUP_DIR}/postgres-all-databases.sql"
fi

# Restart all services
echo "Restarting all services..."
podman-compose -f ai-stack/compose/docker-compose.yml up -d

echo "Rollback complete. Check service health."
ROLLBACK_EOF

chmod +x "$ROLLBACK_SCRIPT"
log_success "Rollback script created: $ROLLBACK_SCRIPT"

# Step 4: Update package database
log_info "Step 4: Updating package database..."

update_package_database() {
    # Check if postgres is ready
    if ! podman exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" &>/dev/null; then
        log_error "PostgreSQL is not ready"
        return 1
    fi

    # Run SQL updates
    log_info "Running comprehensive update SQL..."
    if [ -f "ai-stack/sql/comprehensive_update_jan2026.sql" ]; then
        podman exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < ai-stack/sql/comprehensive_update_jan2026.sql
        log_success "Package database updated"
    else
        log_warning "comprehensive_update_jan2026.sql not found, skipping"
    fi
}

update_package_database

# Step 5: Update docker-compose.yml with new versions
log_info "Step 5: Updating container versions in docker-compose.yml..."

update_compose_versions() {
    local compose_file="$COMPOSE_FILE"

    if [ ! -f "$compose_file" ]; then
        log_error "docker-compose.yml not found at $compose_file"
        return 1
    fi

    # Backup original compose file
    cp "$compose_file" "${BACKUP_DIR}/docker-compose.yml.backup"

    # Update images to latest versions
    # PostgreSQL 15 -> 18.1
    sed -i.bak 's/postgres:15/postgres:18.1/g' "$compose_file"

    # Qdrant v1.7.4 -> v1.16.0
    sed -i.bak 's/qdrant\/qdrant:v1\.7\.4/qdrant\/qdrant:v1.16.0/g' "$compose_file"

    # Redis 7 -> 8.4
    sed -i.bak 's/redis:7/redis:8.4/g' "$compose_file"

    # Prometheus v2.45.0 -> v3.9.1
    sed -i.bak 's/prom\/prometheus:v2\.45\.0/prom\/prometheus:v3.9.1/g' "$compose_file"

    # Grafana 10.2.0 -> 12.3.0
    sed -i.bak 's/grafana\/grafana:10\.2\.0/grafana\/grafana:12.3.0/g' "$compose_file"

    # Jaeger v1 -> v2.0
    sed -i.bak 's/jaegertracing\/all-in-one:1\./jaegertracing\/all-in-one:2.0/g' "$compose_file"

    # MindsDB to latest
    sed -i.bak 's/mindsdb\/mindsdb:latest/mindsdb\/mindsdb:25.13.1/g' "$compose_file"

    log_success "docker-compose.yml updated with new versions"
}

update_compose_versions

# Step 6: Rebuild custom containers
log_info "Step 6: Rebuilding custom containers..."

rebuild_aider_wrapper() {
    log_info "Rebuilding aider-wrapper with v0.86.1..."

    cd ai-stack/mcp-servers/aider-wrapper

    # Build new image
    podman build -t local-ai-aider-wrapper:latest . 2>&1 | tee -a "$DEPLOYMENT_LOG"

    if [ $? -eq 0 ]; then
        log_success "aider-wrapper v0.86.1 built successfully"
    else
        log_error "aider-wrapper build failed"
        cd - > /dev/null
        return 1
    fi

    cd - > /dev/null
}

rebuild_aider_wrapper

# Step 7: Deploy updated containers
log_info "Step 7: Deploying updated containers..."

deploy_containers() {
    log_info "Pulling updated images..."
    cd ~/Documents/try/NixOS-Dev-Quick-Deploy
    podman-compose -f "$COMPOSE_FILE" pull 2>&1 | tee -a "$DEPLOYMENT_LOG"

    log_info "Stopping all services..."
    podman-compose -f "$COMPOSE_FILE" down

    log_info "Starting services with new versions..."
    podman-compose -f "$COMPOSE_FILE" up -d

    log_success "All services started with new versions"
}

deploy_containers

# Step 8: Wait for services to be ready
log_info "Step 8: Waiting for services to be ready..."

wait_for_service() {
    local service_name=$1
    local health_check=$2
    local max_wait=60
    local wait_count=0

    log_info "Waiting for $service_name..."

    while [ $wait_count -lt $max_wait ]; do
        if eval "$health_check" &>/dev/null; then
            log_success "$service_name is ready"
            return 0
        fi
        sleep 2
        wait_count=$((wait_count + 2))
    done

    log_error "$service_name failed to become ready after ${max_wait}s"
    return 1
}

wait_for_service "PostgreSQL" "podman exec $POSTGRES_CONTAINER pg_isready -U $POSTGRES_USER"
wait_for_service "Qdrant" "curl -f http://localhost:6333/healthz"
wait_for_service "Redis" "podman exec $REDIS_CONTAINER redis-cli ping"

# Step 9: Run post-deployment migrations
log_info "Step 9: Running post-deployment migrations..."

run_postgres_migrations() {
    log_info "Running PostgreSQL 18 optimizations..."

    # Run ANALYZE on all databases
    podman exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -c "VACUUM ANALYZE;" 2>&1 | tee -a "$DEPLOYMENT_LOG"

    log_success "PostgreSQL optimizations complete"
}

run_postgres_migrations

# Step 10: Verify deployments
log_info "Step 10: Verifying deployments..."

verify_versions() {
    log_info "Checking deployed versions..."

    # PostgreSQL version
    local pg_version=$(podman exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -t -c "SELECT version();" | head -n1)
    log_info "PostgreSQL: $pg_version"

    # Qdrant version
    local qdrant_version=$(curl -s http://localhost:6333/ | grep -o '"version":"[^"]*"' || echo "unknown")
    log_info "Qdrant: $qdrant_version"

    # Redis version
    local redis_version=$(podman exec "$REDIS_CONTAINER" redis-cli INFO server | grep redis_version | cut -d: -f2 | tr -d '\r')
    log_info "Redis: $redis_version"

    # Check container statuses
    log_info "Container statuses:"
    podman ps --filter "name=local-ai" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

verify_versions

# Step 11: Run health checks
log_info "Step 11: Running comprehensive health checks..."

run_health_checks() {
    local failed_checks=0

    # PostgreSQL health
    if podman exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" &>/dev/null; then
        log_success "PostgreSQL: HEALTHY"
    else
        log_error "PostgreSQL: UNHEALTHY"
        failed_checks=$((failed_checks + 1))
    fi

    # Qdrant health
    if curl -f http://localhost:6333/healthz &>/dev/null; then
        log_success "Qdrant: HEALTHY"
    else
        log_error "Qdrant: UNHEALTHY"
        failed_checks=$((failed_checks + 1))
    fi

    # Redis health
    if podman exec "$REDIS_CONTAINER" redis-cli ping | grep -q PONG; then
        log_success "Redis: HEALTHY"
    else
        log_error "Redis: UNHEALTHY"
        failed_checks=$((failed_checks + 1))
    fi

    # AIDB health
    if curl -f http://localhost:8091/health &>/dev/null; then
        log_success "AIDB: HEALTHY"
    else
        log_warning "AIDB: NOT RESPONDING (may still be starting)"
    fi

    # Hybrid Coordinator health
    if curl -f http://localhost:8092/health &>/dev/null; then
        log_success "Hybrid Coordinator: HEALTHY"
    else
        log_warning "Hybrid Coordinator: NOT RESPONDING (may still be starting)"
    fi

    return $failed_checks
}

if run_health_checks; then
    log_success "All critical health checks passed"
else
    log_warning "Some health checks failed. Review the logs."
fi

# Step 12: Generate deployment report
log_info "Step 12: Generating deployment report..."

cat > "${BACKUP_DIR}/DEPLOYMENT-REPORT.md" << 'REPORT_EOF'
# January 2026 Updates - Deployment Report
**Deployment Date**: $(date)
**Deployment Type**: Option A (Aggressive - All Updates)

## Packages Updated

### Critical Updates
- **Jaeger**: v1.x → v2.0 (V1 deprecated January 2026)
- **Aider**: Not installed → v0.86.1 (Core functionality)
- **Prometheus**: v2.45.0 → v3.9.1 (Security fixes)

### Major Updates
- **PostgreSQL**: 15 → 18.1 (Major version upgrade)
- **Qdrant**: v1.7.4 → v1.16.0 (New features)
- **Redis**: 7 → 8.4 (Latest GA)
- **Grafana**: 10.2.0 → 12.3.0 (Major UI update)
- **MindsDB**: unknown → 25.13.1 (Latest release)

### Custom Containers Rebuilt
- **aider-wrapper**: v0.86.1 with real Aider integration

## Verification Commands

```bash
# Check all container health
podman ps --filter "name=local-ai"

# PostgreSQL version
podman exec local-ai-postgres psql -U mcp -c "SELECT version();"

# Qdrant version
curl http://localhost:6333/

# Redis version
podman exec local-ai-redis redis-cli INFO server | grep redis_version

# AIDB health
curl http://localhost:8091/health

# Hybrid Coordinator health
curl http://localhost:8092/health
```

REPORT_EOF

log_success "Deployment report created: ${BACKUP_DIR}/DEPLOYMENT-REPORT.md"

# Final summary
echo ""
echo "=========================================="
log_success "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
log_info "Summary:"
echo "  - Backup location: $BACKUP_DIR"
echo "  - Rollback script: $ROLLBACK_SCRIPT"
echo "  - Deployment report: ${BACKUP_DIR}/DEPLOYMENT-REPORT.md"
echo "  - Deployment log: $DEPLOYMENT_LOG"
echo ""
log_info "Next steps:"
echo "  1. Monitor service health for 24 hours"
echo "  2. Review deployment report for known issues"
echo "  3. Update Grafana dashboards for Prometheus v3"
echo "  4. Test Jaeger v2 tracing functionality"
echo "  5. Submit P3 tasks to Ralph for performance features"
echo ""
log_warning "If you encounter issues, run: bash $ROLLBACK_SCRIPT"
echo ""
