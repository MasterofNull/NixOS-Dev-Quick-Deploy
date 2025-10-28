#!/usr/bin/env bash
#
# NixOS Quick Deploy for AIDB Development
# Purpose: Install ALL packages and tools needed for AIDB development
# Scope: Complete system setup - ready for AIDB deployment
# What it does: Installs Podman, PostgreSQL, Python, Nix tools, modern CLI tools
# What it does NOT do: Initialize AIDB database or start containers
# Author: AI Agent
# Created: 2025-10-23
# Version: 2.1.1 - Fixed Flatpak integration + automatic flake.lock updates
#

# Error handling: Exit on undefined variable, catch errors in pipes
set -u
set -o pipefail

# Global state tracking
SYSTEM_CONFIG_BACKUP=""
HOME_MANAGER_BACKUP=""
HOME_MANAGER_CHANNEL_REF=""
HOME_MANAGER_CHANNEL_URL=""

# Script version for change tracking
SCRIPT_VERSION="2.1.1"
VERSION_FILE="$HOME/.cache/nixos-quick-deploy-version"

# Force update flag (set via --force-update)
FORCE_UPDATE=false

# Trap errors and interrupts for cleanup
trap 'error_handler $? $LINENO' ERR
trap 'interrupt_handler' INT TERM

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
HM_CONFIG_DIR="$HOME/.config/home-manager"
HM_CONFIG_FILE="$HM_CONFIG_DIR/home.nix"

# ============================================================================
# Error Handling & Cleanup Functions
# ============================================================================

error_handler() {
    local exit_code=$1
    local line_number=$2

    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║${NC}  ERROR: Deployment Failed - Starting Cleanup                 ${RED}║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Error Details:${NC}"
    echo -e "  Exit Code: ${RED}$exit_code${NC}"
    echo -e "  Line: ${RED}$line_number${NC}"
    echo -e "  Function: ${RED}${FUNCNAME[1]:-main}${NC}"
    echo ""

    cleanup_on_failure
    show_fresh_start_instructions
    exit $exit_code
}

interrupt_handler() {
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║${NC}  INTERRUPTED: Deployment Cancelled - Starting Cleanup         ${YELLOW}║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    cleanup_on_failure
    show_fresh_start_instructions
    exit 130
}

cleanup_on_failure() {
    echo -e "${BLUE}Handling deployment failure...${NC}"
    echo ""

    # CRITICAL: DO NOT remove Claude/VSCodium - these are essential for recovery
    echo -e "${YELLOW}⚠${NC} Deployment failed, but preserving critical functionality:"
    echo -e "${GREEN}✓${NC} Claude Code installation - PRESERVED"
    echo -e "${GREEN}✓${NC} VSCodium configuration - PRESERVED"
    echo -e "${GREEN}✓${NC} Wrapper scripts - PRESERVED"
    echo ""

    # Only restore system configuration if backup exists
    # DO NOT restore home-manager - partial installation is better than none
    if [ -n "$SYSTEM_CONFIG_BACKUP" ] && [ -f "$SYSTEM_CONFIG_BACKUP" ]; then
        echo -e "${BLUE}→${NC} System configuration backup available at:"
        echo -e "   ${SYSTEM_CONFIG_BACKUP}"
        echo -e "${YELLOW}→${NC} NOT auto-restoring to preserve partial progress"
        echo -e "${BLUE}ℹ${NC} To manually restore: sudo cp $SYSTEM_CONFIG_BACKUP /etc/nixos/configuration.nix"
    fi

    if [ -n "$HOME_MANAGER_BACKUP" ] && [ -f "$HOME_MANAGER_BACKUP" ]; then
        echo -e "${BLUE}→${NC} Home-manager backup available at:"
        echo -e "   ${HOME_MANAGER_BACKUP}"
        echo -e "${YELLOW}→${NC} NOT auto-restoring to preserve partial progress"
        echo -e "${BLUE}ℹ${NC} To manually restore: cp $HOME_MANAGER_BACKUP $HM_CONFIG_FILE"
    fi

    echo ""
    echo -e "${GREEN}Safe cleanup complete - critical tools preserved.${NC}"
}

show_fresh_start_instructions() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  Recovery Instructions                                        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}IMPORTANT: Claude Code and VSCodium have been PRESERVED!${NC}"
    echo ""
    echo -e "${YELLOW}To diagnose and fix the issue:${NC}"
    echo ""
    echo -e "${YELLOW}1. Review the error above${NC}"
    echo "   Common issues:"
    echo "   • Duplicate nix.settings.experimental-features"
    echo "     Fix: Edit /etc/nixos/configuration.nix, keep only one definition"
    echo ""
    echo "   • Git package conflict (locale files)"
    echo "     Fix: nix-env -e git"
    echo ""
    echo "   • Network connection problems"
    echo "     Fix: Check connection, retry with stable internet"
    echo ""
    echo "   • Disk space full"
    echo "     Fix: nix-collect-garbage -d"
    echo ""
    echo -e "${YELLOW}2. Check for conflicting packages (old deployment):${NC}"
    echo "   # List nix-env packages (should be empty!)"
    echo "   nix-env -q"
    echo ""
    echo "   # Remove all nix-env packages"
    echo "   nix-env -e '.*' --remove-all"
    echo ""
    echo -e "${YELLOW}3. Review available backups (NOT auto-restored):${NC}"
    echo "   ls -lt ~/.config/home-manager/home.nix.backup.*"
    echo "   ls -lt ~/.config/home-manager/configuration.nix.backup.*"                                       #/etc/nixos/configuration.nix.backup.*"
    echo ""
    echo -e "${YELLOW}4. Read the recovery guide:${NC}"
    echo "   cat ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy/RECOVERY-GUIDE.md"
    echo ""
    echo -e "${YELLOW}5. After fixing the issue, re-run deployment:${NC}"
    echo "   cd ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy"
    echo "   ./nixos-quick-deploy.sh"
    echo ""
    echo -e "${GREEN}✓ The script preserves progress and is safe to re-run.${NC}"
    echo -e "${GREEN}✓ Claude Code will remain functional even after failure.${NC}"
    echo ""
}

# ============================================================================
# Helper Functions
# ============================================================================

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --force-update    Force recreation of all configurations"
    echo "                        (ignores existing configs and applies updates)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Normal run (smart change detection)"
    echo "  $0 --force-update     # Force update all configs"
    echo ""
}

print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  NixOS Quick Deploy for AIDB Development v${SCRIPT_VERSION}        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    echo -e "${YELLOW}This installs ALL prerequisites for AIDB (Podman, PostgreSQL, etc.)${NC}"
    echo -e "${YELLOW}After this completes, you'll be ready to run aidb-quick-setup.sh${NC}\n"
}

print_section() {
    echo -e "\n${GREEN}▶ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

normalize_channel_name() {
    local raw="$1"

    if [[ -z "$raw" ]]; then
        echo ""
        return 0
    fi

    raw="${raw##*/}"
    raw="${raw%%\?*}"
    raw="${raw%.tar.gz}"
    raw="${raw%.tar.xz}"
    raw="${raw%.tar.bz2}"
    raw="${raw%.tar}"
    raw="${raw%.tgz}"
    raw="${raw%.zip}"

    echo "$raw"
}

confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e ${BLUE}?${NC} $prompt)" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}

prompt_user() {
    local prompt="$1"
    local default="${2:-}"
    local response

    if [[ -n "$default" ]]; then
        read -p "$(echo -e ${BLUE}?${NC} $prompt [$default]: )" response
        echo "${response:-$default}"
    else
        read -p "$(echo -e ${BLUE}?${NC} $prompt: )" response
        echo "$response"
    fi
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_prerequisites() {
    print_section "Checking Prerequisites"

    # Check NixOS
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    # Detect and handle old deployment method artifacts
    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="/home/$USER/Documents/nixos-quick-deploy.sh"
    local FOUND_OLD_ARTIFACTS=false

    if [ -f "$OLD_SCRIPT" ]; then
        print_warning "Found old deployment script at: $OLD_SCRIPT"
        FOUND_OLD_ARTIFACTS=true
    fi

    # Check for packages from old nix-env based deployment
    if nix-env -q 2>/dev/null | grep -q "git\|vscodium\|nodejs"; then
        print_warning "Found packages installed via nix-env (old deployment method)"
        print_info "These will be cleaned up to prevent conflicts"
        FOUND_OLD_ARTIFACTS=true
    fi

    if [ "$FOUND_OLD_ARTIFACTS" = true ]; then
        echo ""
        print_warning "Old deployment artifacts detected"
        print_info "This script uses home-manager (declarative, better approach)"
        print_info "The old script used nix-env (imperative, causes conflicts)"
        echo ""

        if confirm "Remove old deployment artifacts before continuing?" "y"; then
            # Rename old script
            if [ -f "$OLD_SCRIPT" ]; then
                mv "$OLD_SCRIPT" "$OLD_SCRIPT.old.$(date +%Y%m%d_%H%M%S)"
                print_success "Renamed old deployment script"
            fi

            # Clean up nix-env packages will happen in apply_home_manager_config
            print_success "Old artifacts will be cleaned up during installation"
        else
            print_warning "Continuing with old artifacts present - may cause conflicts"
            print_info "If you encounter issues, re-run and accept cleanup"
        fi
        echo ""
    else
        print_success "No old deployment artifacts found"
    fi

    # Check disk space (need at least 10GB free in /nix/store)
    local available_gb=$(df -BG /nix/store | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_gb" -lt 10 ]; then
        print_error "Insufficient disk space: ${available_gb}GB available"
        print_error "At least 10GB free space required in /nix/store"
        echo ""
        print_info "Free up space with:"
        echo "  sudo nix-collect-garbage -d"
        echo "  sudo nix-store --optimize"
        exit 1
    fi
    print_success "Disk space check passed (${available_gb}GB available)"

    # Check network connectivity
    print_info "Checking network connectivity..."
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_success "Network connectivity OK"
    else
        print_error "No network connectivity detected"
        print_error "Internet connection required to download packages"
        echo ""
        print_info "Check your network and try again"
        exit 1
    fi

    # Update NixOS channels before proceeding
    print_section "Updating NixOS Channels"
    update_nixos_channels

    # Check home-manager (required - auto-install if missing)
    # First, ensure ~/.nix-profile/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.nix-profile/bin:"* ]]; then
        export PATH="$HOME/.nix-profile/bin:$PATH"
        print_info "Added ~/.nix-profile/bin to PATH"
    fi

    if command -v home-manager &> /dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        print_info "home-manager is required for this setup"
        install_home_manager
    fi
}

# ============================================================================
# NixOS Version Selection
# ============================================================================

select_nixos_version() {
    print_section "NixOS Version Selection"

    # Get current system version
    local CURRENT_VERSION=$(nixos-version | cut -d'.' -f1-2)
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

update_nixos_channels() {
    print_info "Synchronizing NixOS and home-manager channels..."

    # Use selected version if available, otherwise auto-detect
    local TARGET_VERSION="${SELECTED_NIXOS_VERSION:-}"

    if [ -z "$TARGET_VERSION" ]; then
        # Auto-detect from current system if no selection was made
        TARGET_VERSION=$(nixos-version | cut -d'.' -f1-2)
        print_info "Auto-detected NixOS version: $TARGET_VERSION"
    else
        print_info "Using selected NixOS version: $TARGET_VERSION"
    fi

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

    # Extract channel name and version from URL
    # Examples:
    #   https://nixos.org/channels/nixos-24.11 → nixos-24.11
    #   https://nixos.org/channels/nixos-unstable → nixos-unstable
    local NIXOS_CHANNEL_NAME=$(basename "$CURRENT_NIXOS_CHANNEL")
    print_info "Current NixOS channel: $NIXOS_CHANNEL_NAME"

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

    print_success "Channel synchronization plan:"
    print_info "  NixOS:        $NIXOS_CHANNEL_NAME"
    print_info "  home-manager: $HM_CHANNEL_NAME"
    print_info "  ✓ Versions synchronized"
    echo ""

    # Ensure NixOS channel is set (in case it wasn't)
    print_info "Ensuring NixOS channel is set..."
    if sudo nix-channel --add "$CURRENT_NIXOS_CHANNEL" nixos; then
        print_success "NixOS channel confirmed: $NIXOS_CHANNEL_NAME"
    else
        print_error "Failed to set NixOS channel"
        exit 1
    fi

    # Set user nixpkgs channel to MATCH system NixOS version
    print_info "Setting user nixpkgs channel to match system NixOS..."
    if nix-channel --add "$CURRENT_NIXOS_CHANNEL" nixpkgs; then
        print_success "User nixpkgs channel set to $NIXOS_CHANNEL_NAME"
    else
        print_error "Failed to set user nixpkgs channel"
        exit 1
    fi

    # Set home-manager channel to MATCH nixos version
    print_info "Setting home-manager channel to match NixOS..."
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
    local NIXPKGS_VERSION=$(nix-instantiate --eval -E '(import <nixpkgs> {}).lib.version' 2>/dev/null | tr -d '"' || echo "unknown")
    local HM_VERSION=$(nix-instantiate --eval -E '(import <home-manager> {}).home-manager.version' 2>/dev/null | tr -d '"' || echo "unknown")

    if [ "$NIXPKGS_VERSION" != "unknown" ] && [ "$HM_VERSION" != "unknown" ]; then
        print_info "  nixpkgs version:      $NIXPKGS_VERSION"
        print_info "  home-manager version: $HM_VERSION"

        # Extract major.minor for comparison
        local NIXPKGS_MAJ_MIN=$(echo "$NIXPKGS_VERSION" | grep -oP '^\d+\.\d+' || echo "$NIXPKGS_VERSION")
        local HM_MAJ_MIN=$(echo "$HM_VERSION" | grep -oP '^\d+\.\d+' || echo "$HM_VERSION")

        if [ "$NIXPKGS_MAJ_MIN" = "$HM_MAJ_MIN" ]; then
            print_success "✓ Channels synchronized: both on $NIXPKGS_MAJ_MIN"
        else
            print_error "✗ CRITICAL: Version mismatch detected!"
            print_error "  nixpkgs:      $NIXPKGS_MAJ_MIN"
            print_error "  home-manager: $HM_MAJ_MIN"
            print_error "This WILL cause compatibility issues and build failures"
            echo ""
            print_info "Attempting to fix by re-synchronizing channels..."

            # Force re-add the correct home-manager channel
            nix-channel --remove home-manager 2>/dev/null || true
            nix-channel --add "https://github.com/nix-community/home-manager/archive/release-${NIXPKGS_MAJ_MIN}.tar.gz" home-manager
            nix-channel --update

            print_success "Channels re-synchronized to $NIXPKGS_MAJ_MIN"
        fi
    else
        print_warning "Could not verify channel versions"
        print_info "Will proceed but may encounter compatibility issues"
    fi
    echo ""
}

install_home_manager() {
    print_section "Installing home-manager"

    # CRITICAL: Backup and remove old home-manager config files BEFORE installation
    # The home-manager install script will try to use existing home.nix, which may be broken
    if [ -d "$HOME/.config/home-manager" ]; then
        print_info "Found existing home-manager config, backing up..."
        local BACKUP_DIR="$HOME/.config-backups/pre-install-$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"

        if [ -f "$HOME/.config/home-manager/home.nix" ]; then
            cp "$HOME/.config/home-manager/home.nix" "$BACKUP_DIR/home.nix"
            print_success "Backed up old home.nix"
        fi

        if [ -f "$HOME/.config/home-manager/flake.nix" ]; then
            cp "$HOME/.config/home-manager/flake.nix" "$BACKUP_DIR/flake.nix"
            print_success "Backed up old flake.nix"
        fi

        if [ -f "$HOME/.config/home-manager/flake.lock" ]; then
            cp "$HOME/.config/home-manager/flake.lock" "$BACKUP_DIR/flake.lock"
            print_success "Backed up old flake.lock"
        fi

        # Remove the old config directory to start fresh
        print_warning "Removing old home-manager config to prevent conflicts..."
        rm -rf "$HOME/.config/home-manager"
        print_success "Old config removed, will create fresh configuration"
        echo ""
    fi

    print_info "Installing home-manager (this may take 5-10 minutes)..."
    if ! nix-shell '<home-manager>' -A install 2>&1 | tee /tmp/home-manager-install.log; then
        print_error "Failed to install home-manager"
        print_info "Log saved to: /tmp/home-manager-install.log"
        echo ""
        print_warning "Common causes:"
        echo "  • Network issues during download"
        echo "  • Insufficient disk space"
        echo "  • Conflicting Nix configuration"
        echo ""
        exit 1
    fi

    print_success "home-manager installed successfully"

    # Update PATH to include newly installed home-manager command
    print_info "Updating PATH to include home-manager..."
    export PATH="$HOME/.nix-profile/bin:$PATH"
    #nix-shell -p home-manager

    # Verify home-manager is now available
    if command -v home-manager &> /dev/null; then
        print_success "home-manager command is now available: $(which home-manager)"
    else
        print_error "home-manager installed but command not found in PATH"
        print_info "Expected location: $HOME/.nix-profile/bin/home-manager"
        print_info "Current PATH: $PATH"
        exit 1
    fi
}

# ============================================================================
# User Information Gathering
# ============================================================================

gather_user_info() {
    print_section "Gathering User Preferences"

    # Timezone configuration
    local CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")
    print_info "Current timezone: $CURRENT_TZ"
    echo ""
    print_info "Common US timezones:"
    echo "  1) America/Los_Angeles (Pacific)"
    echo "  2) America/Denver (Mountain)"
    echo "  3) America/Chicago (Central)"
    echo "  4) America/New_York (Eastern)"
    echo "  5) Keep current ($CURRENT_TZ)"
    echo "  6) Custom (enter manually)"

    TZ_CHOICE=$(prompt_user "Choose timezone (1-6)" "5")

    case $TZ_CHOICE in
        1) SELECTED_TIMEZONE="America/Los_Angeles" ;;
        2) SELECTED_TIMEZONE="America/Denver" ;;
        3) SELECTED_TIMEZONE="America/Chicago" ;;
        4) SELECTED_TIMEZONE="America/New_York" ;;
        5) SELECTED_TIMEZONE="$CURRENT_TZ" ;;
        6) SELECTED_TIMEZONE=$(prompt_user "Enter timezone (e.g., America/Los_Angeles)") ;;
        *) SELECTED_TIMEZONE="$CURRENT_TZ" ;;
    esac

    print_success "Timezone: $SELECTED_TIMEZONE"
    echo ""

    # Editor preference
    print_info "Default editor options:"
    echo "  1) vim"
    echo "  2) neovim"
    echo "  3) vscodium"
    EDITOR_CHOICE=$(prompt_user "Choose editor (1-3)" "1")

    case $EDITOR_CHOICE in
        1) DEFAULT_EDITOR="vim" ;;
        2) DEFAULT_EDITOR="nvim" ;;
        3) DEFAULT_EDITOR="code" ;;
        *) DEFAULT_EDITOR="vim" ;;
    esac

    print_success "Editor preference: $DEFAULT_EDITOR"
    echo ""

    # Password Migration/Setup
    print_section "Password Configuration"

    # Check if user already has a password in /etc/shadow
    local EXISTING_HASH=$(sudo grep "^$USER:" /etc/shadow 2>/dev/null | cut -d: -f2)

    if [ -n "$EXISTING_HASH" ] && [ "$EXISTING_HASH" != "!" ] && [ "$EXISTING_HASH" != "*" ] && [ "$EXISTING_HASH" != "" ]; then
        # User has existing password - migrate it
        print_success "Existing password found - will be migrated to new configuration"
        USER_PASSWORD_HASH="$EXISTING_HASH"
        PASSWORD_MIGRATION=true

        # Ask if sudo password should be different
        echo ""
        print_info "Current setup: User password exists and will be preserved"
        if confirm "Do you want a DIFFERENT password for sudo operations?" "n"; then
            print_info "Enter new sudo password (will be required for 'sudo' commands)"
            read -s -p "$(echo -e ${BLUE}?${NC} New sudo password: )" SUDO_PASS1
            echo ""
            read -s -p "$(echo -e ${BLUE}?${NC} Confirm sudo password: )" SUDO_PASS2
            echo ""

            if [ "$SUDO_PASS1" != "$SUDO_PASS2" ]; then
                print_error "Passwords don't match!"
                exit 1
            fi

            # Generate hash for sudo password
            SUDO_PASSWORD_HASH=$(echo "$SUDO_PASS1" | mkpasswd -m sha-512 -s)
            SEPARATE_SUDO_PASSWORD=true
            print_success "Separate sudo password configured"
        else
            SEPARATE_SUDO_PASSWORD=false
            print_success "User and sudo passwords will be the same"
        fi
    else
        # No existing password - need to set one
        print_warning "No existing password found for user: $USER"
        print_info "Setting up new password for system login"
        echo ""

        read -s -p "$(echo -e ${BLUE}?${NC} Enter new password: )" USER_PASS1
        echo ""
        read -s -p "$(echo -e ${BLUE}?${NC} Confirm password: )" USER_PASS2
        echo ""

        if [ "$USER_PASS1" != "$USER_PASS2" ]; then
            print_error "Passwords don't match!"
            exit 1
        fi

        # Generate hash for user password
        USER_PASSWORD_HASH=$(echo "$USER_PASS1" | mkpasswd -m sha-512 -s)
        PASSWORD_MIGRATION=false

        # Ask if sudo password should be different
        echo ""
        if confirm "Do you want a DIFFERENT password for sudo operations?" "n"; then
            print_info "Enter sudo password (will be required for 'sudo' commands)"
            read -s -p "$(echo -e ${BLUE}?${NC} New sudo password: )" SUDO_PASS1
            echo ""
            read -s -p "$(echo -e ${BLUE}?${NC} Confirm sudo password: )" SUDO_PASS2
            echo ""

            if [ "$SUDO_PASS1" != "$SUDO_PASS2" ]; then
                print_error "Passwords don't match!"
                exit 1
            fi

            SUDO_PASSWORD_HASH=$(echo "$SUDO_PASS1" | mkpasswd -m sha-512 -s)
            SEPARATE_SUDO_PASSWORD=true
            print_success "Separate sudo password configured"
        else
            SEPARATE_SUDO_PASSWORD=false
            SUDO_PASSWORD_HASH="$USER_PASSWORD_HASH"
            print_success "User and sudo passwords will be the same"
        fi

        print_success "Password configured successfully"
    fi

    echo ""
    print_info "Note: Git can be configured later with 'git config --global'"
}

# ============================================================================
# Home Manager Configuration
# ============================================================================

create_home_manager_config() {
    print_section "Creating Home Manager Configuration"

    # Detect stateVersion from synchronized channels
    # IMPORTANT: stateVersion should match the NixOS/nixpkgs release
    local HM_CHANNEL=$(nix-channel --list | grep 'home-manager' | awk '{print $2}')
    local NIXOS_CHANNEL=$(sudo nix-channel --list | grep '^nixos' | awk '{print $2}')
    local STATE_VERSION
    local NIXOS_CHANNEL_NAME=""
    local HM_CHANNEL_NAME=""

    # Extract version from nixos channel (source of truth)
    if [[ "$NIXOS_CHANNEL" =~ nixos-([0-9]+\.[0-9]+) ]]; then
        STATE_VERSION="${BASH_REMATCH[1]}"
        print_info "Detected stateVersion from NixOS channel: $STATE_VERSION"
    elif [[ "$HM_CHANNEL" == *"release-"* ]]; then
        # Fallback: Extract from home-manager channel
        STATE_VERSION=$(echo "$HM_CHANNEL" | grep -oP 'release-\K[0-9]+\.[0-9]+')
        print_info "Detected stateVersion from home-manager: $STATE_VERSION"
    elif [[ "$HM_CHANNEL" == *"master"* ]] || [[ "$NIXOS_CHANNEL" == *"unstable"* ]]; then
        # Unstable/master: Use current system version (don't hardcode!)
        STATE_VERSION=$(nixos-version | cut -d'.' -f1-2)
        print_info "Using unstable channel, stateVersion from system: $STATE_VERSION"
    else
        # Final fallback: system version
        STATE_VERSION=$(nixos-version | cut -d'.' -f1-2)
        print_warning "Could not detect from channels, using system version: $STATE_VERSION"
    fi

    if [[ -n "$NIXOS_CHANNEL" ]]; then
        NIXOS_CHANNEL_NAME=$(basename "$NIXOS_CHANNEL")
    else
        NIXOS_CHANNEL_NAME="nixos-${STATE_VERSION}"
        print_warning "Could not detect nixos channel name, defaulting to $NIXOS_CHANNEL_NAME"
    fi

    if [[ -n "$HOME_MANAGER_CHANNEL_REF" ]]; then
        HM_CHANNEL_NAME="$HOME_MANAGER_CHANNEL_REF"
    elif [[ -n "$HOME_MANAGER_CHANNEL_URL" ]]; then
        HM_CHANNEL_NAME=$(normalize_channel_name "$HOME_MANAGER_CHANNEL_URL")
    elif [[ -n "$HM_CHANNEL" ]]; then
        HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL")
    fi

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        # Mirror the nixos channel when home-manager is missing
        HM_CHANNEL_NAME="release-${STATE_VERSION}"
        print_warning "Could not detect home-manager channel, defaulting to $HM_CHANNEL_NAME"
    fi

    if [[ -z "$HOME_MANAGER_CHANNEL_URL" && -n "$HM_CHANNEL" ]]; then
        HOME_MANAGER_CHANNEL_URL="$HM_CHANNEL"
    fi

    local HM_CHANNEL_REF=$(normalize_channel_name "$HM_CHANNEL_NAME")
    if [[ -n "$HM_CHANNEL_REF" ]]; then
        HM_CHANNEL_NAME="$HM_CHANNEL_REF"
    fi

    HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"

    print_success "Configuration versions:"
    print_info "  stateVersion:     $STATE_VERSION"
    print_info "  NixOS channel:    $NIXOS_CHANNEL_NAME"
    print_info "  home-manager:     $HM_CHANNEL_NAME"
    echo ""

    # Backup existing config if it exists
    # Backup ALL existing home-manager config files before overwriting
    if [[ -d "$HM_CONFIG_DIR" ]]; then
        local BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        local BACKUP_DIR="$HM_CONFIG_DIR/backup"
        mkdir -p "$BACKUP_DIR"
        print_info "Found existing home-manager config, backing up all files..."

        if [[ -f "$HM_CONFIG_FILE" ]]; then
            HOME_MANAGER_BACKUP="$HM_CONFIG_FILE.backup.$BACKUP_TIMESTAMP"
            cp "$HM_CONFIG_FILE" "$HOME_MANAGER_BACKUP"
            print_success "Backed up home.nix"
        fi

        if [[ -f "$HM_CONFIG_DIR/flake.nix" ]]; then
            cp "$HM_CONFIG_DIR/flake.nix" "$BACKUP_DIR/flake.nix.backup.$BACKUP_TIMESTAMP"
            print_success "Backed up flake.nix"
        fi

        if [[ -f "$HM_CONFIG_DIR/flake.lock" ]]; then
            cp "$HM_CONFIG_DIR/flake.lock" "$BACKUP_DIR/flake.lock.backup.$BACKUP_TIMESTAMP"
            print_success "Backed up flake.lock"
        fi

        print_info "Creating fresh configuration (old files backed up)..."
        echo ""
    fi

    print_info "Creating new home-manager configuration..."

    mkdir -p "$HM_CONFIG_DIR"

    # Copy p10k-setup-wizard.sh to home-manager config dir so home.nix can reference it
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/p10k-setup-wizard.sh" ]; then
        cp "$SCRIPT_DIR/p10k-setup-wizard.sh" "$HM_CONFIG_DIR/p10k-setup-wizard.sh"
        print_success "Copied p10k-setup-wizard.sh to home-manager config directory"
    else
        print_warning "p10k-setup-wizard.sh not found in $SCRIPT_DIR - skipping copy"
        print_info "If you need the prompt wizard, place the script next to nixos-quick-deploy.sh"
    fi

    local TEMPLATE_DIR="$SCRIPT_DIR/templates"
    if [[ ! -d "$TEMPLATE_DIR" ]]; then
        print_error "Template directory not found: $TEMPLATE_DIR"
        print_info "Ensure the repository includes the templates directory"
        exit 1
    fi

    # Create a flake.nix in the home-manager config directory for proper Flatpak support
    # This enables using: home-manager switch --flake ~/.config/home-manager
    print_info "Creating home-manager flake configuration for Flatpak support..."
    local FLAKE_TEMPLATE="$TEMPLATE_DIR/flake.nix"
    if [[ ! -f "$FLAKE_TEMPLATE" ]]; then
        print_error "Missing flake template: $FLAKE_TEMPLATE"
        exit 1
    fi

    local FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
    local SYSTEM_ARCH=$(nix eval --raw --expr builtins.currentSystem 2>/dev/null || echo "x86_64-linux")
    local CURRENT_HOSTNAME=$(hostname)

    install -Dm644 "$FLAKE_TEMPLATE" "$FLAKE_FILE"

    if [[ ! -s "$FLAKE_FILE" ]]; then
        print_error "Failed to copy flake manifest to $FLAKE_FILE"
        print_info "Check filesystem permissions and rerun with --force-update"
        exit 1
    fi
    # Align flake inputs with the synchronized channels
    sed -i "s|NIXPKGS_CHANNEL_PLACEHOLDER|$NIXOS_CHANNEL_NAME|" "$FLAKE_FILE"
    sed -i "s|HM_CHANNEL_PLACEHOLDER|$HM_CHANNEL_NAME|" "$FLAKE_FILE"
    sed -i "s|HOSTNAME_PLACEHOLDER|$CURRENT_HOSTNAME|" "$FLAKE_FILE"
    sed -i "s|HOME_USERNAME_PLACEHOLDER|$USER|" "$FLAKE_FILE"
    sed -i "s|SYSTEM_PLACEHOLDER|$SYSTEM_ARCH|" "$FLAKE_FILE"

    print_success "Created flake.nix in home-manager config directory"

    print_info "To use Flatpak declarative management:"
    print_info "  home-manager switch --flake ~/.config/home-manager"
    echo ""

    local HOME_TEMPLATE="$TEMPLATE_DIR/home.nix"
    if [[ ! -f "$HOME_TEMPLATE" ]]; then
        print_error "Missing home-manager template: $HOME_TEMPLATE"
        exit 1
    fi

    install -Dm644 "$HOME_TEMPLATE" "$HM_CONFIG_FILE"

    # Calculate template hash for change detection
    local TEMPLATE_HASH=$(echo -n "AIDB-v4.0-packages-v$SCRIPT_VERSION" | sha256sum | cut -d' ' -f1 | cut -c1-16)

    # Validate all variables are set before replacement
    if [ -z "$USER" ] || [ -z "$HOME" ] || [ -z "$STATE_VERSION" ]; then
        print_error "Critical variables not set!"
        print_error "USER='$USER' HOME='$HOME' STATE_VERSION='$STATE_VERSION'"
        exit 1
    fi

    # Set defaults for optional variables if not set
    DEFAULT_EDITOR="${DEFAULT_EDITOR:-vim}"

    print_info "Using configuration:"
    print_info "  User: $USER"
    print_info "  Home: $HOME"
    print_info "  State Version: $STATE_VERSION"
    print_info "  Editor: $DEFAULT_EDITOR"

    # Replace placeholders in home.nix (using | delimiter to handle special characters in variables)
    sed -i "s|VERSIONPLACEHOLDER|$SCRIPT_VERSION|" "$HM_CONFIG_FILE"
    sed -i "s|HASHPLACEHOLDER|$TEMPLATE_HASH|" "$HM_CONFIG_FILE"

    # Replace placeholders in flake.nix
    sed -i "s|HOMEUSERNAME|$USER|g" "$HM_CONFIG_DIR/flake.nix"
    sed -i "s|HOMEUSERNAME|$USER|" "$HM_CONFIG_FILE"
    sed -i "s|HOMEDIR|$HOME|" "$HM_CONFIG_FILE"
    sed -i "s|STATEVERSION_PLACEHOLDER|$STATE_VERSION|" "$HM_CONFIG_FILE"
    sed -i "s|DEFAULTEDITOR|$DEFAULT_EDITOR|g" "$HM_CONFIG_FILE"

    print_success "Home manager configuration created at $HM_CONFIG_FILE"
    print_info "Configuration includes $(grep -c "^    " "$HM_CONFIG_FILE" || echo 'many') packages"

    # Verify the generated file is valid Nix syntax
    print_info "Validating generated home.nix syntax..."
    if nix-instantiate --parse "$HM_CONFIG_FILE" &>/dev/null; then
        print_success "✓ home.nix syntax is valid"
    else
        print_error "✗ home.nix has syntax errors!"
        print_error "Please check: $HM_CONFIG_FILE"
        print_info "Running nix-instantiate for details..."
        nix-instantiate --parse "$HM_CONFIG_FILE" 2>&1 | tail -20
        exit 1
    fi
}

# ============================================================================
# Apply Configuration
# ============================================================================

apply_home_manager_config() {
    print_section "Applying Home Manager Configuration"

    # CRITICAL: Ensure home-manager is in PATH
    # This is needed because home-manager might have been just installed
    if [[ ":$PATH:" != *":$HOME/.nix-profile/bin:"* ]]; then
        export PATH="$HOME/.nix-profile/bin:$PATH"
        print_info "Added ~/.nix-profile/bin to PATH for home-manager"
    fi

    # Verify home-manager is available
    if ! command -v home-manager &> /dev/null; then
        print_error "home-manager command not found even after PATH update!"
        print_info "Expected location: $HOME/.nix-profile/bin/home-manager"
        print_info "Current PATH: $PATH"
        print_info "Checking if file exists..."
        ls -la "$HOME/.nix-profile/bin/home-manager" || echo "File does not exist"
        exit 1
    fi
    print_success "home-manager command available: $(which home-manager)"
    echo ""

    print_info "This will install packages and configure your environment..."
    print_warning "This may take 10-15 minutes on first run"
    echo ""

    # Note about nix-flatpak for Flatpak declarative management
    print_info "Flatpak Integration:"
    print_info "  Your home.nix includes declarative Flatpak configuration via nix-flatpak"
    print_info "  Edit the services.flatpak.packages section in home.nix to add/remove Flatpak apps"
    print_info "  Uncomment desired Flatpak apps and re-run: home-manager switch"
    echo ""

    # Clean up ALL packages installed via nix-env to prevent conflicts
    # We manage everything declaratively through home-manager now
    print_info "Checking for packages installed via nix-env (imperative method)..."
    local IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null)
    if [ -n "$IMPERATIVE_PKGS" ]; then
        print_warning "Found packages installed via nix-env (will cause conflicts):"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""

        print_info "Removing ALL nix-env packages (switching to declarative home-manager)..."
        print_info "This prevents package collisions and ensures reproducibility"

        # Remove all packages installed via nix-env
        if nix-env -e '.*' --remove-all 2>&1 | tee /tmp/nix-env-cleanup.log; then
            print_success "All nix-env packages removed successfully"
        else
            # Fallback: Try removing packages one by one
            print_warning "Batch removal failed, trying individual package removal..."
            while IFS= read -r pkg; do
                local pkg_name=$(echo "$pkg" | awk '{print $1}')
                if [ -n "$pkg_name" ]; then
                    print_info "Removing: $pkg_name"
                    nix-env -e "$pkg_name" 2>/dev/null && print_success "  Removed: $pkg_name" || print_warning "  Failed: $pkg_name"
                fi
            done <<< "$IMPERATIVE_PKGS"
        fi

        # Verify all removed
        local REMAINING=$(nix-env -q 2>/dev/null)
        if [ -n "$REMAINING" ]; then
            print_warning "Some packages remain in nix-env:"
            echo "$REMAINING" | sed 's/^/    /'
            print_warning "These may cause conflicts with home-manager"
        else
            print_success "All nix-env packages successfully removed"
            print_success "All packages now managed declaratively via home-manager"
        fi
    else
        print_success "No nix-env packages found - clean state!"
    fi
    echo ""

    # Backup existing configuration files
    backup_existing_configs

    print_info "Running home-manager switch (automatic, no confirmation needed)..."
    echo ""

    # Run home-manager switch with flake support for declarative Flatpak management
    # This passes nix-flatpak as an input to home.nix, enabling services.flatpak
    print_info "Applying your custom home-manager configuration..."
    print_info "Config: ~/.config/home-manager/home.nix"
    print_info "Using flake for full Flatpak declarative support..."
    echo ""

    # Update flake.lock to ensure we have latest versions of inputs
    local HM_FLAKE_PATH="$HM_CONFIG_DIR/flake.nix"
    if [[ ! -f "$HM_FLAKE_PATH" ]]; then
        print_error "home-manager flake manifest missing: $HM_FLAKE_PATH"
        print_info "The configuration step did not complete successfully."
        print_info "Re-run this script with --force-update after fixing the issue."
        exit 1
    fi

    print_info "Updating flake inputs (nix-flatpak, home-manager, nixpkgs)..."
    if (cd ~/.config/home-manager && nix flake update) 2>&1 | tee /tmp/flake-update.log; then
        print_success "Flake inputs updated successfully"
    else
        print_warning "Flake update failed, continuing with existing lock file..."
        print_info "This is usually fine for first-time installations"
    fi
    echo ""

    # Use home-manager with flakes to enable nix-flatpak module and declarative Flatpak
    # Must specify the configuration name: #username
    local CURRENT_USER=$(whoami)
    #nix-shell -p home-manager
    print_info "Using configuration: homeConfigurations.$CURRENT_USER"
    if home-manager switch --flake ~/.config/home-manager --show-trace 2>&1 | tee /tmp/home-manager-switch.log; then    #original code 'if home-manager switch --flake ~/.config/home-manager#$CURRENT_USER --show-trace 2>&1 | tee /tmp/home-manager-switch.log; then'
        print_success "Home manager configuration applied successfully!"
        echo ""

        # Source the home-manager session vars to update PATH immediately
        print_info "Updating current shell environment..."
        if [ -f "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
            # Temporarily disable 'set -u' for sourcing external scripts
            set +u
            source "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
            set -u
            print_success "PATH updated with new packages"
        fi

        # Verify critical packages are now in PATH
        print_info "Verifying package installation..."
        MISSING_COUNT=0
        for pkg in podman python3 ripgrep bat eza fd git; do
            if command -v "$pkg" &>/dev/null; then
                print_success "$pkg found at $(command -v $pkg)"
            else
                print_warning "$pkg not found in PATH yet"
                ((MISSING_COUNT++))
            fi
        done

        if [ $MISSING_COUNT -gt 0 ]; then
            print_warning "$MISSING_COUNT packages not yet in PATH"
            print_info "Restart your shell to load all packages: exec zsh"
        else
            print_success "All critical packages are in PATH!"
        fi
        echo ""
    else
        local hm_exit_code=$?
        print_error "home-manager switch failed (exit code: $hm_exit_code)"
        echo ""
        print_warning "Common causes:"
        echo "  • Conflicting files (check ~/.config collisions)"
        echo "  • Syntax errors in home.nix"
        echo "  • Network issues downloading packages"
        echo "  • Package conflicts or missing dependencies"
        echo ""
        print_info "Full log saved to: /tmp/home-manager-switch.log"
        print_info "Backup is at: $HOME_MANAGER_BACKUP"
        echo ""
        print_error "Automatic rollback will restore your previous configuration."
        print_error "Fix the issue above, then run this script again for a fresh start."
        echo ""

        # Trigger cleanup and exit
        exit 1
    fi

    # Apply system-wide changes
    apply_system_changes
}

backup_existing_configs() {
    print_info "Backing up and removing conflicting configuration files..."
    local BACKUP_DIR="$HOME/.config-backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup and remove VSCodium settings.json to prevent collision
    VSCODIUM_SETTINGS="$HOME/.config/VSCodium/User/settings.json"
    if [ -f "$VSCODIUM_SETTINGS" ] && [ ! -L "$VSCODIUM_SETTINGS" ]; then
        cp "$VSCODIUM_SETTINGS" "$BACKUP_DIR/vscodium-settings.json"
        rm "$VSCODIUM_SETTINGS"
        print_success "Backed up and removed VSCodium settings"
    fi

    # Backup and remove .bashrc if it exists to prevent collision
    if [ -f "$HOME/.bashrc" ] && [ ! -L "$HOME/.bashrc" ]; then
        cp "$HOME/.bashrc" "$BACKUP_DIR/.bashrc"
        rm "$HOME/.bashrc"
        print_success "Backed up and removed .bashrc"
    fi

    # Backup and remove existing .zshrc
    if [ -f "$HOME/.zshrc" ] && [ ! -L "$HOME/.zshrc" ]; then
        cp "$HOME/.zshrc" "$BACKUP_DIR/.zshrc"
        rm "$HOME/.zshrc"
        print_success "Backed up and removed .zshrc"
    fi

    # Backup and remove existing .p10k.zsh
    if [ -f "$HOME/.p10k.zsh" ] && [ ! -L "$HOME/.p10k.zsh" ]; then
        cp "$HOME/.p10k.zsh" "$BACKUP_DIR/.p10k.zsh"
        rm "$HOME/.p10k.zsh"
        print_success "Backed up and removed .p10k.zsh"
    fi

    # Also check for VSCodium User directory conflict
    VSCODIUM_USER_DIR="$HOME/.config/VSCodium/User"
    if [ -d "$VSCODIUM_USER_DIR" ] && [ ! -L "$VSCODIUM_USER_DIR" ]; then
        # Only back up the directory if it has files we care about
        if [ -n "$(ls -A "$VSCODIUM_USER_DIR" 2>/dev/null)" ]; then
            mkdir -p "$BACKUP_DIR/VSCodium-User"
            cp -r "$VSCODIUM_USER_DIR"/* "$BACKUP_DIR/VSCodium-User/" 2>/dev/null || true
            print_info "Backed up VSCodium User directory contents"
        fi
    fi

    if [ -d "$BACKUP_DIR" ] && [ -n "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        print_success "All conflicting configs backed up to: $BACKUP_DIR"
    fi
    print_info "Home-manager will now create managed symlinks"
}

apply_system_changes() {
    print_section "Applying System-Wide Changes"

    # Force reload of zsh configuration
    if [ -f "$HOME/.zshrc" ]; then
        print_info "ZSH configuration is managed by home-manager"
        print_info "Configuration file: $HOME/.zshrc"
    fi

    # Ensure p10k wizard script is executable
    if [ -f "$HOME/.local/bin/p10k-setup-wizard.sh" ]; then
        chmod +x "$HOME/.local/bin/p10k-setup-wizard.sh"
        print_success "Made p10k setup wizard executable"
    fi

    # Set ZSH as default shell if not already
    # This matches the NixOS configuration which sets shell = pkgs.zsh
    if [ "$SHELL" != "$(which zsh)" ]; then
        print_info "Setting ZSH as default shell (configured in NixOS)"
        chsh -s "$(which zsh)"
        print_success "Default shell set to ZSH (restart terminal to apply)"
    else
        print_success "ZSH is already your default shell"
    fi

    print_success "System changes applied"

    # Trigger cleanup and exit
        #exit 1
}

# ============================================================================
# Hardware Detection & Optimization
# ============================================================================

detect_gpu_and_cpu() {
    print_section "Detecting Hardware for Optimization"

    # ========================================================================
    # GPU Detection
    # ========================================================================

    # Initialize GPU variables
    GPU_TYPE="unknown"
    GPU_DRIVER=""
    GPU_PACKAGES=""
    LIBVA_DRIVER=""

    # Check for Intel GPU
    if lspci | grep -iE "VGA|3D|Display" | grep -iq "Intel"; then
        GPU_TYPE="intel"
        GPU_DRIVER="intel"
        LIBVA_DRIVER="iHD"  # Intel iHD for Gen 8+ (Broadwell+), or "i965" for older
        GPU_PACKAGES="intel-media-driver vaapiIntel"
        print_success "Detected: Intel GPU"
    fi

    # Check for AMD GPU
    if lspci | grep -iE "VGA|3D|Display" | grep -iq "AMD\|ATI"; then
        GPU_TYPE="amd"
        GPU_DRIVER="amdgpu"
        LIBVA_DRIVER="radeonsi"
        GPU_PACKAGES="mesa amdvlk rocm-opencl-icd"
        print_success "Detected: AMD GPU"
    fi

    # Check for NVIDIA GPU
    if lspci | grep -iE "VGA|3D|Display" | grep -iq "NVIDIA"; then
        GPU_TYPE="nvidia"
        GPU_DRIVER="nvidia"
        LIBVA_DRIVER="nvidia"  # NVIDIA uses different VA-API backend
        GPU_PACKAGES="nvidia-vaapi-driver"
        print_success "Detected: NVIDIA GPU"
        print_warning "NVIDIA on Wayland requires additional configuration"
        print_info "Consider enabling: hardware.nvidia.modesetting.enable = true"
    fi

    # Fallback for systems with no dedicated GPU
    if [ "$GPU_TYPE" == "unknown" ]; then
        print_warning "No dedicated GPU detected - using software rendering"
        GPU_TYPE="software"
        LIBVA_DRIVER=""
        GPU_PACKAGES=""
    fi

    print_info "GPU Type: $GPU_TYPE"
    if [ -n "$LIBVA_DRIVER" ]; then
        print_info "VA-API Driver: $LIBVA_DRIVER"
    fi

    # ========================================================================
    # CPU Detection
    # ========================================================================

    CPU_VENDOR="unknown"
    CPU_MICROCODE=""

    # Detect CPU vendor
    if grep -q "GenuineIntel" /proc/cpuinfo; then
        CPU_VENDOR="intel"
        CPU_MICROCODE="intel-microcode"
        print_success "Detected: Intel CPU"
    elif grep -q "AuthenticAMD" /proc/cpuinfo; then
        CPU_VENDOR="amd"
        CPU_MICROCODE="amd-microcode"
        print_success "Detected: AMD CPU"
    else
        print_warning "Unknown CPU vendor"
    fi

    # Detect CPU core count for optimization
    CPU_CORES=$(nproc)
    print_info "CPU Cores: $CPU_CORES"

    # ========================================================================
    # Memory Detection
    # ========================================================================

    # Total RAM in GB
    TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
    print_info "Total RAM: ${TOTAL_RAM_GB}GB"

    # Set zramSwap memory percentage based on available RAM
    if [ "$TOTAL_RAM_GB" -ge 16 ]; then
        ZRAM_PERCENT=25
    elif [ "$TOTAL_RAM_GB" -ge 8 ]; then
        ZRAM_PERCENT=50
    else
        ZRAM_PERCENT=75
    fi
    print_info "Zram percentage: $ZRAM_PERCENT%"

    echo ""
    print_success "Hardware detection complete"
    echo ""
}

# ============================================================================
# NixOS System Configuration Updates
# ============================================================================

update_nixos_system_config() {
    print_section "Generating Fresh NixOS Configuration"

    local SYSTEM_CONFIG="/etc/nixos/configuration.nix"
    local HARDWARE_CONFIG="/etc/nixos/hardware-configuration.nix"

    # Detect system info
    local HOSTNAME=$(hostname)
    local NIXOS_VERSION=$(nixos-version | cut -d'.' -f1-2)
    local HM_CHANNEL_NAME=""
    local HM_FETCH_URL=""
    local DETECTED_HM_CHANNEL=""

    # Use timezone selected by user (from gather_user_info)
    # If not set, detect current timezone
    if [ -z "$SELECTED_TIMEZONE" ]; then
        SELECTED_TIMEZONE=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")
    fi

    # Detect current locale to preserve user's setting
    local CURRENT_LOCALE=$(localectl status | grep "LANG=" | cut -d= -f2 | tr -d ' ' 2>/dev/null || echo "en_US.UTF-8")

    # Resolve the home-manager channel reference for templating
    if [[ -n "$HOME_MANAGER_CHANNEL_REF" ]]; then
        HM_CHANNEL_NAME="$HOME_MANAGER_CHANNEL_REF"
    fi

    if [[ -n "$HOME_MANAGER_CHANNEL_URL" ]]; then
        DETECTED_HM_CHANNEL="$HOME_MANAGER_CHANNEL_URL"
    fi

    if [[ -z "$DETECTED_HM_CHANNEL" ]]; then
        DETECTED_HM_CHANNEL=$(nix-channel --list | awk '/home-manager/ {print $2}')
    fi

    if [[ -z "$HM_CHANNEL_NAME" && -n "$DETECTED_HM_CHANNEL" ]]; then
        HM_CHANNEL_NAME=$(normalize_channel_name "$DETECTED_HM_CHANNEL")
    fi

    HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL_NAME")

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        HM_CHANNEL_NAME="release-${NIXOS_VERSION}"
        print_warning "Could not auto-detect home-manager channel, defaulting to $HM_CHANNEL_NAME"
    fi

    HM_FETCH_URL="https://github.com/nix-community/home-manager/archive/${HM_CHANNEL_NAME}.tar.gz"
    HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
    HOME_MANAGER_CHANNEL_URL="$HM_FETCH_URL"

    if [[ -z "$HM_FETCH_URL" ]]; then
        print_error "Failed to resolve home-manager tarball URL"
        exit 1
    fi

    print_info "Home-manager channel (system config): $HM_CHANNEL_NAME"

    # Detect hardware for optimization
    detect_gpu_and_cpu

    print_info "System: $HOSTNAME (NixOS $NIXOS_VERSION)"
    print_info "User: $USER"
    print_info "Timezone: $SELECTED_TIMEZONE"
    print_info "Locale: $CURRENT_LOCALE"

    # Backup old config
    if [[ -f "$SYSTEM_CONFIG" ]]; then
        SYSTEM_CONFIG_BACKUP="$SYSTEM_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
        sudo cp "$SYSTEM_CONFIG" "$SYSTEM_CONFIG_BACKUP"
        print_success "✓ Backed up: $SYSTEM_CONFIG_BACKUP"
    fi

    if [[ -f "$HARDWARE_CONFIG" ]]; then
        mkdir -p "$HM_CONFIG_DIR"

        local TARGET_HARDWARE_CONFIG="$HM_CONFIG_DIR/hardware-configuration.nix"

        # Remove a stale copy so we can replace it with the latest data
        if [[ -e "$TARGET_HARDWARE_CONFIG" || -L "$TARGET_HARDWARE_CONFIG" ]]; then
            rm -f "$TARGET_HARDWARE_CONFIG"
        fi

        # Prefer a symlink so updates to /etc/nixos/hardware-configuration.nix are picked up automatically
        if ln -s "$HARDWARE_CONFIG" "$TARGET_HARDWARE_CONFIG" 2>/dev/null; then
            print_success "Linked hardware-configuration.nix from /etc/nixos into $HM_CONFIG_DIR"
        else
            # Fall back to copying if the symlink cannot be created (e.g. different filesystem)
            if sudo cp "$HARDWARE_CONFIG" "$TARGET_HARDWARE_CONFIG"; then
                sudo chown "$USER":"$USER" "$TARGET_HARDWARE_CONFIG" 2>/dev/null || true
                print_success "Copied hardware-configuration.nix to $HM_CONFIG_DIR for flake builds"
            else
                print_warning "Could not copy hardware-configuration.nix to $HM_CONFIG_DIR"
            fi
        fi
    else
        print_warning "System hardware-configuration.nix not found; run 'sudo nixos-generate-config' if needed"
    fi


    # Generate complete AIDB configuration
    print_info "Generating complete AIDB development configuration..."
    echo ""

    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local TEMPLATE_DIR="$SCRIPT_DIR/templates"
    local SYSTEM_TEMPLATE="$TEMPLATE_DIR/configuration.nix"
    local GENERATED_CONFIG="$HM_CONFIG_DIR/configuration.nix"

    if [[ ! -f "$SYSTEM_TEMPLATE" ]]; then
        print_error "Missing NixOS configuration template: $SYSTEM_TEMPLATE"
        exit 1
    fi

    install -Dm644 "$SYSTEM_TEMPLATE" "$GENERATED_CONFIG"

    local CONFIG_WRITE_STATUS=$?

    if [ $CONFIG_WRITE_STATUS -ne 0 ]; then
        print_error "Failed to generate configuration"
        return 1
    fi

    local GENERATED_AT
    GENERATED_AT=$(date '+%Y-%m-%d %H:%M:%S %Z')

    local CPU_VENDOR_LABEL="$CPU_VENDOR"
    if [[ -z "$CPU_VENDOR_LABEL" || "$CPU_VENDOR_LABEL" == "unknown" ]]; then
        CPU_VENDOR_LABEL="Unknown"
    else
        CPU_VENDOR_LABEL="${CPU_VENDOR_LABEL^}"
    fi

    local INITRD_KERNEL_MODULES="# initrd.kernelModules handled by hardware-configuration.nix"
    case "$CPU_VENDOR" in
        intel)
            INITRD_KERNEL_MODULES='initrd.kernelModules = [ "i915" ];  # Intel GPU early KMS'
            ;;
        amd)
            INITRD_KERNEL_MODULES='initrd.kernelModules = [ "amdgpu" ];  # AMD GPU early KMS'
            ;;
    esac

    local MICROCODE_SECTION="# hardware.cpu microcode updates managed automatically"
    if [[ -n "$CPU_MICROCODE" && "$CPU_VENDOR" != "unknown" ]]; then
        MICROCODE_SECTION="hardware.cpu.${CPU_VENDOR}.updateMicrocode = true;  # Enable ${CPU_VENDOR_LABEL} microcode updates"
    fi

    local gpu_hardware_section
    case "$GPU_TYPE" in
        intel)
            gpu_hardware_section=$(cat <<'EOF'
hardware.opengl = {
    enable = true;
    extraPackages = with pkgs; [
      intel-media-driver  # VAAPI driver for Broadwell+ (>= 5th gen)
      vaapiIntel          # Older VAAPI driver for Haswell and older
      vaapiVdpau
      libvdpau-va-gl
      intel-compute-runtime  # OpenCL support
    ];
    driSupport = true;
    driSupport32Bit = true;  # For 32-bit applications
};
EOF
)
            ;;
        amd)
            gpu_hardware_section=$(cat <<'EOF'
hardware.opengl = {
    enable = true;
    extraPackages = with pkgs; [
      mesa              # Open-source AMD drivers
      amdvlk            # AMD Vulkan driver
      rocm-opencl-icd   # AMD OpenCL support
    ];
    driSupport = true;
    driSupport32Bit = true;
};
EOF
)
            ;;
        nvidia)
            gpu_hardware_section=$(cat <<'EOF'
# NVIDIA GPU configuration (auto-detected)
# Note: NVIDIA on Wayland requires additional setup
services.xserver.videoDrivers = [ "nvidia" ];
hardware.nvidia = {
    modesetting.enable = true;  # Required for Wayland
    open = false;  # Use proprietary driver (better performance)
    nvidiaSettings = true;  # Enable nvidia-settings GUI
    # Optional: Power management (for laptops)
    # powerManagement.enable = true;
};
hardware.opengl = {
    enable = true;
    driSupport = true;
    driSupport32Bit = true;
};
EOF
)
            ;;
        *)
            gpu_hardware_section="# No dedicated GPU configuration required (software rendering)"
            ;;
    esac

    local cosmic_gpu_block
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" && -n "$LIBVA_DRIVER" ]]; then
        local gpu_label="${GPU_TYPE^}"
        cosmic_gpu_block=$(cat <<EOF
# Hardware acceleration enabled (auto-detected: ${gpu_label} GPU)
    # VA-API driver: $LIBVA_DRIVER for video decode/encode acceleration
    extraSessionCommands = ''
      # Enable hardware video acceleration
      export LIBVA_DRIVER_NAME=$LIBVA_DRIVER
      # Enable touch/gesture support for trackpads
      export MOZ_USE_XINPUT2=1
    '';
EOF
)
    else
        cosmic_gpu_block=$(cat <<'EOF'
# No dedicated GPU detected - using software rendering
    # Hardware acceleration disabled
EOF
)
    fi

    local total_ram_value="${TOTAL_RAM_GB:-0}"
    local zram_value="${ZRAM_PERCENT:-50}"

    SCRIPT_VERSION_VALUE="$SCRIPT_VERSION" \
    GENERATED_AT="$GENERATED_AT" \
    HOSTNAME_VALUE="$HOSTNAME" \
    USER_VALUE="$USER" \
    CPU_VENDOR_LABEL_VALUE="$CPU_VENDOR_LABEL" \
    INITRD_KERNEL_MODULES_VALUE="$INITRD_KERNEL_MODULES" \
    MICROCODE_SECTION_VALUE="$MICROCODE_SECTION" \
    GPU_HARDWARE_SECTION_VALUE="$gpu_hardware_section" \
    COSMIC_GPU_BLOCK_VALUE="$cosmic_gpu_block" \
    SELECTED_TIMEZONE_VALUE="$SELECTED_TIMEZONE" \
    CURRENT_LOCALE_VALUE="$CURRENT_LOCALE" \
    NIXOS_VERSION_VALUE="$NIXOS_VERSION" \
    ZRAM_PERCENT_VALUE="$zram_value" \
    TOTAL_RAM_GB_VALUE="$total_ram_value" \
    python3 - "$GENERATED_CONFIG" <<'PY'
import os
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

replacements = {
    "@SCRIPT_VERSION@": os.environ.get("SCRIPT_VERSION_VALUE", ""),
    "@GENERATED_AT@": os.environ.get("GENERATED_AT", ""),
    "@HOSTNAME@": os.environ.get("HOSTNAME_VALUE", ""),
    "@USER@": os.environ.get("USER_VALUE", ""),
    "@CPU_VENDOR_LABEL@": os.environ.get("CPU_VENDOR_LABEL_VALUE", "Unknown"),
    "@INITRD_KERNEL_MODULES@": os.environ.get("INITRD_KERNEL_MODULES_VALUE", ""),
    "@MICROCODE_SECTION@": os.environ.get("MICROCODE_SECTION_VALUE", ""),
    "@GPU_HARDWARE_SECTION@": os.environ.get("GPU_HARDWARE_SECTION_VALUE", ""),
    "@COSMIC_GPU_BLOCK@": os.environ.get("COSMIC_GPU_BLOCK_VALUE", ""),
    "@SELECTED_TIMEZONE@": os.environ.get("SELECTED_TIMEZONE_VALUE", "UTC"),
    "@CURRENT_LOCALE@": os.environ.get("CURRENT_LOCALE_VALUE", "en_US.UTF-8"),
    "@NIXOS_VERSION@": os.environ.get("NIXOS_VERSION_VALUE", "23.11"),
    "@ZRAM_PERCENT@": os.environ.get("ZRAM_PERCENT_VALUE", "50"),
    "@TOTAL_RAM_GB@": os.environ.get("TOTAL_RAM_GB_VALUE", "0"),
}

for placeholder, value in replacements.items():
    text = text.replace(placeholder, value)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
PY

    local render_status=$?
    if [ $render_status -ne 0 ]; then
        print_error "Failed to render configuration template"
        return 1
    fi

    print_success "✓ Complete AIDB configuration generated"
    print_info "Includes: Cosmic Desktop, Podman, Fonts, Audio, ZSH"
    echo ""

    # Apply the new configuration
    print_section "Applying New Configuration"
    print_warning "Running: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$HOSTNAME"
    print_info "This will download and install all AIDB components using the generated flake..."
    print_info "May take 10-20 minutes on first run"
    echo ""

    if sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$HOSTNAME" 2>&1 | tee /tmp/nixos-rebuild.log; then
        print_success "✓ NixOS system configured successfully!"
        print_success "✓ AIDB development environment ready"
        echo ""

        # Configure Flatpak for COSMIC Store
        print_section "Configuring Flatpak for COSMIC App Store"
        print_info "Adding Flathub repository for user..."
        if flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null; then
            print_success "✓ Flathub repository added"
            print_info "COSMIC Store can now install Flatpak applications"
        else
            print_warning "Flatpak repository setup skipped (may already exist)"
        fi
        echo ""
    else
        print_error "nixos-rebuild failed - restoring backup"
        sudo cp "$SYSTEM_CONFIG_BACKUP" "$SYSTEM_CONFIG"
        print_info "Backup restored. Check: /tmp/nixos-rebuild.log"
        exit 1
    fi
}


# ============================================================================
# Flake Integration & AIDB Development Environment
# ============================================================================

setup_flake_environment() {
    print_section "Setting Up Flake-based Development Environment"

    # Check if flake.nix exists in the NixOS-Quick-Deploy directory
    FLAKE_DIR="$HM_CONFIG_DIR"
    FLAKE_FILE="$FLAKE_DIR/flake.nix"

    if [[ ! -f "$FLAKE_FILE" ]]; then
        print_warning "flake.nix not found at $FLAKE_FILE"
        print_info "Flake integration will be skipped"
        return 1
    fi

    print_success "Found flake.nix at $FLAKE_FILE"

    # Check if activation script already exists (IDEMPOTENCY CHECK)
    if [ -f "$HOME/.local/bin/aidb-dev-env" ] && [ -f "$HOME/.config/zsh/aidb-flake.zsh" ]; then
        print_success "✓ Flake activation scripts already configured"
        print_info "Skipping flake setup (idempotent)"

        # Still check if flake needs update
        print_info "Verifying flake environment is cached..."
        if cd "$FLAKE_DIR" && nix flake metadata >/dev/null 2>&1; then
            print_success "✓ Flake environment is ready"
            cd - > /dev/null
            echo ""
            return 0
        fi
        cd - > /dev/null 2>&1 || true
    fi

    # Enable experimental features for flakes
    print_info "Ensuring Nix flakes are enabled..."
    mkdir -p "$HOME/.config/nix"
    cat > "$HOME/.config/nix/nix.conf" <<'NIXCONF'
experimental-features = nix-command flakes
NIXCONF
    print_success "Nix flakes enabled"

    # Build the flake development shell to ensure all packages are available
    print_info "Building flake development environment (this may take a few minutes)..."
    echo ""

    if cd "$FLAKE_DIR" && nix develop --command echo "Flake environment built successfully" 2>&1 | tee /tmp/flake-build.log; then
        print_success "Flake development environment built and cached"
        echo ""
        cd - > /dev/null
    else
        local flake_exit_code=$?
        cd - > /dev/null 2>&1 || true
        print_error "Failed to build flake environment (exit code: $flake_exit_code)"
        echo ""
        print_warning "Common causes:"
        echo "  • Syntax error in flake.nix"
        echo "  • Network issues downloading dependencies"
        echo "  • Flakes not enabled in system configuration"
        echo ""
        print_info "Full log saved to: /tmp/flake-build.log"
        print_info "You can manually build it later with: cd $FLAKE_DIR && nix develop"
        echo ""
        print_warning "This is not critical - continuing without flake environment"
        echo ""
    fi

    # Create a convenient activation script
    print_info "Creating flake activation script..."
    cat > "$HOME/.local/bin/aidb-dev-env" <<'DEVENV'
#!/usr/bin/env bash
# AIDB Development Environment Activator
# Enters the flake development shell with all AIDB tools

FLAKE_DIR="/home/$USER/.config/home-manager/"

if [[ ! -f "$FLAKE_DIR/flake.nix" ]]; then
    echo "Error: flake.nix not found at $FLAKE_DIR"
    exit 1
fi

echo "Entering AIDB development environment..."
cd "$FLAKE_DIR" && exec nix develop
DEVENV

    # Fix the $USER variable in the script
    sed -i "s|\$USER|$USER|g" "$HOME/.local/bin/aidb-dev-env"
    chmod +x "$HOME/.local/bin/aidb-dev-env"
    print_success "Created aidb-dev-env activation script"

    # Add flake information to shell profile
    print_info "Adding flake information to ZSH profile..."
    mkdir -p "$HOME/.config/zsh"
    cat > "$HOME/.config/zsh/aidb-flake.zsh" <<'ZSHFLAKE'

# AIDB Flake Integration
# Quick access to AIDB development environment

alias aidb-dev='aidb-dev-env'
alias aidb-shell='cd ~/.config/home-manager/ && nix develop'
alias aidb-update='cd ~/.config/home-manager/ && nix flake update'

# Show AIDB development environment info
aidb-info() {
    echo "AIDB Development Environment"
    echo "  Flake location: ~/.config/home-manager/flake.nix"
    echo "  Enter dev env:  aidb-dev or aidb-shell"
    echo "  Update flake:   aidb-update"
    echo ""
    echo "Available in dev environment:"
    echo "  - Podman + podman-compose"
    echo "  - Python 3.11 with cryptography, fastapi, uvicorn"
    echo "  - SQLite, OpenSSL, Git, jq, curl"
    echo "  - inotify-tools (for Guardian file watching)"
}
ZSHFLAKE

    # Source this in .zshrc if not already done
    if ! grep -q "aidb-flake.zsh" "$HOME/.zshrc" 2>/dev/null; then
        echo 'source ~/.config/zsh/aidb-flake.zsh' >> "$HOME/.zshrc"
        print_success "Added AIDB flake aliases to .zshrc"
    fi

    print_success "Flake environment setup complete!"
    print_info "Use 'aidb-dev' or 'aidb-shell' to enter the development environment"
}

# ============================================================================
# Claude Code Installation & Configuration
# ============================================================================

install_claude_code() {
    print_section "Installing Claude Code"

    # Set up NPM paths
    export NPM_CONFIG_PREFIX=~/.npm-global
    mkdir -p ~/.npm-global/bin
    export PATH=~/.npm-global/bin:$PATH

    # Check if Claude Code already installed (SMART CHANGE DETECTION)
    CLI_FILE="$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"
    WRAPPER_FILE="$HOME/.npm-global/bin/claude-wrapper"

    if [ -f "$CLI_FILE" ] && [ -f "$WRAPPER_FILE" ] && [ "$FORCE_UPDATE" = false ]; then
        # Check if wrapper still works
        if ~/.npm-global/bin/claude-wrapper --version >/dev/null 2>&1; then
            CLAUDE_VERSION=$(~/.npm-global/bin/claude-wrapper --version 2>/dev/null | head -n1)
            print_success "✓ Claude Code installed: ${CLAUDE_VERSION}"

            # Check if there's an update available
            print_info "Checking for Claude Code updates..."
            LATEST_VERSION=$(npm view @anthropic-ai/claude-code version 2>/dev/null || echo "")

            if [ -n "$LATEST_VERSION" ]; then
                # Extract version numbers for comparison
                CURRENT_VER=$(echo "$CLAUDE_VERSION" | grep -oP '\d+\.\d+\.\d+' || echo "0.0.0")

                if [ "$CURRENT_VER" != "$LATEST_VERSION" ]; then
                    print_warning "Update available: $CURRENT_VER → $LATEST_VERSION"

                    if confirm "Update Claude Code to latest version?" "y"; then
                        print_info "Updating Claude Code..."
                        # Continue to update
                    else
                        print_info "Skipping update - keeping version $CURRENT_VER"
                        echo ""
                        return 0
                    fi
                else
                    print_success "✓ Claude Code is up-to-date (v$CURRENT_VER)"
                    echo ""
                    return 0
                fi
            else
                print_info "Skipping version check (npm registry unavailable)"
                print_success "✓ Claude Code wrapper working, keeping current version"
                echo ""
                return 0
            fi
        else
            print_warning "Claude Code installed but wrapper not working"
            print_info "Will recreate wrapper..."
            # Continue to recreate wrapper
        fi
    fi

    # Install or update Claude Code
    if [ -f "$CLI_FILE" ]; then
        print_info "Updating @anthropic-ai/claude-code via npm..."
    else
        print_info "Installing @anthropic-ai/claude-code via npm..."
    fi

    if npm install -g @anthropic-ai/claude-code 2>&1 | tee /tmp/claude-code-install.log; then
        print_success "Claude Code npm package installed/updated"
    else
        local npm_exit_code=$?
        print_error "Failed to install Claude Code (exit code: $npm_exit_code)"
        echo ""
        print_warning "Common causes:"
        echo "  • Network connection issues"
        echo "  • NPM registry unavailable"
        echo "  • Insufficient disk space"
        echo "  • Node.js not properly installed"
        echo ""
        print_info "Full log saved to: /tmp/claude-code-install.log"
        print_warning "Claude Code integration will be skipped - you can install it manually later"
        echo ""
        print_info "Manual installation:"
        echo "  export NPM_CONFIG_PREFIX=~/.npm-global"
        echo "  npm install -g @anthropic-ai/claude-code"
        echo ""
        return 1
    fi

    # Verify installation
    CLI_FILE="$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"
    if [ ! -f "$CLI_FILE" ]; then
        print_error "Claude Code CLI not found at $CLI_FILE"
        return 1
    fi

    # Make CLI executable
    chmod +x "$CLI_FILE"
    print_success "Claude Code CLI is executable"

    # Create smart Node.js wrapper
    print_info "Creating smart Node.js wrapper..."

    cat > ~/.npm-global/bin/claude-wrapper << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Smart Claude Code Wrapper - Finds Node.js dynamically
# Works across Node.js updates and NixOS rebuilds

# Strategy 1: Try common Nix profile locations (fastest)
NODE_LOCATIONS=(
    "$HOME/.nix-profile/bin/node"
    "/run/current-system/sw/bin/node"
    "/nix/var/nix/profiles/default/bin/node"
    "$(which node 2>/dev/null)"
)

NODE_BIN=""
for node_path in "${NODE_LOCATIONS[@]}"; do
    # Resolve symlinks to get actual Nix store path
    if [ -n "$node_path" ] && [ -x "$node_path" ]; then
        NODE_BIN=$(readlink -f "$node_path" 2>/dev/null || echo "$node_path")
        if [ -x "$NODE_BIN" ]; then
            break
        fi
    fi
done

# Strategy 2: Search PATH if not found
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    NODE_BIN=$(command -v node 2>/dev/null)
    if [ -n "$NODE_BIN" ]; then
        NODE_BIN=$(readlink -f "$NODE_BIN")
    fi
fi

# Strategy 3: Find in Nix store directly (last resort)
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    NODE_BIN=$(find /nix/store -maxdepth 2 -name "node" -type f -executable 2>/dev/null | grep -m1 "nodejs.*bin/node" || echo "")
fi

# Fail if still not found
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    echo "Error: Could not find Node.js executable" >&2
    echo "Searched locations:" >&2
    printf '%s\n' "${NODE_LOCATIONS[@]}" >&2
    echo "PATH: $PATH" >&2
    exit 127
fi

# Path to Claude Code CLI
CLAUDE_CLI="$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"

if [ ! -f "$CLAUDE_CLI" ]; then
    echo "Error: Claude Code CLI not found at $CLAUDE_CLI" >&2
    exit 127
fi

# Execute with Node.js
exec "$NODE_BIN" "$CLAUDE_CLI" "$@"
WRAPPER_EOF

    chmod +x ~/.npm-global/bin/claude-wrapper
    print_success "Created claude-wrapper"

    # Test the wrapper
    if ~/.npm-global/bin/claude-wrapper --version >/dev/null 2>&1; then
        CLAUDE_VERSION=$(~/.npm-global/bin/claude-wrapper --version 2>/dev/null | head -n1)
        print_success "Claude Code wrapper works! Version: ${CLAUDE_VERSION}"
        CLAUDE_EXEC_PATH="$HOME/.npm-global/bin/claude-wrapper"
    else
        print_warning "Wrapper test inconclusive, but created"
        CLAUDE_EXEC_PATH="$HOME/.npm-global/bin/claude-wrapper"
    fi

    # Create VSCodium wrapper
    print_info "Creating VSCodium wrapper..."
    mkdir -p ~/.local/bin

    cat > ~/.local/bin/codium-wrapped << 'CODIUM_WRAPPER_EOF'
#!/usr/bin/env bash
# VSCodium wrapper that ensures Claude Code is in PATH

export NPM_CONFIG_PREFIX="$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

# Debug mode
if [ -n "$CODIUM_DEBUG" ]; then
    echo "NPM_CONFIG_PREFIX: $NPM_CONFIG_PREFIX"
    echo "PATH: $PATH"
    echo "Claude wrapper: $(which claude-wrapper 2>/dev/null || echo 'not found')"
fi

exec codium "$@"
CODIUM_WRAPPER_EOF

    chmod +x ~/.local/bin/codium-wrapped
    print_success "VSCodium wrapper created"
}

configure_vscodium_for_claude() {
    print_section "Adding Claude Code Configuration to VSCodium"

    # Get paths for environment variables
    NODE_BIN_DIR=$(dirname $(readlink -f $(which node) 2>/dev/null) 2>/dev/null || echo "$HOME/.nix-profile/bin")
    NIX_PROFILE_BIN="$HOME/.nix-profile/bin"
    CLAUDE_EXEC_PATH="$HOME/.npm-global/bin/claude-wrapper"

    print_info "Node.js bin directory: $NODE_BIN_DIR"
    print_info "Nix profile bin: $NIX_PROFILE_BIN"
    print_info "Claude wrapper: $CLAUDE_EXEC_PATH"

    SETTINGS_FILE="$HOME/.config/VSCodium/User/settings.json"

    # Check if Claude Code settings already configured (IDEMPOTENCY CHECK)
    if [ -f "$SETTINGS_FILE" ]; then
        if jq -e '."claude-code.executablePath"' "$SETTINGS_FILE" >/dev/null 2>&1; then
            print_success "✓ Claude Code already configured in VSCodium settings"
            print_info "Skipping configuration (idempotent)"

            # Update paths if they've changed (silent update)
            jq --arg execPath "$CLAUDE_EXEC_PATH" \
               --arg nixBin "$NIX_PROFILE_BIN" \
               --arg nodeBin "$NODE_BIN_DIR" \
               --arg npmModules "$HOME/.npm-global/lib/node_modules" \
               '."claude-code.executablePath" = $execPath |
                ."claudeCode.executablePath" = $execPath |
                ."claude-code.claudeProcessWrapper" = $execPath |
                ."claudeCode.claudeProcessWrapper" = $execPath' \
               "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp" && mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"

            print_success "✓ Paths updated to current system"
            echo ""
            return 0
        fi
    fi

    # Backup existing settings ONLY if making changes
    if [ -f "$SETTINGS_FILE" ]; then
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%s)"
        print_success "Backed up existing settings"
    fi

    # Use jq to merge Claude Code settings with existing settings
    # This preserves home-manager's declarative settings while adding dynamic paths
    if command -v jq &> /dev/null && [ -f "$SETTINGS_FILE" ]; then
        print_info "Merging Claude Code settings with existing configuration..."

        TEMP_SETTINGS=$(mktemp)
        jq --arg execPath "$CLAUDE_EXEC_PATH" \
           --arg nixBin "$NIX_PROFILE_BIN" \
           --arg nodeBin "$NODE_BIN_DIR" \
           --arg npmModules "$HOME/.npm-global/lib/node_modules" \
           '. + {
              "claude-code.executablePath": $execPath,
              "claude-code.claudeProcessWrapper": $execPath,
              "claude-code.environmentVariables": [
                {
                  "name": "PATH",
                  "value": ($nixBin + ":" + $nodeBin + ":/run/current-system/sw/bin:${env:PATH}")
                },
                {
                  "name": "NODE_PATH",
                  "value": $npmModules
                }
              ],
              "claude-code.autoStart": false,
              "claudeCode.executablePath": $execPath,
              "claudeCode.claudeProcessWrapper": $execPath,
              "claudeCode.environmentVariables": [
                {
                  "name": "PATH",
                  "value": ($nixBin + ":" + $nodeBin + ":/run/current-system/sw/bin:${env:PATH}")
                },
                {
                  "name": "NODE_PATH",
                  "value": $npmModules
                }
              ],
              "claudeCode.autoStart": false
           }' "$SETTINGS_FILE" > "$TEMP_SETTINGS"

        mv "$TEMP_SETTINGS" "$SETTINGS_FILE"
        print_success "Claude Code settings merged successfully"
    else
        print_warning "jq not available, creating full settings file"
        # Fallback: create complete settings file
        cat > "$SETTINGS_FILE" << 'SETTINGS_EOF'
{
  "claude-code.executablePath": "CLAUDE_EXEC_PATH_PLACEHOLDER",
  "claude-code.claudeProcessWrapper": "CLAUDE_EXEC_PATH_PLACEHOLDER",
  "claude-code.environmentVariables": [
    {"name": "PATH", "value": "NIX_PROFILE_BIN_PLACEHOLDER:NODE_BIN_DIR_PLACEHOLDER:/run/current-system/sw/bin:${env:PATH}"},
    {"name": "NODE_PATH", "value": "NPM_MODULES_PLACEHOLDER"}
  ],
  "claude-code.autoStart": false,
  "claudeCode.executablePath": "CLAUDE_EXEC_PATH_PLACEHOLDER",
  "claudeCode.claudeProcessWrapper": "CLAUDE_EXEC_PATH_PLACEHOLDER",
  "claudeCode.environmentVariables": [
    {"name": "PATH", "value": "NIX_PROFILE_BIN_PLACEHOLDER:NODE_BIN_DIR_PLACEHOLDER:/run/current-system/sw/bin:${env:PATH}"},
    {"name": "NODE_PATH", "value": "NPM_MODULES_PLACEHOLDER"}
  ],
  "claudeCode.autoStart": false
}
SETTINGS_EOF
        # Replace placeholders
        sed -i "s|CLAUDE_EXEC_PATH_PLACEHOLDER|${CLAUDE_EXEC_PATH}|g" "$SETTINGS_FILE"
        sed -i "s|NIX_PROFILE_BIN_PLACEHOLDER|${NIX_PROFILE_BIN}|g" "$SETTINGS_FILE"
        sed -i "s|NODE_BIN_DIR_PLACEHOLDER|${NODE_BIN_DIR}|g" "$SETTINGS_FILE"
        sed -i "s|NPM_MODULES_PLACEHOLDER|${HOME}/.npm-global/lib/node_modules|g" "$SETTINGS_FILE"
        print_success "Claude Code settings created"
    fi
}

install_vscodium_extensions() {
    print_section "Installing Additional VSCodium Extensions"

    # Export PATH
    export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

    # Kill any running VSCodium instances
    pkill -f "codium" 2>/dev/null && print_info "Killed running VSCodium processes" || true
    sleep 2

    # Function to install extension with retry
    install_ext() {
        local ext=$1
        local name=$2

        print_info "Installing: ${name}"

        for i in {1..3}; do
            if codium --install-extension "$ext" 2>/dev/null; then
                print_success "${name} installed"
                return 0
            else
                if [ $i -lt 3 ]; then
                    print_warning "Retry $i/3..."
                    sleep 2
                fi
            fi
        done

        print_warning "${name} - install manually if needed"
        return 1
    }

    # Note: Base extensions (Nix IDE, GitLens, Prettier, EditorConfig)
    # are already installed via home-manager's programs.vscode.extensions

    # Install Claude Code (main addition)
    print_info "Installing Claude Code extension..."
    install_ext "Anthropic.claude-code" "Claude Code"

    # Install additional helpful extensions not in nixpkgs
    print_info "Installing additional development extensions..."
    install_ext "dbaeumer.vscode-eslint" "ESLint"
    install_ext "mhutchie.git-graph" "Git Graph"
    install_ext "golang.go" "Go"
    install_ext "rust-lang.rust-analyzer" "Rust Analyzer"
    install_ext "usernamehw.errorlens" "Error Lens"
    install_ext "tamasfe.even-better-toml" "Even Better TOML"
    install_ext "redhat.vscode-yaml" "YAML"
    install_ext "mechatroner.rainbow-csv" "Rainbow CSV"
    install_ext "gruntfuggly.todo-tree" "Todo Tree"
    install_ext "pkief.material-icon-theme" "Material Icon Theme"
    install_ext "ms-azuretools.vscode-docker" "Docker"
    install_ext "hashicorp.terraform" "Terraform"

    print_success "Additional extensions installation complete"
}

# ============================================================================
# Post-Install Instructions
# ============================================================================

print_post_install() {
    print_section "Installation Complete!"

    echo ""
    echo -e "${GREEN}✓ NixOS Quick Deploy Complete - FULLY CONFIGURED!${NC}"
    echo ""
    echo -e "${BLUE}What was installed and configured:${NC}"
    echo ""
    echo -e "  ${GREEN}System Configuration (via nixos-rebuild):${NC}"
    echo "    • Nix flakes enabled"
    echo "    • Podman virtualization enabled"
    echo "    • Cosmic desktop environment enabled"
    echo "    • Unfree packages allowed"
    echo ""
    echo -e "  ${GREEN}AIDB Prerequisites (via home-manager):${NC}"
    echo "    • Podman + podman-compose (container runtime)"
    echo "    • SQLite (Tier 1 Guardian database)"
    echo "    • Python 3.11 + pip + virtualenv"
    echo "    • OpenSSL, inotify-tools, bc"
    echo ""
    echo -e "  ${GREEN}NixOS Development Tools:${NC}"
    echo "    • Nix tools (nix-tree, nixpkgs-fmt, alejandra, statix, etc.)"
    echo "    • VSCodium with NixOS + Claude Code extensions"
    echo ""
    echo -e "  ${GREEN}Claude Code Integration:${NC}"
    echo "    • Claude Code CLI installed globally"
    echo "    • Smart Node.js wrapper (fixes Error 127)"
    echo "    • VSCodium fully configured for Claude Code"
    echo "    • All required extensions installed"
    echo ""
    echo -e "  ${GREEN}Modern CLI & Terminal:${NC}"
    echo "    • ZSH with Powerlevel10k theme"
    echo "    • Modern tools (ripgrep, bat, eza, fzf, fd, etc.)"
    echo "    • Alacritty terminal"
    echo "    • Git with aliases"
    echo ""
    echo -e "  ${GREEN}Desktop Environment:${NC}"
    echo "    • Cosmic desktop components (cosmic-edit, cosmic-files, cosmic-term)"
    echo "    • Modern Rust-based desktop environment"
    echo ""
    echo -e "  ${GREEN}Flake-based AIDB Environment:${NC}"
    echo "    • Development shell with all AIDB dependencies"
    echo "    • Commands: aidb-dev, aidb-shell, aidb-info"
    echo "    • Auto-configured Python environment"
    echo ""
    echo -e "${BLUE}Important Notes:${NC}"
    echo -e "  1. ${YELLOW}REBOOT REQUIRED:${NC} System configuration changed (Cosmic desktop added)"
    echo -e "     Run: ${GREEN}sudo reboot${NC}"
    echo -e "  2. ${YELLOW}After reboot:${NC} Select \"Cosmic\" from the session menu at login"
    echo -e "  3. ${YELLOW}Restart your terminal:${NC} exec zsh (or after reboot)"
    echo -e "  4. VSCodium command: ${GREEN}codium${NC} or ${GREEN}codium-wrapped${NC}"
    echo -e "  5. Claude Code wrapper: ${GREEN}~/.npm-global/bin/claude-wrapper${NC}"
    echo -e "  6. ${GREEN}All configurations applied automatically!${NC}"
    echo ""
    echo -e "${BLUE}Next Steps - Deploy AIDB:${NC}"
    echo -e "  ${GREEN}1. Clone AIDB repository:${NC}"
    echo "     git clone <your-repo> ~/Documents/AI-Opitmizer"
    echo "     cd ~/Documents/AI-Opitmizer"
    echo ""
    echo -e "  ${GREEN}2. Setup AIDB template:${NC}"
    echo "     bash aidb-quick-setup.sh --template"
    echo ""
    echo -e "  ${GREEN}3. Create your first project:${NC}"
    echo "     bash aidb-quick-setup.sh --project MyProject"
    echo ""
    echo -e "  ${GREEN}4. Start AIDB:${NC}"
    echo "     cd ~/Documents/Projects/MyProject/.aidb/deployment/"
    echo "     ./scripts/start.sh"
    echo ""
    echo -e "  ${GREEN}5. Verify AIDB is running:${NC}"
    echo "     curl http://localhost:8000/health"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo -e "  ${GREEN}NixOS:${NC}"
    echo "    nrs              # sudo nixos-rebuild switch"
    echo "    hms              # home-manager switch"
    echo "    nfu              # nix flake update"
    echo ""
    echo -e "  ${GREEN}AIDB Development Environment:${NC}"
    echo "    aidb-dev         # Enter flake dev environment with all tools"
    echo "    aidb-shell       # Alternative way to enter dev environment"
    echo "    aidb-info        # Show AIDB environment information"
    echo "    aidb-update      # Update flake dependencies"
    echo ""
    echo -e "  ${GREEN}Container Management:${NC}"
    echo "    podman pod ps    # List running pods"
    echo "    podman ps        # List running containers"
    echo ""
    echo -e "  ${GREEN}Development:${NC}"
    echo "    nixpkgs-fmt      # Format Nix code"
    echo "    alejandra        # Alternative Nix formatter"
    echo "    statix check     # Lint Nix code"
    echo "    lg               # lazygit"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo "  • AIDB docs: ~/Documents/AI-Opitmizer/README.md"
    echo "  • Shared knowledge: ~/Documents/AI-Opitmizer/.aidb-shared-knowledge/"
    echo "  • Home manager: https://nix-community.github.io/home-manager/"
    echo ""
    echo -e "${GREEN}System is ready! Now deploy AIDB when you're ready.${NC}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force-update|-f)
                FORCE_UPDATE=true
                shift
                ;;
            --help|-h)
                print_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    print_header

    # Check if running with proper permissions
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        exit 1
    fi

    if [ "$FORCE_UPDATE" = true ]; then
        print_warning "Force update mode enabled - will recreate all configurations"
        echo ""
    fi

    check_prerequisites
    gather_user_info

    # Step 0: Select NixOS version (25.11 or current)
    # This must run before updating channels
    select_nixos_version

    # Step 1: Update NixOS system configuration (Cosmic, Podman, Flakes)
    # This runs first so system-level packages are available
    update_nixos_system_config

    # Step 2: Create and apply home-manager configuration (user packages)
    create_home_manager_config
    apply_home_manager_config

    # Step 3: Flake integration (runs after home-manager to use packages for AIDB development)
    # Non-critical - errors won't stop deployment
    if ! setup_flake_environment; then
        print_warning "Flake environment setup had issues (see above)"
        print_info "You can set it up manually later if needed"
        echo ""
    fi

    # Step 4: Claude Code integration (runs after home-manager so Node.js is available)
    # Non-critical - errors won't stop deployment
    if install_claude_code; then
        configure_vscodium_for_claude || print_warning "VSCodium configuration had issues"
        install_vscodium_extensions || print_warning "Some VSCodium extensions may not have installed"
    else
        print_warning "Claude Code installation skipped due to errors"
        print_info "You can install it manually later if needed"
        echo ""
    fi


    print_post_install

    # NEVER auto-reboot - just provide clear instructions
    echo ""
    print_section "Setup Complete!"
    echo ""
    print_warning "IMPORTANT: System reboot required"
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║${NC}  MANUAL REBOOT REQUIRED                                       ${YELLOW}║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}A reboot is required to:${NC}"
    echo -e "  ${GREEN}•${NC} Load Cosmic desktop environment"
    echo -e "  ${GREEN}•${NC} Ensure all system services start properly"
    echo -e "  ${GREEN}•${NC} Apply kernel-level changes"
    echo -e "  ${GREEN}•${NC} Load all home-manager packages into PATH"
    echo ""
    echo -e "${BLUE}When you're ready to reboot:${NC}"
    echo -e "  ${GREEN}1.${NC} Save all your work"
    echo -e "  ${GREEN}2.${NC} Close all applications"
    echo -e "  ${GREEN}3.${NC} Run: ${YELLOW}sudo reboot${NC}"
    echo ""
    echo -e "${BLUE}After reboot:${NC}"
    echo -e "  ${GREEN}•${NC} Select 'Cosmic' from the session menu at login"
    echo -e "  ${GREEN}•${NC} Open a terminal and verify: ${YELLOW}which claude-wrapper${NC}"
    echo -e "  ${GREEN}•${NC} Launch VSCodium: ${YELLOW}codium${NC}"
    echo ""
    echo -e "${GREEN}✓ Deployment complete! All configurations applied successfully.${NC}"
    echo -e "${GREEN}✓ Claude Code and VSCodium are fully configured and will persist.${NC}"
    echo ""
    echo -e "${YELLOW}Remember: ${NC}Reboot manually when ready: ${YELLOW}sudo reboot${NC}"
    echo ""
}

main "$@"
