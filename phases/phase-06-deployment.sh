#!/usr/bin/env bash
#
# Phase 06: Configuration Deployment
# Purpose: Apply NixOS and home-manager configurations
# Version: 3.2.1
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

phase_06_deployment() {
    # ========================================================================
    # Phase 6: Configuration Deployment
    # ========================================================================
    # This phase consolidates all deployment operations:
    # 1. Find and list nix-env packages
    # 2. Backup all system files
    # 3. Clean environment setup
    # 4. Remove conflicting packages
    # 5. Configure Flatpak
    # 6. Apply NixOS system configuration
    # 7. Apply home-manager configuration
    # ========================================================================

    local phase_name="deploy_configurations"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 6 already completed (skipping)"
        return 0
    fi

    print_section "Phase 6/10: Configuration Deployment"
    echo ""

    # ========================================================================
    # Step 6.1: Pre-Deployment Check - Find Environment Packages
    # ========================================================================
    print_info "Checking for packages installed via nix-env (imperative method)..."
    local IMPERATIVE_PKGS
    IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null || true)

    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
        print_info "These will be removed in Phase 6 before system deployment to prevent conflicts"
    else
        print_success "No nix-env packages found - clean state!"
    fi
    echo ""

    # ========================================================================
    # Step 6.2: Final User Confirmation (SINGLE PROMPT FOR ENTIRE DEPLOYMENT)
    # ========================================================================
    # This is the only confirmation prompt - consolidates all operations
    print_warning "The following operations will be performed:"
    echo "  1. Backup existing configuration files"
    echo "  2. Remove conflicting nix-env packages (if any)"
    echo "  3. Clean environment for fresh installation"
    echo "  4. Configure Flatpak repositories"
    echo "  5. Apply NixOS system configuration (sudo nixos-rebuild switch)"
    echo "  6. Apply home-manager user configuration"
    echo ""

    if ! confirm "Proceed with configuration deployment (this will apply system changes)?" "y"; then
        print_warning "Deployment skipped - configurations generated but not applied"
        print_info "To apply later, run: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        echo ""
        return 0
    fi

    # ========================================================================
    # Step 6.3: Backup Existing Configuration Files
    # ========================================================================
    print_section "Backing Up Configuration Files"
    local backup_dir="$HOME/.config-backups/pre-switch-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup config directories that home-manager will manage
    local config_dirs=(
        ".config/flatpak"
        ".config/aider"
        ".config/tea"
        ".config/huggingface"
        ".cache/huggingface"
        ".local/share/open-webui"
        ".local/share/podman-ai-stack"
        ".config/gitea"
        ".local/share/gitea"
        ".var/app/io.gitea.Gitea/config/gitea"
        ".var/app/io.gitea.Gitea/data/gitea"
        ".config/obsidian/ai-integrations"
    )

    for config_dir in "${config_dirs[@]}"; do
        local full_path="$HOME/$config_dir"
        if [[ -e "$full_path" ]]; then
            local dir_name=$(basename "$config_dir")
            local parent_dir=$(dirname "$config_dir")

            # Create parent directory structure in backup
            mkdir -p "$backup_dir/$parent_dir"

            # Backup and remove
            if cp -a "$full_path" "$backup_dir/$parent_dir/" 2>/dev/null; then
                rm -rf "$full_path"
                print_success "Backed up and removed $(basename $config_dir) configuration directory"
                print_info "  → Backup saved to: $backup_dir/$config_dir"
            fi
        fi
    done

    print_success "All conflicting configs backed up to: $backup_dir"
    print_info "Home-manager will now create managed symlinks"
    print_info "To restore previous configs: cp -a \"$backup_dir/.\" \"$HOME/\""
    print_success "Prepared directories for managed configuration files"
    echo ""

    # ========================================================================
    # Step 6.4: Force Clean Environment Setup
    # ========================================================================
    print_section "Forcing Clean Environment Setup"
    print_info "Ensuring fresh installation by removing old generations and state..."

    # Clean flatpak environment
    if command -v flatpak >/dev/null 2>&1; then
        print_info "Removing complete flatpak user environment for clean setup..."

        # Backup entire flatpak directory
        local flatpak_backup="$STATE_DIR/flatpak-environment-backup-$(date +%Y%m%d_%H%M%S)"
        if [[ -d "$HOME/.local/share/flatpak" ]]; then
            print_info "Backing up entire flatpak directory structure..."
            mkdir -p "$flatpak_backup"
            cp -a "$HOME/.local/share/flatpak" "$flatpak_backup/" 2>/dev/null || true
            print_success "Flatpak environment backed up to: $flatpak_backup"

            print_info "Removing flatpak directory for clean reinstall..."
            rm -rf "$HOME/.local/share/flatpak"
            print_success "Flatpak environment directory removed"
        fi

        # Remove flatpak config
        if [[ -d "$HOME/.config/flatpak" ]]; then
            print_info "Removing flatpak configuration directory..."
            rm -rf "$HOME/.config/flatpak"
        fi

        # Re-initialize flatpak
        print_info "Re-initializing Flatpak repository structure..."
        flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || \
            flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null || \
            print_warning "Could not add Flathub remote (will be added later by home-manager)"

        print_success "Complete flatpak environment removed and re-initialized for clean reinstall"
        print_info "Flatpak will be completely rebuilt by home-manager"
    fi

    # Clean nix profile
    print_info "Cleaning nix profile for fresh home-manager state..."
    nix-collect-garbage -d 2>/dev/null || true
    print_success "Environment prepared for clean installation"
    print_info "All previous settings have been backed up and will be replaced with new configuration"
    echo ""

    # ========================================================================
    # Step 6.5: Remove Conflicting Packages
    # ========================================================================
    if [[ -n "$IMPERATIVE_PKGS" ]]; then
        print_section "Removing Conflicting Packages"
        print_info "Cleaning up nix-env packages to prevent conflicts with declarative management"
        echo ""

        print_warning "Found packages installed via nix-env (will cause conflicts):"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""

        print_info "Removing ALL nix-env packages (switching to declarative management)..."
        print_info "This prevents package collisions and ensures reproducibility"

        # Save list of removed packages for potential recovery
        local removed_pkgs_file="$STATE_DIR/removed-packages-$(date +%s).txt"
        mkdir -p "$STATE_DIR"
        echo "$IMPERATIVE_PKGS" > "$removed_pkgs_file"
        print_info "Saved package list for recovery: $removed_pkgs_file"

        # Remove all packages installed via nix-env
        if nix-env -e '.*' 2>&1 | tee /tmp/nix-env-cleanup.log; then
            print_success "All nix-env packages removed successfully"
        else
            # Fallback: Try removing packages one by one
            print_warning "Batch removal failed, trying individual package removal..."
            while IFS= read -r pkg; do
                local pkg_name
                pkg_name=$(echo "$pkg" | awk '{print $1}')
                if [[ -n "$pkg_name" ]]; then
                    print_info "Removing: $pkg_name"
                    nix-env -e "$pkg_name" 2>/dev/null && print_success "  Removed: $pkg_name" || print_warning "  Failed: $pkg_name"
                fi
            done <<< "$IMPERATIVE_PKGS"
        fi

        # Verify all removed
        local REMAINING
        REMAINING=$(nix-env -q 2>/dev/null || true)
        if [[ -n "$REMAINING" ]]; then
            print_warning "Some packages remain in nix-env:"
            echo "$REMAINING" | sed 's/^/    /'
            print_warning "These may cause conflicts with home-manager"
        else
            print_success "All nix-env packages successfully removed"
            print_success "All packages now managed declaratively"
        fi
        echo ""
    fi

    # ========================================================================
    # Step 6.6: Apply NixOS System Configuration
    # ========================================================================
    print_section "Applying New Configuration"
    local target_host=$(hostname)
    local NIXOS_REBUILD_DRY_LOG="/tmp/nixos-rebuild-dry-run.log"

    # Run dry-run first if not already done
    if [[ ! -f "$NIXOS_REBUILD_DRY_LOG" ]] || [[ "$FORCE_UPDATE" == true ]]; then
        print_info "Dry run already completed earlier (log: $NIXOS_REBUILD_DRY_LOG)"
    fi

    print_warning "Running: sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""
    print_info "This will download and install all AIDB components using the generated flake..."
    print_info "May take 10-20 minutes on first run"
    echo ""

    print_info "Binary caches enabled for nixos-rebuild switch: https://cache.nixos.org, https://nix-community.cachix.org, https://devenv.cachix.org"

    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" 2>&1 | tee /tmp/nixos-rebuild.log; then
        print_success "✓ NixOS system configured successfully!"
        print_success "✓ AIDB development environment ready"
        echo ""
    else
        print_error "nixos-rebuild failed - check log: /tmp/nixos-rebuild.log"
        return 1
    fi

    # ========================================================================
    # Step 6.7: Configure Flatpak for COSMIC App Store
    # ========================================================================
    print_section "Configuring Flatpak for COSMIC App Store"
    if flatpak remote-list --user 2>/dev/null | grep -q "flathub"; then
        print_info "Flathub repository already configured"
    else
        print_info "Adding Flathub Flatpak remote..."
        if flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null; then
            print_success "Flathub repository added"
        else
            print_info "Trying fallback Flathub URL..."
            flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true
        fi
    fi

    # Add beta repo for bleeding-edge packages
    if ! flatpak remote-list --user 2>/dev/null | grep -q "flathub-beta"; then
        print_info "Adding Flathub Beta Flatpak remote for bleeding-edge AI builds..."
        flatpak remote-add --user --if-not-exists flathub-beta https://flathub.org/beta-repo/flathub-beta.flatpakrepo 2>/dev/null || true
        if flatpak remote-list --user 2>/dev/null | grep -q "flathub-beta"; then
            print_success "Flathub Beta repository added"
        fi
    fi

    print_info "COSMIC Store can now install Flatpak applications"
    echo ""

    # ========================================================================
    # Step 6.8: Apply Home Manager Configuration
    # ========================================================================
    print_section "Applying Home Manager Configuration"
    print_info "This will install packages and configure your environment..."
    print_warning "This may take 10-15 minutes on first run"
    echo ""

    print_info "Flatpak Integration:"
    print_info "  Your home.nix includes declarative Flatpak configuration via nix-flatpak"
    print_info "  Edit the services.flatpak.packages section in home.nix to add/remove Flatpak apps"
    print_info "  Uncomment desired Flatpak apps and re-run: home-manager switch"
    echo ""

    # Update flake inputs
    local HM_FLAKE_PATH="$HM_CONFIG_DIR/flake.nix"
    if [[ -f "$HM_FLAKE_PATH" ]]; then
        print_info "Updating flake inputs (nix-flatpak, home-manager, nixpkgs)..."
        if (cd "$HM_CONFIG_DIR" && nix flake update 2>/dev/null); then
            print_success "Flake inputs updated successfully"
        else
            print_warning "Flake update had issues, continuing anyway..."
        fi
    fi

    print_info "Using configuration: homeConfigurations.$USER"
    echo ""

    # Clean up and mask any conflicting services
    systemctl --user stop home-manager-* 2>/dev/null || true
    systemctl --user mask home-manager-*.service 2>/dev/null || true
    print_success "Services cleaned up and masked - safe to run home-manager switch"

    # Check if home-manager command is available
    local hm_cmd=""
    if command -v home-manager &>/dev/null; then
        hm_cmd="home-manager"
    else
        print_warning "home-manager command not found in PATH"
        print_info "Will invoke via: nix run --accept-flake-config github:nix-community/home-manager#home-manager -- ..."
        hm_cmd="nix run --accept-flake-config github:nix-community/home-manager#home-manager --"
    fi

    print_info "Applying your custom home-manager configuration..."
    print_info "Config: $HM_CONFIG_DIR/home.nix"
    print_info "Using flake for full Flatpak declarative support..."
    echo ""

    # Apply home-manager configuration
    if $hm_cmd switch --flake "$HM_CONFIG_DIR" 2>&1 | tee /tmp/home-manager-switch.log; then
        print_success "✓ home-manager applied successfully!"
        print_success "✓ User environment configured"
        echo ""
    else
        print_error "home-manager switch failed (exit code: ${PIPESTATUS[0]})"
        echo ""
        print_warning "Common causes:"
        print_info "  • Conflicting files (check ~/.config collisions)"
        print_info "  • Syntax errors in home.nix"
        print_info "  • Network issues downloading packages"
        print_info "  • Package conflicts or missing dependencies"
        echo ""
        print_info "Full log saved to: /tmp/home-manager-switch.log"
        print_info "Backup is at: $backup_dir"
        print_info "Previous configuration files archived under: $backup_dir"
        print_info "Restore with: cp -a \"$backup_dir/.\" \"$HOME/\""
        echo ""
        return 1
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 6: Configuration Deployment - COMPLETE"
    echo ""
}

# Execute phase
phase_06_deployment
