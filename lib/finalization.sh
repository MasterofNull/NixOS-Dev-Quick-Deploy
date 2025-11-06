#!/usr/bin/env bash
#
# System Finalization
# Purpose: Final system configuration and service activation
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
#   - apply_final_system_configuration() → Apply final configs
#   - finalize_configuration_activation() → Activate all configs
#
# ============================================================================

# ============================================================================
# Apply Final System Configuration
# ============================================================================
# Purpose: Apply configurations that require running services
# Returns:
#   0 - Success
#   1 - Failure
#
# This function handles:
# - Database initialization
# - Service configuration
# - Integration setup
# - Permission finalization
# ============================================================================
apply_final_system_configuration() {
    print_section "Applying Final System Configuration"

    # ========================================================================
    # 1. Database Initialization
    # ========================================================================
    print_info "Checking database status..."

    if systemctl is-active --quiet postgresql 2>/dev/null; then
        print_success "PostgreSQL is running"

        # Check if gitea database exists
        if sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw gitea; then
            print_success "Gitea database already exists"
        else
            print_info "Gitea database will be created on first Gitea start"
        fi
    else
        print_info "PostgreSQL not running (may not be configured)"
    fi
    echo ""

    # ========================================================================
    # 2. Service Configuration
    # ========================================================================
    print_info "Checking service configurations..."

    local services_to_check=(
        "gitea:Git hosting service"
        "ollama:Local AI model server"
        "postgresql:Database server"
    )

    for service_info in "${services_to_check[@]}"; do
        local service_name="${service_info%%:*}"
        local service_desc="${service_info#*:}"

        if systemctl list-unit-files | grep -q "^${service_name}.service"; then
            if systemctl is-enabled --quiet "$service_name" 2>/dev/null; then
                print_success "  $service_name: enabled ($service_desc)"
            else
                print_info "  $service_name: disabled ($service_desc)"
            fi
        else
            print_info "  $service_name: not configured ($service_desc)"
        fi
    done
    echo ""

    # ========================================================================
    # 3. User Service Integration
    # ========================================================================
    print_info "Checking user services..."

    # Check if systemd user session is available
    if systemctl --user list-units &>/dev/null; then
        print_success "User systemd session available"

        # List user services (if any)
        local user_services=$(systemctl --user list-unit-files --type=service --no-legend 2>/dev/null | wc -l)
        print_info "  Found $user_services user service(s) configured"
    else
        print_info "User systemd session not yet active (will be available after relogin)"
    fi
    echo ""

    # ========================================================================
    # 4. Permission Finalization
    # ========================================================================
    print_info "Finalizing permissions..."

    # Ensure user owns their home directory configurations
    if [[ -d "$HOME/.config" ]]; then
        # Only fix if not already owned by user
        local current_owner=$(stat -c %U "$HOME/.config" 2>/dev/null || echo "unknown")
        local expected_owner="${SUDO_USER:-${PRIMARY_USER:-$USER}}"
        if [[ "$current_owner" != "$expected_owner" ]]; then
            if safe_chown_user_dir "$HOME/.config"; then
                print_success "Fixed .config ownership"
            else
                print_warning "Could not fix .config ownership (may require sudo)"
            fi
        else
            print_success ".config directory has correct ownership"
        fi
    fi

    # Ensure dotfiles directory has correct ownership
    if [[ -d "$DOTFILES_ROOT" ]]; then
        local current_owner=$(stat -c %U "$DOTFILES_ROOT" 2>/dev/null || echo "unknown")
        local expected_owner="${SUDO_USER:-${PRIMARY_USER:-$USER}}"
        if [[ "$current_owner" != "$expected_owner" ]]; then
            if safe_chown_user_dir "$DOTFILES_ROOT"; then
                print_success "Fixed dotfiles ownership"
            else
                print_warning "Could not fix dotfiles ownership"
            fi
        else
            print_success "Dotfiles directory has correct ownership"
        fi
    fi
    echo ""

    print_success "Final system configuration applied"
    return 0
}

# ============================================================================
# Finalize Configuration Activation
# ============================================================================
# Purpose: Ensure all configurations are active and services using them
# Returns:
#   0 - Success
#   1 - Failure
#
# This function:
# - Reloads systemd configurations
# - Enables user services
# - Cleans up temporary files
# - Verifies service dependencies
# ============================================================================
finalize_configuration_activation() {
    print_section "Finalizing Configuration Activation"

    # ========================================================================
    # 1. Reload Systemd Configurations
    # ========================================================================
    print_info "Reloading systemd configurations..."

    # Reload system daemon
    if sudo systemctl daemon-reload 2>/dev/null; then
        print_success "System daemon reloaded"
    else
        print_warning "Could not reload system daemon"
    fi

    # Reload user daemon (if session available)
    if systemctl --user daemon-reload 2>/dev/null; then
        print_success "User daemon reloaded"
    else
        print_info "User daemon reload skipped (will reload on next login)"
    fi
    echo ""

    # ========================================================================
    # 2. Enable User Services
    # ========================================================================
    print_info "Enabling user services..."

    # Check if home-manager has set up any services
    local hm_services_dir="$HOME/.config/systemd/user"
    if [[ -d "$hm_services_dir" ]]; then
        local service_count=$(find "$hm_services_dir" -name "*.service" -type f 2>/dev/null | wc -l)
        if [[ $service_count -gt 0 ]]; then
            print_info "Found $service_count home-manager service(s)"
            print_info "Services will be activated on next login or via: systemctl --user start <service>"
        else
            print_info "No home-manager services configured"
        fi
    fi
    echo ""

    # ========================================================================
    # 3. Clean Up Temporary Files
    # ========================================================================
    print_info "Cleaning up temporary files..."

    local temp_files=(
        "/tmp/nixos-rebuild-dry-run.log"
        "/tmp/nixos-rebuild-dry-build.log"
        "/tmp/home-manager-bootstrap.log"
        "/tmp/nixos-rebuild.log"
        "/tmp/home-manager-switch.log"
        "/tmp/flake-check.log"
        "/tmp/flake-update.log"
    )

    local cleaned=0
    for temp_file in "${temp_files[@]}"; do
        if [[ -f "$temp_file" ]]; then
            rm -f "$temp_file" 2>/dev/null && ((cleaned++))
        fi
    done

    if [[ $cleaned -gt 0 ]]; then
        print_success "Cleaned $cleaned temporary file(s)"
    else
        print_info "No temporary files to clean"
    fi
    echo ""

    # ========================================================================
    # 4. Verify Service Dependencies
    # ========================================================================
    print_info "Verifying service dependencies..."

    # Check if critical services can start their dependencies
    local services_with_deps=(
        "gitea"
        "ollama"
    )

    for service in "${services_with_deps[@]}"; do
        if systemctl list-unit-files | grep -q "^${service}.service"; then
            # Check if service has dependency issues
            if systemctl show "$service" --property=LoadState 2>/dev/null | grep -q "loaded"; then
                print_success "  $service: configuration loaded"
            else
                print_info "  $service: not loaded (will load on enable/start)"
            fi
        fi
    done
    echo ""

    # ========================================================================
    # 5. Update Command Cache
    # ========================================================================
    print_info "Updating command cache..."

    # Rehash command cache if using zsh
    if [[ "$SHELL" == *"zsh"* ]]; then
        print_info "Run 'rehash' or restart terminal to update zsh command cache"
    fi

    # For bash, suggest reloading profile
    if [[ "$SHELL" == *"bash"* ]]; then
        print_info "Run 'source ~/.bashrc' or restart terminal to update bash environment"
    fi
    echo ""

    print_success "Configuration activation finalized"
    print_info "Some changes may require a logout/login or reboot to take full effect"
    return 0
}
