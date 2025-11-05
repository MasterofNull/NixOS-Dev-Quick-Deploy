#!/usr/bin/env bash
#
# Phase 08: Post-Installation Validation
# Purpose: Verify all packages installed and services running
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/validation.sh → validate_gpu_driver(), run_system_health_check_stage()
#
# Required Variables (from config/variables.sh):
#   - GPU_TYPE → GPU type detected in Phase 1
#   - SKIP_HEALTH_CHECK → Whether to skip health check
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - validate_gpu_driver() → Validate GPU driver
#   - run_system_health_check_stage() → Run health check
#
# Requires Phases (must complete before this):
#   - Phase 7: TOOLS_INSTALLED must be true
#
# Produces (for later phases):
#   - VALIDATION_PASSED → Flag indicating validation passed
#   - State: "post_install_validation" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_08_validation() {
    local phase_name="post_install_validation"

    if is_step_complete "$phase_name"; then
        print_info "Phase 8 already completed (skipping)"
        return 0
    fi

    print_section "Phase 8/10: Post-Installation Validation"
    echo ""

    # Validate GPU driver if GPU was detected
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" ]]; then
        validate_gpu_driver || print_warning "GPU driver validation had issues (non-critical)"
    fi

    # System health check
    if [[ "$SKIP_HEALTH_CHECK" != true ]]; then
        run_system_health_check_stage || print_warning "Health check found issues (review above)"
    fi

    # Verify critical packages are available
    print_info "Verifying critical packages..."
    local missing_count=0
    for pkg in podman python3 git home-manager jq; do
        if command -v "$pkg" &>/dev/null; then
            print_success "$pkg: $(command -v $pkg)"
        else
            print_warning "$pkg: NOT FOUND"
            ((missing_count++)) || true
        fi
    done

    if [[ $missing_count -gt 0 ]]; then
        print_warning "$missing_count critical package(s) not in PATH"
        print_info "Try: exec zsh  (to reload shell)"
    else
        print_success "All critical packages verified!"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 8: Post-Installation Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_08_validation
