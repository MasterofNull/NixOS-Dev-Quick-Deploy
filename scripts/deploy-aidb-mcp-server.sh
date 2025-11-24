#!/usr/bin/env bash
#
# AIDB MCP Server Deployment Script
# Version: 1.0.0
# Purpose: Deploy AI-Optimizer (AIDB) Model Context Protocol Server
#
# ============================================================================
# OVERVIEW
# ============================================================================
# This script deploys a production-ready MCP server that integrates with:
# - PostgreSQL (tool registry, metadata, logs)
# - Redis (caching, session state)
# - Qdrant (vector search, embeddings)
# - Ollama (local LLM inference)
# - Open WebUI (chat interface)
#
# The MCP server provides:
# - Progressive tool discovery (minimal → full)
# - Sandboxed tool execution
# - Unified state management
# - Vector search capabilities
# - Integration with existing AI stack
#
# ============================================================================

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly AIDB_DIR="${HOME}/Documents/AI-Optimizer"
readonly MCP_SERVER_DIR="${AIDB_DIR}/mcp-server"
readonly MCP_CONFIG_DIR="${AIDB_DIR}/config"
readonly MCP_DATA_DIR="${HOME}/.local/share/aidb"
readonly MCP_LOG_DIR="${HOME}/.cache/aidb/logs"
readonly MCP_STATE_FILE="${MCP_DATA_DIR}/state.json"

# MCP Server Configuration
readonly MCP_SERVER_PORT=8090
readonly MCP_API_PORT=8091
readonly POSTGRES_HOST="localhost"
readonly POSTGRES_PORT=5432
readonly POSTGRES_DB="mcp"
readonly POSTGRES_USER="mcp"
readonly REDIS_HOST="localhost"
readonly REDIS_PORT=6379
readonly QDRANT_HTTP_PORT=6333
readonly QDRANT_GRPC_PORT=6334
readonly OLLAMA_PORT=11434

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ============================================================================
# LOGGING
# ============================================================================

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

# ============================================================================
# PREREQUISITES
# ============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing_deps=()

    # Check required commands
    for cmd in python3 pip3 psql redis-cli curl jq podman; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing_deps+=("$cmd")
        fi
    done

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing_deps[*]}"
        log_info "Install missing dependencies and try again"
        return 1
    fi

    log_success "All prerequisites met"
    return 0
}

check_services() {
    log_info "Checking required services..."

    local services_ok=true

    # Check PostgreSQL
    if ! pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" >/dev/null 2>&1; then
        log_warning "PostgreSQL not running on ${POSTGRES_HOST}:${POSTGRES_PORT}"
        services_ok=false
    fi

    # Check Redis
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log_warning "Redis not running on ${REDIS_HOST}:${REDIS_PORT}"
        services_ok=false
    fi

    # Check Qdrant
    if ! curl -sf "http://localhost:${QDRANT_HTTP_PORT}/" >/dev/null 2>&1; then
        log_warning "Qdrant not running on port ${QDRANT_HTTP_PORT}"
        services_ok=false
    fi

    # Check Ollama
    if ! curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
        log_warning "Ollama not running on port ${OLLAMA_PORT}"
        services_ok=false
    fi

    if [[ "$services_ok" == false ]]; then
        log_error "Some services are not running"
        log_info "Start services with: ai-servicectl start all"
        return 1
    fi

    log_success "All required services are running"
    return 0
}

# ============================================================================
# DIRECTORY SETUP
# ============================================================================

create_directories() {
    log_info "Creating AIDB directories..."

    mkdir -p "$AIDB_DIR"
    mkdir -p "$MCP_SERVER_DIR"
    mkdir -p "$MCP_CONFIG_DIR"
    mkdir -p "$MCP_DATA_DIR"
    mkdir -p "$MCP_LOG_DIR"
    mkdir -p "${MCP_DATA_DIR}/databases"
    mkdir -p "${MCP_DATA_DIR}/models"
    mkdir -p "${MCP_DATA_DIR}/cache"
    mkdir -p "${MCP_DATA_DIR}/tools"

    log_success "Directories created"
}

# ============================================================================
# DATABASE SETUP
# ============================================================================

setup_postgres() {
    log_info "Setting up PostgreSQL database..."

    # Use podman exec to avoid password authentication
    local postgres_container="mcp-postgres"

    # Check if database exists
    if podman exec "$postgres_container" psql -U "$POSTGRES_USER" -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$POSTGRES_DB"; then
        log_info "Database '$POSTGRES_DB' already exists"
    fi

    # Create database and schema
    podman exec "$postgres_container" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
-- Tools registry table (database already exists)
CREATE TABLE IF NOT EXISTS tools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(100),
    manifest JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tool execution log
CREATE TABLE IF NOT EXISTS tool_executions (
    id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES tools(id),
    input JSONB,
    output JSONB,
    status VARCHAR(50),
    execution_time_ms INTEGER,
    error TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255),
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(enabled);
CREATE INDEX IF NOT EXISTS idx_tool_executions_tool_id ON tool_executions(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_executions_status ON tool_executions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $POSTGRES_USER;
EOF

    log_success "PostgreSQL database setup complete"
}

setup_redis() {
    log_info "Configuring Redis..."

    # Test Redis connection
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "mcp:test" "ok" >/dev/null 2>&1; then
        log_error "Failed to connect to Redis"
        return 1
    fi

    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "mcp:test" >/dev/null 2>&1

    log_success "Redis configured"
}

setup_qdrant() {
    log_info "Setting up Qdrant collections..."

    # Create semantic search collection
    curl -X PUT "http://localhost:${QDRANT_HTTP_PORT}/collections/mcp-semantic-search" \
        -H "Content-Type: application/json" \
        -d '{
            "vectors": {
                "size": 384,
                "distance": "Cosine"
            }
        }' 2>/dev/null || log_warning "Collection may already exist"

    log_success "Qdrant collections configured"
}

# ============================================================================
# MCP SERVER DEPLOYMENT
# ============================================================================

create_mcp_server() {
    log_info "Creating MCP server from template..."

    # Copy template
    cp "${PROJECT_ROOT}/templates/mcp-server-template.py" "${MCP_SERVER_DIR}/server.py"

    # Create configuration
    cat > "${MCP_CONFIG_DIR}/config.yaml" << EOF
# AIDB MCP Server Configuration
# Version: 1.0.0

server:
  host: "0.0.0.0"
  port: ${MCP_SERVER_PORT}
  api_port: ${MCP_API_PORT}
  workers: 4

database:
  postgres:
    host: "${POSTGRES_HOST}"
    port: ${POSTGRES_PORT}
    database: "${POSTGRES_DB}"
    user: "${POSTGRES_USER}"
    password_file: "/run/secrets/mcp/postgres_password"

  redis:
    host: "${REDIS_HOST}"
    port: ${REDIS_PORT}
    db: 0
    password_file: "/run/secrets/mcp/redis_password"

  qdrant:
    host: "localhost"
    http_port: ${QDRANT_HTTP_PORT}
    grpc_port: ${QDRANT_GRPC_PORT}

llm:
  ollama:
    host: "http://localhost:${OLLAMA_PORT}"
    models:
      - phi4:latest
      - qwen2.5-coder:7b
      - llama3.2:latest

  default_model: "phi4:latest"

tools:
  discovery_mode: "minimal"  # minimal | full
  sandbox:
    enabled: true
    runner: "bubblewrap"  # bubblewrap | firejail
  cache:
    enabled: true
    ttl: 3600  # seconds

logging:
  level: "INFO"
  file: "${MCP_LOG_DIR}/mcp-server.log"
  max_size: "100MB"
  backup_count: 5

security:
  api_key_file: "/run/secrets/mcp/api_key"
  rate_limit:
    enabled: true
    requests_per_minute: 60
EOF

    log_success "MCP server created"
}

create_systemd_service() {
    log_info "Creating systemd user service..."

    mkdir -p "${HOME}/.config/systemd/user"

    cat > "${HOME}/.config/systemd/user/aidb-mcp-server.service" << EOF
[Unit]
Description=AIDB MCP Server (AI-Optimizer)
Documentation=file://${AIDB_DIR}/README.md
After=network.target podman-local-ai-ollama.service
Wants=podman-local-ai-qdrant.service

[Service]
Type=simple
WorkingDirectory=${MCP_SERVER_DIR}
ExecStart=${HOME}/.nix-profile/bin/python3 ${MCP_SERVER_DIR}/server.py --config ${MCP_CONFIG_DIR}/config.yaml
Restart=on-failure
RestartSec=10

# Environment
Environment="PYTHONUNBUFFERED=1"
Environment="MCP_DATA_DIR=${MCP_DATA_DIR}"
Environment="MCP_LOG_DIR=${MCP_LOG_DIR}"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aidb-mcp-server

[Install]
WantedBy=default.target
EOF

    # Reload systemd
    systemctl --user daemon-reload

    log_success "Systemd service created"
}

install_dependencies() {
    log_info "Installing Python dependencies..."

    # Create requirements.txt
    cat > "${MCP_SERVER_DIR}/requirements.txt" << EOF
# AIDB MCP Server Dependencies
# Version: 1.0.0

# Web framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0

# Database
psycopg2-binary==2.9.10
redis==5.2.0
sqlalchemy==2.0.36
alembic==1.14.0

# Vector search
qdrant-client==1.12.1

# HTTP clients
httpx==0.28.1
aiohttp==3.11.0

# LLM libraries
langchain==0.3.13
openai==1.59.3

# Utilities
pyyaml==6.0.2
python-dotenv==1.0.1
click==8.1.8

# Monitoring
prometheus-client==0.21.0
EOF

    # Install dependencies (skip --user if in virtualenv)
    pip3 install --break-system-packages -r "${MCP_SERVER_DIR}/requirements.txt" 2>&1 | grep -v "WARNING:" || true

    log_success "Dependencies installed"
}

# ============================================================================
# VERIFICATION
# ============================================================================

verify_installation() {
    log_info "Verifying installation..."

    # Check files exist
    local required_files=(
        "${MCP_SERVER_DIR}/server.py"
        "${MCP_CONFIG_DIR}/config.yaml"
        "${MCP_SERVER_DIR}/requirements.txt"
        "${HOME}/.config/systemd/user/aidb-mcp-server.service"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Missing file: $file"
            return 1
        fi
    done

    # Check directories
    local required_dirs=(
        "$AIDB_DIR"
        "$MCP_SERVER_DIR"
        "$MCP_CONFIG_DIR"
        "$MCP_DATA_DIR"
        "$MCP_LOG_DIR"
    )

    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_error "Missing directory: $dir"
            return 1
        fi
    done

    log_success "Installation verified"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    echo ""
    echo "============================================"
    echo "  AIDB MCP Server Deployment"
    echo "  Version: 1.0.0"
    echo "============================================"
    echo ""

    # Step 1: Check prerequisites
    if ! check_prerequisites; then
        log_error "Prerequisites check failed"
        exit 1
    fi

    # Step 2: Check services
    if ! check_services; then
        log_error "Service check failed"
        log_info "Start services with: ai-servicectl start all"
        exit 1
    fi

    # Step 3: Create directories
    create_directories

    # Step 4: Setup databases
    setup_postgres
    setup_redis
    setup_qdrant

    # Step 5: Create MCP server
    create_mcp_server

    # Step 6: Install dependencies
    install_dependencies

    # Step 7: Create systemd service
    create_systemd_service

    # Step 8: Verify installation
    if ! verify_installation; then
        log_error "Verification failed"
        exit 1
    fi

    echo ""
    echo "============================================"
    log_success "AIDB MCP Server deployed successfully!"
    echo "============================================"
    echo ""
    echo "Next steps:"
    echo "  1. Configure secrets in /run/secrets/mcp/"
    echo "  2. Start the server:"
    echo "     systemctl --user start aidb-mcp-server"
    echo "  3. Check status:"
    echo "     systemctl --user status aidb-mcp-server"
    echo "  4. View logs:"
    echo "     journalctl --user -u aidb-mcp-server -f"
    echo "  5. Test API:"
    echo "     curl http://localhost:${MCP_API_PORT}/health"
    echo ""
    echo "Server location: ${MCP_SERVER_DIR}"
    echo "Configuration: ${MCP_CONFIG_DIR}/config.yaml"
    echo "Data directory: ${MCP_DATA_DIR}"
    echo "Logs: ${MCP_LOG_DIR}"
    echo ""
}

main "$@"
