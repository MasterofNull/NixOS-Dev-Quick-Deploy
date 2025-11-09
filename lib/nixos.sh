#!/usr/bin/env bash
#
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
#   - resolve_nixos_release_version() → Map requested versions to a supported NixOS release channel
#   - emit_nixos_channel_fallback_notice() → Display fallback messaging when NixOS channel downgrades
#   - resolve_home_manager_release_version() → Map requested versions to a supported home-manager release
#   - get_home_manager_flake_uri() → Get home-manager flake URI
#   - get_home_manager_package_ref() → Get home-manager package ref
#   - select_nixos_version() → Prompt user for NixOS version
#   - emit_home_manager_fallback_notice() → Display fallback messaging when release mapping downgrades
#   - update_nixos_channels() → Update and synchronize channels
#
# ============================================================================

# Supported release list (descending order) shared by both NixOS and home-manager
SUPPORTED_NIX_RELEASES=("25.05" "24.11" "24.05" "23.11")

# Track fallback context so callers can emit user-facing notices without
# polluting resolver stdout (which is frequently used inside command
# substitutions).
: "${NIXOS_CHANNEL_FALLBACK_REQUESTED:=}"
: "${NIXOS_CHANNEL_FALLBACK_RESOLVED:=}"
: "${HOME_MANAGER_FALLBACK_REQUESTED:=}"
: "${HOME_MANAGER_FALLBACK_RESOLVED:=}"

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
# Resolve NixOS Release Version
# ============================================================================
# Purpose: Map requested NixOS versions to an existing release channel.
# Returns:
#   Matching release version (e.g., "25.05") or closest supported entry.
# ============================================================================
resolve_nixos_release_version() {
    local requested="$1"
    local normalized="$requested"

    if [[ -z "$normalized" ]]; then
        normalized="${SUPPORTED_NIX_RELEASES[0]}"
    fi

    if [[ "$normalized" == "unstable" || "$normalized" == "nixos-unstable" ]]; then
        NIXOS_CHANNEL_FALLBACK_REQUESTED=""
        NIXOS_CHANNEL_FALLBACK_RESOLVED=""
        echo "unstable"
        return 0
    fi

    normalized="${normalized#nixos-}"
    normalized="${normalized#release-}"

    local -a supported_releases=("${SUPPORTED_NIX_RELEASES[@]}")
    local newest="${supported_releases[0]}"
    local oldest="${supported_releases[${#supported_releases[@]}-1]}"
    local resolved=""

    if [[ "$normalized" =~ ^[0-9]+\.[0-9]+$ ]]; then
        for version in "${supported_releases[@]}"; do
            if [[ "$version" == "$normalized" ]]; then
                resolved="$version"
                break
            fi
        done

        if [[ -z "$resolved" ]]; then
            local requested_num="${normalized//./}"
            for version in "${supported_releases[@]}"; do
                local version_num="${version//./}"
                if (( version_num <= requested_num )); then
                    resolved="$version"
                    break
                fi
            done
        fi
    fi

    if [[ -z "$resolved" ]]; then
        resolved="$oldest"
    fi

    NIXOS_CHANNEL_FALLBACK_REQUESTED=""
    NIXOS_CHANNEL_FALLBACK_RESOLVED=""

    if [[ "$normalized" != "$resolved" ]]; then
        NIXOS_CHANNEL_FALLBACK_REQUESTED="$normalized"
        NIXOS_CHANNEL_FALLBACK_RESOLVED="$resolved"
    fi

    echo "$resolved"
}

emit_nixos_channel_fallback_notice() {
    if [[ -n "${NIXOS_CHANNEL_FALLBACK_REQUESTED:-}" && -n "${NIXOS_CHANNEL_FALLBACK_RESOLVED:-}" ]]; then
        print_warning "nixos-${NIXOS_CHANNEL_FALLBACK_REQUESTED} channel not yet available upstream."
        print_info "Using nixos-${NIXOS_CHANNEL_FALLBACK_RESOLVED} until the requested release is published."
        NIXOS_CHANNEL_FALLBACK_REQUESTED=""
        NIXOS_CHANNEL_FALLBACK_RESOLVED=""
    fi
}

# ============================================================================
# Resolve Home Manager Release Version
# ============================================================================
# Purpose: Map requested NixOS versions to an existing home-manager release.
# Rationale: Home Manager occasionally lags behind new NixOS releases (e.g.,
# 25.11). Without this guard, we generate flake references to branches that
# do not exist upstream, which causes nixos-rebuild dry runs to fail before
# any real validation happens.
# Returns:
#   Matching release version (e.g., "25.05") or the closest supported entry.
# ============================================================================
resolve_home_manager_release_version() {
    local requested="$1"
    local -a supported_releases=("${SUPPORTED_NIX_RELEASES[@]}")
    local newest="${supported_releases[0]}"
    local oldest="${supported_releases[${#supported_releases[@]}-1]}"
    local resolved=""

    if [[ -z "$requested" ]]; then
        echo "$newest"
        return 0
    fi

    for version in "${supported_releases[@]}"; do
        if [[ "$version" == "$requested" ]]; then
            resolved="$version"
            break
        fi
    done

    if [[ -z "$resolved" ]]; then
        local requested_num="${requested//./}"
        for version in "${supported_releases[@]}"; do
            local version_num="${version//./}"
            if (( version_num <= requested_num )); then
                resolved="$version"
                break
            fi
        done
    fi

    if [[ -z "$resolved" ]]; then
        resolved="$oldest"
    fi

    HOME_MANAGER_FALLBACK_REQUESTED=""
    HOME_MANAGER_FALLBACK_RESOLVED=""

    if [[ -n "$requested" && "$resolved" != "$requested" ]]; then
        HOME_MANAGER_FALLBACK_REQUESTED="$requested"
        HOME_MANAGER_FALLBACK_RESOLVED="$resolved"
    fi

    echo "$resolved"
}

emit_home_manager_fallback_notice() {
    if [[ -n "${HOME_MANAGER_FALLBACK_REQUESTED:-}" && -n "${HOME_MANAGER_FALLBACK_RESOLVED:-}" ]]; then
        print_warning "home-manager release-${HOME_MANAGER_FALLBACK_REQUESTED} not available upstream."
        print_info "Falling back to release-${HOME_MANAGER_FALLBACK_RESOLVED} until a matching branch is published."
        HOME_MANAGER_FALLBACK_REQUESTED=""
        HOME_MANAGER_FALLBACK_RESOLVED=""
    fi
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

    local resolved_target
    resolved_target=$(resolve_nixos_release_version "$TARGET_VERSION")
    emit_nixos_channel_fallback_notice
    TARGET_VERSION="$resolved_target"
    SELECTED_NIXOS_VERSION="$TARGET_VERSION"

    # Set the target channel URL
    local CURRENT_NIXOS_CHANNEL
    if [[ "$TARGET_VERSION" == "unstable" ]]; then
        CURRENT_NIXOS_CHANNEL="https://nixos.org/channels/nixos-unstable"
    else
        CURRENT_NIXOS_CHANNEL="https://nixos.org/channels/nixos-${TARGET_VERSION}"
    fi

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
        local HM_RELEASE_VERSION
        HM_RELEASE_VERSION=$(resolve_home_manager_release_version "$VERSION")
        HM_CHANNEL_URL="https://github.com/nix-community/home-manager/archive/release-${HM_RELEASE_VERSION}.tar.gz"
        HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL_URL")
        HOME_MANAGER_CHANNEL_URL="$HM_CHANNEL_URL"
        HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
        if [[ "$HM_RELEASE_VERSION" == "$VERSION" ]]; then
            print_info "Using home-manager ${HM_CHANNEL_NAME} (matches nixos-${VERSION})"
        else
            print_info "Using home-manager ${HM_CHANNEL_NAME} (closest available for nixos-${VERSION})"
        fi
        emit_home_manager_fallback_notice
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
