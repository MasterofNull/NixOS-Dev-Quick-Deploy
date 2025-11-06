#!/usr/bin/env bash
#
# Additional Tools Installation
# Purpose: Install non-declarative tools like Claude Code, Flatpak apps, etc.
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#
# Exports:
#   - install_flatpak_stage() → Install Flatpak applications
#   - install_claude_code() → Install Claude Code CLI
#   - configure_vscodium_for_claude() → Configure VSCodium for Claude
#   - install_vscodium_extensions() → Install VSCodium extensions
#   - install_openskills_tooling() → Install OpenSkills tools
#   - setup_flake_environment() → Setup Nix flakes dev environment
#
# ============================================================================

# ============================================================================
# Install Flatpak Applications
# ============================================================================
# Purpose: Install Flatpak applications from home.nix configuration
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_flatpak_stage() {
    print_section "Installing Flatpak Applications"

    # Check if Flatpak is available
    if ! command -v flatpak &>/dev/null; then
        print_warning "Flatpak not found in PATH"
        print_info "Flatpak applications are managed declaratively via home-manager"
        print_info "After home-manager switch, Flatpak apps will be available"
        return 0
    fi

    # Flatpak apps are now managed declaratively via nix-flatpak in home.nix
    # This function ensures the Flatpak environment is ready
    print_info "Flatpak applications are managed declaratively"
    print_info "They should already be installed via home-manager switch"

    # Verify some flatpaks are installed
    local installed_count=$(flatpak list --app 2>/dev/null | wc -l)
    if [[ $installed_count -gt 0 ]]; then
        print_success "Found $installed_count Flatpak applications installed"
    else
        print_info "No Flatpak applications found (may install after next home-manager switch)"
    fi

    return 0
}

# ============================================================================
# Install Claude Code CLI
# ============================================================================
# Purpose: Install Claude Code CLI for AI assistance
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_claude_code() {
    print_section "Installing Claude Code CLI"

    # Check if already installed
    if command -v claude &>/dev/null; then
        print_success "Claude Code CLI already installed: $(which claude)"
        return 0
    fi

    print_info "Claude Code CLI installation is currently optional"
    print_info "To install manually:"
    print_info "  1. Visit: https://github.com/anthropics/claude-code"
    print_info "  2. Follow installation instructions"
    print_info "  3. Set up API key in configuration"

    # TODO: Implement actual Claude Code installation
    # This would typically involve:
    # 1. Download latest release from GitHub
    # 2. Extract binary to ~/.local/bin or /usr/local/bin
    # 3. Make executable
    # 4. Create config file
    # 5. Prompt for API key (or use existing)

    return 1  # Return failure to skip dependent steps
}

# ============================================================================
# Configure VSCodium for Claude
# ============================================================================
# Purpose: Configure VSCodium editor for Claude integration
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
configure_vscodium_for_claude() {
    print_section "Configuring VSCodium for Claude"

    # Check if VSCodium is installed
    if ! command -v codium &>/dev/null; then
        print_info "VSCodium not found in PATH"
        print_info "VSCodium may be installed via Flatpak or will be available after relogin"
        return 0
    fi

    print_info "VSCodium Claude configuration is optional"
    print_info "Extension can be installed manually from Open VSX Registry"

    # TODO: Implement VSCodium configuration
    # This would typically involve:
    # 1. Install Claude extension via codium --install-extension
    # 2. Create/modify settings.json
    # 3. Set up keybindings
    # 4. Configure extension settings

    return 0
}

# ============================================================================
# Install VSCodium Extensions
# ============================================================================
# Purpose: Install useful VSCodium extensions for development
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_vscodium_extensions() {
    print_section "Installing VSCodium Extensions"

    # Check if VSCodium is installed
    if ! command -v codium &>/dev/null; then
        print_info "VSCodium not found, skipping extension installation"
        return 0
    fi

    # List of recommended extensions
    local extensions=(
        "bbenoist.nix"                    # Nix language support
        "jnoortheen.nix-ide"              # Nix IDE
        "ms-python.python"                # Python support
        "rust-lang.rust-analyzer"         # Rust support
        "eamodio.gitlens"                 # Git integration
        "esbenp.prettier-vscode"          # Code formatter
    )

    print_info "Recommended extensions for VSCodium:"
    for ext in "${extensions[@]}"; do
        echo "  - $ext"
    done

    print_info "Extensions can be installed via VSCodium extension marketplace"
    print_info "Or manually: codium --install-extension <extension-id>"

    # TODO: Implement extension installation
    # This would loop through extensions and install:
    # for ext in "${extensions[@]}"; do
    #     codium --install-extension "$ext" 2>&1 | grep -v "already installed" || true
    # done

    return 0
}

# ============================================================================
# Install OpenSkills Tooling
# ============================================================================
# Purpose: Install project-specific OpenSkills development tools
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
install_openskills_tooling() {
    print_section "Installing OpenSkills Tooling"

    print_info "OpenSkills tooling installation is project-specific"
    print_info "This is a placeholder for custom project tools"

    # Check if there's a custom install script
    local openskills_install_script="$HOME/.config/openskills/install.sh"
    if [[ -f "$openskills_install_script" ]]; then
        print_info "Found OpenSkills install script, executing..."
        if bash "$openskills_install_script"; then
            print_success "OpenSkills tooling installed"
            return 0
        else
            print_warning "OpenSkills install script failed"
            return 1
        fi
    fi

    print_info "No custom OpenSkills tooling configured"
    print_info "Create $openskills_install_script to add custom tools"

    return 0
}

# ============================================================================
# Setup Flake Environment
# ============================================================================
# Purpose: Setup Nix flakes development environment
# Returns:
#   0 - Success
#   1 - Failure (non-critical)
# ============================================================================
setup_flake_environment() {
    print_section "Setting Up Flake Development Environment"

    # Check if flakes are enabled
    if ! nix flake --help &>/dev/null; then
        print_warning "Nix flakes not available"
        print_info "Flakes should be enabled in configuration.nix"
        return 1
    fi

    print_info "Nix flakes are enabled and ready"

    # Check if direnv is available for auto-activation
    if command -v direnv &>/dev/null; then
        print_success "direnv is available for automatic environment activation"
        print_info "In project directories with flake.nix:"
        print_info "  1. Create .envrc with: use flake"
        print_info "  2. Run: direnv allow"
        print_info "  3. Environment activates automatically on cd"
    else
        print_info "Install direnv for automatic flake environment activation"
        print_info "Manual activation: nix develop"
    fi

    # Check if our flake configuration is valid
    if [[ -f "$HM_CONFIG_DIR/flake.nix" ]]; then
        print_info "Validating flake configuration..."
        if nix flake check "$HM_CONFIG_DIR" 2>&1 | tee /tmp/flake-check.log; then
            print_success "Flake configuration is valid"
        else
            print_warning "Flake validation had issues (see /tmp/flake-check.log)"
            print_info "Configuration may still work, issues are often non-critical"
        fi
    fi

    print_success "Flake environment setup complete"
    return 0
}
