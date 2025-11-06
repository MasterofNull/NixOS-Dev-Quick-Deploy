#!/usr/bin/env bash
#
# Configuration Variables
# Purpose: All script constants and configuration variables
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - None (must be loaded first)
#
# Exports:
#   - All script configuration variables and constants
#
# ============================================================================

# ============================================================================
# Script Metadata
# ============================================================================
# readonly: Makes variables immutable (cannot be changed after setting)
# This prevents accidental modification of critical configuration
#
# BASH_SOURCE[0]: Path to current script file (even when sourced)
# dirname: Extract directory part of path
# cd + pwd: Convert to absolute path (resolves symlinks and relative paths)
# ..: Go up one level from config/ to reach project root
#
# Why absolute paths?
# - Works regardless of where script is invoked from
# - Prevents issues with relative paths when changing directories
# - Makes debugging easier (clear where files are located)
#
# NOTE: SCRIPT_VERSION is now defined in main script (nixos-quick-deploy.sh)
# to ensure version consistency across the entire deployment system
# ============================================================================

# SCRIPT_VERSION now defined in main script - DO NOT redefine
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # Project root directory
readonly SCRIPT_NAME="nixos-quick-deploy.sh"  # Main script filename

# ============================================================================
# Exit Codes
# ============================================================================
# Standard Unix/Linux exit codes for proper error reporting
# Exit codes 0-255 are valid; codes >125 have special meanings
# Used by automation tools (CI/CD) to detect specific failure types
# ============================================================================

readonly EXIT_SUCCESS=0                  # Success (standard: 0 = success)
readonly EXIT_GENERAL_ERROR=1            # General/unspecified error
readonly EXIT_NOT_FOUND=2                # File or resource not found
readonly EXIT_UNSUPPORTED=3              # Unsupported operation/platform
readonly EXIT_TIMEOUT=124                # Command timed out (standard: timeout uses 124)
readonly EXIT_PERMISSION_DENIED=126      # Permission denied (standard: 126 = cannot execute)
readonly EXIT_COMMAND_NOT_FOUND=127      # Command not found (standard: 127 = command not in PATH)

# ============================================================================
# Timeouts and Retries
# ============================================================================

readonly DEFAULT_SERVICE_TIMEOUT=180
readonly RETRY_MAX_ATTEMPTS=4
readonly RETRY_BACKOFF_MULTIPLIER=2
readonly NETWORK_TIMEOUT=300

# ============================================================================
# Disk Space Requirements
# ============================================================================

# This deployment requires substantial disk space due to:
# - 100+ CLI tools and development utilities
# - Complete Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)
# - AI development tools (Ollama, GPT4All, llama.cpp models, Aider)
# - Container stack (Podman, Buildah, Skopeo) + container images
# - Desktop applications via Flatpak (Firefox, Obsidian, DBeaver, etc.)
# - System services (Gitea, Qdrant, Jupyter, Hugging Face TGI)
# Minimum: 50GB free space in /nix (recommended: 100GB+ for AI models)
readonly REQUIRED_DISK_SPACE_GB=50

# ============================================================================
# Logging Configuration
# ============================================================================
# NOTE: LOG_DIR, LOG_FILE, and LOG_LEVEL are now defined in main script
# (nixos-quick-deploy.sh) BEFORE any libraries are loaded. This ensures
# that logging.sh has access to these variables immediately when sourced.
#
# These variables were moved to prevent "unbound variable" errors that
# occurred when logging.sh tried to use them before they were defined.
# ============================================================================

# LOG_DIR, LOG_FILE, and LOG_LEVEL now defined in main script - DO NOT redefine

# ============================================================================
# State Management
# ============================================================================

readonly STATE_DIR="$HOME/.cache/nixos-quick-deploy"
readonly STATE_FILE="$STATE_DIR/state.json"
readonly ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"

# ============================================================================
# Backup Management
# ============================================================================

readonly BACKUP_ROOT="$STATE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_MANIFEST="$BACKUP_ROOT/manifest.txt"

# ============================================================================
# Mutable Flags
# ============================================================================

DRY_RUN=false
FORCE_UPDATE=false
SKIP_HEALTH_CHECK=false
ENABLE_DEBUG=false

# ============================================================================
# Channel Preferences
# ============================================================================

DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-unstable}"
SYNCHRONIZED_NIXOS_CHANNEL=""
SYNCHRONIZED_HOME_MANAGER_CHANNEL=""
HOME_MANAGER_CHANNEL_REF=""

# ============================================================================
# Flatpak Configuration
# ============================================================================

FLATHUB_REMOTE_NAME="flathub"
FLATHUB_REMOTE_URL="https://dl.flathub.org/repo/flathub.flatpakrepo"
FLATHUB_REMOTE_FALLBACK_URL="https://flathub.org/repo/flathub.flatpakrepo"
FLATHUB_BETA_REMOTE_NAME="flathub-beta"
FLATHUB_BETA_REMOTE_URL="https://flathub.org/beta-repo/flathub-beta.flatpakrepo"

DEFAULT_FLATPAK_APPS=(
    "com.github.tchx84.Flatseal"
    "org.gnome.FileRoller"
    "net.nokyan.Resources"
    "org.videolan.VLC"
    "io.mpv.Mpv"
    "org.mozilla.firefox"
    "md.obsidian.Obsidian"
    "io.podman_desktop.PodmanDesktop"
    "org.sqlitebrowser.sqlitebrowser"
)

LAST_FLATPAK_QUERY_MESSAGE=""

# ============================================================================
# User Resolution (handle sudo invocation)
# ============================================================================
# Problem: When script is run with sudo, USER=$SUDO_USER but HOME=/root
# This causes deployment to target root's home instead of actual user's home
#
# Solution: Detect sudo invocation and resolve to the invoking user
#
# How it works:
# 1. If run without sudo: USER and HOME are correct, use as-is
# 2. If run with sudo: SUDO_USER contains real user, resolve their HOME
# 3. Override USER and HOME to target the invoking user's environment
#
# Why this matters:
# - NixOS config goes in user's home (~/.config/nixos)
# - Home Manager config goes in user's home
# - User-level packages install to user's profile
# - Flatpak apps install to user's ~/.local/share/flatpak
#
# Without this resolution, everything would install to root's home!
# ============================================================================

# Initialize with current user/home (correct if not using sudo)
RESOLVED_USER="${USER:-}"  # Current username
RESOLVED_HOME="$HOME"      # Current home directory

# Check if running via sudo (SUDO_USER is set and we're root)
# EUID = Effective User ID (0 = root)
if [[ -n "${SUDO_USER:-}" && "$EUID" -eq 0 ]]; then
    # Script was invoked with sudo - resolve to original user
    RESOLVED_USER="$SUDO_USER"  # Get the real user who ran sudo

    # Get home directory from passwd database (most reliable method)
    # getent passwd: Query user database
    # cut -d: -f6: Extract field 6 (home directory) from colon-separated output
    RESOLVED_HOME="$(getent passwd "$RESOLVED_USER" 2>/dev/null | cut -d: -f6)"

    # Fallback 1: Try shell expansion if getent failed
    # eval echo ~username expands to user's home directory
    if [[ -z "$RESOLVED_HOME" ]]; then
        RESOLVED_HOME="$(eval echo "~$RESOLVED_USER" 2>/dev/null || true)"
    fi

    # Fallback 2: If both methods failed, error out
    # Cannot proceed without knowing where to install user files
    if [[ -z "$RESOLVED_HOME" ]]; then
        echo "Error: unable to resolve home directory for invoking user '$RESOLVED_USER'." >&2
        exit 1  # Fatal error - cannot continue
    fi

    # Preserve original root environment (might be needed for some operations)
    export ORIGINAL_ROOT_HOME="$HOME"          # Save /root
    export ORIGINAL_ROOT_USER="${USER:-root}"   # Save "root"

    # Override environment to target the real user
    # This makes the rest of the script work as if run by the real user
    export HOME="$RESOLVED_HOME"  # Change HOME to user's home
    export USER="$RESOLVED_USER"  # Change USER to real username
fi

# After this block, HOME and USER always refer to the target user
# regardless of whether script was run with or without sudo

# ============================================================================
# Primary User Configuration
# ============================================================================

PRIMARY_USER="$USER"
PRIMARY_HOME="$HOME"
PRIMARY_GROUP="$(id -gn "$PRIMARY_USER" 2>/dev/null || id -gn 2>/dev/null || echo "$PRIMARY_USER")"
PRIMARY_UID="$(id -u "$PRIMARY_USER" 2>/dev/null || echo "$EUID")"
PRIMARY_RUNTIME_DIR=""

if [[ -n "$PRIMARY_UID" && -d "/run/user/$PRIMARY_UID" ]]; then
    PRIMARY_RUNTIME_DIR="/run/user/$PRIMARY_UID"
fi

PRIMARY_PROFILE_BIN="$PRIMARY_HOME/.nix-profile/bin"
PRIMARY_ETC_PROFILE_BIN="/etc/profiles/per-user/$PRIMARY_USER/bin"
PRIMARY_LOCAL_BIN="$PRIMARY_HOME/.local/bin"
LOCAL_BIN_DIR="$PRIMARY_LOCAL_BIN"

# ============================================================================
# Application Directories
# ============================================================================

FLATPAK_DIAGNOSTIC_ROOT="$PRIMARY_HOME/.cache/nixos-quick-deploy/flatpak"

# Gitea Configuration
GITEA_FLATPAK_APP_ID="io.gitea.Gitea"
GITEA_FLATPAK_CONFIG_DIR="$PRIMARY_HOME/.var/app/$GITEA_FLATPAK_APP_ID/config/gitea"
GITEA_FLATPAK_DATA_DIR="$PRIMARY_HOME/.var/app/$GITEA_FLATPAK_APP_ID/data/gitea"
GITEA_NATIVE_CONFIG_DIR="$PRIMARY_HOME/.config/gitea"
GITEA_NATIVE_DATA_DIR="$PRIMARY_HOME/.local/share/gitea"

# Other Application Directories
HUGGINGFACE_CONFIG_DIR="$PRIMARY_HOME/.config/huggingface"
HUGGINGFACE_CACHE_DIR="$PRIMARY_HOME/.cache/huggingface"
OPEN_WEBUI_DATA_DIR="$PRIMARY_HOME/.local/share/open-webui"
AIDER_CONFIG_DIR="$PRIMARY_HOME/.config/aider"
TEA_CONFIG_DIR="$PRIMARY_HOME/.config/tea"

# ============================================================================
# Gitea Secrets (initialized empty, populated during runtime)
# ============================================================================

GITEA_SECRETS_CACHE_DIR="$PRIMARY_HOME/.config/nixos-quick-deploy"
GITEA_SECRETS_CACHE_FILE="$GITEA_SECRETS_CACHE_DIR/gitea-secrets.env"
GITEA_SECRET_KEY=""
GITEA_INTERNAL_TOKEN=""
GITEA_LFS_JWT_SECRET=""
GITEA_JWT_SECRET=""
GITEA_ADMIN_PASSWORD=""
GITEA_ADMIN_USER=""
GITEA_ADMIN_EMAIL=""
GITEA_BOOTSTRAP_ADMIN="false"
GITEA_ADMIN_PROMPTED="false"
GITEA_PROMPT_CHANGED="false"

# ============================================================================
# Phase-Produced Variables (populated during execution)
# ============================================================================

# Hardware Detection
GPU_TYPE=""
GPU_DRIVER=""
GPU_PACKAGES=""
LIBVA_DRIVER=""
CPU_VENDOR=""
CPU_MICROCODE=""
CPU_CORES=""
TOTAL_RAM_GB=""
ZRAM_PERCENT=""

# User Information
SELECTED_TIMEZONE=""
SELECTED_USERS=""

# System Status
USER_SYSTEMD_CHANNEL_STATUS="unknown"
USER_SYSTEMD_CHANNEL_MESSAGE=""
LATEST_CONFIG_BACKUP_DIR=""

# Home Manager Configuration
DOTFILES_ROOT="$PRIMARY_HOME/.dotfiles"
DEV_HOME_ROOT="$DOTFILES_ROOT"
HM_CONFIG_DIR="$DOTFILES_ROOT/home-manager"
FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
HOME_MANAGER_FILE="$HM_CONFIG_DIR/home.nix"
SYSTEM_CONFIG_FILE="$HM_CONFIG_DIR/configuration.nix"
HARDWARE_CONFIG_FILE="$HM_CONFIG_DIR/hardware-configuration.nix"

# Python Runtime (initialized as array, populated during execution)
PYTHON_BIN=()
