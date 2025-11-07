#!/usr/bin/env bash
#
# Phase 07: Post-Deployment Validation
# Purpose: Verify all packages installed and services running
# Version: 4.0.0
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

phase_07_post_deployment_validation() {
    # ========================================================================
    # Phase 7: Post-Deployment Validation
    # ========================================================================
    # This is the "verification" phase - confirm everything installed correctly
    # and is working as expected. Quality assurance before finalizing.
    #
    # Why validate after installation:
    # - Catch installation failures early
    # - Verify services are running
    # - Confirm packages are in PATH
    # - Test GPU drivers loaded correctly
    # - Ensure system health before user handoff
    #
    # Three validation layers:
    # 1. Hardware validation (GPU drivers)
    # 2. System health check (services, resources)
    # 3. Package availability (critical tools in PATH)
    #
    # All checks are non-fatal:
    # - Failures result in warnings, not errors
    # - User can investigate and fix manually
    # - System functional even if some checks fail
    # - Deployment continues to completion
    #
    # Why non-fatal:
    # - Some features optional (GPU for headless server)
    # - User might have custom setup
    # - Better to complete with warnings than fail completely
    # - User has rollback option if system broken
    # ========================================================================

    local phase_name="post_install_validation"  # State tracking identifier for this phase

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state.json for completion marker
        print_info "Phase 7 already completed (skipping)"
            return 0  # Skip to next phase
    fi

    print_section "Phase 7/8: Post-Deployment Validation"  # Display phase header
        echo ""

    # ========================================================================
    # Step 8.1: GPU Driver Validation
    # ========================================================================
    # Why: Verify GPU drivers loaded and functioning
    # When: Only if GPU was detected in Phase 1
    # How: validate_gpu_driver() checks:
    #      - Kernel module loaded (lsmod | grep nvidia/amdgpu/i915)
    #      - Device files exist (/dev/dri/card0, /dev/nvidia0)
    #      - Driver version matches expected
    #      - Hardware acceleration available
    #
    # GPU types:
    # - software: No GPU, software rendering (skip validation)
    # - unknown: Detection failed (skip, might not have GPU)
    # - nvidia/amd/intel: Hardware GPU (validate)
    #
    # What validate_gpu_driver() does:
    # NVIDIA:
    #   - Check nvidia-smi command works
    #   - Verify CUDA runtime if installed
    #   - Test GPU compute capability
    #
    # AMD:
    #   - Check rocm-smi command
    #   - Verify AMDGPU kernel module
    #   - Test ROCm runtime if installed
    #
    # Intel:
    #   - Check i915/xe kernel module
    #   - Verify VA-API hardware acceleration
    #   - Test compute runtime if installed
    #
    # Non-critical: System works without GPU, just no hardware acceleration
    # || print_warning: Show warning if validation fails, continue
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" ]]; then  # Have hardware GPU
        validate_gpu_driver || print_warning "GPU driver validation had issues (non-critical)"  # Validate driver loaded
    fi

    # ========================================================================
    # Step 8.2: System Health Check
    # ========================================================================
    # Why: Comprehensive system validation
    # When: Unless user specified --skip-health-check
    # How: run_system_health_check_stage() performs:
    #      1. Service status checks
    #      2. Resource utilization checks
    #      3. Disk space verification
    #      4. Network connectivity tests
    #      5. Database accessibility
    #      6. Container runtime status
    #
    # Services checked:
    # System services (systemctl status):
    #   - postgresql: Database server
    #   - ollama: Local AI model server
    #   - gitea: Git hosting server
    #   - huggingface-tgi: Text generation inference
    #   - qdrant: Vector database
    #
    # User services (systemctl --user status):
    #   - jupyter-lab: Interactive notebooks
    #   - Custom user daemons
    #
    # Resource checks:
    # - CPU usage (warn if >90%)
    # - Memory usage (warn if <500MB free)
    # - Disk space (warn if <5GB free)
    # - Load average (warn if >CPU count)
    #
    # Network checks:
    # - Can reach internet
    # - DNS resolution working
    # - Cache.nixos.org accessible
    #
    # Container checks:
    # - podman command available
    # - Can pull images
    # - Network configured
    # - Storage driver working
    #
    # Exit behavior:
    # - Returns 0 if all checks pass
    # - Returns 1 if any check fails (warnings shown)
    # - || print_warning: Show summary warning, continue
    #
    # Why allow skip:
    # - Time-consuming (2-5 minutes)
    # - User might want faster deployment
    # - Can run health check manually later
    #   Command: ~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh
    #
    # SKIP_HEALTH_CHECK variable:
    # - Set via --skip-health-check CLI flag
    # - Default: false (run health check)
    # - != true: Check if NOT explicitly true (covers unset/false/empty)
    if [[ "$SKIP_HEALTH_CHECK" != true ]]; then  # User wants health check
        run_system_health_check_stage || print_warning "Health check found issues (review above)"  # Run comprehensive validation
    fi

    # ========================================================================
    # Step 8.3: Critical Package Verification
    # ========================================================================
    # Why: Ensure essential development tools are accessible
    # How: Check each package with command -v
    # What: Verify packages are in current PATH
    #
    # Critical packages checked:
    # - podman: Container runtime (Docker alternative)
    # - python3: Python interpreter for development
    # - git: Version control system
    # - home-manager: User environment manager
    # - jq: JSON processor (used by deployment scripts)
    #
    # Why these packages:
    # - Required for development workflow
    # - Used by deployment scripts
    # - Expected by later phases
    # - Core tools for project
    #
    # PATH issues:
    # - New packages might not be in current shell's PATH
    # - Shell needs reload to pick up new environment
    # - Solution: exec zsh (or exec bash) to restart shell
    # - Reason: home-manager modifies ~/.zshrc but shell already loaded
    #
    # Counter variable:
    # - missing_count: Track how many packages not found
    # - Increment with ((missing_count++))
    # - || true: Prevent script exit if arithmetic fails
    #   Why: set -e would exit on ((missing_count++)) when count is 0
    #        in some bash versions, because ++ returns old value
    print_info "Verifying critical packages..."
        local missing_count=0  # Counter for missing packages

    # Loop through critical packages to verify each is in PATH
    for pkg in podman python3 git home-manager jq; do  # Essential development tools
        # command -v: Find command in PATH, return path or empty
        # &>/dev/null: Suppress output (just checking existence)
        if command -v "$pkg" &>/dev/null; then  # Package found in PATH
            # Package found - show where it's located
            # $(command -v $pkg): Get full path to package
            print_success "$pkg: $(command -v $pkg)"  # Display package location
        else  # Package not found
            # Package not found - warn and count
            print_warning "$pkg: NOT FOUND"  # Alert user

            # Increment counter for missing packages
            # ((expr)): Arithmetic expansion
            # || true: Prevent exit on failure (set -e safety)
            ((missing_count++)) || true  # Count this missing package
        fi
    done

    # Check if any packages were missing and provide guidance
    # -gt 0: Greater than zero
    if [[ $missing_count -gt 0 ]]; then  # Some packages not accessible
        # Some packages not in PATH
        print_warning "$missing_count critical package(s) not in PATH"
            print_info "Try: exec zsh  (to reload shell)"  # Suggest shell reload
        # Note: Not exiting - user can fix by reloading shell
    else  # All packages found successfully
        # All packages found - deployment successful!
        print_success "All critical packages verified!"  # Success message
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Validation complete. System checked and verified (with possible warnings).
    #
    # What we validated:
    # - GPU drivers loaded (if applicable)
    # - System services running
    # - Resources available
    # - Critical packages accessible
    #
    # State: "post_install_validation" marked complete
    # Next: Phase 8 will finalize system configuration
    mark_step_complete "$phase_name"  # Update state.json with completion marker
        print_success "Phase 7: Post-Deployment Validation - COMPLETE"
    echo ""
}

# Execute phase function (called when this script is sourced by main orchestrator)
phase_07_post_deployment_validation  # Run all validation checks
