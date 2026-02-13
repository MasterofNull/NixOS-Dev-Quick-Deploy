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

    local additional_swap_gb=$(( min_swap_gb - swap_total_gb ))
    if (( additional_swap_gb < 1 )); then
        additional_swap_gb=1
    fi

    print_info "Provisioning temporary ${additional_swap_gb}GB swapfile at $swapfile_path (RAM: ${ram_value}GB, existing swap: ${swap_total_gb}GB)."

    if ! sudo bash -c "umask 077; set -o noclobber; : > '$swapfile_path'" 2>/dev/null; then
        if [[ -e "$swapfile_path" ]]; then
            print_warning "Temporary swapfile already present at $swapfile_path; skipping automatic provisioning."
        else
            print_warning "Unable to create temporary swapfile at $swapfile_path. Continuing without additional swap."
        fi
        return 0
    fi

    local allocated=false
    if command -v fallocate >/dev/null 2>&1; then
        if sudo fallocate -l "${additional_swap_gb}G" "$swapfile_path" 2>/dev/null; then
            allocated=true
        else
            print_warning "fallocate failed for $swapfile_path; falling back to dd."
        fi
    fi

    if [[ "$allocated" != true ]]; then
        local block_count=$(( additional_swap_gb * 1024 ))
        if ! sudo dd if=/dev/zero of="$swapfile_path" bs=1M count="$block_count" status=none; then
            print_warning "Failed to allocate temporary swapfile at $swapfile_path. Continuing without additional swap."
            sudo rm -f "$swapfile_path" >/dev/null 2>&1 || true
            return 0
        fi
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
        local -a unwritable_files=()
        while IFS= read -r _f; do
            [[ -n "$_f" ]] && unwritable_files+=("$_f")
        done < <(find "$eval_cache" -maxdepth 1 -type f -name "*.sqlite" ! -writable -print 2>/dev/null)
        if (( ${#unwritable_files[@]} > 0 )); then
            print_warning "Removing unwritable Nix eval cache database(s):"
            printf '  • %s\n' "${unwritable_files[@]}"
            if ! sudo rm -f "${unwritable_files[@]}" 2>/dev/null && ! rm -f "${unwritable_files[@]}" 2>/dev/null; then
                print_error "Failed to remove unwritable eval cache database(s). Delete ${eval_cache}/*.sqlite manually and rerun."
                return 1
            fi
        fi
    fi

    # Also clean root-level fetcher cache DBs (e.g., fetcher-cache-v4.sqlite).
    local -a root_sqlite_files=()
    while IFS= read -r _f; do
        [[ -n "$_f" ]] && root_sqlite_files+=("$_f")
    done < <(find "$cache_root" -maxdepth 1 -type f -name "*.sqlite" ! -writable -print 2>/dev/null)
    if (( ${#root_sqlite_files[@]} > 0 )); then
        print_warning "Removing unwritable Nix fetcher cache database(s):"
        printf '  • %s\n' "${root_sqlite_files[@]}"
        if ! sudo rm -f "${root_sqlite_files[@]}" 2>/dev/null && ! rm -f "${root_sqlite_files[@]}" 2>/dev/null; then
            print_error "Failed to remove unwritable fetcher cache database(s). Delete ${cache_root}/*.sqlite manually and rerun."
            return 1
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
        if ! sed -i '/system.activationScripts.disableAvahiUnits/,+5d' "$sys_config" 2>/dev/null; then
            log_warning "sanitize: failed to remove disableAvahiUnits block from $sys_config"
        fi
        # Rename nssmdns to current option names.
        if grep -q 'services\.avahi\.nssmdns' "$sys_config" 2>/dev/null; then
            if ! sed -i 's/services\.avahi\.nssmdns *=.*/  services.avahi.nssmdns4 = lib.mkForce false;\\n  services.avahi.nssmdns6 = lib.mkForce false;/' "$sys_config" 2>/dev/null; then
                log_warning "sanitize: failed to rename nssmdns options in $sys_config"
            fi
        fi
        # Remove unsupported systemd.maskedServices/sockets entries.
        local tmp_norm
        tmp_norm=$(mktemp)
        # grep returns 1 when no lines match, which is expected here.
        grep -v 'systemd\.maskedServices' "$sys_config" | grep -v 'systemd\.maskedSockets' > "$tmp_norm" || true
        mv "$tmp_norm" "$sys_config"
        # Ensure printing is disabled and CUPS socket overrides removed to avoid avahi pull-in.
        if grep -q 'services\.printing\.enable' "$sys_config" 2>/dev/null; then
            if ! sed -i 's/services\.printing\.enable *= *.*/  services.printing.enable = false;/' "$sys_config" 2>/dev/null; then
                log_warning "sanitize: failed to disable printing in $sys_config"
            fi
        fi
        if ! sed -i '/systemd\.sockets\.cups\.listenStreams/,+5d' "$sys_config" 2>/dev/null; then
            log_warning "sanitize: failed to remove CUPS socket overrides from $sys_config"
        fi
    fi
}

phase_05_prepare_flake_workspace() {
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
}

phase_05_collect_imperative_packages() {
    print_info "Checking for nix-env packages (imperative management)..."
    PHASE_05_IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null || true)

    if [[ -n "$PHASE_05_IMPERATIVE_PKGS" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$PHASE_05_IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
        print_warning "These MUST be removed to switch to declarative management"
        print_info "They will conflict with packages in configuration.nix/home.nix"
    else
        print_success "No nix-env packages found - ready for declarative management"
    fi

    echo ""
}

phase_05_confirm_deployment() {
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

    if [[ -n "$PHASE_05_IMPERATIVE_PKGS" ]]; then
        echo "Packages to be removed:"
        echo "$PHASE_05_IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
        echo "To keep these packages, add them to configuration.nix or home.nix"
    fi

    echo ""

    if ! confirm "Proceed with deployment (removes nix-env packages, applies declarative config)?" "y"; then
        print_warning "Deployment cancelled"
        print_info "To apply later:"
        print_info "  1. Manually remove nix-env packages: nix-env -e '.*'"
        print_info "  2. Apply system config: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        print_info "  3. Apply user config: home-manager switch --flake $HM_CONFIG_DIR#$PHASE_05_HM_USER"
        echo ""
        PHASE_05_DEPLOYMENT_CANCELLED=true
        return 0
    fi

    PHASE_05_DEPLOYMENT_CANCELLED=false
    echo ""
}

phase_05_remove_imperative_packages() {
    if [[ -z "$PHASE_05_IMPERATIVE_PKGS" ]]; then
        return 0
    fi

    print_section "Removing nix-env Packages"
    print_info "Switching to declarative package management..."
    echo ""

    PHASE_05_REMOVED_PKGS_FILE="$STATE_DIR/removed-nix-env-packages-$(date +%s).txt"
    if safe_mkdir "$STATE_DIR"; then
        echo "$PHASE_05_IMPERATIVE_PKGS" > "$PHASE_05_REMOVED_PKGS_FILE"
        print_info "Package list saved to: $PHASE_05_REMOVED_PKGS_FILE"
        print_info "Add these to configuration.nix or home.nix if you want them back"
    else
        print_warning "Could not save package list"
    fi
    echo ""

    print_info "Removing ALL nix-env packages..."
    local tmp_dir="${TMP_DIR:-/tmp}"
    if nix-env -e '.*' > >(tee "${tmp_dir}/nix-env-cleanup.log") 2>&1; then
        print_success "✓ All nix-env packages removed successfully"
    else
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
        done <<< "$PHASE_05_IMPERATIVE_PKGS"
    fi

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
}

phase_05_update_flake_inputs() {
    if [[ "$AUTO_UPDATE_FLAKE_INPUTS" == true ]]; then
        print_section "Updating Flake Inputs"
        print_info "Ensuring all configurations use the pinned revisions before switching..."
        echo ""

        local -a flake_update_cmd=(nix flake update)
        if [[ "$(get_effective_max_jobs)" == "0" ]]; then
            print_warning "max-jobs=0 detected; forcing max-jobs=1 for nix flake update."
            flake_update_cmd=(env NIX_CONFIG="max-jobs = 1" nix flake update)
        fi

        local flake_update_output=""
        local flake_update_status=0

        if ! flake_update_output=$(cd "$HM_CONFIG_DIR" && "${flake_update_cmd[@]}" 2>&1); then
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
        return 0
    fi

    print_section "Flake Inputs"
    print_info "Skipping automatic 'nix flake update' to keep the bundled lockfile intact."
    print_info "Use --update-flake-inputs when you want to refresh upstream sources."
    echo ""
}

phase_05_ensure_flake_lock_complete() {
    # Validate that all inputs declared in flake.nix are present in flake.lock.
    # This catches issues like missing sops-nix or nix-vscode-extensions entries
    # in the bundled lock file, which cause silent failures during home-manager
    # switch (e.g., VSCodium marketplace extensions not installed).
    #
    # Unlike `nix flake update` (which refreshes ALL inputs), `nix flake lock`
    # only resolves inputs that are missing from the lock — existing pins are
    # preserved. This is safe to run even when --update-flake-inputs is NOT set.
    if declare -F validate_flake_lock_inputs >/dev/null 2>&1; then
        print_info "Verifying flake lock completeness..."
        if ! validate_flake_lock_inputs "$HM_CONFIG_DIR"; then
            print_warning "Some flake inputs could not be resolved — deployment will attempt to continue"
        fi
        echo ""
    fi
}

phase_05_prepare_home_manager_targets() {
    if ! prepare_home_manager_targets "pre-switch"; then
        print_warning "Encountered issues while archiving existing configuration files. Review the messages above before continuing."
    fi
    echo ""
}

phase_05_prepare_home_manager_switch() {
    print_section "Applying Home Manager Configuration"
    print_info "This configures your user environment declaratively..."
    echo ""

    if declare -F cleanup_preflight_profile_packages >/dev/null 2>&1; then
        print_info "Cleaning preflight nix profiles before Home Manager setup..."
        cleanup_preflight_profile_packages
        echo ""
    fi

    if declare -F aggressively_clean_home_manager_profile >/dev/null 2>&1; then
        if ! aggressively_clean_home_manager_profile; then
            print_error "Failed to clean home-manager profile before switch"
            print_error "This will cause file collisions (e.g., frameobject.h) and prevent deployment"
            print_info "Manual cleanup required before retrying Phase 5"
            return 1
        fi
    else
        local hm_profile="${HOME}/.local/state/nix/profiles/home-manager"
        if command -v nix >/dev/null 2>&1 && [[ -e "$hm_profile" ]]; then
            local python_check
            python_check=$(nix profile list --profile "$hm_profile" 2>/dev/null | grep -iE 'python3' || true)
            if [[ -n "$python_check" ]]; then
                print_error "home-manager profile still contains python3; this will collide with home-manager-path."
                print_info "Detected packages:"
                echo "$python_check" | sed 's/^/  /'
                print_info "Fix by removing them before retrying:"
                print_info "  nix profile list --profile $hm_profile"
                print_info "  nix profile remove <index> --profile $hm_profile"
                return 1
            fi
        fi
    fi

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

    PHASE_05_HM_FLAKE_TARGET="${HM_CONFIG_DIR}#${PHASE_05_HM_USER}"
    if command -v home-manager &>/dev/null; then
        PHASE_05_HM_CMD="home-manager"
        print_info "Using: home-manager switch --flake $PHASE_05_HM_FLAKE_TARGET"
    else
        PHASE_05_HM_CMD="nix run github:nix-community/home-manager#home-manager --"
        print_info "Using: nix run github:nix-community/home-manager -- switch --flake $PHASE_05_HM_FLAKE_TARGET"
    fi
    echo ""

    PHASE_05_HOME_SWITCH_DISPLAY="$PHASE_05_HM_CMD switch --flake $PHASE_05_HM_FLAKE_TARGET"
    PHASE_05_PERFORM_HOME_SWITCH=true
    if [[ "${AUTO_APPLY_HOME_CONFIGURATION,,}" != "true" ]]; then
        PHASE_05_PERFORM_HOME_SWITCH=false
        HOME_SWITCH_SKIPPED_REASON="Automatic home-manager switch disabled via flag"
    elif [[ "${PROMPT_BEFORE_HOME_SWITCH,,}" == "true" ]]; then
        if ! confirm "Apply home-manager configuration now?" "y"; then
            PHASE_05_PERFORM_HOME_SWITCH=false
            HOME_SWITCH_SKIPPED_REASON="User skipped home-manager switch prompt"
        fi
    fi
}

phase_05_capture_pre_switch_state() {
    local state_dir="${STATE_DIR:-$HOME/.cache/nixos-quick-deploy}"
    local hm_gen_file="${state_dir}/phase-05-hm-generation.txt"
    local prev_hm_gen=""

    mkdir -p "$state_dir" 2>/dev/null || true

    if [[ -n "${PHASE_05_HM_CMD:-}" ]]; then
        if prev_hm_gen=$($PHASE_05_HM_CMD generations 2>/dev/null | awk '/^[0-9]+/ {print $1}' | head -n 2 | tail -n 1); then
            if [[ -n "$prev_hm_gen" ]]; then
                echo "$prev_hm_gen" > "$hm_gen_file"
                print_info "Saved Home Manager generation: $prev_hm_gen"
                PHASE_05_PREV_HM_GEN="$prev_hm_gen"
                export PHASE_05_PREV_HM_GEN
                return 0
            fi
        fi
    fi

    print_warning "Unable to capture previous Home Manager generation"
    return 0
}

phase_05_run_home_manager_switch() {
    if [[ "$PHASE_05_PERFORM_HOME_SWITCH" != true ]]; then
        print_warning "Skipping automatic Home Manager activation"
        print_info "Run manually when ready: $PHASE_05_HOME_SWITCH_DISPLAY"
        echo ""
        export HOME_CONFIGURATION_APPLIED HOME_SWITCH_SKIPPED_REASON
        return 0
    fi

    if ! ensure_writable_nix_cache; then
        return 1
    fi

    if declare -F cleanup_preflight_profile_packages >/dev/null 2>&1; then
        print_info "Final cleanup of preflight nix-env packages to prevent file collisions..."
        cleanup_preflight_profile_packages
    fi

    if declare -F aggressively_clean_home_manager_profile >/dev/null 2>&1; then
        if ! aggressively_clean_home_manager_profile; then
            print_error "Home-manager profile cleanup failed immediately before switch"
            return "${ERR_PROFILE_CONFLICT:-24}"
        fi
    fi

    if [[ -d "$HM_CONFIG_DIR" ]]; then
        local hm_backup_issue=false
        while IFS= read -r backup_path; do
            hm_backup_issue=true
            print_warning "Fixing permissions on Home Manager backup artefact: $backup_path"
            if ! sudo chown -R "$USER:$(id -gn)" "$backup_path" 2>/dev/null; then
                log_warning "Failed to chown $backup_path"
            fi
            if ! chmod -R u+rwX "$backup_path" 2>/dev/null; then
                log_warning "Failed to chmod $backup_path"
            fi
        done < <(find "$HM_CONFIG_DIR" -maxdepth 1 \( -name "*backup*" -o -name "*.bak" -o -name "*.backup" \) ! -writable 2>/dev/null)

        if [[ "$hm_backup_issue" == true ]]; then
            print_info "Stale Home Manager backups were detected and permission-normalized to prevent switch failures."
        fi
    fi

    rm -f "$HOME/.npmrc.backup" "$HOME/.config/VSCodium/User/settings.json.backup" 2>/dev/null || true

    local tmp_dir="${TMP_DIR:-/tmp}"
    local hm_profile="${HOME}/.local/state/nix/profiles/home-manager"
    local -a hm_env=(env HOME_MANAGER_PROFILE="$hm_profile" NIX_PROFILE="$hm_profile")
    if [[ "$(get_effective_max_jobs)" == "0" ]]; then
        print_warning "max-jobs=0 disables local builds; forcing max-jobs=1 for home-manager switch."
        hm_env+=(NIX_CONFIG="max-jobs = 1")
    fi
    print_info "Using Home Manager profile: $hm_profile"
    if "${hm_env[@]}" $PHASE_05_HM_CMD switch --flake "$PHASE_05_HM_FLAKE_TARGET" -b backup \
        > >(tee "${tmp_dir}/home-manager-switch.log") 2>&1; then
        print_success "✓ Home manager configuration applied!"
        print_success "✓ User packages now managed declaratively"
        HOME_CONFIGURATION_APPLIED="true"
        HOME_SWITCH_SKIPPED_REASON=""

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
        local hm_exit_code=$?
        print_error "home-manager switch failed (exit code: $hm_exit_code)"
        print_info "Log: ${tmp_dir}/home-manager-switch.log"
        print_info "Rollback: home-manager generations (find N) then home-manager switch --generation N"
        echo ""
        print_warning "Common causes:"
        print_info "  • Syntax errors in home.nix"
        print_info "  • Network issues downloading packages"
        print_info "  • Package conflicts (check log)"
        echo ""
        return "${ERR_HOME_MANAGER:-41}"
    fi

    export HOME_CONFIGURATION_APPLIED HOME_SWITCH_SKIPPED_REASON
}

phase_05_configure_flatpak() {
    PHASE_05_FLATPAK_CONFIGURED=false
    if ! command -v flatpak &>/dev/null; then
        return 0
    fi

    PHASE_05_FLATPAK_CONFIGURED=true
    print_section "Configuring Flatpak"

    mkdir -p "$HOME/.local/share/flatpak" "$HOME/.config/flatpak" "$HOME/.local/share/flatpak/repo"
    chmod 700 "$HOME/.local/share/flatpak" "$HOME/.config/flatpak" 2>/dev/null || true

    if ! flatpak remotes --user 2>/dev/null | grep -q "^flathub"; then
        print_info "Adding Flathub repository..."
        if flatpak remote-add --user --if-not-exists flathub             https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null; then
            print_success "✓ Flathub repository added"
        else
            print_info "Trying alternate Flathub URL..."
            flatpak remote-add --user --if-not-exists flathub                 https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null ||                 print_warning "⚠ Could not add Flathub (add manually if needed)"
        fi
    else
        print_success "✓ Flathub repository already configured"
    fi

    if ! flatpak remotes --user 2>/dev/null | grep -q "^flathub-beta"; then
        print_info "Adding Flathub Beta repository (optional)..."
        flatpak remote-add --user --if-not-exists flathub-beta             https://flathub.org/beta-repo/flathub-beta.flatpakrepo 2>/dev/null &&             print_success "✓ Flathub Beta added" ||             print_info "  Flathub Beta not added (not required)"
    fi

    print_info "Flatpak application installs will run in Phase 6 after the system activation to avoid blocking systemd"
    echo ""
}

phase_05_print_ai_stack_notes() {
    if [[ "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        return 0
    fi

    local ai_stack_ns="${AI_STACK_NAMESPACE:-ai-stack}"
    print_section "Local AI Stack Configuration"
    print_info "AI services are deployed via K3s in Phase 9."
    print_info "Core services (llama-cpp, Qdrant, PostgreSQL, Grafana, etc.) run in the ${ai_stack_ns} namespace."
    echo ""
    print_info "After Phase 9 completes, verify with: kubectl get pods -n ${ai_stack_ns}"
}

phase_05_prepare_system_switch() {
    ensure_low_memory_swap

    print_section "Applying NixOS System Configuration"
    PHASE_05_TARGET_HOST=$(hostname)

    PHASE_05_NIXOS_REBUILD_OPTS=()
    if declare -F activate_build_acceleration_context >/dev/null 2>&1; then
        activate_build_acceleration_context
    fi

    if declare -F build_nixos_rebuild_options >/dev/null 2>&1; then
        mapfile -t PHASE_05_NIXOS_REBUILD_OPTS < <(build_nixos_rebuild_options "${USE_BINARY_CACHES:-true}")
    fi

    PHASE_05_REBUILD_DISPLAY="sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$PHASE_05_TARGET_HOST""
    if (( ${#PHASE_05_NIXOS_REBUILD_OPTS[@]} > 0 )); then
        PHASE_05_REBUILD_DISPLAY+=" ${PHASE_05_NIXOS_REBUILD_OPTS[*]}"
    fi

    PHASE_05_PERFORM_SYSTEM_SWITCH=true
    if [[ "${AUTO_APPLY_SYSTEM_CONFIGURATION,,}" != "true" ]]; then
        PHASE_05_PERFORM_SYSTEM_SWITCH=false
        SYSTEM_SWITCH_SKIPPED_REASON="Automatic system switch disabled via flag"
    elif [[ "${PROMPT_BEFORE_SYSTEM_SWITCH,,}" == "true" ]]; then
        if ! confirm "Apply system configuration now via nixos-rebuild switch?" "y"; then
            PHASE_05_PERFORM_SYSTEM_SWITCH=false
            SYSTEM_SWITCH_SKIPPED_REASON="User skipped system switch prompt"
        fi
    fi
}

phase_05_run_system_switch() {
    if [[ "$PHASE_05_PERFORM_SYSTEM_SWITCH" != true ]]; then
        print_warning "Skipping automatic NixOS activation"
        print_info "Run manually when ready: $PHASE_05_REBUILD_DISPLAY"
        echo ""
        export SYSTEM_CONFIGURATION_APPLIED SYSTEM_SWITCH_SKIPPED_REASON
        return 0
    fi

    if ! ensure_writable_nix_cache; then
        return 1
    fi

    sanitize_generated_configs

    if declare -F ensure_gitea_state_directory_ready >/dev/null 2>&1; then
        if ! ensure_gitea_state_directory_ready; then
            if [[ "${GITEA_ENABLE,,}" == "true" ]]; then
                print_warning "Gitea state directory preparation had issues, but continuing..."
                print_info "Gitea directories will be created automatically by NixOS during system activation."
                print_info "If Gitea fails to start, check permissions on /var/lib/gitea"
            else
                print_info "Gitea is disabled; skipping state directory preparation."
            fi
        fi
    fi

    if declare -F stop_managed_services_before_switch >/dev/null 2>&1; then
        stop_managed_services_before_switch
    fi

    print_info "Running: $PHASE_05_REBUILD_DISPLAY"
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
    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$PHASE_05_TARGET_HOST" "${PHASE_05_NIXOS_REBUILD_OPTS[@]}" \
        > >(tee "$rebuild_log") 2>&1; then
        rebuild_exit_code=0
    else
        rebuild_exit_code=$?
    fi
    if (( rebuild_exit_code != 0 )); then
        print_error "nixos-rebuild switch failed (exit code: $rebuild_exit_code)"
        print_info "Log: $rebuild_log"
        return "${ERR_NIXOS_REBUILD:-40}"
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
        return "${ERR_NIXOS_REBUILD:-40}"
    fi

    export SYSTEM_CONFIGURATION_APPLIED SYSTEM_SWITCH_SKIPPED_REASON
}

phase_05_print_summary() {
    print_section "Deployment Complete - Now Fully Declarative"
    echo "✓ All nix-env packages removed"
    echo "✓ Home manager user environment configured"
    if [[ "$PHASE_05_FLATPAK_CONFIGURED" == true ]]; then
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
    echo "  • User:    home-manager generations (find N) then home-manager switch --generation N"
    echo "  • Boot:    Select previous generation in boot menu"
    echo ""
    if [[ -n "$PHASE_05_IMPERATIVE_PKGS" ]]; then
        echo "Removed packages list: $PHASE_05_REMOVED_PKGS_FILE"
        echo "Add them to configs if you want them back"
        echo ""
    fi

    if [[ -n "${LATEST_CONFIG_BACKUP_DIR:-}" ]]; then
        echo "Previous configuration backups archived at: ${LATEST_CONFIG_BACKUP_DIR}"
        echo "Restore with: cp -a "${LATEST_CONFIG_BACKUP_DIR}/." "$HOME/""
        echo ""
    fi
}

phase_05_declarative_deployment() {
    local phase_name="deploy_configurations"
    PHASE_05_HM_USER="${PRIMARY_USER:-$USER}"

    if is_step_complete "$phase_name"; then
        print_info "Phase 5 already completed (skipping)"
        return 0
    fi

    print_section "Phase 5/8: Declarative Deployment"
    echo ""

    phase_05_prepare_flake_workspace || return $?

    phase_05_collect_imperative_packages
    phase_05_confirm_deployment
    if [[ "$PHASE_05_DEPLOYMENT_CANCELLED" == true ]]; then
        return 0
    fi

    phase_05_remove_imperative_packages
    phase_05_update_flake_inputs
    phase_05_ensure_flake_lock_complete
    phase_05_prepare_home_manager_targets
    phase_05_prepare_home_manager_switch || return $?
    phase_05_capture_pre_switch_state
    phase_05_run_home_manager_switch || return $?
    phase_05_configure_flatpak
    phase_05_print_ai_stack_notes
    # Save current state before attempting system switch
    local prev_nixos_gen
    prev_nixos_gen=$(readlink /nix/var/nix/profiles/system-previous || echo "")
    local prev_hm_gen="${PHASE_05_PREV_HM_GEN:-}"
    if [[ -z "$prev_hm_gen" && -n "${PHASE_05_HM_CMD:-}" ]]; then
        prev_hm_gen=$($PHASE_05_HM_CMD generations 2>/dev/null | awk '/^[0-9]+/ {print $1}' | head -n 2 | tail -n 1 || true)
    fi

    phase_05_prepare_system_switch
    if ! phase_05_run_system_switch; then
        print_error "NixOS system switch failed. Attempting coordinated rollback..."
        
        # Attempt to restore previous home-manager generation
        if [[ -n "$prev_hm_gen" && "$prev_hm_gen" =~ ^[0-9]+$ ]]; then
            print_info "Restoring previous home-manager generation: $prev_hm_gen"
            if ! $PHASE_05_HM_CMD switch --generation "$prev_hm_gen" 2>/dev/null; then
                print_error "Failed to restore previous home-manager generation. Manual intervention required."
                return 1
            else
                print_success "Successfully restored home-manager to generation $prev_hm_gen"
            fi
        else
            print_warning "No previous home-manager generation found to restore"
        fi
        
        # Attempt to restore previous NixOS generation
        if [[ -n "$prev_nixos_gen" ]]; then
            print_info "Restoring previous NixOS system generation"
            if ! sudo nixos-rebuild switch --profile "$prev_nixos_gen" 2>/dev/null; then
                print_error "Failed to restore previous NixOS generation. Manual intervention required."
                return 1
            else
                print_success "Successfully restored NixOS to previous generation"
            fi
        else
            print_warning "No previous NixOS generation found to restore"
        fi
        
        print_error "Coordinated rollback completed, but system may be in inconsistent state. Please review configuration."
        return 1
    fi

    phase_05_print_summary

    mark_step_complete "$phase_name"
    print_success "Phase 5: Declarative Deployment - COMPLETE"
    echo ""
}


# Execute phase
phase_05_declarative_deployment
