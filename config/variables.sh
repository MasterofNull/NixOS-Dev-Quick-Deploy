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

readonly SCRIPT_VERSION="3.2.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SCRIPT_NAME="nixos-quick-deploy.sh"

# ============================================================================
# Exit Codes
# ============================================================================

readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
readonly EXIT_NOT_FOUND=2
readonly EXIT_UNSUPPORTED=3
readonly EXIT_TIMEOUT=124
readonly EXIT_PERMISSION_DENIED=126
readonly EXIT_COMMAND_NOT_FOUND=127

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

readonly LOG_DIR="$HOME/.cache/nixos-quick-deploy/logs"
readonly LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"
readonly LOG_LEVEL="${LOG_LEVEL:-INFO}"  # DEBUG, INFO, WARNING, ERROR

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

# Ensure we target the invoking user's home directory even when executed via sudo
RESOLVED_USER="${USER:-}"
RESOLVED_HOME="$HOME"

if [[ -n "${SUDO_USER:-}" && "$EUID" -eq 0 ]]; then
    RESOLVED_USER="$SUDO_USER"
    RESOLVED_HOME="$(getent passwd "$RESOLVED_USER" 2>/dev/null | cut -d: -f6)"

    if [[ -z "$RESOLVED_HOME" ]]; then
        RESOLVED_HOME="$(eval echo "~$RESOLVED_USER" 2>/dev/null || true)"
    fi

    if [[ -z "$RESOLVED_HOME" ]]; then
        echo "Error: unable to resolve home directory for invoking user '$RESOLVED_USER'." >&2
        exit 1
    fi

    export ORIGINAL_ROOT_HOME="$HOME"
    export ORIGINAL_ROOT_USER="${USER:-root}"
    export HOME="$RESOLVED_HOME"
    export USER="$RESOLVED_USER"
fi

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
HM_CONFIG_DIR=""
