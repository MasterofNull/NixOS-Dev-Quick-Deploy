#!/usr/bin/env bash
#
# Deployment Reporting
# Purpose: Generate comprehensive post-deployment reports
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/colors.sh → Color codes
#
# Exports:
#   - print_post_install() → Generate comprehensive deployment report
#
# ============================================================================

# ============================================================================
# Print Post-Install Report
# ============================================================================
# Purpose: Generate comprehensive post-installation report
# Returns:
#   0 - Always succeeds
#
# Report includes:
# - NixOS generation information
# - Home-manager generation information
# - Installed package counts
# - Service status summary
# - Hardware configuration summary
# - Next steps and recommendations
# ============================================================================
print_post_install() {
    print_section "Deployment Report"
    echo ""

    # ========================================================================
    # 1. NixOS Generation Information
    # ========================================================================
    print_info "NixOS System Information:"
    echo ""

    # Current generation
    local current_gen=$(sudo nix-env --list-generations -p /nix/var/nix/profiles/system 2>/dev/null | tail -1)
    if [[ -n "$current_gen" ]]; then
        echo "  Generation: $current_gen"
    fi

    # NixOS version
    local nixos_version=$(nixos-version 2>/dev/null || echo "Unknown")
    echo "  Version: $nixos_version"

    # System configuration path
    if [[ -f "$SYSTEM_CONFIG_FILE" ]]; then
        echo "  Config: $SYSTEM_CONFIG_FILE"
    elif [[ -f "$HM_CONFIG_DIR/configuration.nix" ]]; then
        echo "  Config: $HM_CONFIG_DIR/configuration.nix"
    fi

    # Flake location
    if [[ -f "$FLAKE_FILE" ]]; then
        echo "  Flake: $FLAKE_FILE"
    fi
    echo ""

    # ========================================================================
    # 2. Home-Manager Information
    # ========================================================================
    print_info "Home-Manager User Environment:"
    echo ""

    # Check if home-manager is available
    if command -v home-manager &>/dev/null; then
        # Get current generation
        local hm_gen=$(home-manager generations 2>/dev/null | head -1)
        if [[ -n "$hm_gen" ]]; then
            echo "  $hm_gen"
        fi

        # Home-manager config path
        if [[ -f "$HOME_MANAGER_FILE" ]]; then
            echo "  Config: $HOME_MANAGER_FILE"
        fi
    else
        echo "  Status: Will be available after relogin or manual activation"
        echo "  Command: home-manager switch --flake $HM_CONFIG_DIR"
    fi
    echo ""

    # ========================================================================
    # 3. Package Statistics
    # ========================================================================
    print_info "Installed Packages:"
    echo ""

    # System packages
    local system_pkg_count=$(nix-store --query --requisites /run/current-system 2>/dev/null | wc -l)
    echo "  System packages: $system_pkg_count"

    # User packages (if home-manager is active)
    if [[ -d "$HOME/.nix-profile" ]]; then
        local user_pkg_count=$(nix-store --query --requisites "$HOME/.nix-profile" 2>/dev/null | wc -l)
        echo "  User packages: $user_pkg_count"
    fi

    # Flatpak apps
    if command -v flatpak &>/dev/null; then
        local flatpak_count=$(flatpak list --app 2>/dev/null | wc -l)
        echo "  Flatpak apps: $flatpak_count"
    fi
    echo ""

    # ========================================================================
    # 4. Service Status Summary
    # ========================================================================
    print_info "System Services Status:"
    echo ""

    local services=(
        "postgresql:Database server"
        "ollama:AI model server"
        "gitea:Git hosting"
    )

    for service_info in "${services[@]}"; do
        local service="${service_info%%:*}"
        local desc="${service_info#*:}"

        if systemctl list-unit-files | grep -q "^${service}.service"; then
            if systemctl is-active --quiet "$service" 2>/dev/null; then
                echo -e "  ${GREEN}●${NC} $service: running ($desc)"
            else
                echo -e "  ${YELLOW}○${NC} $service: stopped ($desc)"
            fi
        else
            echo -e "  ${GRAY}−${NC} $service: not configured ($desc)"
        fi
    done
    echo ""

    # ========================================================================
    # 5. Hardware Summary
    # ========================================================================
    print_info "Hardware Configuration:"
    echo ""

    # CPU
    local cpu_model=$(lscpu | grep "Model name" | cut -d: -f2 | xargs)
    echo "  CPU: $cpu_model"

    # Memory
    local total_mem=$(free -h | awk '/^Mem:/ {print $2}')
    echo "  Memory: $total_mem"

    # GPU
    if [[ -n "$GPU_TYPE" && "$GPU_TYPE" != "unknown" ]]; then
        echo "  GPU: $GPU_TYPE"
    fi

    # Disk space
    local nix_total=$(df -h /nix | tail -1 | awk '{print $2}')
    local nix_used=$(df -h /nix | tail -1 | awk '{print $3}')
    local nix_avail=$(df -h /nix | tail -1 | awk '{print $4}')
    echo "  /nix storage: $nix_used used / $nix_total total ($nix_avail available)"
    echo ""

    # ========================================================================
    # 6. Important Paths
    # ========================================================================
    print_info "Important Paths:"
    echo ""
    echo "  Configuration:"
    echo "    System: $SYSTEM_CONFIG_FILE"
    echo "    Home:   $HOME_MANAGER_FILE"
    echo "    Flake:  $FLAKE_FILE"
    echo ""
    echo "  Dotfiles: $DOTFILES_ROOT"
    echo "  Logs:     $LOG_DIR"
    echo ""

    # ========================================================================
    # 7. Next Steps
    # ========================================================================
    print_info "Next Steps:"
    echo ""
    echo "  1. Logout and login to activate all user environment changes"
    echo "  2. Verify services are running:"
    echo "     sudo systemctl status <service-name>"
    echo ""
    echo "  3. Update system configurations:"
    echo "     Edit: $SYSTEM_CONFIG_FILE"
    echo "     Apply: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR"
    echo ""
    echo "  4. Update user configurations:"
    echo "     Edit: $HOME_MANAGER_FILE"
    echo "     Apply: home-manager switch --flake $HM_CONFIG_DIR"
    echo ""
    echo "  5. Update package versions:"
    echo "     cd $HM_CONFIG_DIR && nix flake update"
    echo ""

    # ========================================================================
    # 8. Useful Commands
    # ========================================================================
    print_info "Useful Commands:"
    echo ""
    echo "  # System management"
    echo "  nixos-rebuild switch           # Apply system changes"
    echo "  nixos-rebuild boot             # Apply on next boot"
    echo "  nixos-rebuild test             # Test temporarily"
    echo ""
    echo "  # User environment"
    echo "  home-manager switch            # Apply user changes"
    echo "  home-manager generations       # List generations"
    echo ""
    echo "  # Package management"
    echo "  nix search nixpkgs <query>     # Search for packages"
    echo "  nix-collect-garbage -d         # Clean old generations"
    echo "  nix-store --optimize           # Deduplicate store"
    echo ""
    echo "  # Flake management"
    echo "  nix flake update               # Update flake inputs"
    echo "  nix flake check                # Validate flake"
    echo "  nix develop                    # Enter dev shell"
    echo ""

    # ========================================================================
    # 9. Documentation Links
    # ========================================================================
    print_info "Documentation:"
    echo ""
    echo "  NixOS Manual:       https://nixos.org/manual/nixos/stable/"
    echo "  Home-Manager:       https://nix-community.github.io/home-manager/"
    echo "  Nix Packages:       https://search.nixos.org/packages"
    echo "  Nix Options:        https://search.nixos.org/options"
    echo ""

    # ========================================================================
    # 10. Support and Feedback
    # ========================================================================
    print_info "Support:"
    echo ""
    echo "  Repository: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy"
    echo "  Issues:     https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues"
    echo ""

    print_success "Deployment report complete!"
    return 0
}
