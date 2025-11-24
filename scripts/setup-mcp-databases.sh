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

# Configuration
readonly POSTGRES_VERSION="16"
readonly REDIS_VERSION="7"
readonly MCP_DATA_DIR="${HOME}/.local/share/aidb"
readonly POSTGRES_DATA_DIR="${MCP_DATA_DIR}/postgres"
readonly REDIS_DATA_DIR="${MCP_DATA_DIR}/redis"

# Database credentials (will be stored in sops later)
readonly POSTGRES_USER="mcp"
readonly POSTGRES_PASSWORD="mcp_dev_password_change_me"
readonly POSTGRES_DB="mcp"

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

create_directories() {
    log_info "Creating data directories..."

    mkdir -p "$POSTGRES_DATA_DIR"
    mkdir -p "$REDIS_DATA_DIR"

    log_success "Directories created"
}

setup_postgres() {
    log_info "Setting up PostgreSQL container..."

    # Stop existing container if running
    podman stop mcp-postgres 2>/dev/null || true
    podman rm mcp-postgres 2>/dev/null || true

    # Create and start PostgreSQL container
    podman run -d \
        --name mcp-postgres \
        --network local-ai \
        -e POSTGRES_USER="$POSTGRES_USER" \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -e POSTGRES_DB="$POSTGRES_DB" \
        -v "$POSTGRES_DATA_DIR:/var/lib/postgresql/data:Z" \
        -p 5432:5432 \
        "docker.io/library/postgres:${POSTGRES_VERSION}-alpine"

    log_success "PostgreSQL container created and starting"

    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if podman exec mcp-postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
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

    podman exec mcp-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
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
    podman stop mcp-redis 2>/dev/null || true
    podman rm mcp-redis 2>/dev/null || true

    # Create Redis configuration
    cat > "${REDIS_DATA_DIR}/redis.conf" <<EOF
# Redis configuration for MCP server
bind 0.0.0.0
protected-mode no
port 6379
tcp-backlog 511
timeout 0
tcp-keepalive 300
daemonize no
supervised no
pidfile /var/run/redis_6379.pid
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
    podman run -d \
        --name mcp-redis \
        --network local-ai \
        -v "$REDIS_DATA_DIR:/data:Z" \
        -p 6379:6379 \
        "docker.io/library/redis:${REDIS_VERSION}-alpine" \
        redis-server /data/redis.conf

    log_success "Redis container created and started"

    # Test Redis
    sleep 2
    if podman exec mcp-redis redis-cli ping | grep -q "PONG"; then
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
    if podman exec mcp-postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
        log_success "✓ PostgreSQL is running on localhost:5432"
    else
        log_error "✗ PostgreSQL check failed"
        all_ok=false
    fi

    # Check Redis
    if podman exec mcp-redis redis-cli ping | grep -q "PONG"; then
        log_success "✓ Redis is running on localhost:6379"
    else
        log_error "✗ Redis check failed"
        all_ok=false
    fi

    # Check Qdrant (from existing AI stack)
    if podman ps --filter "name=local-ai-qdrant" --format "{{.Status}}" | grep -q "Up"; then
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
ExecStartPre=-/usr/bin/env podman stop mcp-postgres
ExecStartPre=-/usr/bin/env podman rm mcp-postgres
ExecStart=/usr/bin/env podman run -d \\
    --name mcp-postgres \\
    --network local-ai \\
    -e POSTGRES_USER=${POSTGRES_USER} \\
    -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \\
    -e POSTGRES_DB=${POSTGRES_DB} \\
    -v ${POSTGRES_DATA_DIR}:/var/lib/postgresql/data:Z \\
    -p 5432:5432 \\
    docker.io/library/postgres:${POSTGRES_VERSION}-alpine

ExecStop=/usr/bin/env podman stop mcp-postgres
ExecStopPost=/usr/bin/env podman rm mcp-postgres
Restart=on-failure
RestartSec=10

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
ExecStartPre=-/usr/bin/env podman stop mcp-redis
ExecStartPre=-/usr/bin/env podman rm mcp-redis
ExecStart=/usr/bin/env podman run -d \\
    --name mcp-redis \\
    --network local-ai \\
    -v ${REDIS_DATA_DIR}:/data:Z \\
    -p 6379:6379 \\
    docker.io/library/redis:${REDIS_VERSION}-alpine \\
    redis-server /data/redis.conf

ExecStop=/usr/bin/env podman stop mcp-redis
ExecStopPost=/usr/bin/env podman rm mcp-redis
Restart=on-failure
RestartSec=10

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
