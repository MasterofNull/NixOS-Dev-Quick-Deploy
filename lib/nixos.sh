#!/usr/bin/env bash
#
# NixOS Channel and Version Management
# Purpose: Manage NixOS channels and version selection
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/colors.sh → Color codes ($BLUE, $NC)
#
# Required Variables:
#   - DEFAULT_CHANNEL_TRACK → Channel preference (stable/unstable)
#
# Exports:
#   - derive_system_release_version() → Get current NixOS version
#   - normalize_channel_name() → Extract channel name from URL
#   - get_home_manager_flake_uri() → Get home-manager flake URI
#   - get_home_manager_package_ref() → Get home-manager package ref
#   - select_nixos_version() → Prompt user for NixOS version
#   - update_nixos_channels() → Update and synchronize channels
#
# ============================================================================

# ============================================================================
# Derive System Release Version
# ============================================================================
# Purpose: Get current NixOS version number
# Returns:
#   Current version (e.g., "24.11") or "25.05" as fallback
# ============================================================================
derive_system_release_version() {
    local raw

    if ! raw=$(nixos-version 2>/dev/null); then
        echo "25.05"
        return 0
    fi

    # Extract major.minor version (e.g., "24.11" from "24.11.20230101.abc123")
    raw=$(printf '%s' "$raw" | cut -d'.' -f1-2)
    raw=${raw%%pre*}  # Remove "pre" suffix
    raw=${raw%%-*}    # Remove "-" suffix

    if [[ -z "$raw" ]]; then
        echo "25.05"
    else
        echo "$raw"
    fi
}

# ============================================================================
# Normalize Channel Name
# ============================================================================
# Purpose: Extract clean channel name from URL or path
# Parameters:
#   $1 - Raw channel URL or path
# Returns:
#   Normalized channel name
#
# Examples:
#   "https://nixos.org/channels/nixos-24.11" → "nixos-24.11"
#   "https://github.com/nix-community/home-manager/archive/master.tar.gz" → "master"
# ============================================================================
normalize_channel_name() {
    local raw="$1"

    if [[ -z "$raw" ]]; then
        echo ""
        return 0
    fi

    # Extract basename
    raw="${raw##*/}"
    # Remove query string
    raw="${raw%%\?*}"
    # Remove archive extensions
    raw="${raw%.tar.gz}"
    raw="${raw%.tar.xz}"
    raw="${raw%.tar.bz2}"
    raw="${raw%.tar}"
    raw="${raw%.tgz}"
    raw="${raw%.zip}"

    echo "$raw"
}

# ============================================================================
# Get Home Manager Flake URI
# ============================================================================
# Purpose: Construct home-manager flake URI based on channel
# Returns:
#   Flake URI string
# ============================================================================
get_home_manager_flake_uri() {
    local ref="${HOME_MANAGER_CHANNEL_REF:-}"
    local base="github:nix-community/home-manager"

    if [[ -n "$ref" && "$ref" != "master" ]]; then
        echo "${base}?ref=${ref}"
    else
        echo "$base"
    fi
}

# ============================================================================
# Get Home Manager Package Reference
# ============================================================================
# Purpose: Get full package reference for home-manager
# Returns:
#   Package reference string (e.g., "github:nix-community/home-manager#home-manager")
# ============================================================================
get_home_manager_package_ref() {
    local uri
    uri=$(get_home_manager_flake_uri)
    echo "${uri}#home-manager"
}

# ============================================================================
# Select NixOS Version
# ============================================================================
# Purpose: Prompt user to select NixOS version or auto-select based on preference
# Sets:
#   SELECTED_NIXOS_VERSION - Global variable with selected version
# ============================================================================
select_nixos_version() {
    print_section "NixOS Version Selection"

    local track_preference="${DEFAULT_CHANNEL_TRACK,,}"
    local CURRENT_VERSION=$(derive_system_release_version)

    # Auto-select unstable if preference set
    if [[ "$track_preference" == "unstable" ]]; then
        print_info "Channel preference is set to unstable; automatically tracking nixos-unstable for latest AI tooling."
        print_info "Detected current system release: $CURRENT_VERSION"
        echo ""
        export SELECTED_NIXOS_VERSION="unstable"
        return 0
    fi

    # Get latest stable version
    local LATEST_STABLE="25.05"

    echo ""
    print_info "Current System Version:"
    print_warning "  NixOS $CURRENT_VERSION"
    echo ""

    print_info "Available Options:"
    print_info "  [1] Keep current version ($CURRENT_VERSION)"
    print_info "  [2] Upgrade to latest stable ($LATEST_STABLE) - RECOMMENDED"
    echo ""

    print_info "The latest stable version ($LATEST_STABLE) includes:"
    echo "  • Full COSMIC desktop support with excludePackages option"
    echo "  • Fixes for duplicate system applications"
    echo "  • Latest security patches and performance improvements"
    echo "  • nix-flatpak integration for declarative Flatpak management"
    echo ""

    # Only prompt if not already on latest version
    if [ "$CURRENT_VERSION" = "$LATEST_STABLE" ]; then
        print_success "System is already on latest stable version ($LATEST_STABLE)"
        echo ""
        export SELECTED_NIXOS_VERSION="$LATEST_STABLE"
        return 0
    fi

    # Prompt user for version selection
    read -p "$(echo -e ${BLUE}?${NC} Select version [1-2]: )" -r VERSION_CHOICE

    case "$VERSION_CHOICE" in
        1)
            export SELECTED_NIXOS_VERSION="$CURRENT_VERSION"
            print_info "Keeping current version: $CURRENT_VERSION"
            echo ""
            if [ "$CURRENT_VERSION" = "25.05" ]; then
                print_warning "Note: On NixOS 25.05, COSMIC duplicate apps issue cannot be fixed with excludePackages"
                print_info "      This feature is available in NixOS 25.11+"
                echo ""
            fi
            ;;
        2)
            export SELECTED_NIXOS_VERSION="$LATEST_STABLE"
            print_info "Upgrading to latest stable: $LATEST_STABLE"
            echo ""
            print_success "System will upgrade to NixOS $LATEST_STABLE"
            echo ""
            ;;
        *)
            print_error "Invalid selection. Please choose 1 or 2."
            exit 1
            ;;
    esac
}

# ============================================================================
# Update NixOS Channels
# ============================================================================
# Purpose: Update and synchronize NixOS and home-manager channels
# Sets:
#   SYNCHRONIZED_NIXOS_CHANNEL - NixOS channel name
#   SYNCHRONIZED_HOME_MANAGER_CHANNEL - Home manager channel name
#   HOME_MANAGER_CHANNEL_URL - Home manager channel URL
#   HOME_MANAGER_CHANNEL_REF - Home manager channel reference
# ============================================================================
update_nixos_channels() {
    print_info "Synchronizing NixOS and home-manager channels..."

    # Use selected version if available, otherwise auto-detect
    local TARGET_VERSION="${SELECTED_NIXOS_VERSION:-}"
    local track_preference="${DEFAULT_CHANNEL_TRACK,,}"

    if [ -z "$TARGET_VERSION" ]; then
        if [[ "$track_preference" == "unstable" ]]; then
            TARGET_VERSION="unstable"
            print_info "Auto-selecting nixos-unstable to keep AI toolchain packages current"
        else
            TARGET_VERSION=$(derive_system_release_version)
            print_info "Auto-detected NixOS version: $TARGET_VERSION"
        fi
    elif [[ "$track_preference" == "unstable" && "$TARGET_VERSION" != "unstable" ]]; then
        print_warning "Overriding requested NixOS version '$TARGET_VERSION' with nixos-unstable per channel preference"
        TARGET_VERSION="unstable"
    else
        print_info "Using selected NixOS version: $TARGET_VERSION"
    fi

    SELECTED_NIXOS_VERSION="$TARGET_VERSION"

    # Set the target channel URL
    local CURRENT_NIXOS_CHANNEL="https://nixos.org/channels/nixos-${TARGET_VERSION}"

    # Check if we need to upgrade channels
    local EXISTING_CHANNEL=$(sudo nix-channel --list | grep '^nixos' | awk '{print $2}')

    if [ -n "$EXISTING_CHANNEL" ] && [ "$EXISTING_CHANNEL" != "$CURRENT_NIXOS_CHANNEL" ]; then
        print_warning "Channel change detected"
        print_info "  From: $(basename $EXISTING_CHANNEL)"
        print_info "  To:   $(basename $CURRENT_NIXOS_CHANNEL)"
        echo ""
        sudo nix-channel --remove nixos || true
    fi

    # Use the target channel
    if [ -z "$EXISTING_CHANNEL" ]; then
        print_warning "No nixos channel found, setting up..."
        print_info "Setting channel based on selected version: $TARGET_VERSION"
    fi

    # Extract channel name from URL
    local NIXOS_CHANNEL_NAME=$(basename "$CURRENT_NIXOS_CHANNEL")
    print_info "Current NixOS channel: $NIXOS_CHANNEL_NAME"
    SYNCHRONIZED_NIXOS_CHANNEL="$NIXOS_CHANNEL_NAME"

    # Determine matching home-manager channel
    local HM_CHANNEL_NAME
    local HM_CHANNEL_URL

    if [[ "$NIXOS_CHANNEL_NAME" == "nixos-unstable" ]]; then
        # Unstable → master
        HM_CHANNEL_URL="https://github.com/nix-community/home-manager/archive/master.tar.gz"
        HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL_URL")
        HOME_MANAGER_CHANNEL_URL="$HM_CHANNEL_URL"
        HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
        print_info "Using home-manager ${HM_CHANNEL_NAME} (tracks unstable)"
    elif [[ "$NIXOS_CHANNEL_NAME" =~ nixos-([0-9]+\.[0-9]+) ]]; then
        # Extract version number (e.g., "24.11" from "nixos-24.11")
        local VERSION="${BASH_REMATCH[1]}"
        HM_CHANNEL_URL="https://github.com/nix-community/home-manager/archive/release-${VERSION}.tar.gz"
        HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL_URL")
        HOME_MANAGER_CHANNEL_URL="$HM_CHANNEL_URL"
        HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
        print_info "Using home-manager ${HM_CHANNEL_NAME} (matches nixos-${VERSION})"
    else
        print_error "Could not parse NixOS channel name: $NIXOS_CHANNEL_NAME"
        exit 1
    fi

    if [[ -z "$HOME_MANAGER_CHANNEL_REF" ]]; then
        HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
    fi

    if [[ -z "$HOME_MANAGER_CHANNEL_URL" ]]; then
        HOME_MANAGER_CHANNEL_URL="$HM_CHANNEL_URL"
    fi

    SYNCHRONIZED_HOME_MANAGER_CHANNEL="$HM_CHANNEL_NAME"

    print_success "Channel synchronization plan:"
    print_info "  NixOS:        $NIXOS_CHANNEL_NAME"
    print_info "  home-manager: $HM_CHANNEL_NAME"
    print_info "  ✓ Versions synchronized"
    echo ""

    # Ensure NixOS channel is set
    print_info "Ensuring NixOS channel is set..."
    if sudo nix-channel --add "$CURRENT_NIXOS_CHANNEL" nixos; then
        print_success "NixOS channel confirmed: $NIXOS_CHANNEL_NAME"
    else
        print_error "Failed to set NixOS channel"
        exit 1
    fi

    # Set user nixpkgs channel to MATCH system NixOS version
    print_info "Setting user nixpkgs channel to match system NixOS..."
    local USER_NIXPKGS_CHANNEL
    USER_NIXPKGS_CHANNEL=$(nix-channel --list | awk '/^nixpkgs\s/ {print $2}' | tail -n1)
    if [[ -n "$USER_NIXPKGS_CHANNEL" && "$USER_NIXPKGS_CHANNEL" != "$CURRENT_NIXOS_CHANNEL" ]]; then
        print_warning "Removing mismatched user nixpkgs channel ($(normalize_channel_name "$USER_NIXPKGS_CHANNEL"))"
        nix-channel --remove nixpkgs 2>/dev/null || true
    fi
    if nix-channel --add "$CURRENT_NIXOS_CHANNEL" nixpkgs; then
        print_success "User nixpkgs channel set to $NIXOS_CHANNEL_NAME"
    else
        print_error "Failed to set user nixpkgs channel"
        exit 1
    fi

    # Set home-manager channel to MATCH nixos version
    print_info "Setting home-manager channel to match NixOS..."
    local USER_HOME_MANAGER_CHANNEL
    USER_HOME_MANAGER_CHANNEL=$(nix-channel --list | awk '/^home-manager\s/ {print $2}' | tail -n1)
    if [[ -n "$USER_HOME_MANAGER_CHANNEL" && "$USER_HOME_MANAGER_CHANNEL" != "$HM_CHANNEL_URL" ]]; then
        print_warning "Removing mismatched home-manager channel ($(normalize_channel_name "$USER_HOME_MANAGER_CHANNEL"))"
        nix-channel --remove home-manager 2>/dev/null || true
    fi
    if nix-channel --add "$HM_CHANNEL_URL" home-manager; then
        print_success "home-manager channel set to $HM_CHANNEL_NAME"
    else
        print_error "Failed to set home-manager channel"
        exit 1
    fi

    # Update system channels (root) FIRST
    print_info "Updating system channels (this may take a few minutes)..."
    echo ""
    if sudo nix-channel --update 2>&1 | tee /tmp/nixos-channel-update.log; then
        print_success "NixOS system channels updated"
    else
        print_error "System channel update failed"
        print_info "Log saved to: /tmp/nixos-channel-update.log"
        exit 1
    fi
    echo ""

    # Update user channels (home-manager)
    print_info "Updating user channels (home-manager)..."
    echo ""
    if nix-channel --update 2>&1 | tee /tmp/home-manager-channel-update.log; then
        print_success "User channels updated successfully"
    else
        print_error "User channel update failed"
        print_info "Log saved to: /tmp/home-manager-channel-update.log"
        exit 1
    fi
    echo ""

    # Verify synchronization
    print_info "Verifying channel synchronization..."

    local SYSTEM_CHANNEL
    SYSTEM_CHANNEL=$(sudo nix-channel --list | awk '/^nixos\s/ { print $2 }' | tail -n1)
    local USER_CHANNEL
    USER_CHANNEL=$(nix-channel --list | awk '/^home-manager\s/ { print $2 }' | tail -n1)

    if [[ -z "$SYSTEM_CHANNEL" ]]; then
        print_warning "Unable to determine current nixos channel"
    else
        print_info "  nixos channel:        $(normalize_channel_name "$SYSTEM_CHANNEL")"
    fi

    if [[ -z "$USER_CHANNEL" ]]; then
        print_warning "Unable to determine current home-manager channel"
    else
        print_info "  home-manager channel: $(normalize_channel_name "$USER_CHANNEL")"
    fi

    if [[ -z "$SYSTEM_CHANNEL" || -z "$USER_CHANNEL" ]]; then
        print_warning "Could not verify channel versions"
        print_info "Will proceed but may encounter compatibility issues"
    fi

    echo ""
}
