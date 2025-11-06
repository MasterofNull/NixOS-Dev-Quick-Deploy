#!/usr/bin/env bash
#
# Phase 06: Configuration Deployment
# Purpose: Apply NixOS and home-manager configurations (trust declarative migration)
# Version: 3.3.0
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
    # Following NixOS Best Practices:
    # - Trust nixos-rebuild switch to handle declarative migration
    # - Only remove packages that THIS SCRIPT installed
    # - Let NixOS handle package conflicts automatically
    # - Minimal manual intervention
    #
    # What NixOS handles automatically:
    # - Package conflicts resolution
    # - System state migration
    # - Generation management
    # - Rollback capability
    #
    # What we handle:
    # - Confirm deployment
    # - Remove script-installed packages (if tracked)
    # - Apply configurations
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
    # Step 6.1: Check for Script-Installed Packages
    # ========================================================================
    # We only remove packages that THIS SCRIPT installed during prerequisites
    # Not ALL nix-env packages - user might have their own
    print_info "Checking for script-installed packages..."

    local script_pkg_list="$STATE_DIR/script-installed-packages.txt"
    local script_pkgs=""

    if [[ -f "$script_pkg_list" ]]; then
        script_pkgs=$(cat "$script_pkg_list")
        if [[ -n "$script_pkgs" ]]; then
            print_warning "Found packages installed by this script:"
            echo "$script_pkgs" | sed 's/^/    /'
            echo ""
            print_info "These will be removed before deployment (declarative management)"
        fi
    else
        print_success "No script-installed packages to remove"
    fi

    echo ""

    # ========================================================================
    # Step 6.2: Final Deployment Confirmation
    # ========================================================================
    print_warning "Ready to deploy declarative NixOS configuration"
    echo ""
    echo "This will:"
    echo "  1. Remove script-installed packages (if any)"
    echo "  2. Apply NixOS system configuration"
    echo "  3. Apply home-manager user configuration"
    echo ""
    echo "NixOS will handle:"
    echo "  • Package conflict resolution"
    echo "  • System state migration"
    echo "  • Generation management"
    echo "  • Automatic rollback capability"
    echo ""

    if ! confirm "Proceed with deployment?" "y"; then
        print_warning "Deployment cancelled"
        print_info "To apply later, run:"
        print_info "  sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        print_info "  home-manager switch --flake $HM_CONFIG_DIR"
        echo ""
        return 0
    fi

    echo ""

    # ========================================================================
    # Step 6.3: Remove Script-Installed Packages
    # ========================================================================
    # Only remove packages we installed, not user's packages
    if [[ -n "$script_pkgs" ]]; then
        print_section "Removing Script-Installed Packages"
        print_info "Removing packages installed by this script..."
        echo ""

        while IFS= read -r pkg; do
            if [[ -n "$pkg" ]]; then
                print_info "  Removing: $pkg"
                if nix-env -e "$pkg" 2>/dev/null; then
                    print_success "    ✓ Removed"
                else
                    print_warning "    ⚠ Already removed or not found"
                fi
            fi
        done <<< "$script_pkgs"

        print_success "Script-installed packages removed"
        echo ""
    fi

    # ========================================================================
    # Step 6.4: Apply NixOS System Configuration
    # ========================================================================
    print_section "Applying NixOS System Configuration"
    local target_host=$(hostname)

    print_info "Running: sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""
    print_info "This will apply the declarative system configuration..."
    print_info "NixOS will handle package migration automatically"
    echo ""

    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" 2>&1 | tee /tmp/nixos-rebuild.log; then
        print_success "✓ NixOS system configuration applied successfully!"
        print_success "✓ New generation created with rollback capability"
        echo ""
    else
        local exit_code=${PIPESTATUS[0]}
        print_error "nixos-rebuild failed (exit code: $exit_code)"
        print_info "Log: /tmp/nixos-rebuild.log"
        print_info "Rollback: sudo nixos-rebuild --rollback"
        echo ""
        return 1
    fi

    # ========================================================================
    # Step 6.5: Configure Flatpak (if available)
    # ========================================================================
    if command -v flatpak &>/dev/null; then
        print_section "Configuring Flatpak"

        # Add Flathub if not present
        if ! flatpak remote-list --user 2>/dev/null | grep -q "^flathub"; then
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
        if ! flatpak remote-list --user 2>/dev/null | grep -q "^flathub-beta"; then
            print_info "Adding Flathub Beta repository (optional)..."
            flatpak remote-add --user --if-not-exists flathub-beta \
                https://flathub.org/beta-repo/flathub-beta.flatpakrepo 2>/dev/null && \
                print_success "✓ Flathub Beta added" || \
                print_info "  Flathub Beta not added (not required)"
        fi

        echo ""
    fi

    # ========================================================================
    # Step 6.6: Apply Home Manager Configuration
    # ========================================================================
    print_section "Applying Home Manager Configuration"
    print_info "This will configure your user environment..."
    echo ""

    # Update flake inputs
    print_info "Updating flake inputs..."
    if (cd "$HM_CONFIG_DIR" && nix flake update 2>&1 | grep -E '(Updated|Warning|Error)'); then
        print_success "✓ Flake inputs updated"
    else
        print_warning "⚠ Flake update had issues (continuing anyway)"
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
        print_success "✓ Home manager configuration applied successfully!"
        print_success "✓ User environment configured"
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
    # Deployment Summary
    # ========================================================================
    print_section "Deployment Complete"
    echo "✓ NixOS system configuration applied"
    echo "✓ Home manager user environment configured"
    echo "✓ New generations created (rollback available)"
    echo "✓ Flatpak configured"
    echo ""
    echo "Rollback commands (if needed):"
    echo "  System:  sudo nixos-rebuild --rollback"
    echo "  User:    home-manager --rollback"
    echo "  Boot:    Select previous generation in boot menu"
    echo ""

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 6: Configuration Deployment - COMPLETE"
    echo ""
}

# Execute phase
phase_06_deployment
