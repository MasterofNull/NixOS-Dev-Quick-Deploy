#!/usr/bin/env bash
#
# Setup Podman REST API for Secure Container Management
# This script enables the Podman API socket for use by AI stack services
# Eliminates need for privileged containers and socket mounts
#
# Usage: ./scripts/setup-podman-api.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if running as root (needed for systemd service setup)
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root. Will set up system-wide Podman API."
        USE_USER_MODE=false
    else
        log_info "Running as user. Will set up user-mode Podman API (recommended)."
        USE_USER_MODE=true
    fi
}

# Detect if using Podman or Docker
detect_container_runtime() {
    if command -v podman &> /dev/null; then
        RUNTIME="podman"
        log_success "Detected Podman"
    elif command -v docker &> /dev/null; then
        RUNTIME="docker"
        log_warn "Detected Docker. This script is optimized for Podman."
        log_warn "Docker API setup is similar but may have differences."
    else
        log_error "Neither Podman nor Docker found. Please install Podman."
        exit 1
    fi
}

# Check if Podman API is already enabled
check_existing_api() {
    log_info "Checking if Podman API is already running..."

    if $USE_USER_MODE; then
        if systemctl --user is-active --quiet podman.socket 2>/dev/null; then
            log_warn "Podman API socket is already active (user mode)"
            read -p "Do you want to reconfigure it? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Skipping Podman API setup"
                return 0
            fi
        fi
    else
        if systemctl is-active --quiet podman.socket 2>/dev/null; then
            log_warn "Podman API socket is already active (system mode)"
            read -p "Do you want to reconfigure it? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "Skipping Podman API setup"
                return 0
            fi
        fi
    fi

    return 1
}

# Enable Podman API socket (user mode - RECOMMENDED)
enable_user_podman_api() {
    log_info "Enabling Podman API socket (user mode - rootless)..."

    # Enable and start the socket
    systemctl --user enable podman.socket
    systemctl --user start podman.socket

    # Verify it's running
    if systemctl --user is-active --quiet podman.socket; then
        log_success "Podman API socket enabled and running (user mode)"
    else
        log_error "Failed to start Podman API socket"
        exit 1
    fi

    # Get the socket path
    SOCKET_PATH=$(systemctl --user show podman.socket -p Listen | cut -d= -f2)
    log_info "Socket listening at: $SOCKET_PATH"

    # Test the API
    log_info "Testing Podman API..."
    if curl -s --unix-socket "$HOME/.local/share/containers/podman/machine/podman.sock" http://localhost/v4.0.0/libpod/info > /dev/null 2>&1; then
        log_success "Podman API is responding"
    else
        # Try HTTP endpoint
        if curl -s http://localhost:8080/v4.0.0/libpod/info > /dev/null 2>&1; then
            log_success "Podman API is responding on HTTP"
        else
            log_warn "Could not test Podman API. It may still work from containers."
        fi
    fi
}

# Enable Podman API socket (system mode - if running as root)
enable_system_podman_api() {
    log_info "Enabling Podman API socket (system mode)..."

    # Create systemd socket file
    cat > /etc/systemd/system/podman-api.socket <<'EOF'
[Unit]
Description=Podman API Socket (AI Stack)
Documentation=man:podman-system-service(1)

[Socket]
ListenStream=127.0.0.1:2375
SocketMode=0660

[Install]
WantedBy=sockets.target
EOF

    # Create systemd service file
    cat > /etc/systemd/system/podman-api.service <<'EOF'
[Unit]
Description=Podman API Service (AI Stack)
Requires=podman-api.socket
After=podman-api.socket
Documentation=man:podman-system-service(1)

[Service]
Type=exec
KillMode=process
Environment=LOGGING="--log-level=info"
ExecStart=/usr/bin/podman system service --time=0
Restart=on-failure

[Install]
WantedBy=default.target
EOF

    # Reload systemd
    systemctl daemon-reload

    # Enable and start the socket
    systemctl enable podman-api.socket
    systemctl start podman-api.socket

    # Verify it's running
    if systemctl is-active --quiet podman-api.socket; then
        log_success "Podman API socket enabled and running (system mode)"
    else
        log_error "Failed to start Podman API socket"
        exit 1
    fi

    # Test the API
    log_info "Testing Podman API..."
    if curl -s http://localhost:2375/v4.0.0/libpod/info > /dev/null 2>&1; then
        log_success "Podman API is responding on http://localhost:2375"
    else
        log_error "Podman API is not responding. Check 'journalctl -u podman-api.service'"
        exit 1
    fi
}

# Add environment variable to .env
update_env_file() {
    log_info "Updating .env file with Podman API configuration..."

    ENV_FILE="$PROJECT_ROOT/ai-stack/compose/.env"

    if [[ ! -f "$ENV_FILE" ]]; then
        log_error ".env file not found at $ENV_FILE"
        exit 1
    fi

    # Check if already configured
    if grep -q "^PODMAN_API_URL=" "$ENV_FILE"; then
        log_info "PODMAN_API_URL already in .env, updating..."
        sed -i.bak '/^PODMAN_API_URL=/d' "$ENV_FILE"
    fi

    # Add configuration section
    cat >> "$ENV_FILE" <<'EOF'

# ============================================================================
# Secure Container Management (Day 2 - Week 1)
# ============================================================================
# Podman REST API - replaces privileged containers and socket mounts
# Services use HTTP API instead of direct socket access
PODMAN_API_URL=http://host.containers.internal:2375
PODMAN_API_VERSION=v4.0.0

# Container operation audit logging
CONTAINER_AUDIT_ENABLED=true
CONTAINER_AUDIT_LOG_PATH=/data/telemetry/container-audit.jsonl

# Operation allowlists (comma-separated)
HEALTH_MONITOR_ALLOWED_OPS=list,inspect,restart
RALPH_WIGGUM_ALLOWED_OPS=list,inspect,create,start,stop,logs
CONTAINER_ENGINE_ALLOWED_OPS=list,inspect,logs
EOF

    log_success "Updated .env file with Podman API configuration"
}

# Configure firewall (if needed)
configure_firewall() {
    log_info "Checking firewall configuration..."

    # Check if firewalld is running
    if systemctl is-active --quiet firewalld 2>/dev/null; then
        log_info "Firewalld detected. Ensuring localhost access to Podman API..."

        # Allow localhost connections (should already be allowed, but verify)
        if ! firewall-cmd --query-rich-rule='rule family="ipv4" source address="127.0.0.1" accept' --permanent 2>/dev/null; then
            firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="127.0.0.1" accept'
            firewall-cmd --reload
            log_success "Configured firewall for localhost access"
        else
            log_info "Firewall already configured"
        fi
    else
        log_info "No firewalld detected, skipping firewall configuration"
    fi
}

# Display next steps
show_next_steps() {
    log_success "Podman API setup complete!"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📋 NEXT STEPS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "1. Verify Podman API is accessible:"
    if $USE_USER_MODE; then
        echo "   curl http://localhost:2375/v4.0.0/libpod/info"
    else
        echo "   curl http://localhost:2375/v4.0.0/libpod/info"
    fi
    echo
    echo "2. Update service code to use Podman API (automated in next step)"
    echo
    echo "3. Update docker-compose.yml:"
    echo "   - Remove 'privileged: true' from health-monitor"
    echo "   - Remove socket mounts from ralph-wiggum"
    echo "   - Remove socket mounts from container-engine"
    echo
    echo "4. Restart AI stack services:"
    echo "   cd $PROJECT_ROOT/ai-stack/compose"
    echo "   podman-compose down"
    echo "   podman-compose up -d"
    echo
    echo "5. Verify services work correctly:"
    echo "   podman logs local-ai-health-monitor"
    echo "   podman logs local-ai-ralph-wiggum"
    echo "   podman logs local-ai-container-engine"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    log_info "Configuration saved to: $ENV_FILE"
    log_info "Backup created at: ${ENV_FILE}.bak"
}

# Main execution
main() {
    log_info "Starting Podman API setup for NixOS AI Stack..."
    echo

    check_root
    detect_container_runtime

    if [[ "$RUNTIME" != "podman" ]]; then
        log_error "This script requires Podman. Please install Podman first."
        exit 1
    fi

    # Check if already set up
    if check_existing_api; then
        log_info "Podman API already configured"
    else
        # Set up based on user/root mode
        if $USE_USER_MODE; then
            enable_user_podman_api
        else
            enable_system_podman_api
        fi
    fi

    # Update environment file
    update_env_file

    # Configure firewall if needed
    configure_firewall

    # Show next steps
    show_next_steps
}

# Run main function
main "$@"
