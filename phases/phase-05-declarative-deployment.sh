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
    local detected_ram="${TOTAL_RAM_GB:-}"
    local ram_value

    if [[ "$detected_ram" =~ ^[0-9]+$ ]]; then
        ram_value="$detected_ram"
    else
        ram_value=0
    fi

    # No extra swap needed on well-provisioned systems
    if (( ram_value >= 16 )); then
        return 0
    fi

    local swap_total_kb
    swap_total_kb=$(awk '/^SwapTotal:/ { print $2 }' /proc/meminfo 2>/dev/null || echo "0")
    local swap_total_gb=$(( swap_total_kb / 1024 / 1024 ))

    local min_swap_gb=4
    if (( swap_total_gb >= min_swap_gb )); then
        print_info "Detected ${swap_total_gb}GB swap space — temporary swap guardrail not required."
        return 0
    fi

    local swapfile_path="/swapfile.nixos-quick-deploy"
    if [[ -e "$swapfile_path" ]]; then
        print_warning "Temporary swapfile already present at $swapfile_path; skipping automatic provisioning."
        return 0
    fi

    local additional_swap_gb=$(( min_swap_gb - swap_total_gb ))
    if (( additional_swap_gb < 1 )); then
        additional_swap_gb=1
    fi

    print_info "Provisioning temporary ${additional_swap_gb}GB swapfile at $swapfile_path (RAM: ${ram_value}GB, existing swap: ${swap_total_gb}GB)."

    local block_count=$(( additional_swap_gb * 1024 ))
    if ! sudo dd if=/dev/zero of="$swapfile_path" bs=1M count="$block_count" status=none; then
        print_warning "Failed to allocate temporary swapfile at $swapfile_path. Continuing without additional swap."
        sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true
        return 0
    fi

    if ! sudo chmod 600 "$swapfile_path"; then
        print_warning "Unable to set secure permissions on $swapfile_path. Removing temporary swapfile."
        sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true
        return 0
    fi

    if ! sudo mkswap "$swapfile_path" >/dev/null 2>&1; then
        print_warning "mkswap failed for $swapfile_path. Removing temporary swapfile."
        sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true
        return 0
    fi

    if sudo swapon "$swapfile_path"; then
        print_success "Temporary swapfile enabled: $swapfile_path (${additional_swap_gb}GB)."
        print_info "It will be removed automatically during finalization when permanent swap is detected. Manual cleanup: sudo swapoff $swapfile_path && sudo rm -f $swapfile_path"
        TEMP_SWAP_CREATED=true
        TEMP_SWAP_FILE="$swapfile_path"
        TEMP_SWAP_SIZE_GB="$additional_swap_gb"
        export TEMP_SWAP_CREATED TEMP_SWAP_FILE TEMP_SWAP_SIZE_GB
    else
        print_warning "Failed to activate temporary swapfile at $swapfile_path."
        sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true
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

    local phase_name="deploy_configurations"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 5 already completed (skipping)"
        return 0
    fi

    print_section "Phase 5/8: Declarative Deployment"
    echo ""

    if ! ensure_flake_workspace; then
        print_error "Unable to prepare Home Manager flake workspace at $HM_CONFIG_DIR"
        print_info "Phase 3 (Configuration Generation) should establish this directory."
        print_info "Re-run that phase or restore your dotfiles before continuing."
        echo ""
        return 1
    fi

    if ! verify_home_manager_flake_ready; then
        echo ""
        return 1
    fi

    # ========================================================================
    # Step 6.1: Check for nix-env Packages
    # ========================================================================
    print_info "Checking for nix-env packages (imperative management)..."
    local IMPERATIVE_PKGS
    IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null || true)

    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
        print_warning "These MUST be removed to switch to declarative management"
        print_info "They will conflict with packages in configuration.nix/home.nix"
    else
        print_success "No nix-env packages found - ready for declarative management"
    fi

    echo ""

    # ========================================================================
    # Step 6.2: Final Deployment Confirmation
    # ========================================================================
    print_section "Ready to Deploy Declarative Configuration"
    echo ""
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

    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        echo "Packages to be removed:"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
        echo "To keep these packages, add them to configuration.nix or home.nix"
    fi

    echo ""

    if ! confirm "Proceed with deployment (removes nix-env packages, applies declarative config)?" "y"; then
        print_warning "Deployment cancelled"
        print_info "To apply later:"
        print_info "  1. Manually remove nix-env packages: nix-env -e '.*'"
        print_info "  2. Apply system config: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        print_info "  3. Apply user config: home-manager switch --flake $HM_CONFIG_DIR"
        echo ""
        return 0
    fi

    echo ""

    # ========================================================================
    # Step 6.3: Remove ALL nix-env Packages
    # ========================================================================
    # This is REQUIRED for declarative management to work properly
    # nix-env packages persist and conflict with declarative packages
    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        print_section "Removing nix-env Packages"
        print_info "Switching to declarative package management..."
        echo ""

        # Save package list for user reference
        local removed_pkgs_file="$STATE_DIR/removed-nix-env-packages-$(date +%s).txt"
        if safe_mkdir "$STATE_DIR"; then
            echo "$IMPERATIVE_PKGS" > "$removed_pkgs_file"
            print_info "Package list saved to: $removed_pkgs_file"
            print_info "Add these to configuration.nix or home.nix if you want them back"
        else
            print_warning "Could not save package list"
        fi
        echo ""

        # Remove all nix-env packages
        print_info "Removing ALL nix-env packages..."
        if nix-env -e '.*' 2>&1 | tee /tmp/nix-env-cleanup.log; then
            print_success "✓ All nix-env packages removed successfully"
        else
            # Fallback: Remove packages one by one
            print_warning "Batch removal failed, trying individual removal..."
            while IFS= read -r pkg; do
                local pkg_name
                pkg_name=$(echo "$pkg" | awk '{print $1}')
                if [[ -n "$pkg_name" ]]; then
                    print_info "  Removing: $pkg_name"
                    if nix-env -e "$pkg_name" 2>/dev/null; then
                        print_success "    ✓ Removed"
                    else
                        print_warning "    ⚠ Could not remove (may already be gone)"
                    fi
                fi
            done <<< "$IMPERATIVE_PKGS"
        fi

        # Verify all removed
        local REMAINING
        REMAINING=$(nix-env -q 2>/dev/null || true)
        if [[ -n "$REMAINING" ]]; then
            print_warning "Some packages remain in nix-env:"
            echo "$REMAINING" | sed 's/^/    /'
            print_warning "These may cause conflicts - remove manually: nix-env -e <package>"
        else
            print_success "✓ All nix-env packages removed"
            print_success "✓ Ready for declarative management"
        fi

        echo ""
    fi

    # ========================================================================
    # Step 6.4: Update Flake Inputs (System + Home Manager)
    # ========================================================================
    print_section "Updating Flake Inputs"
    print_info "Ensuring all configurations use the pinned revisions before switching..."
    echo ""

    local flake_update_output=""
    local flake_update_status=0

    if ! flake_update_output=$(cd "$HM_CONFIG_DIR" && nix flake update 2>&1); then
        flake_update_status=$?
    fi

    if (( flake_update_status == 0 )); then
        if [[ -n "$flake_update_output" ]]; then
            echo "$flake_update_output"
        fi
        print_success "✓ Flake inputs updated"
    else
        if [[ -n "$flake_update_output" ]]; then
            echo "$flake_update_output" | sed 's/^/  /'
        fi
        print_warning "⚠ Flake update had issues (continuing anyway)"
    fi

    echo ""

    # ========================================================================
    # Step 6.5: Apply NixOS System Configuration
    # ========================================================================
    ensure_low_memory_swap

    print_section "Applying NixOS System Configuration"
    local target_host=$(hostname)

    local -a nixos_rebuild_opts=()
    if declare -F compose_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t nixos_rebuild_opts < <(compose_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
    fi

    local rebuild_display="sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""
    if (( ${#nixos_rebuild_opts[@]} > 0 )); then
        rebuild_display+=" ${nixos_rebuild_opts[*]}"
    fi

    print_info "Running: $rebuild_display"
    print_info "This applies the declarative system configuration..."
    echo ""

    if declare -F describe_binary_cache_usage >/dev/null 2>&1; then
        describe_binary_cache_usage "nixos-rebuild switch"
    fi

    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" 2>&1 | tee /tmp/nixos-rebuild.log; then
        print_success "✓ NixOS system configuration applied!"
        print_success "✓ System packages now managed declaratively"
        echo ""
    else
        local exit_code=${PIPESTATUS[0]}
        print_error "nixos-rebuild failed (exit code: $exit_code)"
        if [[ ! -d "$HM_CONFIG_DIR" ]]; then
            print_error "Home Manager flake directory is missing: $HM_CONFIG_DIR"
            print_info "Restore the directory or rerun Phase 3 before retrying."
        elif [[ ! -f "$HM_CONFIG_DIR/flake.nix" ]]; then
            print_error "flake.nix is missing from: $HM_CONFIG_DIR"
            print_info "Regenerate the configuration with Phase 3 or restore from backup."
        fi
        print_info "Log: /tmp/nixos-rebuild.log"
        print_info "Rollback: sudo nixos-rebuild --rollback"
        echo ""
        return 1
    fi

    # ========================================================================
    # Step 6.6: Prepare Home Manager Targets
    # ========================================================================
    if ! prepare_home_manager_targets "pre-switch"; then
        print_warning "Encountered issues while archiving existing configuration files. Review the messages above before continuing."
    fi
    echo ""

    # ========================================================================
    # Step 6.7: Apply Home Manager Configuration
    # ========================================================================
    print_section "Applying Home Manager Configuration"
    print_info "This configures your user environment declaratively..."
    echo ""

    # Ensure supporting scripts referenced by the flake are available
    local p10k_source="$BOOTSTRAP_SCRIPT_DIR/scripts/p10k-setup-wizard.sh"
    local p10k_destination="$HM_CONFIG_DIR/p10k-setup-wizard.sh"

    print_info "Ensuring Powerlevel10k setup wizard is available for Home Manager"
    if [[ -f "$p10k_source" ]]; then
        if [[ ! -d "$HM_CONFIG_DIR" ]]; then
            if mkdir -p "$HM_CONFIG_DIR"; then
                print_info "  Created Home Manager config directory at $HM_CONFIG_DIR"
            else
                print_warning "  ⚠ Unable to create $HM_CONFIG_DIR (continuing, but Home Manager may fail)"
            fi
        fi

        if cp "$p10k_source" "$p10k_destination"; then
            chmod +x "$p10k_destination" 2>/dev/null || true
            print_success "  ✓ Synced p10k-setup-wizard.sh to Home Manager flake"
        else
            print_warning "  ⚠ Failed to sync p10k-setup-wizard.sh (continuing, but Home Manager may fail)"
        fi
    else
        print_warning "  ⚠ Source p10k-setup-wizard.sh not found at $p10k_source"
    fi
    echo ""

    # Determine home-manager command
    local hm_cmd
    if command -v home-manager &>/dev/null; then
        hm_cmd="home-manager"
        print_info "Using: home-manager switch --flake $HM_CONFIG_DIR"
    else
        hm_cmd="nix run github:nix-community/home-manager#home-manager --"
        print_info "Using: nix run github:nix-community/home-manager -- switch --flake $HM_CONFIG_DIR"
    fi
    echo ""

    # Apply home-manager
    if $hm_cmd switch --flake "$HM_CONFIG_DIR" 2>&1 | tee /tmp/home-manager-switch.log; then
        print_success "✓ Home manager configuration applied!"
        print_success "✓ User packages now managed declaratively"
        echo ""
    else
        local hm_exit_code=${PIPESTATUS[0]}
        print_error "home-manager switch failed (exit code: $hm_exit_code)"
        print_info "Log: /tmp/home-manager-switch.log"
        print_info "Rollback: home-manager --rollback"
        echo ""
        print_warning "Common causes:"
        print_info "  • Syntax errors in home.nix"
        print_info "  • Network issues downloading packages"
        print_info "  • Package conflicts (check log)"
        echo ""
        return 1
    fi

    # ========================================================================
    # Step 6.8: Configure Flatpak Remotes (if available)
    # ========================================================================
    local flatpak_configured=false
    if command -v flatpak &>/dev/null; then
        flatpak_configured=true
        print_section "Configuring Flatpak"

        # Add Flathub if not present
        if ! flatpak remotes --user 2>/dev/null | grep -q "^flathub"; then
            print_info "Adding Flathub repository..."
            if flatpak remote-add --user --if-not-exists flathub \
                https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null; then
                print_success "✓ Flathub repository added"
            else
                print_info "Trying alternate Flathub URL..."
                flatpak remote-add --user --if-not-exists flathub \
                    https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null || \
                    print_warning "⚠ Could not add Flathub (add manually if needed)"
            fi
        else
            print_success "✓ Flathub repository already configured"
        fi

        # Add Flathub Beta (optional)
        if ! flatpak remotes --user 2>/dev/null | grep -q "^flathub-beta"; then
            print_info "Adding Flathub Beta repository (optional)..."
            flatpak remote-add --user --if-not-exists flathub-beta \
                https://flathub.org/beta-repo/flathub-beta.flatpakrepo 2>/dev/null && \
                print_success "✓ Flathub Beta added" || \
                print_info "  Flathub Beta not added (not required)"
        fi

        print_info "Flatpak application installs will run in Phase 6 to avoid blocking systemd during switch"
        echo ""
    fi

    # ========================================================================
    # Deployment Summary
    # ========================================================================
    print_section "Deployment Complete - Now Fully Declarative"
    echo "✓ All nix-env packages removed"
    echo "✓ NixOS system configuration applied"
    echo "✓ Home manager user environment configured"
    echo "✓ All packages now managed declaratively"
    if [[ "$flatpak_configured" == true ]]; then
        echo "✓ Flatpak repositories configured"
        echo "  • Install declared Flatpak applications after the switch to avoid service timeouts"
    else
        echo "• Flatpak not available - skipped repository configuration"
    fi
    echo ""
    echo "Package Management (Declarative):"
    echo "  • System packages: Edit /etc/nixos/configuration.nix"
    echo "  • User packages: Edit ~/.config/home-manager/home.nix"
    echo "  • Apply changes: nixos-rebuild switch / home-manager switch"
    echo "  • NO MORE: nix-env -i (use declarative configs instead)"
    echo ""
    echo "Rollback (if needed):"
    echo "  • System:  sudo nixos-rebuild --rollback"
    echo "  • User:    home-manager --rollback"
    echo "  • Boot:    Select previous generation in boot menu"
    echo ""
    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        echo "Removed packages list: $removed_pkgs_file"
        echo "Add them to configs if you want them back"
        echo ""
    fi

    if [[ -n "${LATEST_CONFIG_BACKUP_DIR:-}" ]]; then
        echo "Previous configuration backups archived at: ${LATEST_CONFIG_BACKUP_DIR}"
        echo "Restore with: cp -a \"${LATEST_CONFIG_BACKUP_DIR}/.\" \"$HOME/\""
        echo ""
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 5: Declarative Deployment - COMPLETE"
    echo ""
}

# Execute phase
phase_05_declarative_deployment
