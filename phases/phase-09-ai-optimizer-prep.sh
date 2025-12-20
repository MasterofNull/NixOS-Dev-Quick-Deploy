#!/usr/bin/env bash
# Phase 9: AI-Optimizer Preparation
# Part of: nixos-quick-deploy.sh
# Version: Uses SCRIPT_VERSION from main script
# Purpose: Prepare NixOS system for optional AI-Optimizer installation

# ============================================================================
# Phase 9: AI-Optimizer System Preparation
# ============================================================================

phase_09_ai_optimizer_prep() {
    log_phase_start 9 "AI-Optimizer System Preparation (Optional)"

    # Load integration hooks
    if [ -f "${SCRIPT_DIR}/lib/ai-optimizer-hooks.sh" ]; then
        if ! source "${SCRIPT_DIR}/lib/ai-optimizer-hooks.sh"; then
            log_error "Failed to load AI-Optimizer hooks library"
            return 1
        fi
    else
        log_error "AI-Optimizer hooks library not found"
        return 1
    fi

    # Check if user wants to prepare for AI-Optimizer
    if ! prompt_ai_optimizer_prep; then
        log_info "Skipping AI-Optimizer preparation"
        mark_phase_complete "phase-09-ai-optimizer-prep"
        return 0
    fi

    # Verify Docker/Podman is available
    if ! check_docker_podman_ready; then
        log_error "Docker/Podman not available"
        log_info "Please ensure virtualisation.podman or virtualisation.docker is enabled in configuration.nix"
        return 1
    fi

    log_success "Container runtime available"

    # Prepare shared data directories
    log_info "Preparing shared persistent data directories..."
    if prepare_shared_data_directories; then
        log_success "Shared data directories created"
    else
        log_error "Failed to create shared data directories"
        return 1
    fi

    # Check for port conflicts
    log_info "Checking for port conflicts..."
    if detect_port_conflicts; then
        log_success "No port conflicts detected"
    else
        log_warning "Some ports are in use - AI-Optimizer may conflict with existing services"
        log_info "You can resolve conflicts later if needed"
    fi

    # Ensure networking is ready
    if ensure_docker_network_ready; then
        log_success "Container networking ready"
    else
        log_warning "Container networking may need configuration"
    fi

    # Check NVIDIA container toolkit (if GPU present)
    if command -v nvidia-smi &> /dev/null; then
        if check_nvidia_container_toolkit; then
            log_success "NVIDIA container toolkit available"
        else
            log_warning "NVIDIA container toolkit not detected"
            log_info "GPU acceleration may not work in AI-Optimizer containers"
            log_info "Install: hardware.nvidia-container-toolkit.enable = true;"
        fi
    fi

    # Save integration status
    save_integration_status
    log_success "Integration status saved"

    # Check if AI-Optimizer is already installed
    if check_ai_optimizer_installed; then
        local status=$(get_ai_optimizer_status)
        log_info "AI-Optimizer is already installed (status: $status)"

        show_ai_optimizer_info
    else
        log_info "AI-Optimizer not installed yet"

        cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NixOS System Prepared for AI-Optimizer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The "hand" (NixOS) is ready to receive the "glove" (AI-Optimizer).

Shared data directories created:
  • Data:   $AI_OPTIMIZER_DATA_ROOT
  • Config: $AI_OPTIMIZER_CONFIG_ROOT

These directories persist across AI-Optimizer reinstalls.

Next Steps:
  1. Clone AI-Optimizer (your private repository):
     git clone <your-repo-url> ~/Documents/AI-Optimizer

  2. Configure AI-Optimizer:
     cd ~/Documents/AI-Optimizer
     cp .env.example .env
     nano .env  # Edit model selection and settings

  3. Deploy AI-Optimizer:
     docker compose -f docker-compose.new.yml up -d

  4. Verify deployment:
     curl http://localhost:8091/health | jq .

  5. Use AI features in NixOS-Dev:
     cd ~/Documents/NixOS-Dev-Quick-Deploy
     source lib/ai-optimizer.sh
     ai_interactive_help

Integration features:
  • Shared persistent data (survives reinstalls)
  • Zero port conflicts
  • GPU acceleration ready (if NVIDIA GPU detected)
  • Seamless integration with deployment scripts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
    fi

    mark_phase_complete "phase-09-ai-optimizer-prep"
    return 0
}

# ============================================================================
# Helper Functions
# ============================================================================

prompt_ai_optimizer_prep() {
    cat <<EOF

╭───────────────────────────────────────────────────────────────────────────╮
│ AI-Optimizer AIDB MCP Server Integration                                  │
│                                                                            │
│ Prepare NixOS system for optional AI-Optimizer installation?              │
│                                                                            │
│ This will:                                                                 │
│  • Create shared persistent data directories                              │
│  • Verify Docker/Podman prerequisites                                     │
│  • Check for port conflicts                                               │
│  • Configure container networking                                         │
│  • Verify GPU acceleration (if NVIDIA GPU present)                        │
│                                                                            │
│ What is AI-Optimizer?                                                     │
│  • Private AIDB MCP server with vLLM inference                            │
│  • AI-powered NixOS configuration generation                              │
│  • Intelligent code review and assistance                                 │
│  • ML-based system monitoring                                             │
│  • Persistent data across all hosts                                       │
│                                                                            │
│ Note: This only PREPARES the system. You install AI-Optimizer manually.   │
│                                                                            │
╰───────────────────────────────────────────────────────────────────────────╯

EOF

    read -p "Prepare system for AI-Optimizer? [Y/n]: " prep_confirm

    if [[ "$prep_confirm" =~ ^[Nn]$ ]]; then
        return 1
    else
        return 0
    fi
}

# ============================================================================
# Phase Execution Check
# ============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    # Running directly, not sourced
    echo "This script should be sourced by nixos-quick-deploy.sh"
    exit 1
fi
