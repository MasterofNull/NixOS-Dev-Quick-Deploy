#!/usr/bin/env bash
#
# Phase 09: Post-Install Scripts & Finalization
# Purpose: Complete setup of packages requiring post-install configuration
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/finalization.sh → apply_final_system_configuration(), finalize_configuration_activation()
#
# Required Variables (from config/variables.sh):
#   - None (finalization uses system-level operations)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - apply_final_system_configuration() → Apply final config
#   - finalize_configuration_activation() → Finalize activation
#
# Requires Phases (must complete before this):
#   - Phase 8: VALIDATION_PASSED must be true
#
# Produces (for later phases):
#   - FINALIZATION_COMPLETE → Flag indicating finalization done
#   - State: "post_install_finalization" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_09_finalization() {
    local phase_name="post_install_finalization"

    if is_step_complete "$phase_name"; then
        print_info "Phase 9 already completed (skipping)"
        return 0
    fi

    print_section "Phase 9/10: Post-Install Scripts & Finalization"
    echo ""

    # Apply final system configuration
    apply_final_system_configuration

    # Finalize configuration activation
    finalize_configuration_activation

    mark_step_complete "$phase_name"
    print_success "Phase 9: Post-Install Scripts & Finalization - COMPLETE"
    echo ""
}

# Execute phase
phase_09_finalization
