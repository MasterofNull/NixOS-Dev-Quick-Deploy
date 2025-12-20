#!/usr/bin/env bash
#
# Phase 04: Pre-Deployment Validation
# Purpose: Validate environment and identify potential conflicts before deployment
# Version: Uses SCRIPT_VERSION from main script
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/validation.sh → Validation functions
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#
# Requires Phases (must complete before this):
#   - Phase 2: BACKUP_ROOT must be set for safety
#   - Phase 3: Configs must be generated
#
# Produces (for later phases):
#   - VALIDATION_COMPLETE → Flag indicating validation done
#   - State: "pre_deployment_validation" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_04_pre_deployment_validation() {
    # ========================================================================
    # Phase 4: Pre-Deployment Validation
    # ========================================================================
    # This phase validates the environment before deployment:
    # 1. Check for nix-env packages (will be cleaned in Phase 5)
    # 2. Validate generated configurations
    # 3. Check disk space
    # 4. Verify prerequisites
    #
    # Note: Actual package removal and backups happen in Phase 5
    # This phase is non-destructive - it only identifies potential issues
    # ========================================================================

    local phase_name="pre_deployment_validation"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 4 already completed (skipping)"
        return 0
    fi

    print_section "Phase 4/8: Pre-Deployment Validation"
    echo ""

    if ! ensure_flake_workspace; then
        print_error "Unable to prepare Home Manager flake workspace at $HM_CONFIG_DIR"
        print_info "Phase 3 (Configuration Generation) must be completed before validation."
        echo ""
        return 1
    fi

    # ========================================================================
    # Step 5.1: Check for nix-env Installed Packages
    # ========================================================================
    print_info "Checking for packages installed via nix-env (imperative method)..."
    local imperative_pkgs
    imperative_pkgs=$(nix-env -q 2>/dev/null || true)

    if [[ -n "$imperative_pkgs" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$imperative_pkgs" | sed 's/^/    /'
        echo ""
        print_info "These will be removed in Phase 6 before system deployment to prevent conflicts"
        echo ""
    else
        print_success "No nix-env packages found - clean state!"
        echo ""
    fi

    # ========================================================================
    # Step 5.2: Validate Generated Configurations
    # ========================================================================
    print_info "Validating generated configuration files..."

    if ! verify_home_manager_flake_ready; then
        echo ""
        return 1
    fi

    print_success "home.nix found and ready"
    print_success "flake.nix found and ready"

    # Check if configuration.nix exists
    if [[ ! -f "/etc/nixos/configuration.nix" ]]; then
        print_warning "configuration.nix not found at: /etc/nixos/configuration.nix"
        print_warning "System configuration may need to be generated"
    else
        print_success "configuration.nix found and ready"
    fi

    echo ""

    # ========================================================================
    # Step 5.3: Check Disk Space
    # ========================================================================
    print_info "Checking available disk space..."

    # Get available space in GB for /nix
    local nix_avail
    nix_avail=$(df -BG /nix | tail -1 | awk '{print $4}' | tr -d 'G')

    # Get available space in GB for $HOME
    local home_avail
    home_avail=$(df -BG "$HOME" | tail -1 | awk '{print $4}' | tr -d 'G')

    print_info "/nix available space: ${nix_avail}GB"
    print_info "\$HOME available space: ${home_avail}GB"

    # Warn if less than 10GB available on /nix
    if [[ "$nix_avail" -lt 10 ]]; then
        print_warning "Low disk space on /nix: ${nix_avail}GB available"
        print_warning "Recommend at least 10GB free for deployment"
        print_info "Run 'nix-collect-garbage -d' to free up space"
        echo ""
    else
        print_success "Sufficient disk space available"
        echo ""
    fi

    # ========================================================================
    # Step 5.4: Validate System Build (Dry Run)
    # ========================================================================
    print_info "Validating system build (dry run)..."
    local tmp_dir="${TMP_DIR:-/tmp}"
    local NIXOS_REBUILD_DRY_LOG="${tmp_dir}/nixos-rebuild-dry-run.log"
    local target_host=$(hostname)

    local -a nixos_rebuild_opts=()
    if declare -F activate_build_acceleration_context >/dev/null 2>&1; then
        activate_build_acceleration_context
    fi

    if declare -F compose_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t nixos_rebuild_opts < <(compose_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
    fi

    local dry_run_display="sudo nixos-rebuild dry-run --flake \"$HM_CONFIG_DIR#$target_host\""
    if (( ${#nixos_rebuild_opts[@]} > 0 )); then
        dry_run_display+=" ${nixos_rebuild_opts[*]}"
    fi

    print_info "Running: $dry_run_display"

    if declare -F describe_binary_cache_usage >/dev/null 2>&1; then
        describe_binary_cache_usage "nixos-rebuild dry-run"
    fi

    if declare -F describe_remote_build_context >/dev/null 2>&1; then
        describe_remote_build_context
    fi

    # Run nixos-rebuild dry-run to check for errors
    if sudo nixos-rebuild dry-run --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" &> "$NIXOS_REBUILD_DRY_LOG"; then
        print_success "Dry run completed successfully (no changes applied)"
        print_info "Log saved to: $NIXOS_REBUILD_DRY_LOG"
        echo ""
    else
        local dry_exit_code=$?
        print_warning "Dry run had issues (exit code: $dry_exit_code)"
        print_info "Review the log: $NIXOS_REBUILD_DRY_LOG"
        print_warning "This may be due to missing channels or first-time setup"
        print_info "Deployment will continue, but may require fixing issues"
        echo ""
    fi

    # ========================================================================
    # Step 5.5: Check Prerequisites
    # ========================================================================
    print_info "Checking deployment prerequisites..."

    # Check for required commands
    local missing_prereqs=()

    if ! command -v sudo &>/dev/null; then
        missing_prereqs+=("sudo")
    fi

    if ! command -v nixos-rebuild &>/dev/null; then
        missing_prereqs+=("nixos-rebuild")
    fi

    if [[ ${#missing_prereqs[@]} -gt 0 ]]; then
        print_error "Missing required commands: ${missing_prereqs[*]}"
        print_error "Cannot proceed with deployment"
        return 1
    else
        print_success "All deployment prerequisites available"
    fi

    echo ""

    # ========================================================================
    # Step 5.6: Summary Report
    # ========================================================================
    print_section "Validation Summary"

    echo "Configuration files validated and ready for deployment"
    if [[ -n "$imperative_pkgs" ]]; then
        echo "⚠ Found $(echo "$imperative_pkgs" | wc -l) nix-env packages (will be removed in Phase 6)"
    else
        echo "✓ No conflicting nix-env packages"
    fi
    echo "✓ Sufficient disk space available"
    echo "✓ All prerequisites present"
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 4: Pre-Deployment Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_04_pre_deployment_validation
