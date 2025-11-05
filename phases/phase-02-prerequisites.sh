#!/usr/bin/env bash
#
# Phase 02: Prerequisite Package Installation
# Purpose: Install ALL packages needed by deployment script FIRST
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/nixos.sh → select_nixos_version(), update_nixos_channels()
#   - lib/packages.sh → ensure_preflight_core_packages(), cleanup_conflicting_home_manager_profile()
#   - lib/home-manager.sh → install_home_manager()
#   - lib/python.sh → ensure_python_runtime()
#
# Required Variables (from config/variables.sh):
#   - PYTHON_BIN → Python interpreter path (array)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - select_nixos_version() → Let user select NixOS version
#   - update_nixos_channels() → Update system channels
#   - ensure_preflight_core_packages() → Install core packages
#   - cleanup_conflicting_home_manager_profile() → Remove conflicts
#   - install_home_manager() → Install home-manager
#   - ensure_python_runtime() → Ensure Python available
#
# Requires Phases (must complete before this):
#   - Phase 1: GPU_TYPE detection needed for package selection
#
# Produces (for later phases):
#   - PREREQUISITES_INSTALLED → Flag indicating prerequisites ready
#   - PYTHON_BIN → Python interpreter path
#   - State: "install_prerequisites" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_02_prerequisites() {
    local phase_name="install_prerequisites"

    if is_step_complete "$phase_name"; then
        print_info "Phase 2 already completed (skipping)"
        return 0
    fi

    print_section "Phase 2/10: Prerequisite Package Installation"
    echo ""

    # NixOS version selection
    select_nixos_version

    # Update channels
    update_nixos_channels

    # Ensure core packages
    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
        exit 1
    fi

    # Cleanup conflicting home-manager entries
    print_info "Scanning nix profile for legacy home-manager entries..."
    cleanup_conflicting_home_manager_profile

    # Ensure home-manager is available
    if command -v home-manager &>/dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        install_home_manager
    fi

    # Python runtime check
    print_info "Verifying Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        exit 1
    fi

    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        print_success "Python runtime: ephemeral Nix shell"
    else
        print_success "Python runtime: ${PYTHON_BIN[0]} ($(${PYTHON_BIN[@]} --version 2>&1))"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 2: Prerequisite Package Installation - COMPLETE"
    echo ""
}

# Execute phase
phase_02_prerequisites
