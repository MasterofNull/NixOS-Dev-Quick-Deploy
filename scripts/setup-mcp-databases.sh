#!/usr/bin/env bash
#
# MCP Database Setup Script
# Version: 1.0.0
# Purpose: Set up PostgreSQL and Redis containers for AIDB MCP Server
#
# ============================================================================

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Configuration
readonly POSTGRES_IMAGE="${MCP_POSTGRES_IMAGE:-docker.io/library/postgres:16-alpine}"
readonly REDIS_VERSION="7"
readonly MCP_DATA_DIR="${HOME}/.local/share/aidb"
readonly POSTGRES_DATA_DIR="${MCP_DATA_DIR}/postgres"
readonly REDIS_DATA_DIR="${MCP_DATA_DIR}/redis"

# Database credentials - use environment variable or generate secure password
readonly POSTGRES_USER="mcp"
readonly POSTGRES_DB="mcp"

# Security: Generate random password if not provided via environment
if [[ -z "${MCP_POSTGRES_PASSWORD:-}" ]]; then
    log_warning "MCP_POSTGRES_PASSWORD not set - generating secure random password"
    GENERATED_PASSWORD="$(openssl rand -base64 32)"
    readonly POSTGRES_PASSWORD="$GENERATED_PASSWORD"
    log_warning "⚠️  SAVE THIS PASSWORD: $POSTGRES_PASSWORD"
    log_warning "⚠️  Set MCP_POSTGRES_PASSWORD environment variable to persist"
else
    readonly POSTGRES_PASSWORD="$MCP_POSTGRES_PASSWORD"
    log_success "Using password from MCP_POSTGRES_PASSWORD environment variable"
fi

detect_podman() {
    if [[ -x /run/current-system/sw/bin/podman ]]; then
        echo "/run/current-system/sw/bin/podman"
    elif command -v podman >/dev/null 2>&1; then
        command -v podman
    else
        log_error "Podman binary not found in PATH or /run/current-system/sw/bin. Install Podman and re-run this script."
        exit 1
    fi
}

readonly PODMAN_BIN="$(detect_podman)"

create_directories() {
    log_info "Creating data directories..."

    mkdir -p "$POSTGRES_DATA_DIR"
    mkdir -p "$REDIS_DATA_DIR"

    log_success "Directories created"
}

setup_postgres() {
    log_info "Setting up PostgreSQL container..."

    # Stop existing container if running
    "${PODMAN_BIN}" stop mcp-postgres 2>/dev/null || true
    "${PODMAN_BIN}" rm mcp-postgres 2>/dev/null || true

    # Create and start PostgreSQL container
    "${PODMAN_BIN}" run -d \
        --name mcp-postgres \
        --network local-ai \
        -e POSTGRES_USER="$POSTGRES_USER" \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -e POSTGRES_DB="$POSTGRES_DB" \
        -v "$POSTGRES_DATA_DIR:/var/lib/postgresql/data:Z" \
        -p 5432:5432 \
        "${POSTGRES_IMAGE}"

    log_success "PostgreSQL container created and starting"

    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if "${PODMAN_BIN}" exec mcp-postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            return 0
        fi
        sleep 1
    done

    log_error "PostgreSQL failed to start in time"
    return 1
}

create_postgres_databases() {
    log_info "Creating additional PostgreSQL databases..."

    "${PODMAN_BIN}" exec mcp-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
		-- Create additional databases for MCP server
		CREATE DATABASE IF NOT EXISTS mcp_tools;
		CREATE DATABASE IF NOT EXISTS mcp_logs;

		-- Grant permissions
		GRANT ALL PRIVILEGES ON DATABASE mcp TO $POSTGRES_USER;
		GRANT ALL PRIVILEGES ON DATABASE mcp_tools TO $POSTGRES_USER;
		GRANT ALL PRIVILEGES ON DATABASE mcp_logs TO $POSTGRES_USER;
	EOSQL

    log_success "Additional databases created"
}

setup_redis() {
    log_info "Setting up Redis container..."

    # Stop existing container if running
    "${PODMAN_BIN}" stop mcp-redis 2>/dev/null || true
    "${PODMAN_BIN}" rm mcp-redis 2>/dev/null || true

    # Create Redis configuration
    cat > "${REDIS_DATA_DIR}/redis.conf" <<EOF
# Redis configuration for MCP server
bind 127.0.0.1
protected-mode yes
port 6379
tcp-backlog 511
timeout 0
tcp-keepalive 300
daemonize no
supervised no
pidfile /data/redis.pid
loglevel notice
databases 16
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data
maxmemory 512mb
maxmemory-policy allkeys-lru
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
EOF

    # Create and start Redis container
    "${PODMAN_BIN}" run -d \
        --name mcp-redis \
        --network local-ai \
        -v "$REDIS_DATA_DIR:/data:Z" \
        -p 6379:6379 \
        "docker.io/library/redis:${REDIS_VERSION}-alpine" \
        redis-server /data/redis.conf

    log_success "Redis container created and started"

    # Test Redis
    sleep 2
    if "${PODMAN_BIN}" exec mcp-redis redis-cli ping | grep -q "PONG"; then
        log_success "Redis is responding"
    else
        log_error "Redis is not responding"
        return 1
    fi
}

verify_services() {
    log_info "Verifying database services..."

    local all_ok=true

    # Check PostgreSQL
    if "${PODMAN_BIN}" exec mcp-postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
        log_success "✓ PostgreSQL is running on localhost:5432"
    else
        log_error "✗ PostgreSQL check failed"
        all_ok=false
    fi

    # Check Redis
    if "${PODMAN_BIN}" exec mcp-redis redis-cli ping | grep -q "PONG"; then
        log_success "✓ Redis is running on localhost:6379"
    else
        log_error "✗ Redis check failed"
        all_ok=false
    fi

    # Check Qdrant (from existing AI stack)
    if "${PODMAN_BIN}" ps --filter "name=local-ai-qdrant" --format "{{.Status}}" | grep -q "Up"; then
        log_success "✓ Qdrant is running (from AI stack)"
    else
        log_warning "⚠ Qdrant container not found"
    fi

    if [[ "$all_ok" == true ]]; then
        return 0
    else
        return 1
    fi
}

create_systemd_services() {
    log_info "Creating systemd user services..."

    mkdir -p "${HOME}/.config/systemd/user"

    # PostgreSQL systemd service
    cat > "${HOME}/.config/systemd/user/mcp-postgres.service" <<EOF
[Unit]
Description=PostgreSQL Database for MCP Server
After=network.target podman-local-ai-network.service
Requires=podman-local-ai-network.service

[Service]
Type=forking
RemainAfterExit=yes
ExecStartPre=-${PODMAN_BIN} stop mcp-postgres
ExecStartPre=-${PODMAN_BIN} rm mcp-postgres
ExecStart=${PODMAN_BIN} run -d \\
    --name mcp-postgres \\
    --network local-ai \\
    -e POSTGRES_USER=${POSTGRES_USER} \\
    -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \\
    -e POSTGRES_DB=${POSTGRES_DB} \\
    -v ${POSTGRES_DATA_DIR}:/var/lib/postgresql/data:Z \\
    -p 5432:5432 \\
    ${POSTGRES_IMAGE}

ExecStop=${PODMAN_BIN} stop mcp-postgres
ExecStopPost=${PODMAN_BIN} rm mcp-postgres
Restart=on-failure
RestartSec=10
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF

    # Redis systemd service
    cat > "${HOME}/.config/systemd/user/mcp-redis.service" <<EOF
[Unit]
Description=Redis Cache for MCP Server
After=network.target podman-local-ai-network.service
Requires=podman-local-ai-network.service

[Service]
Type=forking
RemainAfterExit=yes
ExecStartPre=-${PODMAN_BIN} stop mcp-redis
ExecStartPre=-${PODMAN_BIN} rm mcp-redis
ExecStart=${PODMAN_BIN} run -d \\
    --name mcp-redis \\
    --network local-ai \\
    -v ${REDIS_DATA_DIR}:/data:Z \\
    -p 6379:6379 \\
    docker.io/library/redis:${REDIS_VERSION}-alpine \\
    redis-server /data/redis.conf

ExecStop=${PODMAN_BIN} stop mcp-redis
ExecStopPost=${PODMAN_BIN} rm mcp-redis
Restart=on-failure
RestartSec=10
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF

    # Reload systemd
    systemctl --user daemon-reload

    log_success "Systemd services created"
}

enable_services() {
    log_info "Enabling services to start on boot..."

    systemctl --user enable mcp-postgres.service
    systemctl --user enable mcp-redis.service

    log_success "Services enabled"
}

show_summary() {
    echo ""
    echo "============================================"
    log_success "MCP Database Setup Complete!"
    echo "============================================"
    echo ""
    echo "Services:"
    echo "  • PostgreSQL: localhost:5432"
    echo "  • Redis:      localhost:6379"
    echo ""
    echo "Database Credentials:"
    echo "  • User:     ${POSTGRES_USER}"
    echo "  • Password: ${POSTGRES_PASSWORD}"
    echo "  • Database: ${POSTGRES_DB}"
    echo ""
    echo "Additional databases:"
    echo "  • mcp_tools"
    echo "  • mcp_logs"
    echo ""
    echo "Data directories:"
    echo "  • PostgreSQL: ${POSTGRES_DATA_DIR}"
    echo "  • Redis:      ${REDIS_DATA_DIR}"
    echo ""
    echo "Container management:"
    echo "  • Start:   systemctl --user start mcp-postgres mcp-redis"
    echo "  • Stop:    systemctl --user stop mcp-postgres mcp-redis"
    echo "  • Status:  systemctl --user status mcp-postgres mcp-redis"
    echo "  • Restart: systemctl --user restart mcp-postgres mcp-redis"
    echo ""
    echo "Connect to PostgreSQL:"
    echo "  podman exec -it mcp-postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
    echo ""
    echo "Connect to Redis:"
    echo "  podman exec -it mcp-redis redis-cli"
    echo ""
    echo "Next step:"
    echo "  ./scripts/deploy-aidb-mcp-server.sh"
    echo ""
}

main() {
    echo ""
    echo "============================================"
    echo "  MCP Database Setup"
    echo "  Version: 1.0.0"
    echo "============================================"
    echo ""

    # Step 1: Create directories
    create_directories

    # Step 2: Setup PostgreSQL
    if ! setup_postgres; then
        log_error "PostgreSQL setup failed"
        exit 1
    fi

    # Step 3: Create databases
    if ! create_postgres_databases; then
        log_warning "Failed to create additional databases (may already exist)"
    fi

    # Step 4: Setup Redis
    if ! setup_redis; then
        log_error "Redis setup failed"
        exit 1
    fi

    # Step 5: Verify services
    if ! verify_services; then
        log_error "Service verification failed"
        exit 1
    fi

    # Step 6: Create systemd services
    create_systemd_services

    # Step 7: Enable services
    enable_services

    # Step 8: Show summary
    show_summary
}

main "$@"
