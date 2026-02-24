#!/usr/bin/env bash
#
# Phase 07: Post-Deployment Validation
# Purpose: Verify all packages installed and services running
# Version: Uses SCRIPT_VERSION from main script
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

check_required_service_active() {
    local unit="$1"
    local label="$2"

    if ! command -v systemctl >/dev/null 2>&1; then
        return 0
    fi

    if ! systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '{print $1}' | grep -Fxq "${unit}.service"; then
        return 0
    fi

    if systemctl is-active --quiet "$unit" 2>/dev/null; then
        print_success "$label service is active"
        return 0
    fi

    # Check if service is in failed state
    local active_state
    active_state=$(systemctl show "$unit" --property=ActiveState --value 2>/dev/null | tr -d '\r')
    if [[ "$active_state" == "failed" ]]; then
        print_error "$label service is in failed state"
        print_info "Check logs with: journalctl -u ${unit}.service -n 50"
        print_info "Recent error: $(systemctl status "$unit" --no-pager -l 2>/dev/null | grep -i 'failed\|error\|no such' | tail -n 1 | sed 's/^[[:space:]]*//')"
        return 1
    fi

    local unit_state
    unit_state=$(systemctl show "$unit" --property=UnitFileState --value 2>/dev/null | tr -d '\r')
    if [[ "$unit_state" =~ ^(enabled|enabled-runtime|linked)$ ]]; then
        print_error "$label service is enabled but not running (state: $active_state)"
        return 1
    fi

    print_warning "$label service installed but disabled"
    return 0
}

check_optional_service_active() {
    local unit="$1"
    local label="$2"

    if ! command -v systemctl >/dev/null 2>&1; then
        return 0
    fi

    if ! systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '{print $1}' | grep -Fxq "${unit}.service"; then
        return 0
    fi

    if systemctl is-active --quiet "$unit" 2>/dev/null; then
        print_success "$label service is active"
        return 0
    fi

    local unit_state
    unit_state=$(systemctl show "$unit" --property=UnitFileState --value 2>/dev/null | tr -d '\r')
    if [[ "$unit_state" =~ ^(enabled|enabled-runtime|linked)$ ]]; then
        print_warning "$label service is enabled but not running"
        return 1
    fi

    print_info "$label service is installed but disabled"
    return 0
}

check_flatpak_remote_health() {
    if ! command -v flatpak >/dev/null 2>&1; then
        return 0
    fi

    # Check for broken symlinks in Flatpak directories
    local flatpak_dir="$HOME/.local/share/flatpak"
    if [[ -L "$flatpak_dir" && ! -e "$flatpak_dir" ]]; then
        print_warning "Detected broken Flatpak symlink - repairing..."
        rm -f "$flatpak_dir" 2>/dev/null || true
        flatpak repair --user >/dev/null 2>&1 || true
    fi

    # Check if repository is corrupted
    if [[ -d "$flatpak_dir/repo" ]] && [[ ! -f "$flatpak_dir/repo/config" ]]; then
        print_warning "Detected corrupted Flatpak repository - repairing..."
        flatpak repair --user >/dev/null 2>&1 || true
    fi

    if flatpak_remote_exists; then
        print_success "Flathub remote is configured"
        return 0
    fi

    print_warning "Flathub remote is missing - attempting to configure..."

    # Try to configure Flathub automatically
    if declare -F ensure_flathub_remote >/dev/null 2>&1; then
        if ensure_flathub_remote; then
            print_success "Flathub remote configured successfully"
            return 0
        fi
    fi

    print_warning "Flathub remote not configured yet"
    print_info "Run: flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"
    return 1
}

check_k3s_cluster_health() {
    if ! command -v kubectl >/dev/null 2>&1; then
        print_info "kubectl not available yet (will be after reboot/relogin)"
        return 0
    fi

    # Check if K3s is running
    if ! systemctl is-active k3s >/dev/null 2>&1; then
        print_warning "K3s service is not running"
        print_info "Start it with: sudo systemctl start k3s"
        return 1
    fi

    # Check if cluster is accessible
    if kubectl_safe cluster-info >/dev/null 2>&1; then
        print_success "K3s cluster is healthy"
        return 0
    fi

    print_warning "K3s cluster not responding"
    return 1
}

check_k3s_ai_stack_health() {
    if ! command -v kubectl >/dev/null 2>&1; then
        return 0
    fi

    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    if ! kubectl_safe get namespace "$namespace" >/dev/null 2>&1; then
        print_info "AI stack namespace not deployed yet (will be created in Phase 9)"
        return 0
    fi

    local running_pods
    running_pods=$(kubectl_safe get pods -n "$namespace" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)

    if [[ "$running_pods" -gt 0 ]]; then
        print_success "K3s AI stack: $running_pods pods running in '$namespace' namespace"
        return 0
    fi

    print_info "AI stack namespace exists but no pods running yet"
    return 0
}

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

    local phase_name="post_install_validation"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 7 already completed (skipping)"
        return 0
    fi

    print_section "Phase 7/8: Post-Deployment Validation"
    echo ""

    local fatal_failures=0
    local warning_failures=0

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
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" ]]; then
        validate_gpu_driver || print_warning "GPU driver validation had issues (non-critical)"
    fi

    local -a critical_services=("gitea:Gitea")

    local entry service label
    for entry in "${critical_services[@]}"; do
        service="${entry%%:*}"
        label="${entry#*:}"
        if ! check_required_service_active "$service" "$label"; then
            ((fatal_failures++))
        fi
    done

    local -a advisory_services=(
        "postgresql:PostgreSQL"
    )

    for entry in "${advisory_services[@]}"; do
        service="${entry%%:*}"
        label="${entry#*:}"
        if ! check_optional_service_active "$service" "$label"; then
            ((warning_failures++))
        fi
    done

    if ! check_flatpak_remote_health; then
        ((fatal_failures++))
    fi

    if ! check_k3s_cluster_health; then
        ((warning_failures++))
    fi

    if ! check_k3s_ai_stack_health; then
        ((warning_failures++))
    fi

    if [[ "${SKIP_HEALTH_CHECK:-false}" == "true" ]]; then
        print_warning "System health check skipped via flag"
    else
        if ! run_system_health_check_stage; then
            ((warning_failures++))
        fi
    fi

    # ========================================================================
    # Step 8.2: Critical Package Verification
    # ========================================================================
    # Why: Ensure essential development tools are accessible
    # How: Check each package with command -v
    # What: Verify packages are in current PATH
    #
    # Critical packages checked:
    # - kubectl: K3s cluster management CLI
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
    local missing_count=0

    # Loop through critical packages
    local -a package_checks=(kubectl python3 git home-manager jq flatpak claude codium)

    for pkg in "${package_checks[@]}"; do
        # command -v: Find command in PATH, return path or empty
        # &>/dev/null: Suppress output (just checking existence)
        if command -v "$pkg" &>/dev/null; then
            # Package found - show where it's located
            # $(command -v $pkg): Get full path to package
            print_success "$pkg: $(command -v $pkg)"
        else
            # Package not found - warn and count
            print_warning "$pkg: NOT FOUND"

            # Increment counter
            # ((expr)): Arithmetic expansion
            # || true: Prevent exit on failure (set -e safety)
            ((missing_count++)) || true
        fi
    done

    # Check if any packages were missing
    # -gt 0: Greater than zero
    if [[ $missing_count -gt 0 ]]; then
        # Some packages not in PATH
        print_warning "$missing_count critical package(s) not in PATH"
        print_info "Try: exec zsh  (to reload shell)"
        # Note: Not exiting - user can fix by reloading shell
    else
        # All packages found - deployment successful!
        print_success "All critical packages verified!"
    fi

    # Optional AI toolchain checks (Home Manager-scoped)
    print_info "Verifying AI toolchain (Home Manager scoped)..."
    local ai_missing=0

    if command -v gpt4all &>/dev/null; then
        print_success "gpt4all: $(command -v gpt4all)"
    else
        print_warning "gpt4all: NOT FOUND (Home Manager)"
        ((ai_missing++)) || true
    fi

    if command -v aider &>/dev/null; then
        print_success "aider: $(command -v aider)"
    else
        print_warning "aider: NOT FOUND (Home Manager)"
        ((ai_missing++)) || true
    fi

    # Nix packages expose llama.cpp as llama-cli/llama-server, not llama-cpp.
    if command -v llama-cli &>/dev/null; then
        print_success "llama-cli: $(command -v llama-cli)"
    elif command -v llama-server &>/dev/null; then
        print_success "llama-server: $(command -v llama-server)"
    else
        print_warning "llama.cpp CLI: NOT FOUND (expected llama-cli or llama-server)"
        ((ai_missing++)) || true
    fi

    if [[ $ai_missing -gt 0 ]]; then
        print_warning "$ai_missing AI tool(s) missing from PATH"
        print_info "If Home Manager was not applied, run:"
        print_info "  nix run home-manager -- switch --flake ${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}#${PRIMARY_USER:-$USER}"
    else
        print_success "AI toolchain detected!"
    fi

    if (( fatal_failures > 0 )); then
        print_warning "Critical validation checks failed (${fatal_failures})"
        print_info "Review the errors above; deployment continues so you can resolve them later."
    else
        print_success "Critical validation checks passed"
    fi

    if (( warning_failures > 0 )); then
        print_warning "${warning_failures} validation warning(s) recorded"
    else
        print_success "No additional validation warnings recorded"
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
    # Next: Phase 9 will finalize system configuration
    mark_step_complete "$phase_name"
    # Ensure phase marker exists even if this script is run directly.
    mark_step_complete "phase-07"
    print_success "Phase 7: Post-Deployment Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_07_post_deployment_validation
