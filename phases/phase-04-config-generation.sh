#!/usr/bin/env bash
#
# Phase 04: Configuration Generation & Validation
# Purpose: Generate all configuration files and validate with dry-run
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/config.sh → generate_nixos_system_config(), validate_system_build_stage()
#   - lib/user.sh → gather_user_info()
#
# Required Variables (from config/variables.sh):
#   - GPU_TYPE → Detected GPU type (from Phase 1)
#   - SYSTEM_CONFIG_FILE → Path to system configuration
#   - HOME_MANAGER_FILE → Path to home-manager configuration
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - gather_user_info() → Collect user information
#   - generate_nixos_system_config() → Generate system config
#   - validate_system_build_stage() → Dry-run build validation
#
# Requires Phases (must complete before this):
#   - Phase 1: GPU_TYPE detection needed
#   - Phase 3: Backup must be created first
#
# Produces (for later phases):
#   - CONFIGS_GENERATED → Flag indicating configs ready
#   - SYSTEM_CONFIG_FILE → Generated system configuration
#   - HOME_MANAGER_FILE → Generated home-manager configuration
#   - State: "generate_validate_configs" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_04_config_generation() {
    local phase_name="generate_validate_configs"

    if is_step_complete "$phase_name"; then
        print_info "Phase 4 already completed (skipping)"
        return 0
    fi

    print_section "Phase 4/10: Configuration Generation & Validation"
    echo ""

    # Gather user info
    gather_user_info

    # Generate NixOS system config
    generate_nixos_system_config

    # Validate system build (dry run)
    validate_system_build_stage

    mark_step_complete "$phase_name"
    print_success "Phase 4: Configuration Generation & Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_04_config_generation
