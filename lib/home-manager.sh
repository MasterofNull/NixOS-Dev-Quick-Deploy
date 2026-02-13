#!/usr/bin/env bash
#
# Home Manager Installation and Management
# Purpose: Install and configure home-manager
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/nixos.sh → get_home_manager_package_ref() function
#
# Required Variables:
#   - HOME → User home directory
#
# Exports:
#   - install_home_manager() → Install home-manager
#
# ============================================================================

# ============================================================================
# Install Home Manager
# ============================================================================
# Purpose: Install home-manager and prepare for dotfiles workflow
# Returns:
#   0 - Success
#   1 - Failure
#
# This function:
# 1. Backs up existing home-manager config
# 2. Removes old config to prevent conflicts
# 3. Pre-fetches home-manager CLI via nix run
# 4. Does NOT install to profile (handled by configuration.nix)
# ============================================================================
install_home_manager() {
    print_section "Installing home-manager"

    # ========================================================================
    # Step 1: Backup and Remove Old Config
    # ========================================================================
    # CRITICAL: Remove old home-manager config files BEFORE installation
    # The home-manager install script may try to use existing home.nix, which could be broken
    if [ -d "$HOME/.config/home-manager" ]; then
        print_info "Found existing home-manager config, backing up..."
        local BACKUP_DIR
        BACKUP_DIR="$HOME/.config-backups/pre-install-$(date +%Y%m%d_%H%M%S)"

        if ! safe_mkdir "$BACKUP_DIR"; then
            print_warning "Could not create backup directory, skipping backup"
        else
            # Backup existing files
            if [ -f "$HOME/.config/home-manager/home.nix" ]; then
                safe_copy_file_silent "$HOME/.config/home-manager/home.nix" "$BACKUP_DIR/home.nix" && \
                    print_success "Backed up old home.nix"
            fi

            if [ -f "$HOME/.config/home-manager/flake.nix" ]; then
                safe_copy_file_silent "$HOME/.config/home-manager/flake.nix" "$BACKUP_DIR/flake.nix" && \
                    print_success "Backed up old flake.nix"
            fi

            if [ -f "$HOME/.config/home-manager/flake.lock" ]; then
                safe_copy_file_silent "$HOME/.config/home-manager/flake.lock" "$BACKUP_DIR/flake.lock" && \
                    print_success "Backed up old flake.lock"
            fi
        fi

        # Remove the old config directory to start fresh
        print_warning "Removing old home-manager config to prevent conflicts..."
        rm -rf "$HOME/.config/home-manager"
        print_success "Old config removed, will create fresh configuration"
        echo ""
    fi

    # ========================================================================
    # Step 2: Get Home Manager Package Reference
    # ========================================================================
    local hm_pkg_ref
    hm_pkg_ref=$(get_home_manager_package_ref)

    print_info "Preparing home-manager CLI for dotfiles workflow..."
    print_info "  Source: ${hm_pkg_ref}"

    # ========================================================================
    # Step 3: Check if Already Available
    # ========================================================================
    if command -v home-manager &> /dev/null; then
        print_success "home-manager command already available: $(which home-manager)"
    else
        # ====================================================================
        # Step 4: Pre-fetch via Nix Run
        # ====================================================================
        local tmp_dir="${TMP_DIR:-/tmp}"
        local bootstrap_log="${tmp_dir}/home-manager-bootstrap.log"
        print_info "Pre-fetching home-manager CLI via nix run (no profile install)..."
        if nix run --accept-flake-config "$hm_pkg_ref" -- --version \
            > >(tee "$bootstrap_log") 2>&1; then
            print_success "home-manager CLI accessible via nix run"
            print_info "Log saved to: $bootstrap_log"
        else
            print_warning "Unable to pre-fetch home-manager CLI (see $bootstrap_log)"
            print_info "Will invoke home-manager through nix run during activation"
        fi
        print_info "Home-manager will be provided permanently by programs.home-manager.enable"
    fi
}

# ============================================================================
# Home Manager CLI Helpers
# ============================================================================
# Purpose: Provide consistent access to the home-manager CLI regardless of
# whether it is already installed into the user's profile.
# ============================================================================

home_manager_cli_available() {
    command -v home-manager >/dev/null 2>&1
}

run_home_manager_cli() {
    if home_manager_cli_available; then
        home-manager "$@"
        return $?
    fi

    if ! command -v nix >/dev/null 2>&1; then
        return 127
    fi

    local hm_pkg_ref
    hm_pkg_ref=$(get_home_manager_package_ref)
    if [[ -z "$hm_pkg_ref" ]]; then
        return 1
    fi

    log DEBUG "home-manager CLI not installed; falling back to nix run ${hm_pkg_ref}"
    nix run --accept-flake-config "$hm_pkg_ref" -- "$@"
}

get_home_manager_generation_line() {
    local hm_output
    if hm_output=$(run_home_manager_cli generations 2>/dev/null); then
        echo "$hm_output" | head -1
        return 0
    fi
    return 1
}

get_home_manager_generation_path() {
    local generation_line
    if ! generation_line=$(get_home_manager_generation_line); then
        return 1
    fi

    local generation_path
    generation_path=$(awk '{print $NF}' <<<"$generation_line" 2>/dev/null)

    if [[ -n "$generation_path" ]]; then
        echo "$generation_path"
        return 0
    fi

    return 1
}
