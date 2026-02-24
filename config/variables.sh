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
# SCRIPT_DIR is defined by the bootstrap loader before sourcing configuration.
# Avoid re-declaring the readonly variable to prevent noisy "readonly variable"
# warnings when the configuration is loaded multiple times. Only define it when
# the main script has not set the variable yet (for example, when the file is
# sourced in isolation during tests).
if [[ -z "${SCRIPT_DIR:-}" ]]; then
    readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # Project root directory
fi
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
# - Container stack (K3s/containerd) + container images
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
# Path Configuration
# ============================================================================
# Use environment variables where available, with safe fallbacks
# This improves portability and allows for testing with different directories
# ============================================================================

# Temporary directory (respects TMPDIR environment variable)
readonly TMP_DIR="${TMPDIR:-/tmp}"

# User directories (respects HOME environment variable)
readonly USER_HOME="${HOME:-$(cd ~ && pwd)}"
readonly USER_LOCAL_BIN="${HOME}/.local/bin"
readonly USER_LOCAL_SHARE="${HOME}/.local/share"
readonly USER_NPM_GLOBAL="${HOME}/.npm-global"

# System directories (configurable for testing)
readonly VAR_LIB_DIR="${VAR_LIB_DIR:-/var/lib}"
readonly NIXOS_SECRETS_DIR="${VAR_LIB_DIR}/nixos-quick-deploy/secrets"

# ============================================================================
# User Resolution (handle sudo invocation)
# ============================================================================
# Problem: When script is run with sudo, USER=$SUDO_USER but HOME=/root
# This causes deployment to target root's home instead of the actual user's home.
#
# Solution: Detect sudo invocation and resolve to the invoking user before any
# per-user paths (state, preferences, backups) are derived.
#
# Why this matters:
# - NixOS/home-manager configs live in the invoking user's home
# - Flatpaks and Podman data belong under the invoking user's XDG dirs
# - Preference caches must remain consistent between helper scripts
# ============================================================================

# Initialize with current user/home (correct if not using sudo)
RESOLVED_USER="${USER:-}"
RESOLVED_HOME="$HOME"

# Check if running via sudo (SUDO_USER is set and we're root)
if [[ -n "${SUDO_USER:-}" && "$EUID" -eq 0 ]]; then
    RESOLVED_USER="$SUDO_USER"
    RESOLVED_HOME="$(getent passwd "$RESOLVED_USER" 2>/dev/null | cut -d: -f6)"

    if [[ -z "$RESOLVED_HOME" ]]; then
        # Fallback: construct home path from HOME_ROOT_DIR (no eval — SEC-03)
        home_root="/${HOME_ROOT_DIR:-home}"
        if [[ -d "${home_root}/${RESOLVED_USER}" ]]; then
            RESOLVED_HOME="${home_root}/${RESOLVED_USER}"
        fi
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

# After this block, HOME and USER always refer to the target user regardless of
# whether the script was invoked directly or through sudo.

# Warn if the home directory itself is a git repo; this breaks nix flake eval
# when dotfiles live under $HOME but are not tracked by that repo.
if [[ -n "${HOME:-}" && -d "${HOME}/.git" ]]; then
    echo "Warning: ${HOME} is a git repository. Untracked dotfiles under ${HOME} can break nix flake evaluation." >&2
    echo "Consider removing ${HOME}/.git or moving DOTFILES_ROOT outside the repo." >&2
fi

# Ensure HOME points to a real user directory even in Nix build/sandbox contexts.
# Some launchers can set HOME to /nix/store/*-source or other transient paths.
if [[ -n "${USER:-}" ]]; then
    _resolved_home="$(getent passwd "$USER" 2>/dev/null | cut -d: -f6)"
    if [[ -z "$_resolved_home" ]]; then
        home_root="/${HOME_ROOT_DIR:-home}"
        if [[ -d "${home_root}/${USER}" ]]; then
            _resolved_home="${home_root}/${USER}"
        fi
    fi
    if [[ -z "$_resolved_home" && "$USER" == "root" && -d "/root" ]]; then
        _resolved_home="/root"
    fi
    if [[ -n "$_resolved_home" && -d "$_resolved_home" ]]; then
        case "${HOME:-}" in
            ""|/nix/store/*|/build/*|/homeless-shelter)
                export HOME="$_resolved_home"
                ;;
            *)
                if [[ ! -d "$HOME" ]]; then
                    export HOME="$_resolved_home"
                fi
                ;;
        esac
    fi
    unset _resolved_home
fi

# ============================================================================
# State Management
# ============================================================================

readonly STATE_DIR="$HOME/.cache/nixos-quick-deploy"
readonly STATE_FILE="$STATE_DIR/state.json"
readonly ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"
readonly HM_BACKUP_DIR="$STATE_DIR/hm-backups"

# ============================================================================
# Backup Management
# ============================================================================

readonly BACKUP_ROOT="$STATE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_MANIFEST="$BACKUP_ROOT/manifest.txt"

# ============================================================================
# Preference Cache Paths
# ============================================================================

readonly DEPLOYMENT_PREFERENCES_DIR="$STATE_DIR/preferences"
readonly BINARY_CACHE_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/binary-cache-preference.env"
readonly HIBERNATION_SWAP_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/hibernation-swap-size.env"
readonly ZSWAP_OVERRIDE_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/zswap-override.env"
readonly REMOTE_BUILDERS_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/remote-builders.env"
readonly FLATPAK_PROFILE_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/flatpak-profile.env"
readonly FLATPAK_PROFILE_STATE_FILE="$DEPLOYMENT_PREFERENCES_DIR/flatpak-profile-state.env"
readonly GIT_IDENTITY_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/git-identity.env"
readonly MANGOHUD_PROFILE_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/mangohud-profile.env"
readonly USER_PROFILE_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/user-profile.env"
readonly HUGGINGFACE_TOKEN_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/huggingface-token.env"
readonly LOCAL_AI_STACK_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/local-ai-stack.env"
readonly LLM_BACKEND_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/llm-backend.env"
readonly LLM_MODELS_PREFERENCE_FILE="$DEPLOYMENT_PREFERENCES_DIR/llm-models.env"

# ============================================================================
# Mutable Flags
# ============================================================================

# NOTE: Use parameter expansion defaults so sourcing this file multiple times
# (e.g., helper scripts, CLI previews) never clobbers values set by flags.
: "${DRY_RUN:=false}"
: "${FORCE_UPDATE:=false}"
: "${SKIP_HEALTH_CHECK:=false}"
: "${SKIP_AI_MODEL:=false}"
: "${ENABLE_DEBUG:=false}"
: "${AUTO_ROLLBACK_ENABLED:=true}"
: "${AUTO_ROLLBACK_REQUESTED:=false}"
: "${ROLLBACK_IN_PROGRESS:=false}"
: "${RESUME_DEVICE_HINT:=}"
: "${RESUME_OFFSET_HINT:=}"

_use_binary_caches_default="true"
if [[ -n "${USE_BINARY_CACHES:-}" ]]; then
    _use_binary_caches_default="$USE_BINARY_CACHES"
fi

if [[ -z "${USE_BINARY_CACHES:-}" && -f "$BINARY_CACHE_PREFERENCE_FILE" ]]; then
    _persisted_preference=$(awk -F'=' '/^USE_BINARY_CACHES=/{print $2}' "$BINARY_CACHE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    case "$_persisted_preference" in
        true|false)
            USE_BINARY_CACHES="$_persisted_preference"
            ;;
    esac
fi

if [[ -z "${USE_BINARY_CACHES:-}" ]]; then
    USE_BINARY_CACHES="$_use_binary_caches_default"
fi

unset _use_binary_caches_default
unset _persisted_preference

ZSWAP_CONFIGURATION_OVERRIDE="${ZSWAP_CONFIGURATION_OVERRIDE:-}"
if [[ -z "$ZSWAP_CONFIGURATION_OVERRIDE" && -f "$ZSWAP_OVERRIDE_PREFERENCE_FILE" ]]; then
    _persisted_zswap_override=$(awk -F'=' '/^ZSWAP_CONFIGURATION_OVERRIDE=/{print $2}' "$ZSWAP_OVERRIDE_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    case "$_persisted_zswap_override" in
        enable|disable|auto)
            ZSWAP_CONFIGURATION_OVERRIDE="$_persisted_zswap_override"
            ;;
    esac
fi

if [[ -z "$ZSWAP_CONFIGURATION_OVERRIDE" ]]; then
    ZSWAP_CONFIGURATION_OVERRIDE="auto"
fi

export ZSWAP_CONFIGURATION_OVERRIDE
unset _persisted_zswap_override

# ============================================================================
# Channel Preferences
# ============================================================================

DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-stable}"
SYNCHRONIZED_NIXOS_CHANNEL=""
SYNCHRONIZED_HOME_MANAGER_CHANNEL=""
HOME_MANAGER_CHANNEL_REF=""
HOME_MANAGER_CHANNEL_URL=""

# ============================================================================
# Build Acceleration Preferences
# ============================================================================

declare -ag REMOTE_BUILDER_SPECS=()
REMOTE_BUILDERS_ENABLED=false
REMOTE_BUILDER_SSH_KEY=""
REMOTE_BUILDER_SSH_OPTIONS=""
REMOTE_BUILD_ACCELERATION_MODE=""

declare -ag ADDITIONAL_BINARY_CACHES=()
declare -ag ADDITIONAL_BINARY_CACHE_KEYS=()

declare -ag CACHIX_CACHE_NAMES=()
CACHIX_AUTH_ENABLED=false
CACHIX_AUTH_TOKEN=""

# ============================================================================
# Flatpak Configuration
# ============================================================================

FLATHUB_REMOTE_NAME="flathub"
FLATHUB_REMOTE_URL="https://dl.flathub.org/repo/flathub.flatpakrepo"
FLATHUB_REMOTE_FALLBACK_URL="https://flathub.org/repo/flathub.flatpakrepo"
FLATHUB_BETA_REMOTE_NAME="flathub-beta"
FLATHUB_BETA_REMOTE_URL="https://flathub.org/beta-repo/flathub-beta.flatpakrepo"
RESET_FLATPAK_STATE_BEFORE_SWITCH="${RESET_FLATPAK_STATE_BEFORE_SWITCH:-false}"

declare -ag FLATPAK_PROFILE_CORE_APPS=(
    # === System Utilities ===
    "com.github.tchx84.Flatseal"         # Flatpak permissions manager
    "org.gnome.FileRoller"               # Archive manager
    "net.nokyan.Resources"               # System monitor
    "com.bitwarden.desktop"              # Password manager
    
    # === Browsers ===
    "com.google.Chrome"
    "org.mozilla.firefox"
    
    # === Media ===
    "org.videolan.VLC"
    "io.mpv.Mpv"
    "com.obsproject.Studio"              # Screen recording/streaming
    
    # === Development Essentials ===
    "md.obsidian.Obsidian"               # Knowledge management
    # NOTE: sqlitebrowser depends on org.kde.Platform — no GNOME equivalent exists.
    "org.sqlitebrowser.sqlitebrowser"    # Database browser
    "com.jgraph.drawio.desktop"          # Diagrams and flowcharts
    
    # === 3D Printing ===
    "com.prusa3d.PrusaSlicer"            # 3D print slicer
    
    # === 3D Modeling/CAD ===
    "org.blender.Blender"                # 3D creation suite
    # NOTE: FreeCAD depends on org.kde.Platform — no GNOME equivalent exists.
    "org.freecad.FreeCAD"                # Parametric 3D CAD (also CNC/CAM)
    "org.openscad.OpenSCAD"              # Programmatic 3D modeling (freedesktop runtime)

    # === PCB/Electronics Design ===
    # NOTE: KiCad depends on org.kde.Platform — no GNOME equivalent exists.
    "org.kicad.KiCad"                    # PCB design and schematic capture

    # === VM Management ===
    "org.virt_manager.virt-manager"      # KVM/QEMU VM manager
    "org.gnome.Boxes"                    # Simple VM management

    # === Gaming (optional) ===
    # NOTE: PrismLauncher depends on org.kde.Platform — no GNOME equivalent exists.
    "org.prismlauncher.PrismLauncher"    # Minecraft launcher
)

declare -ag FLATPAK_PROFILE_AI_WORKSTATION_APPS=()
FLATPAK_PROFILE_AI_WORKSTATION_APPS+=("${FLATPAK_PROFILE_CORE_APPS[@]}")
FLATPAK_PROFILE_AI_WORKSTATION_APPS+=(
    # === AI/ML Development ===
    "org.jupyter.JupyterLab"             # Jupyter notebooks
    
    # === API Development & Testing ===
    "com.getpostman.Postman"             # API testing
    "rest.insomnia.Insomnia"             # API client (lighter alternative)
    
    # === Database Tools ===
    "io.dbeaver.DBeaverCommunity"        # Universal database client
    
    # === Version Control ===
    "io.github.shiftey.Desktop"          # GitHub Desktop
    
    # === Stock Trading/Finance ===
    "com.tradingview.tradingview"        # Charts and market analysis
    
    # === Additional 3D Printing ===
    "com.ultimaker.cura"                 # UltiMaker Cura slicer
)

# ============================================================================
# Gaming Profile - Full gaming experience with launchers, emulators, and dev
# ============================================================================
declare -ag FLATPAK_PROFILE_GAMING_APPS=()
FLATPAK_PROFILE_GAMING_APPS+=("${FLATPAK_PROFILE_CORE_APPS[@]}")
FLATPAK_PROFILE_GAMING_APPS+=(
    # === Game Launchers & Stores ===
    "com.valvesoftware.Steam"            # Steam client
    "net.lutris.Lutris"                  # Game manager (Wine, Proton, native)
    "com.heroicgameslauncher.hgl"        # Epic, GOG, Amazon Games launcher
    "com.usebottles.bottles"             # Run Windows software/games
    
    # === Console Emulators ===
    "org.libretro.RetroArch"             # Multi-system emulator frontend
    "net.pcsx2.PCSX2"                    # PlayStation 2 emulator
    "org.DolphinEmu.dolphin-emu"         # GameCube/Wii emulator
    "net.rpcs3.RPCS3"                    # PlayStation 3 emulator
    "io.github.ryubing.Ryujinx"          # Nintendo Switch emulator
    
    # === Communication ===
    "com.discordapp.Discord"             # Gaming chat & voice
    
    # === Game Utilities ===
    "page.kramo.Cartridges"              # Game library manager
    
    # === Development (VSCodium via Nix, not Flatpak) ===
    # Note: VSCodium is installed via home-manager with extensions
    # Adding here would conflict - use the Nix-managed version instead
    
    # === Streaming & Recording ===
    # OBS already included from core profile
)

declare -ag FLATPAK_PROFILE_MINIMAL_APPS=(
    "org.mozilla.firefox"
    "md.obsidian.Obsidian"
    "com.github.tchx84.Flatseal"
    "com.obsproject.Studio"
)

# Phase 26: Prefer declarative profile data when available.
# Falls back to inline arrays above when evaluation tools are unavailable.
if [[ -n "${SCRIPT_DIR:-}" ]]; then
    declarative_flatpak_profiles_file="${SCRIPT_DIR}/nix/data/flatpak-profiles.nix"
    if [[ -f "$declarative_flatpak_profiles_file" ]] && command -v nix-instantiate >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
        declare -a _flatpak_profile_keys=("core" "ai_workstation" "gaming" "minimal")
        declare -A _flatpak_profile_array_map=(
            [core]="FLATPAK_PROFILE_CORE_APPS"
            [ai_workstation]="FLATPAK_PROFILE_AI_WORKSTATION_APPS"
            [gaming]="FLATPAK_PROFILE_GAMING_APPS"
            [minimal]="FLATPAK_PROFILE_MINIMAL_APPS"
        )

        for _profile_key in "${_flatpak_profile_keys[@]}"; do
            _profile_json="$(
                DECLARATIVE_FLATPAK_FILE="$declarative_flatpak_profiles_file" \
                    DECLARATIVE_FLATPAK_KEY="$_profile_key" \
                    nix-instantiate --eval --strict --json --expr \
                    'let profiles = import (builtins.getEnv "DECLARATIVE_FLATPAK_FILE"); key = builtins.getEnv "DECLARATIVE_FLATPAK_KEY"; in profiles.${key}' \
                    2>/dev/null || true
            )"

            if [[ -z "$_profile_json" ]]; then
                continue
            fi

            mapfile -t _loaded_apps < <(printf '%s' "$_profile_json" | jq -r '.[]' 2>/dev/null || true)
            if (( ${#_loaded_apps[@]} == 0 )); then
                continue
            fi

            _array_name="${_flatpak_profile_array_map[$_profile_key]}"
            declare -n _array_ref="$_array_name"
            _array_ref=("${_loaded_apps[@]}")
        done
    fi
fi

declare -Ag FLATPAK_PROFILE_LABELS=(
    [core]="Core desktop (browser, media, 3D printing, CAD, PCB design, VMs)"
    [ai_workstation]="AI workstation (core + AI tools, trading, API dev, CNC/CAM)"
    [gaming]="Gaming (core + Steam, Lutris, emulators, Discord)"
    [minimal]="Minimal (lean stack for recovery and remote shells)"
)

declare -Ag FLATPAK_PROFILE_APPSETS=(
    [core]="FLATPAK_PROFILE_CORE_APPS"
    [ai_workstation]="FLATPAK_PROFILE_AI_WORKSTATION_APPS"
    [gaming]="FLATPAK_PROFILE_GAMING_APPS"
    [minimal]="FLATPAK_PROFILE_MINIMAL_APPS"
)

declare -ag FLATPAK_ARCH_PRUNED_APPS=()
FLATPAK_INSTALL_ARCH=""

declare -ag FLATPAK_VSCODIUM_CONFLICT_IDS=(
    "com.visualstudio.code"
    "com.visualstudio.code.insiders"
    "com.vscodium.codium"
    "com.vscodium.codium.insiders"
)

DEFAULT_FLATPAK_PROFILE="${DEFAULT_FLATPAK_PROFILE:-core}"
SELECTED_FLATPAK_PROFILE=""
DEFAULT_FLATPAK_APPS=("${FLATPAK_PROFILE_CORE_APPS[@]}")

LAST_FLATPAK_QUERY_MESSAGE=""

# ============================================================================
# Git Identity Preferences
# ============================================================================
GIT_USER_NAME=""
GIT_USER_EMAIL=""
GIT_IDENTITY_SKIP="false"
GIT_IDENTITY_PREFS_LOADED="false"

# Track whether user-facing prompts already ran this session
USER_SETTINGS_INITIALIZED="false"
USER_PROFILE_PREFS_LOADED="false"

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
# Node.js / NPM Paths
# ============================================================================

PRIMARY_NPM_PREFIX="$PRIMARY_HOME/.npm-global"
PRIMARY_NPM_BIN="$PRIMARY_NPM_PREFIX/bin"

if [[ -z "${NPM_CONFIG_PREFIX:-}" ]]; then
    NPM_CONFIG_PREFIX="$PRIMARY_NPM_PREFIX"
fi

export NPM_CONFIG_PREFIX

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
GITEA_ENABLE="false"

# Other Application Directories
HUGGINGFACE_CONFIG_DIR="$PRIMARY_HOME/.config/huggingface"
HUGGINGFACE_CACHE_DIR="$PRIMARY_HOME/.cache/huggingface"
OPEN_WEBUI_DATA_DIR="$PRIMARY_HOME/.local/share/open-webui"
AIDER_CONFIG_DIR="$PRIMARY_HOME/.config/aider"
TEA_CONFIG_DIR="$PRIMARY_HOME/.config/tea"

# Cached secrets and provisioning artifacts
USER_PASSWORD_BLOCK=""
USER_TEMP_PASSWORD=""
ROOT_PASSWORD_BLOCK=""  # Synced with USER_PASSWORD_BLOCK for emergency mode access

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

# Hugging Face token (optional; used for model downloads)
if [[ -z "${HUGGINGFACEHUB_API_TOKEN:-}" && -f "$HUGGINGFACE_TOKEN_PREFERENCE_FILE" ]]; then
    _hf_cached_token=$(awk -F'=' '/^HUGGINGFACEHUB_API_TOKEN=/{print $2}' "$HUGGINGFACE_TOKEN_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    if [[ -n "$_hf_cached_token" ]]; then
        HUGGINGFACEHUB_API_TOKEN="$_hf_cached_token"
        export HUGGINGFACEHUB_API_TOKEN
    fi
fi
unset _hf_cached_token

LOCAL_AI_STACK_ENABLED="${LOCAL_AI_STACK_ENABLED:-}"
if [[ -z "$LOCAL_AI_STACK_ENABLED" && -f "$LOCAL_AI_STACK_PREFERENCE_FILE" ]]; then
    _local_ai_cached=$(awk -F'=' '/^LOCAL_AI_STACK_ENABLED=/{print $2}' "$LOCAL_AI_STACK_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    case "$_local_ai_cached" in
        true|false)
            LOCAL_AI_STACK_ENABLED="$_local_ai_cached"
            ;;
    esac
fi
if [[ -z "$LOCAL_AI_STACK_ENABLED" ]]; then
    # Default to RUN_AI_MODEL (K3s is the supported runtime; prompt removed).
    if [[ "${RUN_AI_MODEL:-true}" == "true" ]]; then
        LOCAL_AI_STACK_ENABLED="true"
    else
        LOCAL_AI_STACK_ENABLED="false"
    fi
fi
export LOCAL_AI_STACK_ENABLED
unset _local_ai_cached

# LLM Backend: llama.cpp server (ghcr.io/ggml-org/llama.cpp:server)
# Serves GGUF models via OpenAI-compatible API on configured LLAMA_CPP_PORT
LLM_BACKEND="${LLM_BACKEND:-llama_cpp}"
readonly LLAMA_CPP_URL="${LLAMA_CPP_URL:-${LLAMA_URL:-http://${SERVICE_HOST:-localhost}:${LLAMA_CPP_PORT}}}"
readonly LLAMA_CPP_HEALTH_URL="${LLAMA_CPP_URL}/health"
export LLM_BACKEND LLAMA_CPP_URL

# LLM Models Configuration (comma-separated list)
# Updated December 2025 - Best coding models for mobile workstations
#
# RECOMMENDED MODELS FOR CODING (ranked by performance/efficiency):
# ─────────────────────────────────────────────────────────────────
# Tier 1 - Primary Coding Models (pick 1-2 based on VRAM):
#   qwen2.5-coder:14b    - Best overall coding model, 14B params, needs ~10GB VRAM
#   qwen2.5-coder:7b     - Fast, efficient, great for 8GB VRAM systems
#   deepseek-coder-v2    - Excellent for complex reasoning, debugging
#   codestral:22b        - Mistral's coding model, strong on completions
#
# Tier 2 - Specialized Models:
#   starcoder2:15b       - 80+ languages, trained on permissive code
#   llama3.2:8b          - General purpose, good instruction following
#   phi-4:14b            - Microsoft's efficient reasoning model
#
# Tier 3 - Lightweight (for limited hardware):
#   qwen2.5-coder:3b     - Minimal footprint, still good for autocomplete
#   deepseek-coder:6.7b  - Fast inference, decent quality
#
# MOBILE WORKSTATION RECOMMENDATIONS:
#   8GB VRAM:   qwen2.5-coder:7b,deepseek-coder:6.7b
#   16GB VRAM:  qwen2.5-coder:14b,deepseek-coder-v2,starcoder2:15b
#   32GB+ VRAM: qwen2.5-coder:32b,codestral:22b,llama3.2:70b
#
LLM_MODELS="${LLM_MODELS:-}"
if [[ -z "$LLM_MODELS" && -f "$LLM_MODELS_PREFERENCE_FILE" ]]; then
    _llm_models_cached=$(awk -F'=' '/^LLM_MODELS=/{print $2}' "$LLM_MODELS_PREFERENCE_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
    if [[ -n "$_llm_models_cached" ]]; then
        LLM_MODELS="$_llm_models_cached"
    fi
fi
if [[ -z "$LLM_MODELS" ]]; then
    # Default models for deployment (coder + embeddings)
    LLM_MODELS="qwen2.5-coder,nomic-embed-text"
fi
export LLM_MODELS
unset _llm_models_cached

# Primary model file for llama-cpp deployment
# This is what gets loaded by the llama-cpp pod on startup
readonly LLAMA_CPP_MODEL_FILE="${LLAMA_CPP_MODEL_FILE:-qwen2.5-coder-7b-instruct-q4_k_m.gguf}"
export LLAMA_CPP_MODEL_FILE

# Embedding model for RAG (OpenAI-compatible embeddings endpoint)
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"
export EMBEDDING_MODEL

# ============================================================================
# Remote LLM Configuration (for hybrid local/remote workflows)
# ============================================================================
# Configure remote LLM endpoints for when local resources are insufficient
# or for accessing larger models (Claude, GPT-4, Gemini)
#
# HYBRID WORKFLOW STRATEGY:
# ─────────────────────────────────────────────────────────────────────────
# Local LLM (fast, private):  Code completion, simple refactoring, docs
# Remote LLM (powerful):      Complex reasoning, architecture, debugging
#
# Supported Remote Providers:
#   - OpenAI:     GPT-4o, o3-mini (fast coding)
#   - Anthropic:  Claude 4.5 Sonnet (best for coding)
#   - Google:     Gemini 3 Flash (multimodal)
#   - OpenRouter: Access to all providers via single API
#   - Self-hosted: vLLM/TGI on remote server
#
# Environment Variables (set in your shell or .env):
#   OPENAI_API_KEY       - For GPT models
#   ANTHROPIC_API_KEY    - For Claude models
#   OPENROUTER_API_KEY   - For OpenRouter (recommended for flexibility)
#   REMOTE_LLM_BASE_URL  - Custom endpoint (e.g., self-hosted vLLM)
#
readonly REMOTE_LLM_PROVIDERS="openai,anthropic,openrouter,custom"
readonly REMOTE_LLM_DEFAULT_PROVIDER="openrouter"

# Remote model recommendations for coding (December 2025):
# Fast & Cheap:    openai/o3-mini, anthropic/claude-3.5-haiku
# Best Quality:    anthropic/claude-4.5-sonnet, google/gemini-3-flash
# Best Value:      openrouter/qwen/qwen3-coder-480b, deepseek/deepseek-r1
readonly REMOTE_LLM_MODELS_RECOMMENDED="anthropic/claude-4.5-sonnet,openai/o3-mini,google/gemini-3-flash"

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
ZSWAP_MAX_POOL_PERCENT="20"
ZSWAP_COMPRESSOR="zstd"
# Leave empty so select_zswap_memory_pool can probe supported zpools at runtime
ZSWAP_ZPOOL=""
HIBERNATION_SWAP_SIZE_GB=""
ENABLE_ZSWAP_CONFIGURATION="false"
HOST_SWAP_LIMIT_ENABLED="${HOST_SWAP_LIMIT_ENABLED:-false}"
HOST_SWAP_LIMIT_GB="${HOST_SWAP_LIMIT_GB:-}"
HOST_SWAP_LIMIT_VALUE="${HOST_SWAP_LIMIT_VALUE:-}"
CONTAINER_STORAGE_FS_TYPE="${CONTAINER_STORAGE_FS_TYPE:-unknown}"
CONTAINER_STORAGE_SOURCE="${CONTAINER_STORAGE_SOURCE:-}"

# Container storage (K3s uses containerd, these are kept for backward compat)
CONTAINER_STORAGE_DRIVER="${CONTAINER_STORAGE_DRIVER:-overlay}"

ENABLE_GAMING_STACK="${ENABLE_GAMING_STACK:-true}"
# Early KMS initrd preload policy (auto|off|force).
EARLY_KMS_POLICY="${EARLY_KMS_POLICY:-${DEFAULT_EARLY_KMS_POLICY:-off}}"
# ENABLE_LACT:
#   auto  -> enable when discrete GPU detected
#   true  -> always enable services.lact
#   false -> never enable
ENABLE_LACT="${ENABLE_LACT:-auto}"
AUTO_APPLY_SYSTEM_CONFIGURATION="${AUTO_APPLY_SYSTEM_CONFIGURATION:-true}"
AUTO_APPLY_HOME_CONFIGURATION="${AUTO_APPLY_HOME_CONFIGURATION:-true}"
AUTO_UPDATE_FLAKE_INPUTS="${AUTO_UPDATE_FLAKE_INPUTS:-false}"
FLAKE_ONLY_MODE="${FLAKE_ONLY_MODE:-false}"
AUTO_UPDATE_REMOTE_AGENTS="${AUTO_UPDATE_REMOTE_AGENTS:-true}"
AUTO_RESOLVE_SERVICE_CONFLICTS="${AUTO_RESOLVE_SERVICE_CONFLICTS:-true}"
RESTORE_KNOWN_GOOD_FLAKE_LOCK="${RESTORE_KNOWN_GOOD_FLAKE_LOCK:-false}"
PROMPT_BEFORE_SYSTEM_SWITCH="${PROMPT_BEFORE_SYSTEM_SWITCH:-false}"
PROMPT_BEFORE_HOME_SWITCH="${PROMPT_BEFORE_HOME_SWITCH:-false}"
SYSTEM_CONFIGURATION_APPLIED="false"
HOME_CONFIGURATION_APPLIED="false"
SYSTEM_SWITCH_SKIPPED_REASON=""
HOME_SWITCH_SKIPPED_REASON=""

# AI-Optimizer / AIDB integration defaults
AI_ENABLED="${AI_ENABLED:-auto}"                        # auto, true, false
AIDB_BASE_URL="${AIDB_BASE_URL:-${AIDB_URL:-http://${SERVICE_HOST:-localhost}:${AIDB_PORT}}}"
AIDB_PROJECT_NAME="${AIDB_PROJECT_NAME:-NixOS-Dev-Quick-Deploy}"

# High-level host role; used as a human- and agent-friendly
# identifier (for example personal laptop, lab machine, guest
# workstation, CI runner). It does not override more specific
# flags, but can be used by tools and agents to infer intent.
HOST_PROFILE="${HOST_PROFILE:-personal}"                # personal, lab, guest, ci

# Edge AI profile for local LLM behavior on this host.
# Currently informational; future phases may use it to
# select which models to download/configure from the
# edge model registry (see config/edge-model-registry.json).
AI_PROFILE="${AI_PROFILE:-cpu_full}"                    # cpu_slim, cpu_full, off

AI_STACK_PROFILE="${AI_STACK_PROFILE:-personal}"        # personal, guest, none

export AI_ENABLED
export AIDB_BASE_URL
export AIDB_PROJECT_NAME
export HOST_PROFILE
export AI_PROFILE
export AI_STACK_PROFILE

# ============================================================================
# AI Stack Service Configuration
# ============================================================================
# Service URLs for the K3s-based AI stack
# All services are deployed as Kubernetes pods in the ai-stack namespace

readonly QDRANT_URL="${QDRANT_URL:-http://${SERVICE_HOST:-localhost}:${QDRANT_PORT}}"
readonly QDRANT_GRPC_URL="${QDRANT_GRPC_URL:-http://${SERVICE_HOST:-localhost}:${QDRANT_GRPC_PORT}}"
readonly LLAMA_CPP_API_URL="${LLAMA_CPP_API_URL:-${LLAMA_URL:-http://${SERVICE_HOST:-localhost}:${LLAMA_CPP_PORT}}/v1}"
readonly OPEN_WEBUI_URL="${OPEN_WEBUI_URL:-http://${SERVICE_HOST:-localhost}:${OPEN_WEBUI_PORT}}"
# POSTGRES_URL: Constructed from separate credentials. Password should be set via
# POSTGRES_PASSWORD env var or SOPS secrets — never hardcode in config files.
readonly POSTGRES_USER="${POSTGRES_USER:-mcp}"
readonly POSTGRES_DB="${POSTGRES_DB:-mcp}"
if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    readonly POSTGRES_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST:-${SERVICE_HOST:-localhost}}:${POSTGRES_PORT}/${POSTGRES_DB}"
else
    # URL without password — scripts that need DB access should set POSTGRES_PASSWORD
    readonly POSTGRES_URL="postgresql://${POSTGRES_USER}@${POSTGRES_HOST:-${SERVICE_HOST:-localhost}}:${POSTGRES_PORT}/${POSTGRES_DB}"
fi
readonly REDIS_URL="${REDIS_URL:-redis://${REDIS_HOST:-${SERVICE_HOST:-localhost}}:${REDIS_PORT}}"
readonly HYBRID_COORDINATOR_URL="${HYBRID_COORDINATOR_URL:-${HYBRID_URL:-http://${SERVICE_HOST:-localhost}:${HYBRID_COORDINATOR_PORT}}}"
readonly MINDSDB_URL="${MINDSDB_URL:-http://${SERVICE_HOST:-localhost}:${MINDSDB_PORT}}"

# AI Stack data directory
readonly AI_STACK_DATA="${HOME}/.local/share/nixos-ai-stack"
readonly AI_STACK_K8S="${SCRIPT_DIR}/ai-stack/kubernetes"

export QDRANT_URL LLAMA_CPP_API_URL HYBRID_COORDINATOR_URL
export AI_STACK_DATA AI_STACK_K8S

# AI Stack config/env paths (allow overrides from config/settings.sh or env)
AI_STACK_CONFIG_DIR="${AI_STACK_CONFIG_DIR:-${PRIMARY_HOME:-$HOME}/.config/nixos-ai-stack}"
AI_STACK_ENV_FILE="${AI_STACK_ENV_FILE:-${AI_STACK_CONFIG_DIR}/.env}"
export AI_STACK_CONFIG_DIR AI_STACK_ENV_FILE

# User Information
SELECTED_TIMEZONE=""
SELECTED_USERS=""
SELECTED_SHELL=""
SELECTED_EDITOR=""
USER_DESCRIPTION=""
SELECTED_NIXOS_VERSION=""

# System Status
USER_SYSTEMD_CHANNEL_STATUS="unknown"
USER_SYSTEMD_CHANNEL_MESSAGE=""
LATEST_CONFIG_BACKUP_DIR=""

# Home Manager Configuration
DOTFILES_ROOT="${DOTFILES_ROOT_OVERRIDE:-$PRIMARY_HOME/.dotfiles}"
if [[ "$DOTFILES_ROOT" != /* ]]; then
    DOTFILES_ROOT="$PRIMARY_HOME/$DOTFILES_ROOT"
fi
DEV_HOME_ROOT="$DOTFILES_ROOT"
HM_CONFIG_DIR="$DOTFILES_ROOT/home-manager"
FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
HOME_MANAGER_FILE="$HM_CONFIG_DIR/home.nix"
SYSTEM_CONFIG_FILE="$HM_CONFIG_DIR/configuration.nix"
HARDWARE_CONFIG_FILE="$HM_CONFIG_DIR/hardware-configuration.nix"

# Python Runtime (initialized as array, populated during execution)
PYTHON_BIN=()
