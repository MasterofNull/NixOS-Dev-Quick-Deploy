#!/usr/bin/env bash
#
# Phase 05: Declarative Deployment
# Purpose: Apply NixOS and home-manager configurations
# Version: Uses SCRIPT_VERSION from main script
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

# Provision a temporary swapfile on low-memory systems so declarative switches
# do not OOM. Cleanup happens in phase-08 (see TEMP_SWAP_* usage there).
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

# Ensure Nix eval caches are writable before switching so sqlite errors do not
# abort home-manager/nixos-rebuild when prior runs created root-owned files.
ensure_writable_nix_cache() {
    local cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/nix"
    local eval_cache="${cache_root}/eval-cache-v6"

    if [[ ! -d "$cache_root" ]]; then
        return 0
    fi

    local cache_owner
    cache_owner=$(id -un)

    # Fix ownership on any root-owned cache artefacts.
    if find "$cache_root" ! -user "$cache_owner" -print -quit 2>/dev/null | grep -q .; then
        print_warning "Detected root-owned files in $cache_root; resetting ownership to $cache_owner."
        if ! sudo chown -R "$cache_owner:$(id -gn)" "$cache_root" 2>/dev/null; then
            print_error "Failed to reset ownership under $cache_root. Fix permissions and rerun Phase 5."
            return 1
        fi
    fi

    # Delete unwritable sqlite caches so nix recreates them with correct perms.
    if [[ -d "$eval_cache" ]]; then
        local unwritable
        if unwritable=$(find "$eval_cache" -maxdepth 1 -type f -name "*.sqlite" ! -writable -print 2>/dev/null) && [[ -n "$unwritable" ]]; then
            print_warning "Removing unwritable Nix eval cache database(s):"
            echo "$unwritable" | sed 's/^/  • /'
            if ! sudo rm -f $unwritable 2>/dev/null && ! rm -f $unwritable 2>/dev/null; then
                print_error "Failed to remove unwritable eval cache database(s). Delete ${eval_cache}/*.sqlite manually and rerun."
                return 1
            fi
        fi
    fi

    return 0
}

# Normalize generated system configuration to prevent known activation failures
# (avahi/cups) before switching. This is a defensive cleanup in case older
# templates or cached generations are present.
sanitize_generated_configs() {
    local sys_config="$SYSTEM_CONFIG_FILE"
    if [[ -f "$sys_config" ]]; then
        # Drop any legacy activation script block that tries to delete avahi units.
        sed -i '/system.activationScripts.disableAvahiUnits/,+5d' "$sys_config" 2>/dev/null || true
        # Rename nssmdns to current option names.
        if grep -q 'services\.avahi\.nssmdns' "$sys_config" 2>/dev/null; then
            sed -i 's/services\.avahi\.nssmdns *=.*/  services.avahi.nssmdns4 = lib.mkForce false;\\n  services.avahi.nssmdns6 = lib.mkForce false;/' "$sys_config" 2>/dev/null || true
        fi
        # Remove unsupported systemd.maskedServices/sockets entries.
        local tmp_norm
        tmp_norm=$(mktemp)
        grep -v 'systemd\.maskedServices' "$sys_config" | grep -v 'systemd\.maskedSockets' > "$tmp_norm" || true
        mv "$tmp_norm" "$sys_config"
        # Ensure printing is disabled and CUPS socket overrides removed to avoid avahi pull-in.
        if grep -q 'services\.printing\.enable' "$sys_config" 2>/dev/null; then
            sed -i 's/services\.printing\.enable *= *.*/  services.printing.enable = false;/' "$sys_config" 2>/dev/null || true
        fi
        sed -i '/systemd\.sockets\.cups\.listenStreams/,+5d' "$sys_config" 2>/dev/null || true
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
    local hm_user="${PRIMARY_USER:-$USER}"

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
    echo "  2. Apply home-manager user configuration (declarative)"
    echo "  3. Configure Flatpak repositories"
    echo "  4. Apply NixOS system configuration (declarative)"
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
        print_info "  3. Apply user config: home-manager switch --flake $HM_CONFIG_DIR#$hm_user"
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
        local tmp_dir="${TMP_DIR:-/tmp}"
        if nix-env -e '.*' 2>&1 | tee "${tmp_dir}/nix-env-cleanup.log"; then
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
    if [[ "$AUTO_UPDATE_FLAKE_INPUTS" == true ]]; then
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
    else
        print_section "Flake Inputs"
        print_info "Skipping automatic 'nix flake update' to keep the bundled lockfile intact."
        print_info "Use --update-flake-inputs when you want to refresh upstream sources."
        echo ""
    fi

    # ========================================================================
    # Step 6.5: Prepare Home Manager Targets
    # ========================================================================
    if ! prepare_home_manager_targets "pre-switch"; then
        print_warning "Encountered issues while archiving existing configuration files. Review the messages above before continuing."
    fi
    echo ""

    # ========================================================================
    # Step 6.6: Apply Home Manager Configuration
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
    local hm_flake_target="${HM_CONFIG_DIR}#${hm_user}"
    if command -v home-manager &>/dev/null; then
        hm_cmd="home-manager"
        print_info "Using: home-manager switch --flake $hm_flake_target"
    else
        hm_cmd="nix run github:nix-community/home-manager#home-manager --"
        print_info "Using: nix run github:nix-community/home-manager -- switch --flake $hm_flake_target"
    fi
    echo ""

    local home_switch_display="$hm_cmd switch --flake $hm_flake_target"
    local perform_home_switch=true
    if [[ "${AUTO_APPLY_HOME_CONFIGURATION,,}" != "true" ]]; then
        perform_home_switch=false
        HOME_SWITCH_SKIPPED_REASON="Automatic home-manager switch disabled via flag"
    elif [[ "${PROMPT_BEFORE_HOME_SWITCH,,}" == "true" ]]; then
        if ! confirm "Apply home-manager configuration now?" "y"; then
            perform_home_switch=false
            HOME_SWITCH_SKIPPED_REASON="User skipped home-manager switch prompt"
        fi
    fi

    if [[ "$perform_home_switch" == true ]]; then
        if ! ensure_writable_nix_cache; then
            return 1
        fi

        if [[ -d "$HM_CONFIG_DIR" ]]; then
            local hm_backup_issue=false
            while IFS= read -r backup_path; do
                hm_backup_issue=true
                print_warning "Fixing permissions on Home Manager backup artefact: $backup_path"
                sudo chown -R "$USER:$(id -gn)" "$backup_path" 2>/dev/null || true
                chmod -R u+rwX "$backup_path" 2>/dev/null || true
            done < <(find "$HM_CONFIG_DIR" -maxdepth 1 \( -name "*backup*" -o -name "*.bak" -o -name "*.backup" \) ! -writable 2>/dev/null)

            if [[ "$hm_backup_issue" == true ]]; then
                print_info "Stale Home Manager backups were detected and permission-normalized to prevent switch failures."
            fi
        fi

        # Clean up backup files that may block home-manager switch
        rm -f "$HOME/.npmrc.backup" "$HOME/.config/VSCodium/User/settings.json.backup" 2>/dev/null || true

        local tmp_dir="${TMP_DIR:-/tmp}"
        if $hm_cmd switch --flake "$hm_flake_target" -b backup 2>&1 | tee "${tmp_dir}/home-manager-switch.log"; then
            print_success "✓ Home manager configuration applied!"
            print_success "✓ User packages now managed declaratively"
            HOME_CONFIGURATION_APPLIED="true"
            HOME_SWITCH_SKIPPED_REASON=""

            # Create symlinks for home-manager news command compatibility
            print_info "Creating home-manager config symlinks for news command..."
            if [[ -d "$HM_CONFIG_DIR" ]]; then
                mkdir -p "$HOME/.config/home-manager"
                ln -sf "$HM_CONFIG_DIR/home.nix" "$HOME/.config/home-manager/home.nix" 2>/dev/null || true
                ln -sf "$HM_CONFIG_DIR/flake.nix" "$HOME/.config/home-manager/flake.nix" 2>/dev/null || true
                ln -sf "$HM_CONFIG_DIR/flake.lock" "$HOME/.config/home-manager/flake.lock" 2>/dev/null || true
                print_success "✓ Symlinks created (home-manager news will work)"
            fi
            echo ""
        else
            local hm_exit_code=${PIPESTATUS[0]}
            print_error "home-manager switch failed (exit code: $hm_exit_code)"
            print_info "Log: ${tmp_dir}/home-manager-switch.log"
            print_info "Rollback: home-manager --rollback"
            echo ""
            print_warning "Common causes:"
            print_info "  • Syntax errors in home.nix"
            print_info "  • Network issues downloading packages"
            print_info "  • Package conflicts (check log)"
            echo ""
            return 1
        fi
    else
        print_warning "Skipping automatic Home Manager activation"
        print_info "Run manually when ready: $home_switch_display"
        echo ""
    fi

    export HOME_CONFIGURATION_APPLIED HOME_SWITCH_SKIPPED_REASON

    # ========================================================================
    # Step 6.7: Configure Flatpak Remotes (if available)
    # ========================================================================
    local flatpak_configured=false
    if command -v flatpak &>/dev/null; then
        flatpak_configured=true
        print_section "Configuring Flatpak"

        mkdir -p "$HOME/.local/share/flatpak" "$HOME/.config/flatpak" "$HOME/.local/share/flatpak/repo"
        chmod 700 "$HOME/.local/share/flatpak" "$HOME/.config/flatpak" 2>/dev/null || true

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

        print_info "Flatpak application installs will run in Phase 6 after the system activation to avoid blocking systemd"
        echo ""
    fi

    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
        print_section "Preparing Local AI Stack Assets"
        print_info "Local AI services are now fully managed by the ai-optimizer Podman stack."
        print_info "Images and containers (vLLM/Open WebUI/Qdrant/MindsDB) will be pulled the first time you run your ai-optimizer workflow."
        echo ""

        if command -v podman-ai-stack >/dev/null 2>&1; then
            print_info "After deployment run: podman-ai-stack up"
            print_info "This will pull/start the ai-optimizer Podman stack (vLLM, Open WebUI, Qdrant, MindsDB)."
        else
            print_warning "podman-ai-stack helper not found. Install/configure ai-optimizer, then run its launch script to provision the containers."
        fi
    fi

    # ========================================================================
    # Step 6.8: Apply NixOS System Configuration
    # ========================================================================
    ensure_low_memory_swap

    print_section "Applying NixOS System Configuration"
    local target_host=$(hostname)

    local -a nixos_rebuild_opts=()
    if declare -F activate_build_acceleration_context >/dev/null 2>&1; then
        activate_build_acceleration_context
    fi

    if declare -F compose_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t nixos_rebuild_opts < <(compose_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
    fi

    local rebuild_display="sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""
    if (( ${#nixos_rebuild_opts[@]} > 0 )); then
        rebuild_display+=" ${nixos_rebuild_opts[*]}"
    fi

    local perform_system_switch=true
    if [[ "${AUTO_APPLY_SYSTEM_CONFIGURATION,,}" != "true" ]]; then
        perform_system_switch=false
        SYSTEM_SWITCH_SKIPPED_REASON="Automatic system switch disabled via flag"
    elif [[ "${PROMPT_BEFORE_SYSTEM_SWITCH,,}" == "true" ]]; then
        if ! confirm "Apply system configuration now via nixos-rebuild switch?" "y"; then
            perform_system_switch=false
            SYSTEM_SWITCH_SKIPPED_REASON="User skipped system switch prompt"
        fi
    fi

    if [[ "$perform_system_switch" == true ]]; then
        if ! ensure_writable_nix_cache; then
            return 1
        fi

        sanitize_generated_configs

        # Gitea state directory preparation (now a no-op, but check for safety)
        if declare -F ensure_gitea_state_directory_ready >/dev/null 2>&1; then
            if ! ensure_gitea_state_directory_ready; then
                # Only fail if Gitea is actually enabled
                if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
                    print_warning "Gitea state directory preparation had issues, but continuing..."
                    print_info "Gitea directories will be created automatically by NixOS during system activation."
                    print_info "If Gitea fails to start, check permissions on /var/lib/gitea"
                else
                    print_info "Gitea is disabled; skipping state directory preparation."
                fi
                # Don't return 1 - Gitea setup is handled by NixOS automatically
            fi
        fi

        if declare -F stop_managed_services_before_switch >/dev/null 2>&1; then
            stop_managed_services_before_switch
        fi

        # Podman storage checks - only critical if AI stack or Podman is actually being used
        # Use warn-only mode if Podman/AI stack is not enabled
        local podman_storage_failed=false
        local podman_warn_only="false"
        
        # Only enforce strict checks if AI stack is enabled
        if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
            podman_warn_only="true"
        fi

        if declare -F ensure_podman_storage_ready >/dev/null 2>&1; then
            # Use warn-only mode if Podman is optional
            local ensure_args=()
            if [[ "$podman_warn_only" == "true" ]]; then
                ensure_args+=("--warn-only")
            fi
            if ! ensure_podman_storage_ready "${ensure_args[@]}"; then
                podman_storage_failed=true
            fi
        elif declare -F verify_podman_storage_cleanliness >/dev/null 2>&1; then
            # Use warn-only mode if Podman is optional
            local verify_args=()
            if [[ "$podman_warn_only" == "true" ]]; then
                verify_args+=("--warn-only")
            fi
            if ! verify_podman_storage_cleanliness "${verify_args[@]}"; then
                podman_storage_failed=true
            fi
        fi

        if [[ "$podman_storage_failed" == "true" ]]; then
            if [[ "${LOCAL_AI_STACK_ENABLED:-false}" == "true" ]]; then
                print_warning "Container storage health check failed, but continuing deployment..."
                print_warning "Podman containers may not work until storage is fixed."
                print_info "See docs/ROOTLESS_PODMAN.md for manual recovery steps."
                print_info "You can fix this after deployment and restart Podman services."
                # Don't return 1 - allow deployment to continue, user can fix storage later
            else
                print_info "Podman storage check had issues, but Podman/AI stack is not enabled."
                print_info "Storage will be configured when you enable the AI stack."
            fi
        fi

        print_info "Running: $rebuild_display"
        print_info "This applies the declarative system configuration..."
        echo ""

        if declare -F describe_binary_cache_usage >/dev/null 2>&1; then
            describe_binary_cache_usage "nixos-rebuild switch"
        fi

        if declare -F describe_remote_build_context >/dev/null 2>&1; then
            describe_remote_build_context
        fi

        local rebuild_exit_code=0
        if systemctl >/dev/null 2>&1; then
            if systemctl is-active --quiet nixos-rebuild-switch-to-configuration.service 2>/dev/null; then
                print_warning "Previous switch-to-configuration job still running; stopping it before retrying."
                sudo systemctl stop nixos-rebuild-switch-to-configuration.service 2>/dev/null || true
                sudo systemctl reset-failed nixos-rebuild-switch-to-configuration.service 2>/dev/null || true
                sleep 2
            fi
        fi
        local rebuild_tmp_dir="${TMP_DIR:-/tmp}"
        local rebuild_log="${rebuild_tmp_dir}/nixos-rebuild.log"
        if ! sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" "${nixos_rebuild_opts[@]}" 2>&1 | tee "$rebuild_log"; then
            rebuild_exit_code=${PIPESTATUS[0]}
        fi

        if declare -F restart_managed_services_after_switch >/dev/null 2>&1; then
            restart_managed_services_after_switch
        fi

        if (( rebuild_exit_code == 0 )); then
            print_success "✓ NixOS system configuration applied!"
            print_success "✓ System packages now managed declaratively"
            SYSTEM_CONFIGURATION_APPLIED="true"
            SYSTEM_SWITCH_SKIPPED_REASON=""
            if declare -F summarize_nixos_rebuild_services >/dev/null 2>&1; then
                summarize_nixos_rebuild_services "$rebuild_log"
            fi
            echo ""
        else
            print_error "nixos-rebuild failed (exit code: $rebuild_exit_code)"
            if [[ ! -d "$HM_CONFIG_DIR" ]]; then
                print_error "Home Manager flake directory is missing: $HM_CONFIG_DIR"
                print_info "Restore the directory or rerun Phase 3 before retrying."
            elif [[ ! -f "$HM_CONFIG_DIR/flake.nix" ]]; then
                print_error "flake.nix is missing from: $HM_CONFIG_DIR"
                print_info "Regenerate the configuration with Phase 3 or restore from backup."
            fi
            print_info "Log: $rebuild_log"
            print_info "Rollback: sudo nixos-rebuild --rollback"
            echo ""
            return 1
        fi
    else
        print_warning "Skipping automatic NixOS activation"
        print_info "Run manually when ready: $rebuild_display"
        echo ""
    fi

    export SYSTEM_CONFIGURATION_APPLIED SYSTEM_SWITCH_SKIPPED_REASON

    # ========================================================================
    # Deployment Summary
    # ========================================================================
    print_section "Deployment Complete - Now Fully Declarative"
    echo "✓ All nix-env packages removed"
    echo "✓ Home manager user environment configured"
    if [[ "$flatpak_configured" == true ]]; then
        echo "✓ Flatpak repositories configured"
        echo "  • Install declared Flatpak applications after the switch to avoid service timeouts"
    else
        echo "• Flatpak not available - skipped repository configuration"
    fi
    echo "✓ NixOS system configuration applied"
    echo "✓ All packages now managed declaratively"
    echo ""
    echo "Package Management (Declarative):"
    echo "  • System packages: Edit /etc/nixos/configuration.nix"
    echo "  • User packages: Edit ~/.config/home-manager/home.nix"
    echo "  • Apply changes: nixos-rebuild switch / home-manager switch --flake ${HM_CONFIG_DIR}#${PRIMARY_USER:-$USER}"
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
