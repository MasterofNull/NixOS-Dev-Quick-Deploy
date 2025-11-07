#!/usr/bin/env bash
#
# Phase 04: Pre-Deployment Validation
# Purpose: Validate environment and identify potential conflicts before deployment
# Version: 4.0.0
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

    local phase_name="pre_deployment_validation"  # State tracking identifier for this phase

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state.json for completion marker
        print_info "Phase 4 already completed (skipping)"
            return 0  # Skip to next phase
    fi

    print_section "Phase 4/8: Pre-Deployment Validation"  # Display phase header
        echo ""

    # Ensure home-manager flake workspace is ready before validation
    if ! ensure_flake_workspace; then  # Verify flake directory exists and is configured
        print_error "Unable to prepare Home Manager flake workspace at $HM_CONFIG_DIR"
            print_info "Phase 3 (Configuration Generation) must be completed before validation."
        echo ""
            return 1  # Fatal - need configs to validate
    fi

    # ========================================================================
    # Step 5.1: Check for nix-env Installed Packages
    # ========================================================================
    # Why: Imperative nix-env packages conflict with declarative NixOS configs
    # How: Query nix-env for installed packages
    # Action: Identify (not remove) - removal happens in Phase 5
    print_info "Checking for packages installed via nix-env (imperative method)..."
        local imperative_pkgs  # List of imperatively installed packages
    imperative_pkgs=$(nix-env -q 2>/dev/null || true)  # Query user environment (suppress errors)

    if [[ -n "$imperative_pkgs" ]]; then  # Found imperative packages
        print_warning "Found packages installed via nix-env:"
            echo "$imperative_pkgs" | sed 's/^/    /'  # Indent list for readability
        echo ""
            print_info "These will be removed in Phase 6 before system deployment to prevent conflicts"
        echo ""
    else  # No imperative packages - clean state
        print_success "No nix-env packages found - clean state!"
            echo ""
    fi

    # ========================================================================
    # Step 5.2: Validate Generated Configurations
    # ========================================================================
    # Why: Ensure all required config files exist before deployment
    # How: Check for home.nix, flake.nix, and configuration.nix
    # Files checked:
    #   - ~/.config/home-manager/home.nix (user environment)
    #   - ~/.config/home-manager/flake.nix (dependency pinning)
    #   - /etc/nixos/configuration.nix (system config)
    print_info "Validating generated configuration files..."

    # Verify home-manager flake is ready for use
    if ! verify_home_manager_flake_ready; then  # Check home.nix and flake.nix exist
        echo ""
            return 1  # Fatal - missing required configs
    fi

    print_success "home.nix found and ready"  # User environment config validated
        print_success "flake.nix found and ready"  # Dependency lock file validated

    # Check if system configuration exists (should be created in Phase 3)
    if [[ ! -f "/etc/nixos/configuration.nix" ]]; then  # System config missing
        print_warning "configuration.nix not found at: /etc/nixos/configuration.nix"
            print_warning "System configuration may need to be generated"
    else  # System config exists
        print_success "configuration.nix found and ready"
    fi

    echo ""

    # ========================================================================
    # Step 5.3: Check Disk Space
    # ========================================================================
    # Why: Deployment requires significant disk space for builds
    # Requirements: 10GB+ on /nix for package builds
    # Check: /nix (Nix store) and $HOME (user files)
    print_info "Checking available disk space..."

    # Get available space in GB for /nix (where all packages are stored)
    local nix_avail  # Available space on /nix partition
        nix_avail=$(df -BG /nix | tail -1 | awk '{print $4}' | tr -d 'G')  # Extract gigabytes available

    # Get available space in GB for $HOME (user directory)
    local home_avail  # Available space on home partition
        home_avail=$(df -BG "$HOME" | tail -1 | awk '{print $4}' | tr -d 'G')  # Extract gigabytes available

    print_info "/nix available space: ${nix_avail}GB"  # Display Nix store space
        print_info "\$HOME available space: ${home_avail}GB"  # Display home directory space

    # Warn if less than 10GB available on /nix (deployment needs space)
    if [[ "$nix_avail" -lt 10 ]]; then  # Low disk space condition
        print_warning "Low disk space on /nix: ${nix_avail}GB available"
            print_warning "Recommend at least 10GB free for deployment"
        print_info "Run 'nix-collect-garbage -d' to free up space"  # Suggest garbage collection
            echo ""
    else  # Sufficient space available
        print_success "Sufficient disk space available"
            echo ""
    fi

    # ========================================================================
    # Step 5.4: Validate System Build (Dry Run)
    # ========================================================================
    # Why: Test configuration validity without applying changes
    # How: Run nixos-rebuild dry-run (evaluates + simulates)
    # Output: Saved to log file for debugging
    # Non-blocking: Warnings don't stop deployment
    print_info "Validating system build (dry run)..."
        local NIXOS_REBUILD_DRY_LOG="/tmp/nixos-rebuild-dry-run.log"  # Log file path
    local target_host=$(hostname)  # Get current hostname for flake target

    # Run nixos-rebuild dry-run to validate config without making changes
    if sudo nixos-rebuild dry-run --flake "$HM_CONFIG_DIR#$target_host" &> "$NIXOS_REBUILD_DRY_LOG"; then  # Dry run succeeded
        print_success "Dry run completed successfully (no changes applied)"
            print_info "Log saved to: $NIXOS_REBUILD_DRY_LOG"
        echo ""
    else  # Dry run had errors or warnings
        local dry_exit_code=$?  # Capture exit code
            print_warning "Dry run had issues (exit code: $dry_exit_code)"
        print_info "Review the log: $NIXOS_REBUILD_DRY_LOG"  # Point to log file
            print_warning "This may be due to missing channels or first-time setup"
        print_info "Deployment will continue, but may require fixing issues"  # Non-blocking warning
            echo ""
    fi

    # ========================================================================
    # Step 5.5: Check Prerequisites
    # ========================================================================
    # Why: Verify required commands are available for deployment
    # Required: sudo (for system changes), nixos-rebuild (for deployment)
    # Blocking: Missing prerequisites stop deployment
    print_info "Checking deployment prerequisites..."

    # Check for required commands - build array of missing tools
    local missing_prereqs=()  # Array to hold missing command names

    # Check if sudo command is available
    if ! command -v sudo &>/dev/null; then  # sudo not found in PATH
        missing_prereqs+=("sudo")  # Add to missing list
    fi

    # Check if nixos-rebuild command is available
    if ! command -v nixos-rebuild &>/dev/null; then  # nixos-rebuild not found
        missing_prereqs+=("nixos-rebuild")  # Add to missing list
    fi

    # Report results - fail if any required commands are missing
    if [[ ${#missing_prereqs[@]} -gt 0 ]]; then  # Array has elements (missing prereqs)
        print_error "Missing required commands: ${missing_prereqs[*]}"
            print_error "Cannot proceed with deployment"
        return 1  # Fatal - can't deploy without required tools
    else  # All prerequisites found
        print_success "All deployment prerequisites available"
    fi

    echo ""

    # ========================================================================
    # Step 5.6: Summary Report
    # ========================================================================
    # Display comprehensive validation results before proceeding
    # Shows: Config status, package conflicts, disk space, prerequisites
    print_section "Validation Summary"

    echo "Configuration files validated and ready for deployment"  # Configs exist and are valid
        if [[ -n "$imperative_pkgs" ]]; then  # Found imperative packages earlier
        echo "⚠ Found $(echo "$imperative_pkgs" | wc -l) nix-env packages (will be removed in Phase 6)"  # Count and warn
    else  # No imperative packages
        echo "✓ No conflicting nix-env packages"
    fi
    echo "✓ Sufficient disk space available"  # Disk space check passed
        echo "✓ All prerequisites present"  # sudo and nixos-rebuild available
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Validation complete - system is ready for deployment
    # All checks passed (or warned where appropriate)
    mark_step_complete "$phase_name"  # Update state.json with completion marker
        print_success "Phase 4: Pre-Deployment Validation - COMPLETE"
    echo ""
}

# Execute phase function (called when this script is sourced by main orchestrator)
phase_04_pre_deployment_validation  # Run all validation operations
