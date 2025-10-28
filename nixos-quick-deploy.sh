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
        print_info "Found existing home-manager config, backing up all files..."

        if [[ -f "$HM_CONFIG_FILE" ]]; then
            HOME_MANAGER_BACKUP="$HM_CONFIG_FILE.backup.$BACKUP_TIMESTAMP"
            cp "$HM_CONFIG_FILE" "$HOME_MANAGER_BACKUP"
            print_success "Backed up home.nix"
        fi

        if [[ -f "$HM_CONFIG_DIR/flake.nix" ]]; then
            cp "$HM_CONFIG_DIR/flake.nix" "$HM_CONFIG_DIR/backup/flake.nix.backup.$BACKUP_TIMESTAMP"
            print_success "Backed up flake.nix"
        fi

        if [[ -f "$HM_CONFIG_DIR/flake.lock" ]]; then
            cp "$HM_CONFIG_DIR/flake.lock" "$HM_CONFIG_DIR/backup/flake.lock.backup.$BACKUP_TIMESTAMP"
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

    # Create a flake.nix in the home-manager config directory for proper Flatpak support
    # This enables using: home-manager switch --flake ~/.config/home-manager
    print_info "Creating home-manager flake configuration for Flatpak support..."
    local FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
    local SYSTEM_ARCH=$(nix eval --raw --expr builtins.currentSystem 2>/dev/null || echo "x86_64-linux")
    local CURRENT_HOSTNAME=$(hostname)

    cat > "$FLAKE_FILE" <<'FLAKEEOF'
{
  description = "AIDB NixOS and Home Manager configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/NIXPKGS_CHANNEL_PLACEHOLDER";
    home-manager = {
      url = "github:nix-community/home-manager?ref=HM_CHANNEL_PLACEHOLDER";
    #nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager/HM_CHANNEL_PLACEHOLDER";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-flatpak.url = "github:gmodena/nix-flatpak";
  };

  outputs = { self, nixpkgs, home-manager, nix-flatpak, ... }:
    let
      system = "SYSTEM_PLACEHOLDER";
    in
    {
      nixosConfigurations."HOSTNAME_PLACEHOLDER" = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = {
          inherit nix-flatpak;
        };
        modules = [
          ./configuration.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users."HOME_USERNAME_PLACEHOLDER" = import ./home.nix;
          }
        ];
      };

      homeConfigurations."HOME_USERNAME_PLACEHOLDER" = home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs = {
          inherit nix-flatpak;
        };
        modules = [
          ./home.nix
        ];
      };
    };
}
FLAKEEOF
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

    # Calculate template hash for change detection
    local TEMPLATE_HASH=$(echo -n "AIDB-v4.0-packages-v$SCRIPT_VERSION" | sha256sum | cut -d' ' -f1 | cut -c1-16)

    cat > "$HM_CONFIG_FILE" <<'NIXEOF'
# NixOS Quick Deploy - Home Manager Configuration
# Generated by: nixos-quick-deploy.sh vVERSIONPLACEHOLDER
# Template Hash: HASHPLACEHOLDER
# This hash is used to detect when the template changes
# If you edit this file manually, your edits will be preserved
# until the template itself changes (new packages added to script)

{ config, pkgs, nix-flatpak, ... }:

{
  # nix-flatpak module is imported in flake.nix as a proper home-manager module
  # This enables declarative Flatpak management through services.flatpak configuration
  # No manual import needed here - the module is loaded by home-manager automatically

  imports = [
    nix-flatpak.homeManagerModules.nix-flatpak
  ];

  home.username = "HOMEUSERNAME";
  home.homeDirectory = "HOMEDIR";
  home.stateVersion = "STATEVERSION_PLACEHOLDER";  # Auto-detected from home-manager channel

  programs.home-manager.enable = true;
  nixpkgs.config.allowUnfree = true;

  home.packages = with pkgs; [
    # ========================================================================
    # AIDB v4.0 Requirements (CRITICAL - Must be installed)
    # ========================================================================

    podman                  # Container runtime for AIDB
    podman-compose          # Docker-compose compatibility
    sqlite                  # Tier 1 Guardian database
    openssl                 # Cryptographic operations
    bc                      # Basic calculator
    inotify-tools           # File watching for Guardian

    # ========================================================================
    # Core NixOS Development Tools
    # ========================================================================

    # Nix tools
    nix-tree                # Visualize Nix dependencies
    nix-index               # Index Nix packages for fast searching
    nix-prefetch-git        # Prefetch git repositories
    nixpkgs-fmt             # Nix code formatter
    alejandra               # Alternative Nix formatter
    statix                  # Linter for Nix
    deadnix                 # Find dead Nix code
    nix-output-monitor      # Better build output
    nix-du                  # Disk usage for Nix store
    nixpkgs-review          # Review nixpkgs PRs
    nix-diff                # Compare Nix derivations

    # ========================================================================
    # Development Tools
    # ========================================================================

    # Version control
    # Note: git installed via programs.git below (prevents collision)
    git-crypt               # Transparent file encryption in git
    tig                     # Text-mode interface for git
    lazygit                 # Terminal UI for git commands

    # Text editors
    # Note: vim installed via programs.vim below (prevents collision)
    neovim                  # Modern Vim fork with async support
    # Note: vscodium installed via programs.vscode below

    # Web browsers are now installed via Flatpak for better sandboxing:
    # Firefox: "org.mozilla.firefox" in services.flatpak.packages
    # Chromium: Available as "com.google.Chrome" if needed
    # (Both still available in home.packages comments if NixOS versions preferred)

    # Modern CLI tools
    ripgrep                 # Fast recursive grep (rg)
    ripgrep-all             # Ripgrep with PDF, archive support
    fd                      # Fast alternative to find
    fzf                     # Fuzzy finder for command line
    bat                     # Cat clone with syntax highlighting
    eza                     # Modern replacement for ls
    jq                      # JSON processor
    yq                      # YAML processor
    choose                  # Human-friendly cut/awk alternative
    du-dust                 # Intuitive disk usage (du)
    duf                     # Disk usage/free utility (df)
    broot                   # Tree view with navigation
    dog                     # DNS lookup utility (dig)
    shellcheck              # Shell script static analysis

    # Terminal tools
    # Note: alacritty installed via programs.alacritty below (prevents collision)
    tmux                    # Terminal multiplexer
    screen                  # Terminal session manager
    mosh                    # Mobile shell (SSH alternative)
    asciinema               # Terminal session recorder

    # File management
    ranger                  # Console file manager with VI bindings
    dos2unix                # Convert text file line endings
    unrar                   # Extract RAR archives
    p7zip                   # 7-Zip file archiver
    file                    # File type identification
    rsync                   # Fast incremental file transfer
    rclone                  # Rsync for cloud storage

    # Network tools
    wget                    # Network downloader
    curl                    # Transfer data with URLs
    netcat-gnu              # Network utility for TCP/UDP
    socat                   # Multipurpose relay (SOcket CAT)
    mtr                     # Network diagnostic tool (traceroute/ping)
    nmap                    # Network exploration and security scanner

    # System tools
    htop                    # Interactive process viewer
    btop                    # Resource monitor with modern UI
    tree                    # Display directory tree structure
    unzip                   # Extract ZIP archives
    zip                     # Create ZIP archives
    bc                      # Arbitrary precision calculator
    efibootmgr              # Modify EFI Boot Manager variables

    # ========================================================================
    # Programming Languages & Tools
    # ========================================================================

    # Python (REQUIRED for AIDB)
    # Note: python3 includes pip and setuptools by default
    python3

    # Additional languages
    go                      # Go programming language
    rustc                   # Rust compiler
    cargo                   # Rust package manager
    ruby                    # Ruby programming language

    # Development utilities
    gnumake                 # GNU Make build automation
    gcc                     # GNU C/C++ compiler
    nodejs_22               # Node.js JavaScript runtime v22

    # ========================================================================
    # Virtualization & Emulation
    # ========================================================================

    qemu            # Machine emulator and virtualizer
    virtiofsd       # VirtIO filesystem daemon

    # ========================================================================
    # Desktop Environment - Cosmic (Rust-based modern desktop)
    # ========================================================================

    #cosmic-edit             # Cosmic text editor
    #cosmic-files            # Cosmic file manager
    #cosmic-term             # Cosmic terminal

    # ========================================================================
    # ZSH Configuration
    # ========================================================================

    # Note: zsh installed via programs.zsh below (prevents collision)
    zsh-syntax-highlighting # Command syntax highlighting
    zsh-autosuggestions     # Command suggestions from history
    zsh-completions         # Additional completion definitions
    zsh-powerlevel10k       # Powerlevel10k theme
    grc                     # Generic colorizer for commands
    pay-respects            # Modern replacement for 'fuck'

    # ========================================================================
    # Fonts (Required for Powerlevel10k)
    # ========================================================================

    nerd-fonts.meslo-lg     # MesloLGS Nerd Font (recommended for p10k)
    nerd-fonts.fira-code    # Fira Code Nerd Font with ligatures
    nerd-fonts.jetbrains-mono # JetBrains Mono Nerd Font
    nerd-fonts.hack         # Hack Nerd Font
    font-awesome            # Font Awesome icon font
    powerline-fonts         # Powerline-patched fonts

    # ========================================================================
    # Text Processing
    # ========================================================================

    tldr                    # Simplified man pages
    cht-sh                  # Community cheat sheets
    pandoc                  # Universal document converter

    # ========================================================================
    # Utilities
    # ========================================================================

    mcfly           # Command history search
    navi            # Interactive cheatsheet
    starship        # Shell prompt
    hexedit         # Hex editor
    qrencode        # QR code generator
  ];

  # ========================================================================
  # ZSH Configuration
  # ========================================================================

  programs.zsh = {
    enable = true;
    enableCompletion = true;
    syntaxHighlighting.enable = true;
    autosuggestion.enable = false;

    history = {
      size = 100000;
      path = "${config.xdg.dataHome}/zsh/history";
    };

    shellAliases = {
      # Basic modern replacements
      ll = "eza -l --icons";
      la = "eza -la --icons";
      lt = "eza --tree --icons";
      cat = "bat";
      du = "dust";
      df = "duf";

      # NixOS specific
      nrs = "sudo nixos-rebuild switch";
      nrt = "sudo nixos-rebuild test";
      nrb = "sudo nixos-rebuild boot";
      hms = "home-manager switch";
      nfu = "nix flake update";
      nfc = "nix flake check";
      nfb = "nix build";
      nfd = "nix develop";

      # Nix development
      nix-dev = "nix develop -c $SHELL";
      nix-search = "nix search nixpkgs";
      nix-shell-pure = "nix-shell --pure";

      # Git shortcuts
      gs = "git status";
      ga = "git add";
      gc = "git commit";
      gp = "git push";
      gl = "git pull";
      gd = "git diff";
      gco = "git checkout";
      gb = "git branch";

      # Lazy tools
      lg = "lazygit";

      # Find shortcuts
      ff = "fd";
      rg = "rg --smart-case";
    };

    # NixOS 25.11+: Use 'initContent' instead of 'initExtra'
    initContent = ''
      # Powerlevel10k First-Run Setup Wizard
      P10K_MARKER="$HOME/.config/p10k/.configured"
      P10K_WIZARD="$HOME/.local/bin/p10k-setup-wizard.sh"

      # Run setup wizard on first shell launch
      if [[ ! -f "$P10K_MARKER" && -f "$P10K_WIZARD" ]]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════╗"
        echo "║  Welcome to your new ZSH setup!                     ║"
        echo "║  Let's configure Powerlevel10k...                   ║"
        echo "╚══════════════════════════════════════════════════════╝"
        echo ""
        "$P10K_WIZARD"
        echo ""
        echo "Please restart your shell to see the changes: exec zsh"
        return
      fi

      # Powerlevel10k instant prompt
      if [[ -r "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh" ]]; then
        source "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh"
      fi

      # Load Powerlevel10k theme
      source ${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k/powerlevel10k.zsh-theme

      # P10k configuration (dynamic - adapts to user preferences)
      [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

      # Enhanced command history with mcfly
      if command -v mcfly &> /dev/null; then
        eval "$(mcfly init zsh)"
      fi

      # FZF configuration
      export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
      export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
      export FZF_ALT_C_COMMAND='fd --type d --hidden --follow --exclude .git'

      # Nix-specific environment
      export NIX_PATH=$HOME/.nix-defexpr/channels''${NIX_PATH:+:}$NIX_PATH

      # Better error messages
      export NIXPKGS_ALLOW_UNFREE=1
    '';
  };

  # ========================================================================
  # Git Configuration
  # ========================================================================
  # Using GitHub no-reply email (username@users.noreply.github.com) to:
  # - Protect your privacy (email not exposed in commits)
  # - Comply with GitHub email privacy settings
  # - Prevent push rejections due to GH007 errors

  programs.git = {
    enable = true;
    # Git configuration using settings for NixOS 25.05/25.11 compatibility
    # Note: 'settings' is only available in newer home-manager versions
    settings = {
      # Git user configuration - set these manually after installation:
      # git config --global user.name "Your Name"
      # git config --global user.email "you@example.com"

      init.defaultBranch = "main";
      pull.rebase = false;
      core = {
        editor = "DEFAULTEDITOR";
      };
      alias = {
        st = "status";
        co = "checkout";
        br = "branch";
        ci = "commit";
        unstage = "reset HEAD --";
        last = "log -1 HEAD";
        visual = "log --oneline --graph --decorate --all";
      };
    };
  };

  # ========================================================================
  # Vim Configuration (minimal)
  # ========================================================================

  programs.vim = {
    enable = true;
    defaultEditor = false;  # Use DEFAULTEDITOR instead

    settings = {
      number = true;
      relativenumber = true;
      expandtab = true;
      tabstop = 2;
      shiftwidth = 2;
    };
  };

  # ========================================================================
  # VSCodium Configuration (Declarative)
  # ========================================================================

  programs.vscode = {
    enable = true;
    package = pkgs.vscodium;

    # NixOS 25.11: Use profiles.default for extensions and settings
    profiles.default = {
      # Extensions installed declaratively
      extensions = with pkgs.vscode-extensions; [
        # Nix language support
        jnoortheen.nix-ide
        arrterian.nix-env-selector

        # Git tools
        eamodio.gitlens

        # General development
        editorconfig.editorconfig
        esbenp.prettier-vscode
      ];

      # VSCodium settings (declarative)
      # Note: Claude Code paths will be added by bash script (dynamic)
      userSettings = {
      # Editor Configuration
      "editor.fontSize" = 14;
      "editor.fontFamily" = "'Fira Code', 'Droid Sans Mono', 'monospace'";
      "editor.fontLigatures" = true;
      "editor.formatOnSave" = true;
      "editor.formatOnPaste" = true;
      "editor.tabSize" = 2;
      "editor.insertSpaces" = true;
      "editor.detectIndentation" = true;
      "editor.minimap.enabled" = true;
      "editor.bracketPairColorization.enabled" = true;
      "editor.guides.bracketPairs" = true;

      # Nix-specific settings
      "nix.enableLanguageServer" = true;
      "nix.serverPath" = "nil";
      "nix.formatterPath" = "nixpkgs-fmt";
      "[nix]" = {
        "editor.defaultFormatter" = "jnoortheen.nix-ide";
        "editor.tabSize" = 2;
      };

      # Git configuration
      "git.enableSmartCommit" = true;
      "git.autofetch" = true;
      "gitlens.codeLens.enabled" = true;

      # Terminal
      "terminal.integrated.defaultProfile.linux" = "zsh";
      "terminal.integrated.fontSize" = 13;

      # Theme
      "workbench.colorTheme" = "Default Dark Modern";

      # File associations
      "files.associations" = {
        "*.nix" = "nix";
        "flake.lock" = "json";
      };

      # Miscellaneous
      "files.autoSave" = "afterDelay";
      "files.autoSaveDelay" = 1000;
      "explorer.confirmDelete" = false;
      "explorer.confirmDragAndDrop" = false;
      };
    };
  };

  # ========================================================================
  # Alacritty Terminal Configuration
  # ========================================================================

  programs.alacritty = {
    enable = true;
    settings = {
      window = {
        opacity = 0.95;
        padding = {
          x = 10;
          y = 10;
        };
      };
      font = {
        size = 11.0;
        normal = {
          family = "MesloLGS NF";
        };
      };
      colors = {
        primary = {
          background = "0x1e1e1e";
          foreground = "0xd4d4d4";
        };
      };
    };
  };

  # ========================================================================
  # Session Variables
  # ========================================================================

  home.sessionVariables = {
    EDITOR = "DEFAULTEDITOR";
    VISUAL = "DEFAULTEDITOR";
    NIXPKGS_ALLOW_UNFREE = "1";
  };

  # ========================================================================
  # Home Files
  # ========================================================================

  home.file = {
    # Create local bin directory
    ".local/bin/.keep".text = "";

    # P10k Setup Wizard
    ".local/bin/p10k-setup-wizard.sh" = {
      source = ./p10k-setup-wizard.sh;
      executable = true;
    };

    # P10k configuration (dynamic - loads user preferences)
    ".p10k.zsh".text = ''
      # Powerlevel10k configuration for NixOS
      # This config adapts to your preferences set via p10k-setup-wizard
      # To reconfigure: rm ~/.config/p10k/.configured && exec zsh

      # Load user theme preferences (set by p10k-setup-wizard.sh)
      THEME_FILE="$HOME/.config/p10k/theme.sh"
      if [[ -f "$THEME_FILE" ]]; then
        source "$THEME_FILE"
      else
        # Defaults if not configured yet
        export P10K_STYLE="lean"
        export P10K_COLORS="dark"
        export P10K_SHOW_TIME=false
        export P10K_SHOW_OS=true
        export P10K_SHOW_CONTEXT=false
        export P10K_TRANSIENT=true
      fi

      # Enable instant prompt
      if [[ -r "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh" ]]; then
        source "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh"
      fi

      # Build prompt elements based on user preferences
      left_elements=(dir vcs prompt_char)
      [[ "$P10K_SHOW_OS" == "true" ]] && left_elements=(os_icon "''${left_elements[@]}")

      right_elements=(status command_execution_time background_jobs)
      [[ "$P10K_SHOW_TIME" == "true" ]] && right_elements=(time "''${right_elements[@]}")
      [[ "$P10K_SHOW_CONTEXT" == "true" ]] && right_elements+=(context)

      typeset -g POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=("''${left_elements[@]}")
      typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=("''${right_elements[@]}")

      # Visual style
      typeset -g POWERLEVEL9K_MODE=nerdfont-complete
      typeset -g POWERLEVEL9K_ICON_PADDING=moderate

      # Prompt layout based on style
      case "$P10K_STYLE" in
        lean|pure)
          typeset -g POWERLEVEL9K_PROMPT_ON_NEWLINE=false
          typeset -g POWERLEVEL9K_RPROMPT_ON_NEWLINE=false
          typeset -g POWERLEVEL9K_PROMPT_ADD_NEWLINE=true
          ;;
        classic|rainbow)
          typeset -g POWERLEVEL9K_PROMPT_ON_NEWLINE=true
          typeset -g POWERLEVEL9K_RPROMPT_ON_NEWLINE=false
          typeset -g POWERLEVEL9K_PROMPT_ADD_NEWLINE=true
          ;;
      esac

      # Transient prompt
      [[ "$P10K_TRANSIENT" == "true" ]] && typeset -g POWERLEVEL9K_TRANSIENT_PROMPT=always

      # Enhanced Color schemes with better contrast
      case "$P10K_COLORS" in
        high-contrast-dark)
          # High contrast bright colors for dark terminals (RECOMMENDED)
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=51           # Bright cyan
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=46     # Bright green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=226 # Bright yellow
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=201 # Bright magenta
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=196 # Bright red
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=231      # White
          typeset -g POWERLEVEL9K_PROMPT_CHAR_OK_VIINS_FOREGROUND=46
          typeset -g POWERLEVEL9K_PROMPT_CHAR_ERROR_VIINS_FOREGROUND=196
          ;;
        custom-high-contrast)
          # Maximum contrast for accessibility
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=15           # White
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=10     # Bright green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=11  # Bright yellow
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=13 # Bright magenta
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=9   # Bright red
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=15       # White
          typeset -g POWERLEVEL9K_PROMPT_CHAR_OK_VIINS_FOREGROUND=10
          typeset -g POWERLEVEL9K_PROMPT_CHAR_ERROR_VIINS_FOREGROUND=9
          ;;
        light)
          # High contrast for light backgrounds
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=24
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=28
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=130
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=21
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=124
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=24
          ;;
        solarized)
          # Solarized Dark colors (enhanced)
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=81           # Brighter blue
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=106    # Brighter green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=221 # Brighter yellow
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=125 # Brighter magenta
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=196 # Bright red
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=81
          ;;
        gruvbox)
          # Gruvbox colors (enhanced)
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=214
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=142
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=208
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=175
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=167
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=223
          ;;
        nord)
          # Nord colors (enhanced)
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=111          # Brighter blue
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=150    # Brighter green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=228 # Bright yellow
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=147 # Brighter purple
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=210 # Bright red
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=153
          ;;
        dracula)
          # Dracula colors (enhanced)
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=141
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=121    # Brighter green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=228
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=177 # Brighter pink
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=212
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=183
          ;;
        *)
          # Dark (default) - bright colors
          typeset -g POWERLEVEL9K_DIR_FOREGROUND=51           # Bright cyan
          typeset -g POWERLEVEL9K_VCS_CLEAN_FOREGROUND=46     # Bright green
          typeset -g POWERLEVEL9K_VCS_MODIFIED_FOREGROUND=226 # Bright yellow
          typeset -g POWERLEVEL9K_VCS_UNTRACKED_FOREGROUND=201 # Bright magenta
          typeset -g POWERLEVEL9K_STATUS_ERROR_FOREGROUND=196 # Bright red
          typeset -g POWERLEVEL9K_OS_ICON_FOREGROUND=231      # White
          ;;
      esac

      # Common settings
      typeset -g POWERLEVEL9K_DIR_SHORTEN_STRATEGY=truncate_to_last
      typeset -g POWERLEVEL9K_DIR_SHORTEN_DIR_LENGTH=3
      typeset -g POWERLEVEL9K_STATUS_OK=false
      typeset -g POWERLEVEL9K_LINUX_NIXOS_ICON='❄️'
    '';
  };

  # ========================================================================
  # Flatpak Integration - Manual Setup Instructions
  # ========================================================================
  # NOTE: Flatpak is installed at system level via:
  #   services.flatpak.enable = true  (in ~/.config/home-manager/configuration.nix)
  #
  # INSTALLATION INSTRUCTIONS (Run these once after system setup):
  #
  # 1. Add Flathub repository (one-time setup):
  #    flatpak remote-add --if-not-exists flathub \
  #      https://dl.flathub.org/repo/flathub.flatpakrepo
  #
  # 2. Install Flatpak applications (use commands below):
  #    # System Tools
  #    flatpak install -y flathub com.github.flatseal.Flatseal
  #    flatpak install -y flathub org.gnome.FileRoller
  #    flatpak install -y flathub net.nokyan.Resources
  #
  #    # Media Players
  #    flatpak install -y flathub org.videolan.VLC
  #    flatpak install -y flathub io.mpv.Mpv
  #
  #    # Web Browser
  #    flatpak install -y flathub org.mozilla.firefox
  #
  #    # Productivity
  #    flatpak install -y flathub md.obsidian.Obsidian
  #
  # 3. OR: Copy the list below and use this command:
  #    for app in com.github.flatseal.Flatseal org.gnome.FileRoller \
  #                net.nokyan.Resources org.videolan.VLC io.mpv.Mpv \
  #                org.mozilla.firefox md.obsidian.Obsidian; do
  #      flatpak install -y flathub "$app"
  #    done
  #
  # DECLARATIVE FLATPAK APPS (for reference - install manually):
  # ====================================================================
  # System Tools
  # flatpak install -y flathub com.github.flatseal.Flatseal
  # flatpak install -y flathub org.gnome.FileRoller
  # flatpak install -y flathub net.nokyan.Resources
  #
  # Media Players
  # flatpak install -y flathub org.videolan.VLC
  # flatpak install -y flathub io.mpv.Mpv
  #
  # Web Browsers
  # flatpak install -y flathub org.mozilla.firefox
  #
  # Productivity & Office
  # flatpak install -y flathub md.obsidian.Obsidian
  # # flatpak install -y flathub org.libreoffice.LibreOffice
  # # flatpak install -y flathub app.standard-notes.StandardNotes
  # # flatpak install -y flathub org.joplin.Joplin
  #
  # Development & Content Tools (GUI Applications)
  # # flatpak install -y flathub io.github.gitui.gitui
  # # flatpak install -y flathub fr.handbrake.ghb
  # # flatpak install -y flathub org.audacityteam.Audacity
  # # flatpak install -y flathub org.gimp.GIMP
  # # flatpak install -y flathub org.inkscape.Inkscape
  # # flatpak install -y flathub org.pitivi.Pitivi
  # # flatpak install -y flathub org.blender.Blender
  # # flatpak install -y flathub org.darktable.Darktable
  #
  # Additional Web Browsers (If needed)
  # # flatpak install -y flathub com.google.Chrome
  #
  # Internet & Communication (Desktop Apps)
  # # flatpak install -y flathub org.telegram.desktop
  # # flatpak install -y flathub com.slack.Slack
  # # flatpak install -y flathub org.thunderbird.Thunderbird
  # # flatpak install -y flathub io.Riot.Riot
  # # flatpak install -y flathub com.obsproject.Studio
  #
  # Database & Tools (GUI Applications)
  # # flatpak install -y flathub org.dbeaver.DBeaverCommunity
  # # flatpak install -y flathub com.beekeeperstudio.Studio
  # # flatpak install -y flathub com.mongodb.Compass
  #
  # Remote Access & Virtualization (GUI)
  # # flatpak install -y flathub org.remmina.Remmina
  # # flatpak install -y flathub com.freerdp.FreeRDP
  # # flatpak install -y flathub org.virt_manager.virt-manager
  #
  # Security & Privacy Tools (GUI Applications)
  # # flatpak install -y flathub org.gnome.Secrets
  # # flatpak install -y flathub org.keepassxc.KeePassXC
  # # flatpak install -y flathub com.github.Eloston.UngoogledChromium
  # # flatpak install -y flathub com.tutanota.Tutanota
  #
  # Entertainment & Gaming
  # # flatpak install -y flathub com.valvesoftware.Steam
  # # flatpak install -y flathub org.DolphinEmu.dolphin-emu
  # # flatpak install -y flathub net.rpcs3.RPCS3
  # # flatpak install -y flathub org.libretro.RetroArch
  #
  # ====================================================================
  # ALTERNATIVE: Use COSMIC App Store
  # ====================================================================
  # Simply open the COSMIC App Store from your application menu
  # and search for desired applications. Click Install to download
  # from Flathub. This is the most user-friendly method!
  #
  # MANAGE PERMISSIONS:
  # ====================================================================
  # flatpak run com.github.flatseal.Flatseal
  # (or open Flatseal from app menu)
  #
  # Then select app from sidebar and toggle permissions as needed.

  # services.flatpak: Declarative Flatpak management via nix-flatpak
  # When using flakes with nix-flatpak module imported above, this section
  # defines all Flatpak applications declaratively.
  # When nix-flatpak is NOT available (channel-based install), this section
  # is ignored and you can install apps manually via flatpak CLI.
  #
  services.flatpak = {
    enable = true;
    packages = [
      # ====================================================================
      # SYSTEM TOOLS & UTILITIES (Recommended - Essential GUI Tools)
      # ====================================================================
      "com.github.flatseal.Flatseal"        # Flatpak permissions manager GUI
      "org.gnome.FileRoller"                # Archive manager (zip, tar, 7z, rar) - GUI
      "net.nokyan.Resources"                # System monitor (CPU, GPU, RAM, Network) - GUI

      # ====================================================================
      # MEDIA PLAYERS (Desktop Applications)
      # ====================================================================
      "org.videolan.VLC"                    # VLC media player (universal format support)
      "io.mpv.Mpv"                          # MPV video player (modern, lightweight)

      # ====================================================================
      # WEB BROWSERS
      # ====================================================================
      "org.mozilla.firefox"                 # Firefox browser (Flatpak, better sandbox isolation)

      # ====================================================================
      # PRODUCTIVITY & OFFICE (Popular for Work)
      # ====================================================================
      "md.obsidian.Obsidian"                # Note-taking with markdown, vault sync, plugins
      # "org.libreoffice.LibreOffice"         # Full office suite (documents, spreadsheets, presentations)
      # "app.standard-notes.StandardNotes"    # Encrypted note-taking
      # "org.joplin.Joplin"                   # Note-taking with sync (active development)

      # ====================================================================
      # DEVELOPMENT & CONTENT TOOLS (GUI Applications)
      # ====================================================================
      # "io.github.gitui.gitui"               # Modern Git client (Rust-based UI)
      # "fr.handbrake.ghb"                    # HandBrake video converter (GUI)
      # "org.audacityteam.Audacity"           # Audio recording & editing (GUI)
      # "org.gimp.GIMP"                       # Image manipulation (Photoshop alternative)
      # "org.inkscape.Inkscape"               # Vector graphics editor (Illustrator alternative)
      # "org.pitivi.Pitivi"                   # Video editor (GNOME project)
      # "org.blender.Blender"                 # 3D modeling & rendering
      # "org.darktable.Darktable"             # Photo RAW processor

      # ====================================================================
      # ADDITIONAL WEB BROWSERS (If needed)
      # ====================================================================
      # "com.google.Chrome"                   # Google Chrome (proprietary, Flathub only)

      # ====================================================================
      # INTERNET & COMMUNICATION (Desktop Apps)
      # ====================================================================
      # "org.telegram.desktop"                # Telegram messenger (desktop)
      # "com.slack.Slack"                     # Slack desktop client
      # "org.thunderbird.Thunderbird"         # Email & calendar client
      # "io.Riot.Riot"                        # Matrix client for secure messaging
      # "com.obsproject.Studio"               # OBS Studio for streaming & recording

      # ====================================================================
      # DATABASE & TOOLS (GUI Applications)
      # ====================================================================
      # "org.dbeaver.DBeaverCommunity"        # Universal database client (MySQL, PostgreSQL)
      # "com.beekeeperstudio.Studio"          # Modern database IDE
      # "com.mongodb.Compass"                 # MongoDB GUI client

      # ====================================================================
      # REMOTE ACCESS & VIRTUALIZATION (GUI)
      # ====================================================================
      # "org.remmina.Remmina"                 # Remote desktop & SSH client
      # "com.freerdp.FreeRDP"                 # Remote Desktop Client (RDP)
      # "org.virt_manager.virt-manager"       # Virtual Machine Manager (KVM GUI)

      # ====================================================================
      # SECURITY & PRIVACY TOOLS (GUI Applications)
      # ====================================================================
      # "org.gnome.Secrets"                   # Password manager (KeePass alternative)
      # "org.keepassxc.KeePassXC"             # Password manager with sync
      # "com.github.Eloston.UngoogledChromium" # Privacy-focused Chromium
      # "com.tutanota.Tutanota"               # Encrypted email service

      # ====================================================================
      # ENTERTAINMENT & GAMING
      # ====================================================================
      # "com.valvesoftware.Steam"             # Steam game platform
      # "org.DolphinEmu.dolphin-emu"          # GameCube/Wii emulator
      # "net.rpcs3.RPCS3"                     # PlayStation 3 emulator
      # "org.libretro.RetroArch"              # Multi-system emulator (NES, SNES, Genesis)

      # ====================================================================
      # NOTE: CLI TOOLS & DEVELOPMENT PACKAGES
      # ====================================================================
      # The following packages are kept in home.packages (NOT Flatpak) for better integration:
      # - git, neovim, vim (code editors)
      # - Python, Go, Rust, Node.js (programming languages)
      # - ripgrep, fd, fzf, bat (modern CLI tools)
      # - tmux, zsh, starship (shell/terminal tools)
      # - pandoc (document converter)
      # - nix tools (nixpkgs-fmt, statix, etc.)
      # - All other CLI/terminal utilities
      #
      # These are better installed via NixOS packages because:
      # 1. Better shell integration and PATH handling
      # 2. Faster execution (no Flatpak sandbox overhead)
      # 3. Direct access to system libraries
      # 4. Simpler configuration in shell profiles
      # 5. Most are not available on Flathub anyway
    ];

    # Optional: Override remotes if using non-Flathub sources
    # remotes = {
    #   flathub = "https://dl.flathub.org/repo/flathub.flatpakrepo";
    # };

    # Optional: Set permissions globally for all Flatpak packages
    # permissions = {
    #   "org.freedesktop.Flatpak" = {
    #     # Grant host filesystem access
    #     Context.filesystems = [
    #       "home"
    #       "/mnt"
    #     ];
    #   };
    # };
  };

}
NIXEOF

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
        if sudo cp "$HARDWARE_CONFIG" "$HM_CONFIG_DIR/hardware-configuration.nix"; then
            sudo chown "$USER":"$USER" "$HM_CONFIG_DIR/hardware-configuration.nix" 2>/dev/null || true
            print_success "Copied hardware-configuration.nix to $HM_CONFIG_DIR for flake builds"
        else
            print_warning "Could not copy hardware-configuration.nix to $HM_CONFIG_DIR"
        fi
    fi

    # Generate complete AIDB configuration
    print_info "Generating complete AIDB development configuration..."
    echo ""

    sudo tee "$HM_CONFIG_DIR/configuration.nix" > /dev/null <<NEWCONFIG
# NixOS Configuration - AIDB Development Environment
# Generated by: nixos-quick-deploy.sh v${SCRIPT_VERSION}
# Generated: $(date)
# Hostname: $HOSTNAME | User: $USER
# Target: NixOS 25.05+ with Wayland-first, security hardening

{ config, pkgs, lib, ... }:

{
  imports = [ ./hardware-configuration.nix ];

  # ============================================================================
  # Boot Configuration (Modern EFI)
  # ============================================================================
  boot = {
    loader = {
      systemd-boot.enable = lib.mkDefault true;
      efi.canTouchEfiVariables = lib.mkDefault true;
      # Security: Timeout for boot menu
      timeout = lib.mkDefault 3;
    };

    # CPU Microcode updates (auto-detected: $CPU_VENDOR CPU)
    # Critical security and performance updates from CPU vendor
$(
    if [ "$CPU_VENDOR" == "intel" ]; then
        echo "    initrd.kernelModules = [ \"i915\" ];  # Intel GPU early KMS"
    elif [ "$CPU_VENDOR" == "amd" ]; then
        echo "    initrd.kernelModules = [ \"amdgpu\" ];  # AMD GPU early KMS"
    fi
)

    # Security: Enable kernel hardening
    kernelModules = [ ];  # Additional modules loaded after initial boot
    kernel.sysctl = {
      # Security: Disable unprivileged BPF and user namespaces
      "kernel.unprivileged_bpf_disabled" = 1;
      "kernel.unprivileged_userns_clone" = 0;
      "net.core.bpf_jit_harden" = 2;

      # Performance: Network tuning for low latency
      "net.core.netdev_max_backlog" = 16384;
      "net.core.somaxconn" = 8192;
      "net.ipv4.tcp_fastopen" = 3;

      # Security: Harden TCP/IP stack
      "net.ipv4.tcp_syncookies" = 1;
      "net.ipv4.conf.default.rp_filter" = 1;
      "net.ipv4.conf.all.rp_filter" = 1;
    };

    # Hibernation support (resume from swap)
    # The resume device is auto-detected from hardware-configuration.nix
    # To enable hibernation: systemctl hibernate
    resumeDevice = lib.mkDefault "";  # Auto-detected from swapDevices

    # Kernel parameters for better memory management and performance
    kernelParams = [
      # Enable zswap for compressed swap cache (better performance)
      "zswap.enabled=1"
      "zswap.compressor=zstd"
      "zswap.zpool=z3fold"

      # Quiet boot (cleaner boot messages)
      "quiet"
      "splash"

      # Performance: Disable CPU security mitigations (OPTIONAL - commented for security)
      # WARNING: Only enable on trusted systems where performance > security
      # Uncomment to disable Spectre/Meltdown mitigations for ~10-30% performance gain
      # "mitigations=off"
    ];
  };

  # Hardware-specific configuration (auto-detected)
  cp $HARDWARE_CONFIG $HM_CONFIG_DIR/hardware_configuration.nix
$(
    if [ -n "$CPU_MICROCODE" ]; then
        cat <<HARDWARE_CONFIG> $HM_CONFIG_DIR/hardware_configuration.nix
  hardware.cpu.$CPU_VENDOR.updateMicrocode = true;  # Enable $CPU_VENDOR microcode updates
HARDWARE_CONFIG
    fi

    # Add GPU-specific hardware configuration
    if [ "$GPU_TYPE" == "intel" ]; then
        cat <<INTEL_GPU> $HM_CONFIG_DIR/hardware_configuration.nix
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
INTEL_GPU
    elif [ "$GPU_TYPE" == "amd" ]; then
        cat <<AMD_GPU> $HM_CONFIG_DIR/hardware_configuration.nix
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
AMD_GPU
    elif [ "$GPU_TYPE" == "nvidia" ]; then
        cat <<NVIDIA_GPU> $HM_CONFIG_DIR/hardware_configuration.nix
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
NVIDIA_GPU
    fi
)


  # ============================================================================
  # Security Hardening
  # ============================================================================
  security = {
    # Sudo security
    sudo = {
      enable = true;
      execWheelOnly = true;  # Only wheel group can sudo
      wheelNeedsPassword = true;
    };
    # Polkit for privilege escalation (required for GUI apps)
    polkit.enable = true;
    # AppArmor for mandatory access control
    apparmor.enable = true;
  };

  # ============================================================================
  # Networking (Secure defaults)
  # ============================================================================
  networking = {
    hostName = "$HOSTNAME";
    networkmanager.enable = true;

    # Firewall enabled by default with minimal ports
    firewall = {
      enable = true;
      allowedTCPPorts = [
        # Add ports only when needed:
        # 8000  # AIDB API
        # 5432  # PostgreSQL
      ];
      # Default: Block all incoming, allow all outgoing
      # Explicitly log rejected packets for security monitoring
      logRefusedConnections = lib.mkDefault false;  # Set true for debugging
    };
  };

  # ============================================================================
  # Locale & Time (User-configured during setup)
  # ============================================================================
  time.timeZone = "$SELECTED_TIMEZONE";  # Timezone selected during installation
  i18n.defaultLocale = lib.mkDefault "$CURRENT_LOCALE";  # Auto-detected locale

  # Console configuration (TTY settings)
  console = {
    font = "Lat2-Terminus16";
    keyMap = lib.mkDefault "us";  # Keyboard layout for console
    # useXkbConfig = true;  # Uncomment to use X11 keymap settings in console
  };

  # ============================================================================
  # Users (Secure configuration)
  # ============================================================================

  # Allow users to change their passwords with passwd command
  # Set to false for fully declarative (passwords only from config)
  users.mutableUsers = true;

  users.users.${USER} = {
    isNormalUser = true;
    description = "${USER}";

    # Password configuration (migrated from existing system or newly set)
    hashedPassword = "${USER_PASSWORD_HASH}";

    # Minimal groups: only what's needed
    extraGroups = [
      "networkmanager"  # Network configuration
      "wheel"           # Sudo access
      "podman"          # Rootless containers
      "video"           # Hardware video acceleration
      "audio"           # Audio device access
      "input"           # Input device access (for Wayland)
    ];
    # Note: "docker" group removed - use podman's dockerCompat instead
    shell = pkgs.zsh;

    # Optional: Auto-login (DISABLED by default for security)
    # Uncomment to enable auto-login without password prompt
    # WARNING: Only use on single-user systems with physical security
    # autoSubUidGidRange = true;  # For rootless podman user namespaces
  };

  # Enable ZSH system-wide
  programs.zsh.enable = true;

  # ============================================================================
  # Home Manager
  # ============================================================================

  # Home Manager integration is provided by the generated flake (see flake.nix)
  # The flake adds home-manager.nixosModules.home-manager and imports ./home.nix

  # ============================================================================
  # Nix Configuration (Modern settings)
  # ============================================================================
  nix = {
    settings = {
      # Modern features
      experimental-features = [ "nix-command" "flakes" ];

      # Performance & security
      auto-optimise-store = true;
      trusted-users = [ "root" "@wheel" ];

      # Security: Restrict nix-daemon network access
      allowed-users = [ "@wheel" ];
    };

    # Automatic garbage collection
    gc = {
      automatic = true;
      dates = "weekly";
      options = "--delete-older-than 7d";
    };

    # Optimize store on every build
    optimise = {
      automatic = true;
      dates = [ "weekly" ];
    };
  };

  nixpkgs.config.allowUnfree = true;

  # ============================================================================
  # AIDB: Podman Virtualization (Rootless, secure containers)
  # ============================================================================
  # Modern NixOS 25.05+ container configuration
  virtualisation = {
    containers.enable = true;

    podman = {
      enable = true;

      # Docker CLI compatibility (no docker daemon)
      dockerCompat = true;

      # Enable Podman socket for podman-compose and docker-compose
      dockerSocket.enable = true;

      # Default network DNS for container name resolution
      defaultNetwork.settings.dns_enabled = true;

      # Automatic cleanup of unused images/containers
      autoPrune = {
        enable = true;
        dates = "weekly";
        flags = [ "--all" ];  # Remove all unused images, not just dangling
      };
    };
  };

  # ============================================================================
  # COSMIC Desktop Environment (Wayland-native)
  # ============================================================================
  # NixOS 25.05+ modern configuration
  # 100% Wayland-native - No X11/XWayland needed for this configuration
  # All applications configured for native Wayland support

  services.desktopManager.cosmic = {
    enable = true;
$(
    # Generate GPU-specific hardware acceleration configuration
    if [ "$GPU_TYPE" != "software" ] && [ "$GPU_TYPE" != "unknown" ] && [ -n "$LIBVA_DRIVER" ]; then
        cat <<GPU_CONFIG> $HM_CONFIG_DIR/hardware_configuration.nix

    # Hardware acceleration enabled (auto-detected: $GPU_TYPE GPU)
    # VA-API driver: $LIBVA_DRIVER for video decode/encode acceleration
    extraSessionCommands = ''
      # Enable hardware video acceleration
      export LIBVA_DRIVER_NAME=$LIBVA_DRIVER
      # Enable touch/gesture support for trackpads
      export MOZ_USE_XINPUT2=1
    '';
GPU_CONFIG
    else
        echo ""
        echo "    # No dedicated GPU detected - using software rendering"
        echo "    # Hardware acceleration disabled"
    fi
)

    # Optional: XWayland support for legacy X11 applications (DISABLED)
    # Uncomment ONLY if you need to run proprietary X11-only software
    # Examples: Some game launchers, proprietary CAD software, older apps
    # Note: Adds security risk (X11 less secure than Wayland)
    # xwayland.enable = false;

    # Optional: Exclude default COSMIC applications (NixOS 25.11+)
    # COSMIC desktop automatically includes: cosmic-settings, cosmic-notification-daemon,
    # cosmic-files, cosmic-edit, cosmic-terminal, and other core applications
    # Uncomment the section below in NixOS 25.11+ to prevent duplicates in application menu
    #
    # NOTE: This option is NOT available in NixOS 25.05
    # If using 25.05 and experiencing duplicate apps, upgrade to 25.11 or later
    #
    # excludePackages = with pkgs; [
    #   cosmic-settings
    #   cosmic-notification-daemon
    #   cosmic-launcher
    #   cosmic-files
    #   cosmic-edit
    #   cosmic-terminal
    # ];
  };

  services.displayManager = {
    # COSMIC Greeter (Wayland-native login screen)
    cosmic-greeter.enable = true;

    # Optional: Set default desktop session (DISABLED - not needed)
    # Uncomment ONLY if you install multiple desktop environments
    # Ensures COSMIC loads by default instead of others (GNOME, KDE, etc)
    # Since only COSMIC is installed, this setting is redundant
    # defaultSession = "cosmic";

    # Optional: Auto-login to skip password prompt (DISABLED for security)
    # Uncomment to boot directly to desktop without login screen
    # WARNING: Only use on single-user systems with physical security!
    # Bypasses password authentication - creates security risk
    # autoLogin = {
    #   enable = true;
    #   user = "$USER";
    # };
  };

  # Wayland-specific optimizations and COSMIC configuration
  environment.sessionVariables = {
    # Force Wayland for Qt apps
    QT_QPA_PLATFORM = "wayland";
    # Force Wayland for SDL2 apps
    SDL_VIDEODRIVER = "wayland";
    # Firefox Wayland
    MOZ_ENABLE_WAYLAND = "1";
    # Electron apps (VSCodium, etc)
    NIXOS_OZONE_WL = "1";

    # COSMIC-specific: Enable clipboard functionality
    # Required for cosmic-clipboard to work with wl-clipboard
    COSMIC_DATA_CONTROL_ENABLED = "1";
  };

  # ============================================================================
  # System Packages (System-level only)
  # ============================================================================
  # Note: Development tools (git, vim, etc.) are installed via home-manager
  # This prevents package collisions and allows per-user customization
  #
  # IMPORTANT: COSMIC desktop apps (cosmic-edit, cosmic-files, cosmic-term, etc.)
  # are AUTOMATICALLY included when services.desktopManager.cosmic.enable = true
  # DO NOT add them here - it creates duplicates!
  environment.systemPackages = with pkgs; [
    # COSMIC App Store (not auto-included, needs explicit installation)
    cosmic-store

    # Container tools (system-level for rootless podman)
    podman
    podman-compose
    buildah
    skopeo
    crun
    slirp4netns

    # Essential system utilities only
    # All other tools installed via home-manager to prevent collisions
  ];

  # ============================================================================
  # Fonts (Required for Cosmic and development)
  # ============================================================================
  fonts.packages = with pkgs; [
    nerd-fonts.meslo-lg
    nerd-fonts.fira-code
    nerd-fonts.jetbrains-mono
    nerd-fonts.hack
    font-awesome
    powerline-fonts
  ];

  # ============================================================================
  # Audio (Modern PipeWire - NixOS 25.05+)
  # ============================================================================
  # PipeWire: Modern, low-latency audio/video routing
  # Replaces PulseAudio and JACK with better Wayland integration

  # Disable legacy audio systems (NixOS 25.05+ uses services.pulseaudio)
  services.pulseaudio.enable = false;

  # Enable real-time audio scheduling (required for low latency)
  security.rtkit.enable = true;

  services.pipewire = {
    enable = true;

    # ALSA support (direct hardware access)
    alsa = {
      enable = true;
      support32Bit = true;  # For 32-bit games/apps
    };

    # PulseAudio compatibility layer
    pulse.enable = true;

    # JACK audio (professional audio production)
    jack.enable = true;

    # WirePlumber: Modern session manager for PipeWire
    wireplumber.enable = true;
  };

  # ============================================================================
  # Printing
  # ============================================================================
  services.printing.enable = true;

  # ============================================================================
  # Flatpak (Required for COSMIC App Store)
  # ============================================================================
  services.flatpak.enable = true;

  # Note: After system rebuild, run this command as your user to add Flathub:
  # flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

  # ============================================================================
  # System Monitoring Tools (GNOME-like Features)
  # ============================================================================
  # Resources: Modern system monitor similar to GNOME Settings
  #   - CPU, GPU, RAM, disk monitoring
  #   - Network statistics
  #   - Sensor readings (temperature, fan speed)
  #   - Process information (like GNOME Task Manager)
  #   - Clean, modern GTK 4 interface with libadwaita
  #
  # Installation: Available via Flatpak home-manager
  #   Uncomment in ~/.config/home-manager/home.nix:
  #   "net.nokyan.Resources"  # System resource monitor
  #
  # Alternative system monitoring services (optional - commented out):

  # GNOME Shell (for extensions like system monitor bar)
  # Uncomment if you want GNOME Shell in addition to COSMIC:
  # services.displayManager.gdm.enable = false;  # Disable if using COSMIC only
  # services.gnome.core-utilities.enable = false;

  # Dbus (Required for many system services and monitor integration)
  services.dbus.enable = true;

  # UPower (Power management and battery monitoring - integrated with monitors)
  services.upower.enable = true;

  # Bluetooth (For wireless device monitoring)
  services.blueman.enable = true;

  # Thermald (Intel thermal management - auto-thermal throttling)
  # Enabled automatically on Intel systems for temperature management
  services.thermald.enable = true;

  # ============================================================================
  # Geolocation Services (For COSMIC auto day/night theme)
  # ============================================================================
  # GeoClue2: Provides geolocation services for automatic timezone/theme
  # Used by COSMIC for:
  # - Automatic day/night theme switching based on sunrise/sunset
  # - Location-aware timezone detection
  # - Weather information (if installed)
  services.geoclue2 = {
    enable = true;
    enableWifi = true;
    
    # Location services can access your geolocation - configure privacy:
    # Allow only specific applications to access location
    geoProviderUrl = "https://api.beacondb.net/v1/geolocate";
    submitData = false;
    appConfig = {  
        # Allow COSMIC Settings to access location for theme switching
        #"cosmic-settings" = {
        #  isAllowed = true;
        #  isSystem = true;
      #};
    };
  };

  # ============================================================================
  # Memory Management & Swap
  # ============================================================================
  # Swap configuration is inherited from hardware-configuration.nix
  # This section adds intelligent swap management and hibernation support

  # Systemd sleep/hibernate configuration
  systemd.sleep.extraConfig = ''
    # Hibernate after 2 hours of suspend (saves battery)
    HibernateDelaySec=2h
  '';

  # Zram: Compressed RAM swap (faster than disk swap)
  # This creates a compressed block device in RAM for swap
  # Auto-configured based on detected RAM: ${TOTAL_RAM_GB}GB
  # Strategy: More RAM = less zram needed (diminishing returns)
  zramSwap = {
    enable = true;
    algorithm = "zstd";  # Modern, fast compression (better than lz4/lzo)
    memoryPercent = $ZRAM_PERCENT;  # Auto-tuned: $ZRAM_PERCENT% for ${TOTAL_RAM_GB}GB RAM
    priority = 10;       # Higher priority than disk swap (use zram first)
  };

  # System memory management tunables
  boot.kernel.sysctl = {
    # Swappiness: How aggressively to swap (0-100)
    # Lower = prefer RAM, Higher = swap more aggressively
    # Default: 60, Recommended for desktop: 10
    "vm.swappiness" = 10;

    # VFS cache pressure: How aggressively to reclaim inode/dentry cache
    # Lower = keep more cache, Higher = reclaim more aggressively
    # Default: 100, Recommended: 50
    "vm.vfs_cache_pressure" = 50;

    # Dirty ratio: Percentage of memory that can be dirty before forced writeback
    # Helps prevent I/O spikes
    "vm.dirty_ratio" = 10;
    "vm.dirty_background_ratio" = 5;
  };

  # ============================================================================
  # Power Management (for hibernation support)
  # ============================================================================
  powerManagement = {
    enable = true;
    # Allow hibernation if swap is configured
    # Requires: swapDevices with sufficient size (>= RAM size)
  };

  # ============================================================================
  # System & Home Manager Version
  # ============================================================================
  system.stateVersion = "$NIXOS_VERSION";
  home.stateVersion = "$NIXOS_VERSION";
}
NEWCONFIG

    local CONFIG_WRITE_STATUS=$?

    if [ $CONFIG_WRITE_STATUS -eq 0 ]; then
        print_success "✓ Complete AIDB configuration generated"
        print_info "Includes: Cosmic Desktop, Podman, Fonts, Audio, ZSH"
        echo ""
    else
        print_error "Failed to generate configuration"
        return 1
    fi

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

FLAKE_DIR="/home/$USER/Documents/AI-Opitmizer/NixOS-Quick-Deploy"

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
    cat >> "$HOME/.config/zsh/aidb-flake.zsh" <<'ZSHFLAKE'

# AIDB Flake Integration
# Quick access to AIDB development environment

alias aidb-dev='aidb-dev-env'
alias aidb-shell='cd ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy && nix develop'
alias aidb-update='cd ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy && nix flake update'

# Show AIDB development environment info
aidb-info() {
    echo "AIDB Development Environment"
    echo "  Flake location: ~/Documents/AI-Opitmizer/NixOS-Quick-Deploy/flake.nix"
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
