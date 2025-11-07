#!/usr/bin/env bash
#
# Phase 05: Declarative Deployment
# Purpose: Apply NixOS and home-manager configurations
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/user-interaction.sh → confirm()
#
# Required Variables (from config/variables.sh):
#   - HM_CONFIG_DIR → Home-manager configuration directory
#   - STATE_DIR → State directory for logs
#   - USER → Primary user
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

ensure_low_memory_swap() {
    # ========================================================================
    # Helper: Ensure Low Memory Swap
    # ========================================================================
    # Why: NixOS builds can consume significant RAM (8-12GB+)
    # Action: Create temporary swap on systems with <16GB RAM and <4GB swap
    # Cleanup: Automatically removed in Phase 8 when permanent swap detected
    # ========================================================================

    local detected_ram="${TOTAL_RAM_GB:-}"  # RAM detected in Phase 1 (may be empty)
        local ram_value  # Numeric RAM value for comparison

    # Parse detected RAM value (ensure it's a number)
    if [[ "$detected_ram" =~ ^[0-9]+$ ]]; then  # Valid numeric value
        ram_value="$detected_ram"
    else  # Invalid or missing - assume 0
        ram_value=0
    fi

    # No extra swap needed on well-provisioned systems (16GB+ RAM)
    if (( ram_value >= 16 )); then  # System has sufficient RAM
        return 0  # Skip swap creation
    fi

    # Check current swap availability
    local swap_total_kb  # Current swap space in kilobytes
        swap_total_kb=$(awk '/^SwapTotal:/ { print $2 }' /proc/meminfo 2>/dev/null || echo "0")  # Read from /proc/meminfo
    local swap_total_gb=$(( swap_total_kb / 1024 / 1024 ))  # Convert KB to GB

    # Minimum swap requirement for builds
    local min_swap_gb=4  # 4GB minimum for safe NixOS builds
        if (( swap_total_gb >= min_swap_gb )); then  # Already have sufficient swap
        print_info "Detected ${swap_total_gb}GB swap space — temporary swap guardrail not required."
            return 0  # Skip swap creation
    fi

    # Check if temporary swapfile already exists
    local swapfile_path="/swapfile.nixos-quick-deploy"  # Standard temporary swap location
        if [[ -e "$swapfile_path" ]]; then  # Swapfile already exists
        print_warning "Temporary swapfile already present at $swapfile_path; skipping automatic provisioning."
            return 0  # Don't overwrite existing swap
    fi

    # Calculate how much additional swap is needed
    local additional_swap_gb=$(( min_swap_gb - swap_total_gb ))  # Gap between current and minimum
        if (( additional_swap_gb < 1 )); then  # Ensure at least 1GB created
        additional_swap_gb=1
    fi

    print_info "Provisioning temporary ${additional_swap_gb}GB swapfile at $swapfile_path (RAM: ${ram_value}GB, existing swap: ${swap_total_gb}GB)."

    # Allocate swap file using dd (1MB blocks)
    local block_count=$(( additional_swap_gb * 1024 ))  # Convert GB to MB for dd
        if ! sudo dd if=/dev/zero of="$swapfile_path" bs=1M count="$block_count" status=none; then  # Allocate file
        print_warning "Failed to allocate temporary swapfile at $swapfile_path. Continuing without additional swap."
            sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true  # Clean up partial file
        return 0  # Non-fatal - deployment can continue
    fi

    # Set secure permissions (600 = rw only for root)
    if ! sudo chmod 600 "$swapfile_path"; then  # Restrict access for security
        print_warning "Unable to set secure permissions on $swapfile_path. Removing temporary swapfile."
            sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true  # Remove insecure file
        return 0  # Non-fatal
    fi

    # Format file as swap space
    if ! sudo mkswap "$swapfile_path" >/dev/null 2>&1; then  # Initialize swap format
        print_warning "mkswap failed for $swapfile_path. Removing temporary swapfile."
            sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true  # Clean up
        return 0  # Non-fatal
    fi

    # Activate swap space
    if sudo swapon "$swapfile_path"; then  # Enable swap for use
        print_success "Temporary swapfile enabled: $swapfile_path (${additional_swap_gb}GB)."
            print_info "It will be removed automatically during finalization when permanent swap is detected. Manual cleanup: sudo swapoff $swapfile_path && sudo rm -f $swapfile_path"
        # Export variables for Phase 8 cleanup
        TEMP_SWAP_CREATED=true  # Flag indicating we created temporary swap
            TEMP_SWAP_FILE="$swapfile_path"  # Path to temporary swap file
        TEMP_SWAP_SIZE_GB="$additional_swap_gb"  # Size for logging
            export TEMP_SWAP_CREATED TEMP_SWAP_FILE TEMP_SWAP_SIZE_GB  # Make available to other phases
    else  # Failed to activate swap
        print_warning "Failed to activate temporary swapfile at $swapfile_path."
            sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true  # Clean up
    fi
}

phase_05_declarative_deployment() {
    # ========================================================================
    # Phase 5: Declarative Deployment
    # ========================================================================
    # Switching from Imperative to Declarative Package Management:
    #
    # The Problem:
    # - nix-env packages (imperative) persist in user profile
    # - Declarative packages (configuration.nix/home.nix) are separate
    # - Having the SAME package in both locations causes conflicts
    # - nixos-rebuild DOES NOT automatically remove nix-env packages
    #
    # The Solution:
    # - Remove ALL nix-env packages before switching to declarative
    # - Save the list so user can add them back declaratively if wanted
    # - Apply declarative configurations
    #
    # Reference: NixOS Manual - Chapter on Declarative Package Management
    # ========================================================================

    local phase_name="deploy_configurations"  # State tracking identifier for this phase

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state.json for completion marker
        print_info "Phase 5 already completed (skipping)"
            return 0  # Skip to next phase
    fi

    print_section "Phase 5/8: Declarative Deployment"  # Display phase header
        echo ""

    # Ensure home-manager flake workspace exists and is ready
    if ! ensure_flake_workspace; then  # Verify flake directory structure
        print_error "Unable to prepare Home Manager flake workspace at $HM_CONFIG_DIR"
            print_info "Phase 3 (Configuration Generation) should establish this directory."
        print_info "Re-run that phase or restore your dotfiles before continuing."
            echo ""
        return 1  # Fatal - need flake workspace for deployment
    fi

    # Verify home-manager configuration files exist
    if ! verify_home_manager_flake_ready; then  # Check for home.nix and flake.nix
        echo ""
            return 1  # Fatal - missing required config files
    fi

    # ========================================================================
    # Step 6.1: Check for nix-env Packages
    # ========================================================================
    # Why: Imperative packages conflict with declarative configurations
    # Action: Identify all nix-env packages (removed in Step 6.3)
    # Conflict: Same package in both locations causes deployment failures
    print_info "Checking for nix-env packages (imperative management)..."
        local IMPERATIVE_PKGS  # List of imperatively installed packages
    IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null || true)  # Query user environment

    if [[ -n "$IMPERATIVE_PKGS" ]]; then  # Found imperative packages
        print_warning "Found packages installed via nix-env:"
            echo "$IMPERATIVE_PKGS" | sed 's/^/    /'  # Indent package list
        echo ""
            print_warning "These MUST be removed to switch to declarative management"
        print_info "They will conflict with packages in configuration.nix/home.nix"
    else  # No imperative packages - clean state
        print_success "No nix-env packages found - ready for declarative management"
    fi

    echo ""

    # ========================================================================
    # Step 6.2: Final Deployment Confirmation
    # ========================================================================
    # Why: Last chance for user to review deployment plan
    # Shows: What will be changed/removed during deployment
    # Allows: User to cancel or proceed
    print_section "Ready to Deploy Declarative Configuration"
        echo ""
    # Display deployment plan clearly
    echo "This deployment will:"
        echo "  1. Remove ALL nix-env packages (saved to backup for reference)"
    echo "  2. Apply NixOS system configuration (declarative)"
        echo "  3. Apply home-manager user configuration (declarative)"
    echo "  4. Configure Flatpak repositories"
        echo ""
    echo "After deployment:"
        echo "  • All packages managed declaratively via configuration files"
    echo "  • Add/remove packages by editing configuration.nix or home.nix"
        echo "  • No more 'nix-env -i' needed (use declarative configs instead)"
    echo ""

    # Show packages that will be removed (if any)
    if [[ -n "$IMPERATIVE_PKGS" ]]; then  # Imperative packages found earlier
        echo "Packages to be removed:"
            echo "$IMPERATIVE_PKGS" | sed 's/^/    /'  # Indent list
        echo ""
            echo "To keep these packages, add them to configuration.nix or home.nix"
    fi

    echo ""

    # Get user confirmation before proceeding with destructive changes
    if ! confirm "Proceed with deployment (removes nix-env packages, applies declarative config)?" "y"; then  # User declined
        print_warning "Deployment cancelled"
            print_info "To apply later:"
        print_info "  1. Manually remove nix-env packages: nix-env -e '.*'"
            print_info "  2. Apply system config: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        print_info "  3. Apply user config: home-manager switch --flake $HM_CONFIG_DIR"
            echo ""
        return 0  # Exit phase gracefully (not an error)
    fi

    echo ""

    # ========================================================================
    # Step 6.3: Remove ALL nix-env Packages
    # ========================================================================
    # This is REQUIRED for declarative management to work properly
    # nix-env packages persist and conflict with declarative packages
    # Strategy: Batch removal first, fallback to individual if needed
    if [[ -n "$IMPERATIVE_PKGS" ]]; then  # Imperative packages exist
        print_section "Removing nix-env Packages"
            print_info "Switching to declarative package management..."
        echo ""

        # Save package list for user reference before removing
        local removed_pkgs_file="$STATE_DIR/removed-nix-env-packages-$(date +%s).txt"  # Timestamped filename
            if safe_mkdir "$STATE_DIR"; then  # Ensure state directory exists
            echo "$IMPERATIVE_PKGS" > "$removed_pkgs_file"  # Write package list to file
                print_info "Package list saved to: $removed_pkgs_file"
            print_info "Add these to configuration.nix or home.nix if you want them back"
        else  # Failed to create state directory
            print_warning "Could not save package list"
        fi
        echo ""

        # Remove all nix-env packages using regex pattern '.*' (matches everything)
        print_info "Removing ALL nix-env packages..."
            if nix-env -e '.*' 2>&1 | tee /tmp/nix-env-cleanup.log; then  # Batch removal with regex
            print_success "✓ All nix-env packages removed successfully"
        else  # Batch removal failed (rare but possible)
            # Fallback: Remove packages one by one
            print_warning "Batch removal failed, trying individual removal..."
                while IFS= read -r pkg; do  # Iterate through package list
                local pkg_name  # Package name without version
                    pkg_name=$(echo "$pkg" | awk '{print $1}')  # Extract first field (package name)
                if [[ -n "$pkg_name" ]]; then  # Skip empty lines
                    print_info "  Removing: $pkg_name"
                        if nix-env -e "$pkg_name" 2>/dev/null; then  # Remove individual package
                        print_success "    ✓ Removed"
                    else  # Removal failed
                        print_warning "    ⚠ Could not remove (may already be gone)"
                    fi
                fi
            done <<< "$IMPERATIVE_PKGS"  # Feed package list to while loop
        fi

        # Verify all packages were removed successfully
        local REMAINING  # Any packages still in nix-env after removal
            REMAINING=$(nix-env -q 2>/dev/null || true)  # Query again
        if [[ -n "$REMAINING" ]]; then  # Some packages still present
            print_warning "Some packages remain in nix-env:"
                echo "$REMAINING" | sed 's/^/    /'  # Indent list
            print_warning "These may cause conflicts - remove manually: nix-env -e <package>"
        else  # All packages successfully removed
            print_success "✓ All nix-env packages removed"
                print_success "✓ Ready for declarative management"
        fi

        echo ""
    fi

    # ========================================================================
    # Step 6.4: Update Flake Inputs (System + Home Manager)
    # ========================================================================
    # Why: Ensure latest package versions and dependencies are pinned
    # Action: Run 'nix flake update' to update flake.lock file
    # Result: Pinned revisions for reproducible builds
    print_section "Updating Flake Inputs"
        print_info "Ensuring all configurations use the pinned revisions before switching..."
    echo ""

    # Capture output and status separately for better error handling
    local flake_update_output=""  # Command output
        local flake_update_status=0  # Exit code

    # Update flake inputs (updates flake.lock with latest compatible versions)
    if ! flake_update_output=$(cd "$HM_CONFIG_DIR" && nix flake update 2>&1); then  # Capture output
        flake_update_status=$?  # Save non-zero exit code
    fi

    # Display results based on success/failure
    if (( flake_update_status == 0 )); then  # Update succeeded
        if [[ -n "$flake_update_output" ]]; then  # Has output to show
            echo "$flake_update_output"  # Display update results
        fi
        print_success "✓ Flake inputs updated"  # Success message
    else  # Update had issues
        if [[ -n "$flake_update_output" ]]; then  # Has output to show
            echo "$flake_update_output" | sed 's/^/  /'  # Indent error output
        fi
        print_warning "⚠ Flake update had issues (continuing anyway)"  # Non-fatal warning
    fi

    echo ""

    # ========================================================================
    # Step 6.5: Apply NixOS System Configuration
    # ========================================================================
    # Why: Deploy declarative system configuration to live system
    # Command: nixos-rebuild switch --flake <flake-dir>#<hostname>
    # Result: System matches configuration.nix exactly
    # Critical: This is the main deployment action

    # Ensure sufficient swap for build process (low memory systems)
    ensure_low_memory_swap  # Create temporary swap if needed (<16GB RAM, <4GB swap)

    print_section "Applying NixOS System Configuration"
        local target_host=$(hostname)  # Get hostname for flake target selection

    # Compose additional nixos-rebuild options (binary cache, max-jobs, etc.)
    local -a nixos_rebuild_opts=()  # Array of optional arguments
        if declare -F compose_nixos_rebuild_options >/dev/null 2>&1; then  # Function exists
        mapfile -t nixos_rebuild_opts < <(compose_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")  # Get options as array
    fi

    # Build display command for user information
    local rebuild_display="sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""  # Base command
        if (( ${#nixos_rebuild_opts[@]} > 0 )); then  # Have additional options
        rebuild_display+=" ${nixos_rebuild_opts[*]}"  # Append options
    fi

    print_info "Running: $rebuild_display"  # Show full command
        print_info "This applies the declarative system configuration..."
    echo ""

    # Display binary cache usage information if available
    if declare -F describe_binary_cache_usage >/dev/null 2>&1; then  # Function exists
        describe_binary_cache_usage "nixos-rebuild switch"  # Show cache info
    fi

    # Execute nixos-rebuild switch (THE DEPLOYMENT)
    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" 2>&1 | tee /tmp/nixos-rebuild.log; then  # Success
        print_success "✓ NixOS system configuration applied!"
            print_success "✓ System packages now managed declaratively"
        echo ""
    else  # Deployment failed
        local exit_code=${PIPESTATUS[0]}  # Capture exit code from nixos-rebuild
            print_error "nixos-rebuild failed (exit code: $exit_code)"
        # Diagnose common failure causes
        if [[ ! -d "$HM_CONFIG_DIR" ]]; then  # Flake directory missing
            print_error "Home Manager flake directory is missing: $HM_CONFIG_DIR"
                print_info "Restore the directory or rerun Phase 3 before retrying."
        elif [[ ! -f "$HM_CONFIG_DIR/flake.nix" ]]; then  # flake.nix missing
            print_error "flake.nix is missing from: $HM_CONFIG_DIR"
                print_info "Regenerate the configuration with Phase 3 or restore from backup."
        fi
        print_info "Log: /tmp/nixos-rebuild.log"  # Point to log file
            print_info "Rollback: sudo nixos-rebuild --rollback"  # Show rollback command
        echo ""
            return 1  # Fatal - can't proceed without system config applied
    fi

    # ========================================================================
    # Step 6.6: Prepare Home Manager Targets
    # ========================================================================
    # Why: Backup existing user configs before home-manager overwrites them
    # Action: Archive dotfiles that home-manager will manage
    # Safety: Prevents data loss from existing configurations
    if ! prepare_home_manager_targets "pre-switch"; then  # Archive existing user config files
        print_warning "Encountered issues while archiving existing configuration files. Review the messages above before continuing."
    fi
    echo ""

    # ========================================================================
    # Step 6.7: Apply Home Manager Configuration
    # ========================================================================
    # Why: Deploy declarative user environment configuration
    # Command: home-manager switch --flake <flake-dir>
    # Result: User environment matches home.nix exactly
    print_section "Applying Home Manager Configuration"
        print_info "This configures your user environment declaratively..."
    echo ""

    # Ensure supporting scripts referenced by the flake are available
    local p10k_source="$BOOTSTRAP_SCRIPT_DIR/scripts/p10k-setup-wizard.sh"  # Source location
        local p10k_destination="$HM_CONFIG_DIR/p10k-setup-wizard.sh"  # Destination in flake

    # Copy Powerlevel10k wizard script to flake directory (referenced by home.nix)
    print_info "Ensuring Powerlevel10k setup wizard is available for Home Manager"
        if [[ -f "$p10k_source" ]]; then  # Source file exists
        # Ensure flake directory exists before copying
        if [[ ! -d "$HM_CONFIG_DIR" ]]; then  # Directory missing
            if mkdir -p "$HM_CONFIG_DIR"; then  # Try to create
                print_info "  Created Home Manager config directory at $HM_CONFIG_DIR"
            else  # Creation failed
                print_warning "  ⚠ Unable to create $HM_CONFIG_DIR (continuing, but Home Manager may fail)"
            fi
        fi

        # Copy wizard script to flake directory
        if cp "$p10k_source" "$p10k_destination"; then  # Copy successful
            chmod +x "$p10k_destination" 2>/dev/null || true  # Make executable
                print_success "  ✓ Synced p10k-setup-wizard.sh to Home Manager flake"
        else  # Copy failed
            print_warning "  ⚠ Failed to sync p10k-setup-wizard.sh (continuing, but Home Manager may fail)"
        fi
    else  # Source file doesn't exist
        print_warning "  ⚠ Source p10k-setup-wizard.sh not found at $p10k_source"
    fi
    echo ""

    # Determine home-manager command (installed vs run from flake)
    local hm_cmd  # Command to execute
        if command -v home-manager &>/dev/null; then  # home-manager already installed
        hm_cmd="home-manager"  # Use installed command
            print_info "Using: home-manager switch --flake $HM_CONFIG_DIR"
    else  # home-manager not installed yet
        hm_cmd="nix run github:nix-community/home-manager#home-manager --"  # Run from flake
            print_info "Using: nix run github:nix-community/home-manager -- switch --flake $HM_CONFIG_DIR"
    fi
    echo ""

    # Apply home-manager configuration (THE USER DEPLOYMENT)
    if $hm_cmd switch --flake "$HM_CONFIG_DIR" 2>&1 | tee /tmp/home-manager-switch.log; then  # Success
        print_success "✓ Home manager configuration applied!"
            print_success "✓ User packages now managed declaratively"
        echo ""
    else  # Deployment failed
        local hm_exit_code=${PIPESTATUS[0]}  # Capture exit code
            print_error "home-manager switch failed (exit code: $hm_exit_code)"
        print_info "Log: /tmp/home-manager-switch.log"  # Point to log file
            print_info "Rollback: home-manager --rollback"  # Show rollback command
        echo ""
            print_warning "Common causes:"
        print_info "  • Syntax errors in home.nix"  # Nix syntax issues
            print_info "  • Network issues downloading packages"  # Connectivity problems
        print_info "  • Package conflicts (check log)"  # Conflicting package versions
            echo ""
        return 1  # Fatal - can't proceed without user environment
    fi

    # ========================================================================
    # Step 6.8: Configure Flatpak Remotes (if available)
    # ========================================================================
    # Why: Flatpak provides sandboxed applications not in Nix packages
    # Action: Add Flathub repository for Flatpak app downloads
    # Note: Actual app installation happens in Phase 6
    local flatpak_configured=false  # Track whether we configured Flatpak
        if command -v flatpak &>/dev/null; then  # Flatpak is installed
        flatpak_configured=true  # Mark as configured
            print_section "Configuring Flatpak"

        # Add Flathub repository if not already present
        if ! flatpak remote-list --user 2>/dev/null | grep -q "^flathub"; then  # Flathub not configured
            print_info "Adding Flathub repository..."
                if flatpak remote-add --user --if-not-exists flathub \
                https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null; then  # Primary URL
                print_success "✓ Flathub repository added"
            else  # Primary URL failed, try alternate
                print_info "Trying alternate Flathub URL..."
                    flatpak remote-add --user --if-not-exists flathub \
                    https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null || \
                        print_warning "⚠ Could not add Flathub (add manually if needed)"
            fi
        else  # Flathub already configured
            print_success "✓ Flathub repository already configured"
        fi

        # Add Flathub Beta repository (optional for testing apps)
        if ! flatpak remote-list --user 2>/dev/null | grep -q "^flathub-beta"; then  # Beta not configured
            print_info "Adding Flathub Beta repository (optional)..."
                flatpak remote-add --user --if-not-exists flathub-beta \
                https://flathub.org/beta-repo/flathub-beta.flatpakrepo 2>/dev/null && \
                    print_success "✓ Flathub Beta added" || \
                print_info "  Flathub Beta not added (not required)"
        fi

        # Inform user about Phase 6 app installation
        print_info "Flatpak application installs will run in Phase 6 to avoid blocking systemd during switch"
            echo ""
    fi

    # ========================================================================
    # Deployment Summary
    # ========================================================================
    # Display comprehensive summary of what was accomplished
    # Shows: Completed actions, usage instructions, rollback options
    print_section "Deployment Complete - Now Fully Declarative"
        echo "✓ All nix-env packages removed"  # Imperative packages cleaned
    echo "✓ NixOS system configuration applied"  # System matches configuration.nix
        echo "✓ Home manager user environment configured"  # User matches home.nix
    echo "✓ All packages now managed declaratively"  # Fully declarative state
        if [[ "$flatpak_configured" == true ]]; then  # Flatpak was configured
        echo "✓ Flatpak repositories configured"  # Flathub available
            echo "  • Install declared Flatpak applications after the switch to avoid service timeouts"
    else  # Flatpak not available
        echo "• Flatpak not available - skipped repository configuration"
    fi
    echo ""
        # Teach user how to manage packages declaratively
    echo "Package Management (Declarative):"
        echo "  • System packages: Edit /etc/nixos/configuration.nix"  # System-wide packages
    echo "  • User packages: Edit ~/.config/home-manager/home.nix"  # User environment packages
        echo "  • Apply changes: nixos-rebuild switch / home-manager switch"  # Deployment commands
    echo "  • NO MORE: nix-env -i (use declarative configs instead)"  # Discourage imperative usage
        echo ""
    # Show rollback options for safety
    echo "Rollback (if needed):"
        echo "  • System:  sudo nixos-rebuild --rollback"  # Revert to previous generation
    echo "  • User:    home-manager --rollback"  # Revert user environment
        echo "  • Boot:    Select previous generation in boot menu"  # Boot-time rollback
    echo ""
        # Show removed packages file if applicable
    if [[ -n "$IMPERATIVE_PKGS" ]]; then  # Packages were removed
        echo "Removed packages list: $removed_pkgs_file"  # Where list was saved
            echo "Add them to configs if you want them back"  # Recovery instructions
        echo ""
    fi

    # Show config backup location if applicable
    if [[ -n "${LATEST_CONFIG_BACKUP_DIR:-}" ]]; then  # Configs were backed up
        echo "Previous configuration backups archived at: ${LATEST_CONFIG_BACKUP_DIR}"  # Backup location
            echo "Restore with: cp -a \"${LATEST_CONFIG_BACKUP_DIR}/.\" \"$HOME/\""  # Restore command
        echo ""
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Deployment complete - system is now fully declarative
    # All imperative packages removed, configs applied
    mark_step_complete "$phase_name"  # Update state.json with completion marker
        print_success "Phase 5: Declarative Deployment - COMPLETE"
    echo ""
}

# Execute phase function (called when this script is sourced by main orchestrator)
phase_05_declarative_deployment  # Run all deployment operations
