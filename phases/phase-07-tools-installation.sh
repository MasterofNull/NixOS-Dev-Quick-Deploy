#!/usr/bin/env bash
#
# Phase 07: Tool & Service Installation
# Purpose: Install additional tools (Flatpak, Claude Code, etc.) in parallel
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/tools.sh → install_flatpak_stage(), install_claude_code(), configure_vscodium_for_claude(), install_vscodium_extensions(), install_openskills_tooling()
#   - lib/flake.sh → setup_flake_environment()
#
# Required Variables (from config/variables.sh):
#   - None (tools install to standard locations)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - install_flatpak_stage() → Install Flatpak apps
#   - install_claude_code() → Install Claude Code
#   - configure_vscodium_for_claude() → Configure VSCodium
#   - install_vscodium_extensions() → Install extensions
#   - install_openskills_tooling() → Install OpenSkills
#   - setup_flake_environment() → Setup flake env
#
# Requires Phases (must complete before this):
#   - Phase 6: DEPLOYMENT_COMPLETE must be true
#
# Produces (for later phases):
#   - TOOLS_INSTALLED → Flag indicating tools ready
#   - State: "install_tools_services" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_07_tools_installation() {
    local phase_name="install_tools_services"

    if is_step_complete "$phase_name"; then
        print_info "Phase 7 already completed (skipping)"
        return 0
    fi

    print_section "Phase 7/10: Tool & Service Installation"
    echo ""

    # Flatpak installation (can run in parallel with other installations)
    print_info "Installing Flatpak applications..."
    install_flatpak_stage &
    local flatpak_pid=$!

    # Claude Code installation
    print_info "Installing Claude Code..."
    if install_claude_code; then
        configure_vscodium_for_claude || print_warning "VSCodium configuration had issues"
        install_vscodium_extensions || print_warning "Some VSCodium extensions may not have installed"
    else
        print_warning "Claude Code installation skipped due to errors"
    fi &
    local claude_pid=$!

    # OpenSkills installation
    print_info "Installing OpenSkills tooling..."
    install_openskills_tooling &
    local openskills_pid=$!

    # Wait for parallel installations
    print_info "Waiting for parallel installations to complete..."
    wait $flatpak_pid || print_warning "Flatpak installation had issues"
    wait $claude_pid || print_warning "Claude Code installation had issues"
    wait $openskills_pid || print_warning "OpenSkills installation had issues"

    # Flake environment setup
    if ! setup_flake_environment; then
        print_warning "Flake environment setup had issues (non-critical)"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 7: Tool & Service Installation - COMPLETE"
    echo ""
}

# Execute phase
phase_07_tools_installation
