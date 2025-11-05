#!/usr/bin/env bash
#
# Phase 06: Configuration Deployment
# Purpose: Apply NixOS and home-manager configurations
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/deployment.sh → prompt_installation_stage(), create_home_manager_config(), apply_home_manager_config()
#   - lib/ui.sh → confirm()
#
# Required Variables (from config/variables.sh):
#   - HM_CONFIG_DIR → Home-manager configuration directory
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - confirm() → Get user confirmation
#   - prompt_installation_stage() → Apply system config
#   - create_home_manager_config() → Create home-manager config
#   - apply_home_manager_config() → Apply home-manager config
#
# Requires Phases (must complete before this):
#   - Phase 4: CONFIGS_GENERATED must be true
#   - Phase 5: CLEANUP_COMPLETE must be true
#
# Produces (for later phases):
#   - DEPLOYMENT_COMPLETE → Flag indicating deployment done
#   - State: "deploy_configurations" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_06_deployment() {
    local phase_name="deploy_configurations"

    if is_step_complete "$phase_name"; then
        print_info "Phase 6 already completed (skipping)"
        return 0
    fi

    print_section "Phase 6/10: Configuration Deployment"
    echo ""

    # User confirmation before deployment
    if ! confirm "Proceed with configuration deployment (this will apply system changes)?" "y"; then
        print_warning "Deployment skipped - configurations generated but not applied"
        print_info "To apply later, run: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        echo ""
        return 0
    fi

    # Apply system configuration
    prompt_installation_stage

    # Create and apply home-manager configuration
    create_home_manager_config
    apply_home_manager_config

    mark_step_complete "$phase_name"
    print_success "Phase 6: Configuration Deployment - COMPLETE"
    echo ""
}

# Execute phase
phase_06_deployment
