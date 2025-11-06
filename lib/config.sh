#!/usr/bin/env bash
#
# Configuration Generation
# Purpose: Generate NixOS and home-manager configurations from templates
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/nixos.sh → derive_system_release_version(), normalize_channel_name()
#
# Required Variables:
#   - HM_CONFIG_DIR → Home manager config directory
#   - HOME_MANAGER_FILE → Path to home.nix
#   - FLAKE_FILE → Path to flake.nix
#   - SYSTEM_CONFIG_FILE → Path to configuration.nix
#   - GPU_TYPE → Detected GPU type
#
# Exports:
#   - generate_nixos_system_config() → Generate system configuration
#   - create_home_manager_config() → Generate home-manager configuration
#   - validate_system_build_stage() → Validate configuration with dry-build
#
# ============================================================================

# ============================================================================
# Generate NixOS System Configuration
# ============================================================================
# Purpose: Generate NixOS configuration files from templates
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
generate_nixos_system_config() {
    print_section "Generating NixOS Configuration"

    # ========================================================================
    # Detect System Information
    # ========================================================================
    local HOSTNAME=$(hostname)
    local NIXOS_VERSION=$(derive_system_release_version)
    local STATE_VERSION="$NIXOS_VERSION"
    local SYSTEM_ARCH=$(uname -m)

    # Convert arch names
    case "$SYSTEM_ARCH" in
        x86_64) SYSTEM_ARCH="x86_64-linux" ;;
        aarch64) SYSTEM_ARCH="aarch64-linux" ;;
        *) SYSTEM_ARCH="x86_64-linux" ;;
    esac

    print_info "System: $HOSTNAME"
    print_info "Architecture: $SYSTEM_ARCH"
    print_info "NixOS Version: $NIXOS_VERSION"
    print_info "State Version: $STATE_VERSION"
    echo ""

    # ========================================================================
    # Determine Channels
    # ========================================================================
    local NIXOS_CHANNEL_NAME="${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${NIXOS_VERSION}}"
    local HM_CHANNEL_NAME="${SYNCHRONIZED_HOME_MANAGER_CHANNEL:-release-${NIXOS_VERSION}}"

    # If using unstable, adjust home-manager channel
    if [[ "$NIXOS_CHANNEL_NAME" == "nixos-unstable" ]]; then
        HM_CHANNEL_NAME="master"
    fi

    print_info "NixOS channel: $NIXOS_CHANNEL_NAME"
    print_info "Home-manager channel: $HM_CHANNEL_NAME"
    echo ""

    # ========================================================================
    # Detect Timezone and Locale
    # ========================================================================
    local TIMEZONE="${SELECTED_TIMEZONE:-$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")}"
    local LOCALE=$(localectl status | grep "LANG=" | cut -d= -f2 | tr -d ' ' 2>/dev/null || echo "en_US.UTF-8")

    print_info "Timezone: $TIMEZONE"
    print_info "Locale: $LOCALE"
    echo ""

    # ========================================================================
    # Ensure Config Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating configuration directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
        if [[ ! -d "$PARENT_DIR" ]]; then
            if ! mkdir -p "$PARENT_DIR"; then
                print_error "Failed to create parent directory: $PARENT_DIR"
                return 1
            fi
        fi

        # Create the config directory
        if ! mkdir -p "$HM_CONFIG_DIR"; then
            print_error "Failed to create directory: $HM_CONFIG_DIR"
            return 1
        fi

        # Set ownership to current user
        # Use sudo if we're running as root but need to set ownership to a non-root user
        if [[ "$EUID" -eq 0 ]] && [[ -n "$SUDO_USER" ]]; then
            # Running with sudo - set ownership to the original user
            chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        elif [[ "$EUID" -eq 0 ]]; then
            # Running as root without sudo - set to PRIMARY_USER
            chown -R "$PRIMARY_USER:$(id -gn "$PRIMARY_USER" 2>/dev/null || echo "users")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        fi
        # If running as normal user, ownership is already correct from mkdir

        print_success "Created configuration directory"
    else
        print_success "Configuration directory exists: $HM_CONFIG_DIR"
    fi
    echo ""

    # ========================================================================
    # Backup Existing Configurations
    # ========================================================================
    local BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    if [[ -f "$SYSTEM_CONFIG_FILE" ]]; then
        local BACKUP_FILE="$SYSTEM_CONFIG_FILE.backup.$BACKUP_TIMESTAMP"
        cp "$SYSTEM_CONFIG_FILE" "$BACKUP_FILE" 2>/dev/null || true
        print_success "Backed up configuration.nix"
    fi

    if [[ -f "$FLAKE_FILE" ]]; then
        mkdir -p "$HM_CONFIG_DIR/backup"
        cp "$FLAKE_FILE" "$HM_CONFIG_DIR/backup/flake.nix.backup.$BACKUP_TIMESTAMP" 2>/dev/null || true
        print_success "Backed up flake.nix"
    fi

    # ========================================================================
    # Generate Hardware Configuration
    # ========================================================================
    print_info "Generating hardware configuration..."
    if ! materialize_hardware_configuration; then
        print_warning "Hardware configuration generation had issues"
        # Continue anyway as it might already exist
    fi

    # ========================================================================
    # Copy Configuration Template
    # ========================================================================
    local TEMPLATE_DIR="${SCRIPT_DIR}/templates"
    if [[ ! -d "$TEMPLATE_DIR" ]]; then
        print_error "Template directory not found: $TEMPLATE_DIR"
        return 1
    fi

    local CONFIG_TEMPLATE="$TEMPLATE_DIR/configuration.nix"
    if [[ ! -f "$CONFIG_TEMPLATE" ]]; then
        print_error "Configuration template not found: $CONFIG_TEMPLATE"
        return 1
    fi

    print_info "Copying configuration template..."
    if ! cp "$CONFIG_TEMPLATE" "$SYSTEM_CONFIG_FILE"; then
        print_error "Failed to copy configuration template"
        return 1
    fi

    # ========================================================================
    # Replace Placeholders in configuration.nix
    # ========================================================================
    print_info "Customizing configuration..."

    # GPU monitoring packages
    local GPU_MONITORING_PACKAGES="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES="[ pkgs.radeontop pkgs.amdgpu_top ]"
    elif [[ "$GPU_TYPE" == "nvidia" ]]; then
        GPU_MONITORING_PACKAGES="[ pkgs.nvtop ]"
    fi

    # Use sed to replace placeholders
    sed -i "s|HOSTNAME_PLACEHOLDER|$HOSTNAME|g" "$SYSTEM_CONFIG_FILE"
    sed -i "s|TIMEZONE_PLACEHOLDER|$TIMEZONE|g" "$SYSTEM_CONFIG_FILE"
    sed -i "s|LOCALE_PLACEHOLDER|$LOCALE|g" "$SYSTEM_CONFIG_FILE"
    sed -i "s|STATEVERSION_PLACEHOLDER|$STATE_VERSION|g" "$SYSTEM_CONFIG_FILE"
    sed -i "s|USERNAME_PLACEHOLDER|$USER|g" "$SYSTEM_CONFIG_FILE"
    sed -i "s|@GPU_MONITORING_PACKAGES@|$GPU_MONITORING_PACKAGES|g" "$SYSTEM_CONFIG_FILE"

    print_success "Generated configuration.nix"
    echo ""

    # ========================================================================
    # Generate Flake Configuration
    # ========================================================================
    print_info "Generating flake configuration..."

    local FLAKE_TEMPLATE="$TEMPLATE_DIR/flake.nix"
    if [[ ! -f "$FLAKE_TEMPLATE" ]]; then
        print_error "Flake template not found: $FLAKE_TEMPLATE"
        return 1
    fi

    if ! cp "$FLAKE_TEMPLATE" "$FLAKE_FILE"; then
        print_error "Failed to copy flake template"
        return 1
    fi

    # Replace flake placeholders
    sed -i "s|NIXPKGS_CHANNEL_PLACEHOLDER|$NIXOS_CHANNEL_NAME|g" "$FLAKE_FILE"
    sed -i "s|HM_CHANNEL_PLACEHOLDER|$HM_CHANNEL_NAME|g" "$FLAKE_FILE"
    sed -i "s|HOSTNAME_PLACEHOLDER|$HOSTNAME|g" "$FLAKE_FILE"
    sed -i "s|HOME_USERNAME_PLACEHOLDER|$USER|g" "$FLAKE_FILE"
    sed -i "s|SYSTEM_PLACEHOLDER|$SYSTEM_ARCH|g" "$FLAKE_FILE"

    print_success "Generated flake.nix"
    echo ""

    print_success "NixOS system configuration generated successfully"
    print_info "Location: $SYSTEM_CONFIG_FILE"
    print_info "Flake: $FLAKE_FILE"
    echo ""

    return 0
}

# ============================================================================
# Create Home Manager Configuration
# ============================================================================
# Purpose: Generate home-manager configuration from template
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
create_home_manager_config() {
    print_section "Creating Home Manager Configuration"

    # ========================================================================
    # Detect Versions
    # ========================================================================
    local NIXOS_CHANNEL=$(sudo nix-channel --list 2>/dev/null | grep '^nixos' | awk '{print $2}')
    local HM_CHANNEL=$(nix-channel --list 2>/dev/null | grep 'home-manager' | awk '{print $2}')
    local STATE_VERSION

    # Extract version from nixos channel
    if [[ "$NIXOS_CHANNEL" =~ nixos-([0-9]+\.[0-9]+) ]]; then
        STATE_VERSION="${BASH_REMATCH[1]}"
        print_info "Detected stateVersion: $STATE_VERSION"
    elif [[ "$NIXOS_CHANNEL" == *"unstable"* ]]; then
        STATE_VERSION=$(derive_system_release_version)
        print_info "Using unstable channel, stateVersion: $STATE_VERSION"
    else
        STATE_VERSION=$(derive_system_release_version)
        print_warning "Using system version: $STATE_VERSION"
    fi

    local NIXOS_CHANNEL_NAME=$(basename "$NIXOS_CHANNEL" 2>/dev/null || echo "nixos-${STATE_VERSION}")
    local HM_CHANNEL_NAME="${HOME_MANAGER_CHANNEL_REF:-$(normalize_channel_name "$HM_CHANNEL")}"

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        HM_CHANNEL_NAME="release-${STATE_VERSION}"
    fi

    print_info "NixOS channel: $NIXOS_CHANNEL_NAME"
    print_info "Home-manager channel: $HM_CHANNEL_NAME"
    echo ""

    # ========================================================================
    # Ensure Directory Exists
    # ========================================================================
    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        print_info "Creating home-manager directory: $HM_CONFIG_DIR"

        # Create parent directory first if it doesn't exist
        local PARENT_DIR=$(dirname "$HM_CONFIG_DIR")
        if [[ ! -d "$PARENT_DIR" ]]; then
            if ! mkdir -p "$PARENT_DIR"; then
                print_error "Failed to create parent directory: $PARENT_DIR"
                return 1
            fi
        fi

        # Create the config directory
        if ! mkdir -p "$HM_CONFIG_DIR"; then
            print_error "Failed to create directory: $HM_CONFIG_DIR"
            return 1
        fi

        # Set ownership to current user
        # Use sudo if we're running as root but need to set ownership to a non-root user
        if [[ "$EUID" -eq 0 ]] && [[ -n "$SUDO_USER" ]]; then
            # Running with sudo - set ownership to the original user
            chown -R "$SUDO_USER:$(id -gn "$SUDO_USER")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        elif [[ "$EUID" -eq 0 ]]; then
            # Running as root without sudo - set to PRIMARY_USER
            chown -R "$PRIMARY_USER:$(id -gn "$PRIMARY_USER" 2>/dev/null || echo "users")" "$HM_CONFIG_DIR" || print_warning "Could not set ownership of $HM_CONFIG_DIR"
        fi
        # If running as normal user, ownership is already correct from mkdir

        print_success "Created home-manager directory"
    fi

    # ========================================================================
    # Backup Existing Configuration
    # ========================================================================
    if [[ -f "$HOME_MANAGER_FILE" ]]; then
        local BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        local BACKUP_DIR="$HM_CONFIG_DIR/backup"
        mkdir -p "$BACKUP_DIR"

        cp "$HOME_MANAGER_FILE" "$BACKUP_DIR/home.nix.backup.$BACKUP_TIMESTAMP" 2>/dev/null || true
        print_success "Backed up existing home.nix"
    fi

    # ========================================================================
    # Copy Template
    # ========================================================================
    local TEMPLATE_DIR="${SCRIPT_DIR}/templates"
    local HOME_TEMPLATE="$TEMPLATE_DIR/home.nix"

    if [[ ! -f "$HOME_TEMPLATE" ]]; then
        print_error "Home template not found: $HOME_TEMPLATE"
        return 1
    fi

    print_info "Creating home.nix from template..."
    print_info "  Source: $HOME_TEMPLATE"
    print_info "  Destination: $HOME_MANAGER_FILE"

    if ! cp "$HOME_TEMPLATE" "$HOME_MANAGER_FILE"; then
        print_error "Failed to copy home template"
        print_error "  Check if source exists: $([ -f "$HOME_TEMPLATE" ] && echo 'YES' || echo 'NO')"
        print_error "  Check if destination dir exists: $([ -d "$(dirname "$HOME_MANAGER_FILE")" ] && echo 'YES' || echo 'NO')"
        print_error "  Check if destination dir is writable: $([ -w "$(dirname "$HOME_MANAGER_FILE")" ] && echo 'YES' || echo 'NO')"
        return 1
    fi

    # Verify the file was actually created
    if [[ ! -f "$HOME_MANAGER_FILE" ]]; then
        print_error "home.nix was not created at: $HOME_MANAGER_FILE"
        return 1
    fi

    # ========================================================================
    # Replace Placeholders
    # ========================================================================
    local TEMPLATE_HASH=$(echo -n "AIDB-v4.0-packages-v${SCRIPT_VERSION:-4.0.0}" | sha256sum | cut -d' ' -f1 | cut -c1-16)
    local DEFAULT_EDITOR="${DEFAULT_EDITOR:-nano}"

    # GPU monitoring packages
    local GPU_MONITORING_PACKAGES="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES="[ radeontop amdgpu_top ]"
    elif [[ "$GPU_TYPE" == "nvidia" ]]; then
        GPU_MONITORING_PACKAGES="[ nvtop ]"
    fi

    print_info "Customizing home.nix..."
    sed -i "s|VERSIONPLACEHOLDER|${SCRIPT_VERSION:-4.0.0}|g" "$HOME_MANAGER_FILE"
    sed -i "s|HASHPLACEHOLDER|$TEMPLATE_HASH|g" "$HOME_MANAGER_FILE"
    sed -i "s|HOMEUSERNAME|$USER|g" "$HOME_MANAGER_FILE"
    sed -i "s|HOMEDIR|$HOME|g" "$HOME_MANAGER_FILE"
    sed -i "s|STATEVERSION_PLACEHOLDER|$STATE_VERSION|g" "$HOME_MANAGER_FILE"
    sed -i "s|@GPU_MONITORING_PACKAGES@|$GPU_MONITORING_PACKAGES|g" "$HOME_MANAGER_FILE"

    # Ensure flake.nix is updated if it exists (may have been created by generate_nixos_system_config)
    if [[ -f "$FLAKE_FILE" ]]; then
        sed -i "s|HOME_USERNAME_PLACEHOLDER|$USER|g" "$FLAKE_FILE"
        print_success "Updated flake.nix with username"
    fi

    # ========================================================================
    # Final Verification
    # ========================================================================
    if [[ ! -f "$HOME_MANAGER_FILE" ]]; then
        print_error "VERIFICATION FAILED: home.nix does not exist after creation"
        print_error "Expected location: $HOME_MANAGER_FILE"
        return 1
    fi

    # Check file is readable
    if [[ ! -r "$HOME_MANAGER_FILE" ]]; then
        print_error "VERIFICATION FAILED: home.nix exists but is not readable"
        return 1
    fi

    # Check file has content
    local file_size=$(stat -c%s "$HOME_MANAGER_FILE" 2>/dev/null || echo "0")
    if [[ "$file_size" -eq 0 ]]; then
        print_error "VERIFICATION FAILED: home.nix is empty"
        return 1
    fi

    print_success "Created home.nix"
    print_info "Location: $HOME_MANAGER_FILE"
    print_info "File size: $file_size bytes"
    echo ""

    return 0
}

# ============================================================================
# Materialize Hardware Configuration
# ============================================================================
# Purpose: Generate hardware-configuration.nix
# Returns:
#   0 - Success
#   1 - Failure
# ============================================================================
materialize_hardware_configuration() {
    local HARDWARE_CONFIG="${HARDWARE_CONFIG_FILE:-$HM_CONFIG_DIR/hardware-configuration.nix}"

    # Check if already exists
    if [[ -f "$HARDWARE_CONFIG" ]]; then
        print_success "Hardware configuration already exists"
        return 0
    fi

    # Generate using nixos-generate-config
    print_info "Generating hardware configuration..."
    local TEMP_DIR=$(mktemp -d)

    if sudo nixos-generate-config --dir "$TEMP_DIR" --show-hardware-config > "$HARDWARE_CONFIG" 2>/dev/null; then
        chown "$USER:$(id -gn)" "$HARDWARE_CONFIG" 2>/dev/null || true
        print_success "Generated hardware-configuration.nix"
        rm -rf "$TEMP_DIR"
        return 0
    else
        print_warning "Could not generate hardware configuration"
        rm -rf "$TEMP_DIR"
        return 1
    fi
}

# ============================================================================
# Validate System Build Stage
# ============================================================================
# Purpose: Perform dry-run build to validate configuration
# Returns:
#   0 - Success (validation passed or warnings only)
#   1 - Failure (critical errors)
# ============================================================================
validate_system_build_stage() {
    print_section "Validating Configuration"

    local target_host=$(hostname)
    local log_path="/tmp/nixos-rebuild-dry-build.log"

    print_info "Performing dry-run build validation..."
    print_info "This checks for syntax errors and missing dependencies"
    print_info "Command: sudo nixos-rebuild dry-build --flake \"$HM_CONFIG_DIR#$target_host\""
    echo ""

    # Run dry-build (doesn't actually build, just evaluates)
    if sudo nixos-rebuild dry-build --flake "$HM_CONFIG_DIR#$target_host" 2>&1 | tee "$log_path"; then
        print_success "Configuration validation passed!"
        print_info "Log saved to: $log_path"
        echo ""
        return 0
    else
        local exit_code=$?
        print_warning "Validation had issues (exit code: $exit_code)"
        print_info "Log saved to: $log_path"
        print_info "Review the log for details"
        echo ""

        # Check if it's a critical error or just warnings
        if grep -qi "error:" "$log_path"; then
            print_error "Critical errors found in configuration"
            print_info "Please fix the errors before proceeding"
            return 1
        else
            print_warning "Warnings found but no critical errors"
            print_info "Proceeding with deployment"
            return 0
        fi
    fi
}
