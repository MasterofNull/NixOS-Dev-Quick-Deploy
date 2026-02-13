#!/run/current-system/sw/bin/bash
#
# Dashboard Library
# Functions for installing and configuring the System Command Center dashboard
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
# Required Libraries:
#   - lib/logging.sh → print_info(), print_success(), print_error()
#
# Required Variables:
#   - SCRIPT_DIR → Main script directory
#   - USER → Current user
#   - HOME → User home directory
#
# ============================================================================

setup_system_dashboard() {
    # ========================================================================
    # Setup System Command Center Dashboard
    # ========================================================================
    # Installs the cyberpunk-themed monitoring dashboard as part of the
    # NixOS Quick Deploy process.
    #
    # Features:
    # - Real-time system monitoring (CPU, memory, disk, uptime)
    # - AI stack status (Qdrant, llama.cpp, PostgreSQL, Redis)
    # - Container monitoring (K3s pods)
    # - Network & firewall status
    # - Security monitoring
    # - Database metrics
    # - Quick access links to documentation and services
    #
    # Installation:
    # - Creates systemd user services for data collection and HTTP server
    # - Generates initial dashboard data
    # - Creates desktop launcher (if in desktop environment)
    # - Adds shell aliases for convenience
    #
    # Returns:
    #   0 → Success
    #   1 → Error during setup
    # ========================================================================

    : "${CYAN:=}"
    : "${GREEN:=}"
    : "${YELLOW:=}"
    : "${BLUE:=}"
    : "${NC:=}"

    print_info "Installing System Command Center Dashboard..."
    echo ""

    # Check if setup script exists
    local setup_script="${SCRIPT_DIR}/scripts/setup-dashboard.sh"
    if [[ ! -f "$setup_script" ]]; then
        print_error "Dashboard setup script not found: $setup_script"
        return 1
    fi

    # Run setup script
    if /run/current-system/sw/bin/bash "$setup_script"; then
        print_success "System dashboard installed successfully"
        echo ""
        print_info "Dashboard will be available at: ${BLUE}http://${SERVICE_HOST:-localhost}:8888/dashboard.html${NC}"
        print_info "Use 'dashboard' command to launch, or start systemd services"
        return 0
    else
        print_error "Dashboard setup failed"
        return 1
    fi
}

install_dashboard_to_deployment() {
    # ========================================================================
    # Install Dashboard as Part of Deployment
    # ========================================================================
    # Wrapper function called from Phase 8 to install the dashboard
    # during the finalization stage.
    #
    # This function is optional - if it fails, deployment continues.
    # ========================================================================

    print_section "Installing System Monitoring Dashboard"
    echo ""

    if setup_system_dashboard; then
        print_success "Dashboard installation complete"
        echo ""

        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if command -v kubectl >/dev/null 2>&1 && [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
                systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service >/dev/null 2>&1 || \
                    print_warning "Dashboard services failed to start automatically"
            else
                systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api.service >/dev/null 2>&1 || \
                    print_warning "Dashboard services failed to start automatically"
            fi
        fi

        # Provide post-install instructions
        local dashboard_message
        dashboard_message=$(cat <<EOF
${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
${GREEN}📊 System Dashboard Installed!${NC}

${YELLOW}Quick Start Options:${NC}

1. ${CYAN}One-Command Launch${NC} (recommended for first use):
   ${NC}cd ${SCRIPT_DIR}
   ./launch-dashboard.sh${NC}

2. ${CYAN}As Systemd Service${NC} (runs in background):
   ${NC}systemctl --user start dashboard-server
   systemctl --user start dashboard-collector.timer
   xdg-open http://${SERVICE_HOST:-localhost}:8888/dashboard.html${NC}

3. ${CYAN}Shell Alias${NC} (after reloading shell):
   ${NC}source ~/.zshrc  # or restart terminal
   dashboard  # Quick launcher${NC}

${YELLOW}Features:${NC}
• Real-time monitoring (5-second refresh)
• AI stack status (6 services)
• Container management (K3s)
• Network & security monitoring
• AI-agent friendly JSON export
• Cyberpunk terminal aesthetic

${YELLOW}Documentation:${NC}
• Quick Start: ${SCRIPT_DIR}/DASHBOARD-QUICKSTART.md
• Complete Guide: ${SCRIPT_DIR}/SYSTEM-DASHBOARD-GUIDE.md

${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
EOF
)
        if [[ -t 1 ]]; then
            printf '%b' "$dashboard_message"
        else
            # Strip ANSI codes when output isn't a TTY to avoid raw escape noise.
            # Also strip literal \033[...] sequences if they were logged verbatim.
            printf '%b' "$dashboard_message" | sed -E 's/\x1B\[[0-9;]*m//g; s/\\033\\[[0-9;]*m//g'
        fi
        return 0
    else
        print_warning "Dashboard installation encountered issues (non-fatal)"
        print_info "You can manually install later with: ./scripts/setup-dashboard.sh"
        return 0  # Don't fail deployment
    fi
}
