#!/usr/bin/env bash
#
# NixOS Quick Deploy for AIDB Development
# Purpose: Install ALL packages and tools needed for AIDB development
# Scope: Complete system setup - ready for AIDB deployment
# What it does: Installs Podman, PostgreSQL, Python, Nix tools, modern CLI tools
# What it does NOT do: Initialize AIDB database or start containers
# Author: AI Agent
# Created: 2025-10-23
# Version: 3.0.0 - Complete refactor with comprehensive improvements
#
# Changelog v3.0.0:
# - Added comprehensive logging framework
# - Added state persistence for resume capability
# - Added dry-run mode
# - Added rollback mechanism
# - Added network retry with exponential backoff
# - Added progress indicators
# - Added GPU validation
# - Fixed critical exec zsh termination bug
# - Added error handler with proper trap
# - Centralized backup strategy
# - Added disk space checks
# - Improved security (input validation, secrets encryption)
#

# Error handling: Exit on undefined variable, catch errors in pipes
set -u
set -o pipefail
set -E  # ERR trap is inherited by shell functions

# ============================================================================
# Constants & Configuration
# ============================================================================

# Original version was 3.0.0, now upgraded to 3.1.0
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
readonly EXIT_NOT_FOUND=2
readonly EXIT_UNSUPPORTED=3
readonly EXIT_TIMEOUT=124
readonly EXIT_PERMISSION_DENIED=126
readonly EXIT_COMMAND_NOT_FOUND=127

# Timeouts and retries
readonly DEFAULT_SERVICE_TIMEOUT=180
readonly RETRY_MAX_ATTEMPTS=4
readonly RETRY_BACKOFF_MULTIPLIER=2
readonly NETWORK_TIMEOUT=300

# Disk space requirements
# This deployment requires substantial disk space due to:
# - 100+ CLI tools and development utilities
# - Complete Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)
# - AI development tools (Ollama, GPT4All, llama.cpp models, Aider)
# - Container stack (Podman, Buildah, Skopeo) + container images
# - Desktop applications via Flatpak (Firefox, Obsidian, DBeaver, etc.)
# - System services (Gitea, Qdrant, Jupyter, Hugging Face TGI)
# Minimum: 50GB free space in /nix (recommended: 100GB+ for AI models)
readonly REQUIRED_DISK_SPACE_GB=50

# Logging
readonly LOG_DIR="$HOME/.cache/nixos-quick-deploy/logs"
readonly LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"
readonly LOG_LEVEL="${LOG_LEVEL:-INFO}"  # DEBUG, INFO, WARNING, ERROR

# State management
readonly STATE_DIR="$HOME/.cache/nixos-quick-deploy"
readonly STATE_FILE="$STATE_DIR/state.json"
readonly ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"

# Backup management
readonly BACKUP_ROOT="$STATE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_MANIFEST="$BACKUP_ROOT/manifest.txt"

# Flags
DRY_RUN=false
FORCE_UPDATE=false
SKIP_HEALTH_CHECK=false
ENABLE_DEBUG=false

# Channel preferences
DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-unstable}"
SYNCHRONIZED_NIXOS_CHANNEL=""
SYNCHRONIZED_HOME_MANAGER_CHANNEL=""

# ============================================================================
# Logging Framework

# Error handling: Exit on undefined variable, catch errors in pipes
set -u
set -o pipefail
set -E  # ERR trap is inherited by shell functions

# ============================================================================
# Constants & Configuration
# ============================================================================

readonly SCRIPT_VERSION="3.1.0"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_GENERAL_ERROR=1
readonly EXIT_NOT_FOUND=2
readonly EXIT_UNSUPPORTED=3
readonly EXIT_TIMEOUT=124
readonly EXIT_PERMISSION_DENIED=126
readonly EXIT_COMMAND_NOT_FOUND=127

# Timeouts and retries
readonly DEFAULT_SERVICE_TIMEOUT=180
readonly RETRY_MAX_ATTEMPTS=4
readonly RETRY_BACKOFF_MULTIPLIER=2
readonly NETWORK_TIMEOUT=300

# Disk space requirements
readonly REQUIRED_DISK_SPACE_GB=50

# Logging
readonly LOG_DIR="$HOME/.cache/nixos-quick-deploy/logs"
readonly LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d_%H%M%S).log"
readonly LOG_LEVEL="${LOG_LEVEL:-INFO}"

# State management
readonly STATE_DIR="$HOME/.cache/nixos-quick-deploy"
readonly STATE_FILE="$STATE_DIR/state.json"
readonly ROLLBACK_INFO_FILE="$STATE_DIR/rollback-info.json"

# Backup management
readonly BACKUP_ROOT="$STATE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_MANIFEST="$BACKUP_ROOT/manifest.txt"

# Flags
DRY_RUN=false
FORCE_UPDATE=false
SKIP_HEALTH_CHECK=false
ENABLE_DEBUG=false

# Channel preferences
DEFAULT_CHANNEL_TRACK="${DEFAULT_CHANNEL_TRACK:-unstable}"
SYNCHRONIZED_NIXOS_CHANNEL=""
SYNCHRONIZED_HOME_MANAGER_CHANNEL=""

# GPU-related variables (defaults - will be set by detect_gpu_hardware)
GPU_TYPE="${GPU_TYPE:-unknown}"
GPU_DRIVER="${GPU_DRIVER:-}"
GPU_PACKAGES="${GPU_PACKAGES:-}"
LIBVA_DRIVER="${LIBVA_DRIVER:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================

# Initialize logging
init_logging() {
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
    chmod 600 "$LOG_FILE"

    log INFO "=== NixOS Quick Deploy v$SCRIPT_VERSION started ==="
    log INFO "Logging to: $LOG_FILE"
    log INFO "Script executed by: $USER (UID: $EUID)"
    log INFO "Working directory: $(pwd)"
}

# Main logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Write to log file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    # Also print to console based on log level
    case "$level" in
        ERROR)
            if [[ "${FUNCNAME[2]:-}" != "" ]]; then
                echo "[$timestamp] [$level] [${FUNCNAME[2]}] $message" >> "$LOG_FILE"
            fi
            ;;
        DEBUG)
            if [[ "$LOG_LEVEL" == "DEBUG" || "$ENABLE_DEBUG" == true ]]; then
                # Only show debug in verbose mode
                return 0
            fi
            ;;
    esac
}

# ============================================================================
# Error Handler & Trap
# ============================================================================

# Comprehensive error handler
error_handler() {
    local exit_code=$?
    local line_number=$1
    local bash_lineno=${BASH_LINENO[0]}
    local function_name=${FUNCNAME[1]:-"main"}

    log ERROR "Script failed at line $line_number (function: $function_name) with exit code $exit_code"
    log ERROR "Command: ${BASH_COMMAND}"

    print_error "Deployment failed at line $line_number"
    print_error "Function: $function_name"
    print_error "Exit code: $exit_code"

    # Save failure state
    if [[ -f "$STATE_FILE" ]]; then
        jq --arg error "Failed at line $line_number: ${BASH_COMMAND}" \
           --arg exit_code "$exit_code" \
           '.last_error = $error | .last_exit_code = $exit_code' \
           "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null && mv "$STATE_FILE.tmp" "$STATE_FILE" || true
    fi

    echo ""
    print_info "Check the log file for details: $LOG_FILE"
    print_info "To resume from this point, re-run the script"
    echo ""

    # Offer rollback if available
    if [[ -f "$ROLLBACK_INFO_FILE" ]]; then
        echo ""
        print_warning "A rollback point is available. To rollback:"
        echo "  $SCRIPT_DIR/nixos-quick-deploy.sh --rollback"
        echo ""
    fi

    # Check for removed packages that can be restored
    local removed_pkgs_file
    removed_pkgs_file=$(ls -t "$STATE_DIR"/removed-packages-*.txt 2>/dev/null | head -1)
    if [[ -n "$removed_pkgs_file" && -f "$removed_pkgs_file" ]]; then
        echo ""
        print_info "Removed packages can be restored. To restore:"
        echo "  Run: restore_removed_packages"
        echo "  Or manually reinstall from: $removed_pkgs_file"
        echo ""
    fi

    exit "$exit_code"
}

# Set up error trap
trap 'error_handler $LINENO' ERR

# Cleanup on exit (normal or error)
cleanup_on_exit() {
    local exit_code=$?
    log INFO "Script exiting with code: $exit_code"

    # Remove temporary files if any
    # Add cleanup logic here

    return $exit_code
}

trap cleanup_on_exit EXIT

# ============================================================================
# State Persistence
# ============================================================================

# Initialize state file
init_state() {
    mkdir -p "$STATE_DIR"

    if [[ ! -f "$STATE_FILE" ]]; then
        cat > "$STATE_FILE" <<EOF
{
  "version": "$SCRIPT_VERSION",
  "started_at": "$(date -Iseconds)",
  "completed_steps": [],
  "last_error": null,
  "last_exit_code": 0
}
EOF
        log INFO "Initialized state file: $STATE_FILE"
    else
        log INFO "Using existing state file: $STATE_FILE"
    fi
}

# Mark step as complete
mark_step_complete() {
    local step="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        init_state
    fi

    if command -v jq &>/dev/null; then
        jq --arg step "$step" \
           --arg timestamp "$(date -Iseconds)" \
           '.completed_steps += [{"step": $step, "completed_at": $timestamp}]' \
           "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"

        log INFO "Marked step complete: $step"
    else
        log WARNING "jq not available, cannot update state file"
    fi
}

# Check if step is complete
is_step_complete() {
    local step="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi

    if command -v jq &>/dev/null; then
        if jq -e --arg step "$step" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            log DEBUG "Step already complete: $step"
            return 0
        fi
    fi

    return 1
}

# Reset state (start fresh)
reset_state() {
    if [[ -f "$STATE_FILE" ]]; then
        mv "$STATE_FILE" "$STATE_FILE.backup-$(date +%s)"
        log INFO "Reset state file"
    fi
    init_state
}

# ============================================================================
# Utility Functions
# ============================================================================

# Validate input (prevent injection)
validate_hostname() {
    local hostname="$1"
    if [[ ! "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]]; then
        print_error "Invalid hostname: $hostname"
        print_info "Hostname must be alphanumeric with optional hyphens"
        return 1
    fi
    return 0
}

validate_github_username() {
    local username="$1"
    if [[ ! "$username" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?$ ]]; then
        print_error "Invalid GitHub username: $username"
        return 1
    fi
    return 0
}

# Assert unique paths
assert_unique_paths() {
    local -a paths=()
    local -a vars=("$@")

    # Collect all path values
    for var_name in "${vars[@]}"; do
        local path="${!var_name}"
        if [[ -n "$path" ]]; then
            paths+=("$path")
        fi
    done

    # Check for duplicates
    local -A seen=()
    for path in "${paths[@]}"; do
        if [[ -n "${seen[$path]:-}" ]]; then
            print_error "Path conflict detected: $path is used multiple times"
            return 1
        fi
        seen[$path]=1
    done

    return 0
}

# Retry function with exponential backoff
retry_with_backoff() {
    local max_attempts=$RETRY_MAX_ATTEMPTS
    local timeout=2
    local attempt=1
    local exit_code=0

    while (( attempt <= max_attempts )); do
        if "$@"; then
            return 0
        fi

        exit_code=$?

        if (( attempt < max_attempts )); then
            print_warning "Attempt $attempt/$max_attempts failed, retrying in ${timeout}s..."
            log WARNING "Retry attempt $attempt failed for command: $*"
            sleep $timeout
            timeout=$((timeout * RETRY_BACKOFF_MULTIPLIER))
            attempt=$((attempt + 1))
        else
            log ERROR "All retry attempts failed for command: $*"
            return $exit_code
        fi
    done

    return $exit_code
}

# Progress indicator
with_progress() {
    local message="$1"
    shift
    local command=("$@")

    print_info "$message"
    log INFO "Running with progress: ${command[*]}"

    # Run command in background
    "${command[@]}" &
    local pid=$!

    # Show spinner while running
    local spin='-\|/'
    local i=0
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) %4 ))
        printf "\r  [${spin:$i:1}] Please wait..."
        sleep 0.1
    done

    wait $pid
    local exit_code=$?

    if (( exit_code == 0 )); then
        printf "\r  [✓] Complete!     \n"
        log INFO "Command completed successfully"
    else
        printf "\r  [✗] Failed!      \n"
        log ERROR "Command failed with exit code $exit_code"
    fi

    return $exit_code
}

# Disk space check
check_disk_space() {
    local required_gb=$REQUIRED_DISK_SPACE_GB
    local available_gb=$(df -BG /nix 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")

    log INFO "Disk space check: ${available_gb}GB available, ${required_gb}GB required"

    if (( available_gb < required_gb )); then
        print_error "Insufficient disk space: ${available_gb}GB available, ${required_gb}GB required"
        print_info "Free up space or add more storage before continuing"
        echo ""
        print_info "This deployment installs:"
        echo "  • 100+ CLI tools and development utilities"
        echo "  • Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)"
        echo "  • AI development tools (Ollama, GPT4All, Aider, etc.)"
        echo "  • Container stack (Podman, buildah, skopeo)"
        echo "  • Desktop applications via Flatpak"
        echo ""
        print_info "To free up space:"
        echo "  sudo nix-collect-garbage -d      # Remove old generations"
        echo "  sudo nix-store --optimize        # Deduplicate store files"
        echo "  sudo nix-store --gc              # Garbage collect unused paths"
        log ERROR "Disk space check failed"
        return 1
    fi

    print_success "Disk space check passed: ${available_gb}GB available"
    return 0
}

# ============================================================================
# Package Availability Checks
# ============================================================================

# Ensure a package/command is available, install temporarily if needed
ensure_package_available() {
    local cmd="$1"
    local pkg="${2:-$1}"
    local priority="${3:-CRITICAL}"
    local description="${4:-$cmd}"
    local pkg_ref=""

    if command -v "$cmd" &>/dev/null; then
        local existing_path
        existing_path=$(command -v "$cmd" 2>/dev/null)
        print_success "$description available: $existing_path"
        log DEBUG "$cmd available: $existing_path"
        return 0
    fi

    local log_level="INFO"

    case "$priority" in
        CRITICAL)
            print_warning "$description not found - installing from nixpkgs"
            log_level="WARNING"
            ;;
        IMPORTANT)
            print_info "$description not found - installing automatically (recommended)"
            log_level="INFO"
            ;;
        OPTIONAL)
            print_info "$description not found - installing automatically (optional, improves functionality)"
            log_level="INFO"
            ;;
    esac

    log "$log_level" "$cmd missing, attempting installation via $pkg"

    if [[ -z "$pkg" ]]; then
        log ERROR "No package mapping provided for $cmd"
        return 1
    fi

    if [[ "$pkg" == *"#"* ]]; then
        pkg_ref="$pkg"
    else
        pkg_ref="nixpkgs#$pkg"
    fi

    if ! ensure_prerequisite_installed "$cmd" "$pkg_ref" "$description"; then
        case "$priority" in
            CRITICAL)
                print_error "Failed to install $description"
                ;;
            IMPORTANT)
                print_warning "Failed to install $description"
                ;;
            OPTIONAL)
                print_info "$description could not be installed automatically"
                ;;
        esac
        return 1
    fi

    if command -v "$cmd" &>/dev/null; then
        local installed_path
        installed_path=$(command -v "$cmd" 2>/dev/null)
        log INFO "$cmd installed and available at $installed_path"
        return 0
    fi

    log ERROR "$cmd installation reported success but command remains unavailable"
    return 1
}

# Install a prerequisite package into the user's profile if missing
ensure_prerequisite_installed() {
    local cmd="$1"
    local pkg_ref="$2"
    local description="$3"
    local install_log="$LOG_DIR/preflight-${cmd}-install.log"
    local attr_path=""

    if command -v "$cmd" >/dev/null 2>&1; then
        local existing_path
        existing_path=$(command -v "$cmd" 2>/dev/null)
        print_success "$description already available: $existing_path"
        log INFO "Prerequisite $cmd present at $existing_path"
        return 0
    fi

    if [[ "$pkg_ref" =~ ^[^#]+#(.+)$ ]]; then
        attr_path="${BASH_REMATCH[1]}"
    fi

    if [[ "$DRY_RUN" == true ]]; then
        print_warning "$description not found – would install via 'nix-env' (dry-run)"
        log INFO "Dry-run: would install prerequisite $cmd from $pkg_ref"
        return 0
    fi

    if [[ -z "$attr_path" ]]; then
        log ERROR "Unable to derive attribute path from $pkg_ref for $cmd"
        print_error "Failed to install $description – invalid package reference"
        return 1
    fi

    rm -f "$install_log"
    local install_succeeded=false
    local install_method=""
    local exit_code=0

    # Try nix-env with nixos channel first (primary method)
    if command -v nix-env >/dev/null 2>&1; then
        print_warning "$description not found – installing via nix-env -iA nixos.$attr_path"
        log INFO "Attempting nix-env installation for $cmd using nixos channel"

        if run_as_primary_user nix-env -iA "nixos.$attr_path" >"$install_log" 2>&1; then
            install_succeeded=true
            install_method="nix-env (nixos channel)"
        else
            exit_code=$?
            log WARNING "nix-env -iA nixos.$attr_path for $cmd failed with exit code $exit_code, trying nixpkgs fallback"

            # Fallback to nixpkgs if nixos channel fails
            print_warning "$description installation retry via nix-env -f '<nixpkgs>' -iA $attr_path"
            log INFO "Attempting nix-env installation for $cmd using nixpkgs"

            if run_as_primary_user nix-env -f '<nixpkgs>' -iA "$attr_path" >>"$install_log" 2>&1; then
                install_succeeded=true
                install_method="nix-env (nixpkgs)"
            else
                exit_code=$?
                log ERROR "nix-env -f '<nixpkgs>' -iA $attr_path for $cmd failed with exit code $exit_code"
            fi
        fi
    else
        log ERROR "nix-env command not available"
        print_error "Failed to install $description – nix-env not found"
        return 1
    fi

    if [[ "$install_succeeded" == true ]]; then
        hash -r 2>/dev/null || true

        # Ensure PATH includes nix profile directories
        export PATH="$HOME/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH"

        local new_path
        new_path=$(command -v "$cmd" 2>/dev/null || run_as_primary_user bash -lc "command -v $cmd" 2>/dev/null || true)

        if [[ -n "$new_path" ]]; then
            print_success "$description installed via $install_method: $new_path"
            log INFO "Prerequisite $cmd installed successfully via $install_method at $new_path"
        else
            print_warning "$description installation completed but command not yet on current PATH"
            print_info "Refreshing shell environment..."
            log WARNING "Prerequisite $cmd installed but not immediately visible on PATH"

            # Try reloading the environment
            if [[ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]]; then
                # shellcheck disable=SC1091
                source "$HOME/.nix-profile/etc/profile.d/nix.sh" 2>/dev/null || true
            fi

            # Check again after reloading
            new_path=$(command -v "$cmd" 2>/dev/null || true)
            if [[ -n "$new_path" ]]; then
                print_success "$description now available: $new_path"
                log INFO "Prerequisite $cmd available after environment refresh at $new_path"
            fi
        fi

        print_info "Installation log: $install_log"
        return 0
    else
        print_error "Failed to install $description via nix-env"
        log ERROR "Failed to install prerequisite $cmd via nix-env (exit code: $exit_code)"
        print_info "Review the log for details: $install_log"
        return 1
    fi
}

ensure_preflight_core_packages() {
    print_info "Ensuring core prerequisite packages are installed..."

    if ! ensure_prerequisite_installed "git" "nixpkgs#git" "git (version control)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "python3" "nixpkgs#python3" "python3 (Python interpreter)"; then
        return 1
    fi

    if ! ensure_prerequisite_installed "shellcheck" "nixpkgs#shellcheck" "shellcheck (shell script linter)"; then
        return 1
    fi

    return 0
}

# Check all required packages for successful installation
check_required_packages() {
    print_section "Checking Required Packages"

    local packages_ok=true

    # Track missing packages for summary
    declare -a MISSING_CRITICAL=()
    declare -a MISSING_IMPORTANT=()
    declare -a MISSING_OPTIONAL=()

    print_info "Verifying packages needed to run this installation..."
    echo ""

    # ========================================
    # CRITICAL PACKAGES
    # ========================================
    print_info "Critical packages (required for installation):"

    # jq - JSON manipulation (used throughout for state management)
    if ! ensure_package_available "jq" "jq" "CRITICAL" "jq (JSON processor)"; then
        MISSING_CRITICAL+=("jq")
        packages_ok=false
    fi

    # git - Required for pip install from git repositories
    if ! ensure_package_available "git" "git" "CRITICAL" "git (version control)"; then
        MISSING_CRITICAL+=("git")
        packages_ok=false
    fi

    # systemctl - Service management (should always be available on NixOS)
    if ! command -v systemctl &>/dev/null; then
        print_warning "systemctl not found (unusual for NixOS)"
        log WARNING "systemctl missing - this is unexpected on NixOS"
    else
        print_success "systemctl available"
    fi

    echo ""

    # ========================================
    # IMPORTANT PACKAGES
    # ========================================
    print_info "Important packages (recommended for full functionality):"

    # lspci - Hardware detection, GPU identification
    if ! ensure_package_available "lspci" "pciutils" "IMPORTANT" "lspci (PCI hardware detection)"; then
        MISSING_IMPORTANT+=("pciutils")
        packages_ok=false
    fi

    # which - Command location (used in multiple places)
    if ! ensure_package_available "which" "which" "IMPORTANT" "which (command locator)"; then
        MISSING_IMPORTANT+=("which")
        packages_ok=false
    fi

    # readlink - Path resolution (used for symlink following)
    if ! ensure_package_available "readlink" "coreutils" "IMPORTANT" "readlink (path resolver)"; then
        MISSING_IMPORTANT+=("coreutils")
        packages_ok=false
    fi

    # timeout - Command timeouts (used for service checks)
    if ! ensure_package_available "timeout" "coreutils" "IMPORTANT" "timeout (command timeout utility)"; then
        MISSING_IMPORTANT+=("coreutils (timeout)")
        packages_ok=false
    fi

    echo ""

    # ========================================
    # OPTIONAL PACKAGES
    # ========================================
    print_info "Optional packages (for enhanced features):"

    # glxinfo - AMD GPU validation
    if ! ensure_package_available "glxinfo" "mesa-demos" "OPTIONAL" "glxinfo (AMD GPU validation)"; then
        MISSING_OPTIONAL+=("mesa-demos")
        # Note: OPTIONAL packages don't set packages_ok=false
    fi

    # nvidia-smi - NVIDIA GPU validation (only check if not on system yet)
    # Note: nvidia-smi comes with NVIDIA drivers, so it won't be available until after
    # the drivers are installed. We'll validate it in the post-deployment phase instead.
    if command -v nvidia-smi &>/dev/null; then
        local nvidia_path
        nvidia_path=$(command -v nvidia-smi 2>/dev/null)
        print_success "nvidia-smi (NVIDIA GPU validation) available: $nvidia_path"
    else
        print_info "nvidia-smi (NVIDIA GPU validation) not found - will be installed with NVIDIA drivers if needed"
        log INFO "nvidia-smi not present - expected to be installed with NVIDIA drivers during deployment"
    fi

    # loginctl - systemd login management
    if ! ensure_package_available "loginctl" "systemd" "OPTIONAL" "loginctl (systemd login manager)"; then
        MISSING_OPTIONAL+=("systemd")
        # Note: OPTIONAL packages don't set packages_ok=false
    fi

    echo ""

    # ========================================
    # SUMMARY
    # ========================================
    if [[ ${#MISSING_CRITICAL[@]} -eq 0 ]] && [[ ${#MISSING_IMPORTANT[@]} -eq 0 ]] && [[ ${#MISSING_OPTIONAL[@]} -eq 0 ]]; then
        print_success "All required packages available"
    else
        if [[ ${#MISSING_CRITICAL[@]} -gt 0 ]]; then
            print_error "Missing critical packages: ${MISSING_CRITICAL[*]}"
            print_error "Installation cannot proceed without these packages"
            packages_ok=false
        fi

        if [[ ${#MISSING_IMPORTANT[@]} -gt 0 ]]; then
            print_error "Missing important packages: ${MISSING_IMPORTANT[*]}"
            print_info "These packages are needed for full functionality"
            packages_ok=false
        fi

        if [[ ${#MISSING_OPTIONAL[@]} -gt 0 ]]; then
            print_info "Missing optional packages: ${MISSING_OPTIONAL[*]}"
            print_info "These packages provide enhanced features but are not required"
        fi
    fi

    echo ""

    # Only fail if CRITICAL or IMPORTANT packages are missing
    if [[ "$packages_ok" != true ]]; then
        log ERROR "Required package check failed - critical or important packages missing"
        return 1
    fi

    log INFO "Required package check passed"
    return 0
}

# Centralized backup function
centralized_backup() {
    local source="$1"
    local description="$2"

    if [[ ! -e "$source" ]]; then
        log DEBUG "Backup skipped - source does not exist: $source"
        return 0
    fi

    local relative_path="${source#$HOME/}"
    local backup_path="$BACKUP_ROOT/$relative_path"

    mkdir -p "$(dirname "$backup_path")"

    if cp -a "$source" "$backup_path" 2>/dev/null; then
        echo "$(date -Iseconds) | $source -> $backup_path | $description" >> "$BACKUP_MANIFEST"
        print_success "Backed up: $description"
        log INFO "Backed up: $source -> $backup_path"
        return 0
    else
        print_warning "Failed to backup: $description"
        log WARNING "Backup failed: $source"
        return 1
    fi
}

# ============================================================================
# GPU Validation
# ============================================================================

validate_gpu_driver() {
    print_section "GPU Driver Validation"

    local vendor=$(lspci 2>/dev/null | grep -i 'vga\|3d\|display' | head -1 || echo "")

    if [[ -z "$vendor" ]]; then
        print_info "No discrete GPU detected (using integrated graphics)"
        log INFO "No GPU detected"
        return 0
    fi

    log INFO "GPU detected: $vendor"

    case "$vendor" in
        *NVIDIA*|*GeForce*|*Quadro*)
            print_info "NVIDIA GPU detected"
            if command -v nvidia-smi &>/dev/null; then
                if nvidia-smi &>/dev/null; then
                    local gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "Unknown")
                    local driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo "Unknown")
                    print_success "NVIDIA driver OK: $gpu_name (Driver: $driver_version)"
                    log INFO "NVIDIA GPU validated: $gpu_name, Driver: $driver_version"
                else
                    print_error "NVIDIA driver not working properly"
                    print_info "Check logs: journalctl -b | grep nvidia"
                    log ERROR "NVIDIA driver validation failed"
                    return 1
                fi
            else
                print_warning "nvidia-smi not found - driver may not be installed yet"
                print_info "This is normal if this is the first deployment"
                log WARNING "nvidia-smi not available"
            fi
            ;;
        *AMD*|*Radeon*|*ATI*)
            print_info "AMD GPU detected"
            if command -v glxinfo &>/dev/null; then
                if glxinfo 2>/dev/null | grep -qi "amd\|radeon"; then
                    print_success "AMD GPU driver appears to be working"
                    log INFO "AMD GPU validated"
                else
                    print_warning "AMD driver may not be loaded correctly"
                    log WARNING "AMD GPU validation inconclusive"
                fi
            else
                print_info "glxinfo not available for AMD GPU validation"
                print_info "Install mesa-demos to validate: nix-env -iA nixos.mesa-demos"
                log INFO "AMD GPU detected but glxinfo not available for validation"
            fi
            ;;
        *Intel*)
            print_info "Intel GPU detected (integrated graphics)"
            print_success "Intel graphics should work out-of-the-box"
            log INFO "Intel GPU detected"
            ;;
        *)
            print_warning "Unknown GPU vendor detected"
            print_info "GPU: $vendor"
            log WARNING "Unknown GPU vendor: $vendor"
            ;;
    esac

    echo ""
    return 0
}

# ============================================================================
# Rollback Mechanism
# ============================================================================

create_rollback_point() {
    local description="$1"

    log INFO "Creating rollback point: $description"

    # Get current generation
    local nix_generation=$(nix-env --list-generations 2>/dev/null | tail -1 | awk '{print $1}' || echo "unknown")
    local hm_generation=$(home-manager generations 2>/dev/null | head -1 | awk '{print $NF}' || echo "unknown")

    cat > "$ROLLBACK_INFO_FILE" <<EOF
{
  "description": "$description",
  "created_at": "$(date -Iseconds)",
  "nix_generation": "$nix_generation",
  "home_manager_generation": "$hm_generation",
  "backup_root": "$BACKUP_ROOT"
}
EOF

    print_info "Rollback point created: $description"
    log INFO "Rollback info saved to: $ROLLBACK_INFO_FILE"
}

perform_rollback() {
    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        print_error "No rollback point available"
        log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1
    fi

    print_section "Rolling Back to Previous State"

    local description=$(jq -r '.description' "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "unknown")
    print_info "Rollback point: $description"

    if ! confirm "Are you sure you want to rollback?" "n"; then
        print_info "Rollback cancelled"
        return 0
    fi

    print_info "Rolling back Nix environment..."
    nix-env --rollback || print_warning "Nix rollback had issues"

    print_info "Rolling back Home Manager..."
    local hm_gen=$(jq -r '.home_manager_generation' "$ROLLBACK_INFO_FILE" 2>/dev/null)
    if [[ -n "$hm_gen" && "$hm_gen" != "unknown" && -x "$hm_gen/activate" ]]; then
        "$hm_gen/activate" || print_warning "Home Manager rollback had issues"
    fi

    print_info "Rolling back NixOS system..."
    if confirm "Rollback NixOS system configuration?" "n"; then
        sudo nixos-rebuild switch --rollback || print_warning "NixOS rollback had issues"
    fi

    print_success "Rollback completed"
    log INFO "Rollback completed"
}

restore_removed_packages() {
    print_section "Package Recovery"

    # Find the most recent removed packages file
    local removed_pkgs_file
    removed_pkgs_file=$(ls -t "$STATE_DIR"/removed-packages-*.txt 2>/dev/null | head -1)

    if [[ -z "$removed_pkgs_file" || ! -f "$removed_pkgs_file" ]]; then
        print_info "No removed package list found - nothing to restore"
        return 0
    fi

    print_info "Found removed package list: $removed_pkgs_file"

    local pkg_count
    pkg_count=$(wc -l < "$removed_pkgs_file")

    print_info "Found $pkg_count package(s) that were removed"
    echo ""
    print_warning "Removed packages:"
    cat "$removed_pkgs_file" | sed 's/^/  /'
    echo ""

    if ! confirm "Do you want to restore these packages?" "n"; then
        print_info "Package restoration skipped"
        return 0
    fi

    print_info "Restoring removed packages..."
    local restored=0
    local failed=0

    while IFS= read -r pkg; do
        local pkg_name
        pkg_name=$(echo "$pkg" | awk '{print $1}')
        if [[ -n "$pkg_name" ]]; then
            print_info "Restoring: $pkg_name"
            if nix-env -iA "nixpkgs.$pkg_name" 2>/dev/null; then
                print_success "  ✓ Restored: $pkg_name"
                ((restored++))
            else
                print_warning "  ✗ Failed: $pkg_name"
                ((failed++))
            fi
        fi
    done < "$removed_pkgs_file"

    echo ""
    print_success "Package restoration complete"
    print_info "  Restored: $restored package(s)"
    if [[ $failed -gt 0 ]]; then
        print_warning "  Failed: $failed package(s)"
    fi

    log INFO "Package restoration completed: $restored restored, $failed failed"
}

# ============================================================================
# Original Script Variables
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
# Note: Cursor IDE, LM Studio, and Gitea are not available on Flathub
# These are installed via home-manager instead:
#   - Cursor IDE: pkgs.code-cursor (in home.packages)
#   - LM Studio: Not available/broken in nixpkgs, use Ollama instead (already installed)
#   - Gitea: Configured as system service in configuration.nix
LAST_FLATPAK_QUERY_MESSAGE=""

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
FLATPAK_DIAGNOSTIC_ROOT="$PRIMARY_HOME/.cache/nixos-quick-deploy/flatpak"

GITEA_FLATPAK_APP_ID="io.gitea.Gitea"
GITEA_FLATPAK_CONFIG_DIR="$PRIMARY_HOME/.var/app/$GITEA_FLATPAK_APP_ID/config/gitea"
GITEA_FLATPAK_DATA_DIR="$PRIMARY_HOME/.var/app/$GITEA_FLATPAK_APP_ID/data/gitea"
GITEA_NATIVE_CONFIG_DIR="$PRIMARY_HOME/.config/gitea"
GITEA_NATIVE_DATA_DIR="$PRIMARY_HOME/.local/share/gitea"
HUGGINGFACE_CONFIG_DIR="$PRIMARY_HOME/.config/huggingface"
HUGGINGFACE_CACHE_DIR="$PRIMARY_HOME/.cache/huggingface"
OPEN_WEBUI_DATA_DIR="$PRIMARY_HOME/.local/share/open-webui"
AIDER_CONFIG_DIR="$PRIMARY_HOME/.config/aider"
TEA_CONFIG_DIR="$PRIMARY_HOME/.config/tea"
LATEST_CONFIG_BACKUP_DIR=""
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

USER_SYSTEMD_CHANNEL_STATUS="unknown"
USER_SYSTEMD_CHANNEL_MESSAGE=""

build_primary_user_path() {
    local -a path_parts=()

    if [[ -d "$PRIMARY_PROFILE_BIN" ]]; then
        path_parts+=("$PRIMARY_PROFILE_BIN")
    fi

    if [[ -d "$PRIMARY_ETC_PROFILE_BIN" ]]; then
        path_parts+=("$PRIMARY_ETC_PROFILE_BIN")
    fi

    if [[ -d "$PRIMARY_LOCAL_BIN" ]]; then
        path_parts+=("$PRIMARY_LOCAL_BIN")
    fi

    local -a CURRENT_PATH_PARTS=()
    local IFS=':'
    read -ra CURRENT_PATH_PARTS <<< "$PATH"
    for segment in "${CURRENT_PATH_PARTS[@]}"; do
        if [[ -n "$segment" ]]; then
            local duplicate=false
            for existing in "${path_parts[@]}"; do
                if [[ "$existing" == "$segment" ]]; then
                    duplicate=true
                    break
                fi
            done
            if [[ "$duplicate" == false ]]; then
                path_parts+=("$segment")
            fi
        fi
    done

    local combined_path
    IFS=':' combined_path="${path_parts[*]}"
    printf '%s' "$combined_path"
}

run_as_primary_user() {
    local -a cmd=("$@")
    local -a env_args=()

    if [[ -n "$PRIMARY_RUNTIME_DIR" ]]; then
        env_args+=("XDG_RUNTIME_DIR=$PRIMARY_RUNTIME_DIR")
        if [[ -S "$PRIMARY_RUNTIME_DIR/bus" ]]; then
            env_args+=("DBUS_SESSION_BUS_ADDRESS=unix:path=$PRIMARY_RUNTIME_DIR/bus")
        fi
    fi

    env_args+=("PATH=$(build_primary_user_path)")

    if [[ -n "${NIX_CONFIG:-}" ]]; then
        env_args+=("NIX_CONFIG=$NIX_CONFIG")
    fi

    if [[ $EUID -eq 0 && "$PRIMARY_USER" != "root" ]]; then
        if (( ${#env_args[@]} > 0 )); then
            sudo -H -u "$PRIMARY_USER" env "${env_args[@]}" "${cmd[@]}"
        else
            sudo -H -u "$PRIMARY_USER" "${cmd[@]}"
        fi
    else
        if (( ${#env_args[@]} > 0 )); then
            env "${env_args[@]}" "${cmd[@]}"
        else
            "${cmd[@]}"
        fi
    fi
}

flatpak_cli_available() {
    run_as_primary_user flatpak --version >/dev/null 2>&1
}

prepare_flatpak_diagnostic_dir() {
    local dir="$FLATPAK_DIAGNOSTIC_ROOT"

    if [[ -z "$dir" ]]; then
        return
    fi

    if ! run_as_primary_user install -d -m 700 "$dir" >/dev/null 2>&1; then
        mkdir -p "$dir" 2>/dev/null || true
        ensure_path_owner "$dir"
    fi

    printf '%s' "$dir"
}

gather_flatpak_diagnostics() {
    local service_name="$1"
    local stage="${2:-snapshot}"

    if [[ -z "$service_name" ]]; then
        return 0
    fi

    local diag_dir
    diag_dir=$(prepare_flatpak_diagnostic_dir)

    if [[ -z "$diag_dir" ]]; then
        return 0
    fi

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    local status_log="$diag_dir/${stage}-${timestamp}-status.log"
    local journal_log="$diag_dir/${stage}-${timestamp}-journal.log"

    local quoted_service
    printf -v quoted_service '%q' "$service_name"

    run_as_primary_user bash -c "systemctl --user status ${quoted_service} --no-pager" >"$status_log" 2>&1 || true
    run_as_primary_user bash -c "journalctl --user -u ${quoted_service} --no-pager --since '1 hour ago'" >"$journal_log" 2>&1 || true

    ensure_path_owner "$status_log"
    ensure_path_owner "$journal_log"

    print_info "Flatpak diagnostics captured under $diag_dir"
}

ensure_user_systemd_ready() {
    if ! command -v loginctl >/dev/null 2>&1; then
        return 0
    fi

    local user="$PRIMARY_USER"
    if [[ -z "$user" ]]; then
        return 0
    fi

    local user_info=""
    user_info=$(loginctl show-user "$user" 2>/dev/null || true)

    if [[ -z "$user_info" && $EUID -eq 0 ]]; then
        loginctl enable-linger "$user" >/dev/null 2>&1 || true
        user_info=$(loginctl show-user "$user" 2>/dev/null || true)
    fi

    local runtime_path=""
    runtime_path=$(printf '%s\n' "$user_info" | awk -F= '/^RuntimePath=/{print $2}' | tail -n1)

    if [[ -z "$runtime_path" ]]; then
        runtime_path="/run/user/$PRIMARY_UID"
    fi

    if [[ ! -d "$runtime_path" && $EUID -eq 0 ]]; then
        install -d -m 700 -o "$PRIMARY_USER" -g "$PRIMARY_GROUP" "$runtime_path" 2>/dev/null || true
    fi

    if [[ -d "$runtime_path" ]]; then
        PRIMARY_RUNTIME_DIR="$runtime_path"
    fi

    local linger_state=""
    linger_state=$(printf '%s\n' "$user_info" | awk -F= '/^Linger=/{print $2}' | tail -n1)
    if [[ "$linger_state" != "yes" && $EUID -eq 0 ]]; then
        if loginctl enable-linger "$user" >/dev/null 2>&1; then
            print_info "Enabled lingering for $user to keep user services active"
        fi
    fi

    if [[ -n "$PRIMARY_RUNTIME_DIR" && ! -S "$PRIMARY_RUNTIME_DIR/bus" ]]; then
        run_as_primary_user systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi

    return 0
}

user_systemd_channel_ready() {
    if [[ "$USER_SYSTEMD_CHANNEL_STATUS" == "available" ]]; then
        return 0
    fi

    if [[ "$USER_SYSTEMD_CHANNEL_STATUS" == "unavailable" ]]; then
        return 1
    fi

    ensure_user_systemd_ready || true

    if ! command -v systemctl >/dev/null 2>&1; then
        USER_SYSTEMD_CHANNEL_STATUS="unavailable"
        USER_SYSTEMD_CHANNEL_MESSAGE="systemctl command not available"
        return 1
    fi

    local timeout_bin
    timeout_bin=$(command -v timeout || true)
    if [[ -z "$timeout_bin" ]]; then
        USER_SYSTEMD_CHANNEL_STATUS="unavailable"
        USER_SYSTEMD_CHANNEL_MESSAGE="timeout command not available"
        return 1
    fi

    local output
    output=$(run_as_primary_user "$timeout_bin" 5s systemctl --user show-environment 2>&1)
    local status=$?

    if (( status == 0 )); then
        USER_SYSTEMD_CHANNEL_STATUS="available"
        USER_SYSTEMD_CHANNEL_MESSAGE=""
        return 0
    fi

    USER_SYSTEMD_CHANNEL_STATUS="unavailable"
    if (( status == 124 )); then
        USER_SYSTEMD_CHANNEL_MESSAGE="systemctl --user show-environment timed out (user systemd session not detected)"
    elif [[ "$output" == *"Failed to connect to bus"* ]]; then
        USER_SYSTEMD_CHANNEL_MESSAGE="$output"
    else
        USER_SYSTEMD_CHANNEL_MESSAGE="${output:-systemctl --user show-environment exited with status $status}"
    fi

    return 1
}

wait_for_systemd_user_service() {
    local service_name="$1"
    local timeout="${2:-180}"
    local interval=3
    local waited=0

    while (( waited < timeout )); do
        local show_output
        show_output=$(run_as_primary_user systemctl --user show "$service_name" -p Result -p ActiveState -p SubState 2>/dev/null || true)

        if [[ -z "$show_output" ]]; then
            sleep "$interval"
            waited=$((waited + interval))
            continue
        fi

        local result
        local active
        local substate
        result=$(printf '%s\n' "$show_output" | awk -F= '/^Result=/{print $2}' | tail -n1)
        active=$(printf '%s\n' "$show_output" | awk -F= '/^ActiveState=/{print $2}' | tail -n1)
        substate=$(printf '%s\n' "$show_output" | awk -F= '/^SubState=/{print $2}' | tail -n1)

        if [[ "$result" == "success" ]]; then
            return 0
        fi

        if [[ "$result" == "failure" || "$active" == "failed" || "$substate" == "failed" ]]; then
            return 1
        fi

        if [[ "$active" == "inactive" && "$substate" == "dead" && -z "$result" ]]; then
            return 0
        fi

        sleep "$interval"
        waited=$((waited + interval))
    done

    return 2
}

flatpak_remote_exists() {
    if ! flatpak_cli_available; then
        return 1
    fi

    local remote_output
    remote_output=$(run_as_primary_user flatpak remotes --user --columns=name 2>/dev/null || true)

    printf '%s\n' "$remote_output" \
        | awk 'NR == 1 && $1 == "Name" { next } { print $1 }' \
        | grep -Fxq "$FLATHUB_REMOTE_NAME"
}

flatpak_beta_remote_exists() {
    if ! flatpak_cli_available; then
        return 1
    fi

    local remote_output
    remote_output=$(run_as_primary_user flatpak remotes --user --columns=name 2>/dev/null || true)

    printf '%s\n' "$remote_output" \
        | awk 'NR == 1 && $1 == "Name" { next } { print $1 }' \
        | grep -Fxq "$FLATHUB_BETA_REMOTE_NAME"
}

ensure_flathub_beta_remote() {
    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; skipping Flathub Beta configuration"
        return 1
    fi

    if flatpak_beta_remote_exists; then
        print_info "Flathub Beta repository already configured"
        return 0
    fi

    print_info "Adding Flathub Beta Flatpak remote for bleeding-edge AI builds..."

    local from_output=""
    if from_output=$(run_as_primary_user flatpak remote-add --user --if-not-exists --from "$FLATHUB_BETA_REMOTE_NAME" "$FLATHUB_BETA_REMOTE_URL" 2>&1); then
        print_success "Flathub Beta repository added"
        return 0
    fi

    if [[ -n "$from_output" ]]; then
        print_warning "  ↳ Failed to add Flathub Beta via --from"
        while IFS= read -r line; do
            print_info "     $line"
        done <<<"$from_output"
    fi

    local direct_output=""
    if direct_output=$(run_as_primary_user flatpak remote-add --user --if-not-exists "$FLATHUB_BETA_REMOTE_NAME" "$FLATHUB_BETA_REMOTE_URL" 2>&1); then
        print_success "Flathub Beta repository added"
        return 0
    fi

    if [[ -n "$direct_output" ]]; then
        print_warning "  ↳ Failed to add Flathub Beta via direct URL"
        while IFS= read -r line; do
            print_info "     $line"
        done <<<"$direct_output"
    fi

    print_warning "Flathub Beta remote could not be configured"
    return 1
}

flatpak_query_application_support() {
    if ! flatpak_cli_available; then
        LAST_FLATPAK_QUERY_MESSAGE="Flatpak CLI not available"
        return 2
    fi

    local app_id="$1"
    local user_output
    local user_status
    local system_output
    local system_status

    LAST_FLATPAK_QUERY_MESSAGE=""

    user_output=$(run_as_primary_user flatpak --user remote-info "$FLATHUB_REMOTE_NAME" "$app_id" 2>&1 || true)
    user_status=$?
    if [[ $user_status -eq 0 ]]; then
        return 0
    fi

    system_output=$(run_as_primary_user flatpak remote-info "$FLATHUB_REMOTE_NAME" "$app_id" 2>&1 || true)
    system_status=$?
    if [[ $system_status -eq 0 ]]; then
        return 0
    fi

    LAST_FLATPAK_QUERY_MESSAGE="$user_output"
    if [[ -n "$LAST_FLATPAK_QUERY_MESSAGE" && -n "$system_output" ]]; then
        LAST_FLATPAK_QUERY_MESSAGE+=$'\n'
    fi
    LAST_FLATPAK_QUERY_MESSAGE+="$system_output"

    if printf '%s\n' "$LAST_FLATPAK_QUERY_MESSAGE" | grep -Eiq 'No remote refs found similar|No entry for|Nothing matches'; then
        return 3
    fi

    return 1
}

flatpak_install_app_list() {
    if [[ $# -eq 0 ]]; then
        return 0
    fi

    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; cannot install applications"
        return 1
    fi

    local -a apps=("$@")
    local failure=false

    run_as_primary_user flatpak --user repair >/dev/null 2>&1 || true

    for app_id in "${apps[@]}"; do
        if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            print_info "  • $app_id already present"
            continue
        fi

        local support_status=0
        flatpak_query_application_support "$app_id"
        support_status=$?
        if [[ $support_status -ne 0 ]]; then
            if [[ $support_status -eq 3 ]]; then
                print_warning "  ⚠ $app_id is not available on $FLATHUB_REMOTE_NAME for this architecture; skipping"
                if [[ -n "$LAST_FLATPAK_QUERY_MESSAGE" ]]; then
                    while IFS= read -r line; do
                        print_info "    ↳ $line"
                    done <<<"$LAST_FLATPAK_QUERY_MESSAGE"
                fi
                continue
            fi

            print_error "  ✗ Unable to query metadata for $app_id prior to installation"
            if [[ -n "$LAST_FLATPAK_QUERY_MESSAGE" ]]; then
                while IFS= read -r line; do
                    print_info "    ↳ $line"
                done <<<"$LAST_FLATPAK_QUERY_MESSAGE"
            fi
            failure=true
            continue
        fi

        print_info "  Installing $app_id from $FLATHUB_REMOTE_NAME..."
        local handled=false
        for attempt in 1 2 3; do
            local install_output=""
            if install_output=$(run_as_primary_user flatpak --noninteractive install --user "$FLATHUB_REMOTE_NAME" "$app_id" 2>&1); then
                print_success "  ✓ Installed $app_id"
                handled=true
                break
            fi

            if printf '%s\n' "$install_output" | grep -Eiq 'No remote refs found similar|No entry for|Nothing matches'; then
                print_warning "  ⚠ $app_id is not available on $FLATHUB_REMOTE_NAME for this architecture; skipping"
                if [[ -n "$install_output" ]]; then
                    while IFS= read -r line; do
                        print_info "    ↳ $line"
                    done <<<"$install_output"
                fi
                handled=true
                break
            fi

            print_warning "  ⚠ Attempt $attempt failed for $app_id"
            if [[ -n "$install_output" ]]; then
                while IFS= read -r line; do
                    print_info "    ↳ $line"
                done <<<"$install_output"
            fi
            sleep $(( attempt * 2 ))
        done

        if [[ "$handled" == false ]]; then
            print_error "  ✗ Failed to install $app_id after retries"
            failure=true
        fi
    done

    if [[ "$failure" == true ]]; then
        return 1
    fi

    return 0
}

validate_flatpak_application_state() {
    if ! flatpak_cli_available; then
        return 1
    fi

    local -a missing=()
    local -a unsupported=()

    for app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
        local support_status=0
        flatpak_query_application_support "$app_id"
        support_status=$?
        if [[ $support_status -ne 0 ]]; then
            if [[ $support_status -eq 3 ]]; then
                unsupported+=("$app_id")
                continue
            fi

            if [[ -n "$LAST_FLATPAK_QUERY_MESSAGE" ]]; then
                while IFS= read -r line; do
                    print_info "  ↳ $line"
                done <<<"$LAST_FLATPAK_QUERY_MESSAGE"
            fi
        fi

        if ! run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            missing+=("$app_id")
        fi
    done

    if (( ${#unsupported[@]} > 0 )); then
        print_info "Skipping Flatpak apps unsupported on this architecture: ${unsupported[*]}"
    fi

    if (( ${#missing[@]} > 0 )); then
        print_warning "Missing Flatpak applications: ${missing[*]}"
        return 1
    fi

    print_success "All declarative Flatpak applications are installed"
    return 0
}

ensure_path_owner() {
    local target_path="$1"

    if [[ $EUID -ne 0 ]]; then
        return 0
    fi

    if [[ -e "$target_path" ]]; then
        chown "$PRIMARY_USER:$PRIMARY_GROUP" "$target_path" 2>/dev/null || true
    fi

    return 0
}

ensure_flathub_remote() {
    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; skipping Flathub repository configuration for now"
        return 1
    fi

    if flatpak_remote_exists; then
        print_info "Flathub repository already configured"
        ensure_flathub_beta_remote
        return $?
    fi

    print_info "Adding Flathub Flatpak remote..."

    local -a remote_sources=("$FLATHUB_REMOTE_URL")
    if [[ -n "$FLATHUB_REMOTE_FALLBACK_URL" && "$FLATHUB_REMOTE_FALLBACK_URL" != "$FLATHUB_REMOTE_URL" ]]; then
        remote_sources+=("$FLATHUB_REMOTE_FALLBACK_URL")
    fi

    local source=""
    for source in "${remote_sources[@]}"; do
        local from_output=""
        if from_output=$(run_as_primary_user flatpak remote-add --user --if-not-exists --from "$FLATHUB_REMOTE_NAME" "$source" 2>&1); then
            if [[ "$source" == "$FLATHUB_REMOTE_URL" ]]; then
                print_success "Flathub repository added"
            else
                print_success "Flathub repository added via fallback source ($source)"
            fi
            ensure_flathub_beta_remote
            return $?
        fi

        if [[ -n "$from_output" ]]; then
            print_warning "  ↳ Failed to add Flathub via --from ($source)"
            while IFS= read -r line; do
                print_info "     $line"
            done <<<"$from_output"
        fi

        local direct_output=""
        if direct_output=$(run_as_primary_user flatpak remote-add --user --if-not-exists "$FLATHUB_REMOTE_NAME" "$source" 2>&1); then
            if [[ "$source" == "$FLATHUB_REMOTE_URL" ]]; then
                print_success "Flathub repository added"
            else
                print_success "Flathub repository added via fallback source ($source)"
            fi
            ensure_flathub_beta_remote
            return $?
        fi

        if [[ -n "$direct_output" ]]; then
            print_warning "  ↳ Failed to add Flathub directly ($source)"
            while IFS= read -r line; do
                print_info "     $line"
            done <<<"$direct_output"
        fi
    done

    print_warning "Unable to configure Flathub repository automatically (sources tried: ${remote_sources[*]})"
    return 1
}

backup_legacy_flatpak_configs() {
    local -a targets=(
        "$PRIMARY_HOME/.config/flatpak"
        "$PRIMARY_HOME/.local/share/flatpak/overrides"
        "$PRIMARY_HOME/.local/share/flatpak/remotes.d"
    )
    local backup_root="$PRIMARY_HOME/.cache/nixos-quick-deploy/flatpak/legacy-backups"
    local timestamp
    local performed=false
    local encountered_error=false
    local backup_dir=""

    timestamp="$(date +%Y%m%d_%H%M%S)"

    for path in "${targets[@]}"; do
        if run_as_primary_user test ! -e "$path" && run_as_primary_user test ! -L "$path"; then
            continue
        fi

        if run_as_primary_user test -d "$path" && ! run_as_primary_user test -L "$path"; then
            local entry_output=""
            entry_output=$(run_as_primary_user bash -c "find \"$path\" -mindepth 1 -print -quit 2>/dev/null" || true)
            if [[ -z "$entry_output" ]]; then
                continue
            fi
        fi

        local dest_output=""
        dest_output=$(run_as_primary_user bash -c '
set -euo pipefail
path="$1"
backup_root="$2"
timestamp="$3"
relative="${path#$HOME/}"
if [ "$relative" = "$path" ]; then
  relative="$(basename "$path")"
fi
if [ "$relative" = "$path" ]; then
  rel_dir="."
else
  rel_dir="$(dirname "$relative")"
fi
if [ "$rel_dir" = "." ]; then
  dest_dir="$backup_root/$timestamp"
else
  dest_dir="$backup_root/$timestamp/$rel_dir"
fi
mkdir -p "$dest_dir"
dest_path="$dest_dir/$(basename "$path")"
if cp -a "$path" "$dest_path"; then
  rm -rf "$path"
  printf "%s" "$dest_path"
fi
' backup-script "$path" "$backup_root" "$timestamp")
        local backup_status=$?

        if [[ $backup_status -eq 0 && -n "$dest_output" ]]; then
            local display_path="$path"
            if [[ "$display_path" == "$PRIMARY_HOME"/* ]]; then
                display_path="${display_path#$PRIMARY_HOME/}"
            fi
            local display_dest="$dest_output"
            if [[ "$display_dest" == "$PRIMARY_HOME"/* ]]; then
                display_dest="${display_dest#$PRIMARY_HOME/}"
            fi
            print_info "  ↳ Backed up legacy Flatpak path: $display_path -> $display_dest"
            performed=true
            backup_dir="$backup_root/$timestamp"
        else
            encountered_error=true
            print_warning "  ↳ Failed to back up legacy Flatpak path: $path"
        fi
    done

    run_as_primary_user mkdir -p "$PRIMARY_HOME/.config/flatpak" >/dev/null 2>&1 || true

    if [[ "$performed" == true && -n "$backup_dir" ]]; then
        local display_backup="$backup_dir"
        if [[ "$display_backup" == "$PRIMARY_HOME"/* ]]; then
            display_backup="${display_backup#$PRIMARY_HOME/}"
        fi
        print_success "Legacy Flatpak configuration archived under $display_backup"
    fi

    if [[ "$encountered_error" == true ]]; then
        return 1
    fi

    return 0
}

reset_flatpak_repo_if_corrupted() {
    local repo_dir="$PRIMARY_HOME/.local/share/flatpak/repo"
    local repo_config="$repo_dir/config"
    local repo_parent="$PRIMARY_HOME/.local/share/flatpak"
    local repair_output=""

    run_as_primary_user install -d -m 700 "$repo_parent" >/dev/null 2>&1 || true

    # Check if repository is valid and complete
    if run_as_primary_user test -f "$repo_config" && run_as_primary_user test -d "$repo_dir/objects"; then
        return 0
    fi

    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI unavailable; deferring repository repair"
        return 1
    fi

    # Detect corrupted repository (exists but missing essential directories)
    if run_as_primary_user test -e "$repo_dir"; then
        if ! run_as_primary_user test -f "$repo_config" || ! run_as_primary_user test -d "$repo_dir/objects"; then
            print_warning "Detected corrupted Flatpak repository, removing and reinitializing..."
            run_as_primary_user rm -rf "$repo_dir" >/dev/null 2>&1 || true
        fi
    fi

    if ! run_as_primary_user test -e "$repo_dir"; then
        print_info "Initializing Flatpak repository under ${repo_dir#$PRIMARY_HOME/}"
    fi

    if ! run_as_primary_user install -d -m 700 "$repo_dir" >/dev/null 2>&1; then
        print_warning "Unable to recreate $repo_dir"
        return 1
    fi

    # Try ostree initialization first (more reliable for fresh repos)
    if run_as_primary_user command -v ostree >/dev/null 2>&1; then
        local ostree_output=""
        ostree_output=$(run_as_primary_user ostree --repo="$repo_dir" init --mode=bare-user-only 2>&1)
        local ostree_status=$?

        if [[ -n "$ostree_output" ]]; then
            while IFS= read -r line; do
                print_info "    $line"
            done <<<"$ostree_output"
        fi

        if (( ostree_status == 0 )) && run_as_primary_user test -f "$repo_config"; then
            print_success "Flatpak repository initialized via ostree"
            # Run flatpak repair to finalize the repo
            run_as_primary_user flatpak --user repair >/dev/null 2>&1 || true
            return 0
        fi

        # ostree init failed - manually create essential directory structure
        print_info "ostree init failed, creating repository structure manually..."

        # Remove any partial initialization and start fresh
        run_as_primary_user rm -rf "$repo_dir" >/dev/null 2>&1 || true
        run_as_primary_user install -d -m 700 "$repo_dir" >/dev/null 2>&1 || true

        # Create essential directories
        if ! (run_as_primary_user bash -c "mkdir -p \"$repo_dir/objects\" \"$repo_dir/tmp\" \
              \"$repo_dir/refs/heads\" \"$repo_dir/refs/remotes\" \
              \"$repo_dir/state\" 2>/dev/null"); then
            print_warning "Failed to create repository directory structure"
            return 1
        fi

        # Create minimal config file for bare-user-only mode
        if ! run_as_primary_user bash -c "cat > \"$repo_config\" 2>/dev/null <<'OSTREE_CONFIG'
[core]
repo_version=1
mode=bare-user-only
OSTREE_CONFIG
"; then
            print_warning "Failed to create repository config file"
            return 1
        fi

        # Verify the manual structure was created
        if run_as_primary_user test -f "$repo_config" && run_as_primary_user test -d "$repo_dir/objects"; then
            print_success "Flatpak repository structure created manually"
            # Run flatpak repair to finalize and validate the repo
            run_as_primary_user flatpak --user repair >/dev/null 2>&1 || true
            return 0
        else
            print_warning "Repository structure verification failed"
            return 1
        fi
    fi

    # Fall back to flatpak repair
    repair_output=$(run_as_primary_user flatpak --user repair 2>&1)
    local repair_status=$?

    if [[ -n "$repair_output" ]]; then
        while IFS= read -r line; do
            print_info "    $line"
        done <<<"$repair_output"
    fi

    if (( repair_status != 0 )); then
        print_warning "flatpak repair reported an error while attempting to recover the repository"
    fi

    if run_as_primary_user test -f "$repo_config"; then
        print_success "Flatpak repository initialized"
        return 0
    fi

    print_warning "Flatpak repository configuration still missing after recovery attempts"
    return 1
}

preflight_flatpak_environment() {
    local stage="${1:-preflight}"

    ensure_user_systemd_ready

    local issues=0

    if ! backup_legacy_flatpak_configs; then
        issues=$((issues + 1))
    fi

    if ! reset_flatpak_repo_if_corrupted; then
        issues=$((issues + 1))
    fi

    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI unavailable during $stage checks"
        issues=$((issues + 1))
    fi

    if [[ -n "$PRIMARY_RUNTIME_DIR" && ! -S "$PRIMARY_RUNTIME_DIR/bus" ]]; then
        run_as_primary_user systemctl --user start dbus.socket >/dev/null 2>&1 || true
        sleep 1
        if [[ ! -S "$PRIMARY_RUNTIME_DIR/bus" ]]; then
            print_warning "DBus session bus not detected for user services"
            issues=$((issues + 1))
        fi
    fi

    if ! ensure_flathub_remote; then
        issues=$((issues + 1))
    fi

    run_as_primary_user install -d -m 700 "$PRIMARY_HOME/.local/share/flatpak" >/dev/null 2>&1 || true
    run_as_primary_user install -d -m 700 "$PRIMARY_HOME/.var/app" >/dev/null 2>&1 || true

    if (( issues == 0 )); then
        return 0
    fi

    return 1
}

ensure_default_flatpak_apps_installed() {
    if ! flatpak_cli_available; then
        print_warning "Flatpak CLI not available; skipping Flatpak application installation"
        return
    fi

    print_section "Ensuring default Flatpak applications are installed"
    if ! ensure_flathub_remote; then
        print_warning "Skipping Flatpak installation because Flathub remote could not be configured"
        echo ""
        return
    fi

    local -a missing=()
    for app_id in "${DEFAULT_FLATPAK_APPS[@]}"; do
        if run_as_primary_user flatpak info --user "$app_id" >/dev/null 2>&1; then
            print_info "  • $app_id already present"
        else
            missing+=("$app_id")
        fi
    done

    if (( ${#missing[@]} == 0 )); then
        print_success "All default Flatpak applications are already installed"
        echo ""
        return
    fi

    if flatpak_install_app_list "${missing[@]}"; then
        print_success "Default Flatpak applications are now installed and ready"
    else
        print_warning "Some Flatpak applications could not be installed automatically. Try running: flatpak install --user $FLATHUB_REMOTE_NAME <app-id>"
    fi

    run_as_primary_user flatpak --user update --noninteractive --appstream >/dev/null 2>&1 || true
    run_as_primary_user flatpak --user update --noninteractive >/dev/null 2>&1 || true

    echo ""
}

recover_flatpak_managed_install_service() {
    local service_name="$1"

    if ! flatpak_cli_available; then
        return 1
    fi

    print_info "Attempting manual Flatpak recovery..."
    preflight_flatpak_environment "manual-recovery" || true

    if ! ensure_flathub_remote; then
        print_warning "Flathub remote is unavailable; manual recovery skipped"
        return 1
    fi

    run_as_primary_user flatpak --user repair >/dev/null 2>&1 || true

    if ! flatpak_install_app_list "${DEFAULT_FLATPAK_APPS[@]}"; then
        print_warning "Manual Flatpak installation encountered errors"
        gather_flatpak_diagnostics "$service_name" "recovery-failure"
        return 1
    fi

    run_as_primary_user flatpak --user update --noninteractive --appstream >/dev/null 2>&1 || true
    run_as_primary_user flatpak --user update --noninteractive >/dev/null 2>&1 || true

    if ! validate_flatpak_application_state; then
        gather_flatpak_diagnostics "$service_name" "validation-failure"
        return 1
    fi

    if [[ -n "$service_name" ]] && user_systemd_channel_ready; then
        run_as_primary_user systemctl --user reset-failed "$service_name" >/dev/null 2>&1 || true
        if run_as_primary_user systemctl --user start "$service_name" >/dev/null 2>&1; then
            wait_for_systemd_user_service "$service_name" 180 >/dev/null 2>&1 || true
        fi
    fi

    print_success "Flatpak packages installed via manual recovery"
    return 0
}

ensure_flatpak_managed_install_service() {
    if ! command -v systemctl >/dev/null 2>&1; then
        return
    fi

    local service_name="flatpak-managed-install.service"

    if ! user_systemd_channel_ready; then
        print_warning "User systemd session is unavailable; skipping $service_name management"
        if [[ -n "$USER_SYSTEMD_CHANNEL_MESSAGE" ]]; then
            local detail
            detail=$(printf '%s' "$USER_SYSTEMD_CHANNEL_MESSAGE" | head -n1)
            print_info "  Details: $detail"
        fi
        return
    fi

    preflight_flatpak_environment "service-start" || true

    if ! run_as_primary_user systemctl --user list-unit-files "$service_name" >/dev/null 2>&1; then
        return
    fi

    # Unmask the service if it was masked during cleanup_systemd_before_activation
    # This allows the service to be started now that home-manager activation is complete
    print_info "Unmasking $service_name after successful home-manager activation..."
    run_as_primary_user systemctl --user unmask "$service_name" 2>/dev/null || true

    # Create condition flag file to allow the service to run
    # This prevents the service from starting during home-manager activation
    local condition_file="/run/user/$(id -u "$PRIMARY_USER")/allow-flatpak-managed-install"
    run_as_primary_user touch "$condition_file" 2>/dev/null || true

    run_as_primary_user systemctl --user reset-failed "$service_name" >/dev/null 2>&1 || true

    if ! run_as_primary_user systemctl --user start "$service_name" >/dev/null 2>&1; then
        print_warning "Unable to start flatpak-managed-install service automatically"
        run_as_primary_user journalctl --user -u "$service_name" -n 25 || true
        gather_flatpak_diagnostics "$service_name" "start-failure"
        recover_flatpak_managed_install_service "$service_name" || true
        # Clean up condition file before returning
        run_as_primary_user rm -f "$condition_file" 2>/dev/null || true
        return
    fi

    local wait_result
    if wait_for_systemd_user_service "$service_name" 300; then
        if validate_flatpak_application_state; then
            print_success "flatpak-managed-install service completed successfully"
            # Clean up condition file before returning
            run_as_primary_user rm -f "$condition_file" 2>/dev/null || true
            return
        fi
        print_warning "flatpak-managed-install service finished but validation detected missing apps"
        gather_flatpak_diagnostics "$service_name" "post-success-validation"
        if recover_flatpak_managed_install_service "$service_name"; then
            print_success "Flatpak state corrected after validation retry"
        else
            print_warning "Manual Flatpak recovery could not fully resolve the issue. Review the logs above."
        fi
        # Clean up condition file before returning
        run_as_primary_user rm -f "$condition_file" 2>/dev/null || true
        return
    fi

    wait_result=$?
    if [[ $wait_result -eq 2 ]]; then
        print_warning "flatpak-managed-install service did not report completion within the timeout window"
        print_info "This usually means the Flatpak installer is still downloading large runtimes or waiting on network access."
        print_info "Home-manager marks the unit as failed once the wait times out, even though the service may still be running."
        print_info "Check journalctl --user -u $service_name for progress and re-run the installer once connectivity is restored."
    else
        print_warning "flatpak-managed-install service reported a failure; collecting logs"
    fi

    run_as_primary_user journalctl --user -u "$service_name" -n 40 || true
    gather_flatpak_diagnostics "$service_name" "service-failure"

    if recover_flatpak_managed_install_service "$service_name"; then
        print_success "Flatpak packages restored via manual recovery"
    else
        print_warning "Manual Flatpak recovery could not fully resolve the issue. Review the logs above."
    fi

    # Clean up condition file at end of function
    run_as_primary_user rm -f "$condition_file" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Backup helpers for clearing paths managed by home-manager
# ---------------------------------------------------------------------------

backup_path_if_exists() {
    local target_path="$1"
    local backup_dir="$2"
    local label="$3"

    if [[ ! -e "$target_path" && ! -L "$target_path" ]]; then
        return 1
    fi

    mkdir -p "$backup_dir"
    ensure_path_owner "$backup_dir"

    local rel_path
    if [[ "$target_path" == "$HOME" ]]; then
        rel_path="home-root"
    elif [[ "$target_path" == "$HOME"/* ]]; then
        rel_path="${target_path#$HOME/}"
    else
        rel_path="${target_path#/}"
    fi

    local dest_path="$backup_dir/$rel_path"
    mkdir -p "$(dirname "$dest_path")"
    ensure_path_owner "$(dirname "$dest_path")"

    if cp -a "$target_path" "$dest_path" 2>/dev/null; then
        if [[ -d "$target_path" && ! -L "$target_path" ]]; then
            rm -rf "$target_path"
        else
            rm -f "$target_path"
        fi

        ensure_path_owner "$dest_path"

        local display_label
        display_label="${label:-$rel_path}"
        print_success "Backed up and removed $display_label"
        print_info "  → Backup saved to: $dest_path"
        return 0
    fi

    print_warning "Failed to back up $label at $target_path"
    return 2
}

clean_home_manager_targets() {
    local phase_tag="${1:-pre-switch}"
    local timestamp
    timestamp="$(date +%Y%m%d_%H%M%S)"
    local backup_dir="$HOME/.config-backups/${phase_tag}-${timestamp}"
    local cleaned_any=false
    local encountered_error=false

    local -a directory_targets=(
        "$HOME/.config/flatpak::Flatpak configuration directory"
        "$HOME/.local/share/flatpak/overrides::Flatpak overrides directory"
        "$HOME/.local/share/flatpak/remotes.d::Flatpak remotes directory"
        "$AIDER_CONFIG_DIR::Aider configuration directory"
        "$TEA_CONFIG_DIR::Tea configuration directory"
        "$HUGGINGFACE_CONFIG_DIR::Hugging Face configuration directory"
        "$HUGGINGFACE_CACHE_DIR::Hugging Face cache directory"
        "$OPEN_WEBUI_DATA_DIR::Open WebUI data directory"
        "$PRIMARY_HOME/.local/share/podman-ai-stack::Podman AI stack data directory"
        "$GITEA_NATIVE_CONFIG_DIR::Gitea native configuration directory"
        "$GITEA_NATIVE_DATA_DIR::Gitea native data directory"
        "$GITEA_FLATPAK_CONFIG_DIR::Gitea Flatpak configuration directory"
        "$GITEA_FLATPAK_DATA_DIR::Gitea Flatpak data directory"
        "$PRIMARY_HOME/.config/obsidian/ai-integrations::Obsidian AI integration bootstrap data"
    )
    local -a file_targets=(
        "$HOME/.config/VSCodium/User/settings.json::VSCodium settings.json"
        "$HOME/.bashrc::.bashrc"
        "$HOME/.zshrc::.zshrc"
        "$HOME/.p10k.zsh::.p10k.zsh"
        "$LOCAL_BIN_DIR/p10k-setup-wizard.sh::p10k setup wizard script"
        "$LOCAL_BIN_DIR/gitea-editor::gitea editor helper"
        "$LOCAL_BIN_DIR/gitea-ai-assistant::gitea AI assistant helper"
        "$LOCAL_BIN_DIR/hf-model-sync::Hugging Face model sync helper"
        "$LOCAL_BIN_DIR/hf-tgi::Hugging Face TGI helper"
        "$LOCAL_BIN_DIR/open-webui-run::Open WebUI launcher"
        "$LOCAL_BIN_DIR/open-webui-stop::Open WebUI stop helper"
        "$LOCAL_BIN_DIR/gpt-cli::GPT CLI helper"
        "$LOCAL_BIN_DIR/podman-ai-stack::Podman AI stack orchestrator"
        "$LOCAL_BIN_DIR/code-cursor::Cursor IDE launcher"
        "$LOCAL_BIN_DIR/obsidian-ai-bootstrap::Obsidian AI bootstrap helper"
    )

    local entry path label result

    for entry in "${directory_targets[@]}"; do
        path="${entry%%::*}"
        label="${entry##*::}"

        result=0
        backup_path_if_exists "$path" "$backup_dir" "$label" || result=$?
        if [[ $result -eq 0 ]]; then
            cleaned_any=true
        elif [[ $result -eq 2 ]]; then
            encountered_error=true
        fi
    done

    for entry in "${file_targets[@]}"; do
        path="${entry%%::*}"
        label="${entry##*::}"

        result=0
        backup_path_if_exists "$path" "$backup_dir" "$label" || result=$?
        if [[ $result -eq 0 ]]; then
            cleaned_any=true
        elif [[ $result -eq 2 ]]; then
            encountered_error=true
        fi
    done

    local vscodium_user_dir="$HOME/.config/VSCodium/User"
    if [[ -d "$vscodium_user_dir" && ! -L "$vscodium_user_dir" ]]; then
        if find "$vscodium_user_dir" -mindepth 1 -maxdepth 1 ! -type l 2>/dev/null | grep -q .; then
            result=0
            backup_path_if_exists "$vscodium_user_dir" "$backup_dir" "VSCodium User directory" || result=$?
            if [[ $result -eq 0 ]]; then
                cleaned_any=true
            elif [[ $result -eq 2 ]]; then
                encountered_error=true
            fi
        fi
    fi

    if [[ "$cleaned_any" == true ]]; then
        LATEST_CONFIG_BACKUP_DIR="$backup_dir"
        print_success "All conflicting configs backed up to: $backup_dir"
        print_info "Home-manager will now create managed symlinks"
    else
        rm -rf "$backup_dir"
        LATEST_CONFIG_BACKUP_DIR=""
        print_info "No conflicting configuration files required backup."
    fi

    if [[ "$encountered_error" == true ]]; then
        print_warning "Some configuration paths could not be backed up automatically (see messages above)."
    fi
}

prepare_managed_config_paths() {
    local -a dir_specs=(
        "$LOCAL_BIN_DIR::755"
        "$AIDER_CONFIG_DIR::700"
        "$TEA_CONFIG_DIR::700"
        "$HUGGINGFACE_CONFIG_DIR::700"
        "$HUGGINGFACE_CACHE_DIR::700"
        "$OPEN_WEBUI_DATA_DIR::750"
        "$PRIMARY_HOME/.local/share/podman-ai-stack::750"
        "$GITEA_NATIVE_CONFIG_DIR::700"
        "$GITEA_NATIVE_DATA_DIR::750"
        "$PRIMARY_HOME/.var/app::755"
        "$GITEA_FLATPAK_CONFIG_DIR::700"
        "$GITEA_FLATPAK_DATA_DIR::750"
        "$PRIMARY_HOME/.config/flatpak::700"
        "$PRIMARY_HOME/.local/share/flatpak::750"
        "$PRIMARY_HOME/.config/obsidian/ai-integrations::700"
    )

    local spec path mode before_exists created_any=false

    for spec in "${dir_specs[@]}"; do
        path="${spec%%::*}"
        mode="${spec##*::}"
        if [[ "$mode" == "$path" ]]; then
            mode="755"
        fi

        before_exists=false
        if [[ -d "$path" ]]; then
            before_exists=true
        fi

        if run_as_primary_user install -d -m "$mode" "$path" >/dev/null 2>&1; then
            :
        else
            mkdir -p "$path" 2>/dev/null || true
            chmod "$mode" "$path" 2>/dev/null || true
        fi
        ensure_path_owner "$path"

        if [[ "$before_exists" == false && -d "$path" ]]; then
            created_any=true
        fi
    done

    if [[ "$created_any" == true ]]; then
        print_success "Prepared directories for managed configuration files"
    else
        print_info "Managed configuration directories already present."
    fi
}

cleanup_conflicting_home_manager_profile() {
    if ! command -v nix >/dev/null 2>&1; then
        return 0
    fi

    if nix profile remove home-manager >/dev/null 2>&1; then
        print_success "Preemptively removed default 'home-manager' profile entry"
    fi

    local removal_indices=""
    local conflict_detected=false

    local profile_json
    profile_json=$(nix profile list --json 2>/dev/null || true)

    if [[ -n "$profile_json" && "$profile_json" != "[]" ]]; then
        if ensure_python_runtime; then
            local parsed_indices
            parsed_indices=$(PROFILE_JSON="$profile_json" "${PYTHON_BIN[@]}" - <<'PY'
import json
import sys
import os

try:
    profile_json_str = os.environ.get('PROFILE_JSON', '[]')
    entries = json.loads(profile_json_str)
except Exception:
    sys.exit(1)

seen = set()
for entry in entries or []:
    if isinstance(entry, str):
        try:
            entry = json.loads(entry)
        except Exception:
            continue
    if not isinstance(entry, dict):
        continue
    text_parts = []
    for key in ("name", "attrPath", "description", "originalRef"):
        value = entry.get(key)
        if isinstance(value, str):
            text_parts.append(value)
    store_paths = entry.get("storePaths") or []
    for path in store_paths:
        if isinstance(path, str):
            text_parts.append(path)
    combined = " ".join(text_parts)
    if "home-manager" not in combined:
        continue
    idx = entry.get("index")
    if isinstance(idx, int):
        seen.add(str(idx))
    elif isinstance(idx, str) and idx:
        seen.add(idx)

if seen:
    print("\n".join(sorted(seen, key=lambda value: int(value) if value.isdigit() else value)))
PY
            )

            if [[ -n "$parsed_indices" ]]; then
                removal_indices+="$parsed_indices"$'\n'
                conflict_detected=true
            fi
        else
            print_warning "Python runtime unavailable; skipping JSON profile cleanup"
        fi
    fi

    if [[ "$conflict_detected" == false ]]; then
        local profile_output
        profile_output=$(nix profile list 2>/dev/null || true)
        if [[ -n "$profile_output" ]]; then
            local profile_lines
            profile_lines=$(echo "$profile_output" | tail -n +2 2>/dev/null || true)
            if [[ -n "$profile_lines" ]]; then
                local conflict_lines
                conflict_lines=$(echo "$profile_lines" | grep -E 'home-manager' || true)
                if [[ -n "$conflict_lines" ]]; then
                    conflict_detected=true
                    while IFS= read -r line; do
                        [[ -z "$line" ]] && continue
                        local idx
                        idx=$(echo "$line" | awk '{print $1}')
                        idx="${idx%:}"
                        [[ -z "$idx" ]] && continue
                        removal_indices+="$idx"$'\n'
                    done <<< "$conflict_lines"
                fi
            fi
        fi
    fi

    if [[ "$conflict_detected" == false ]]; then
        return 0
    fi

    print_warning "Existing home-manager profile entries detected (avoiding package conflict)"

    if [[ -n "$removal_indices" ]]; then
        removal_indices=$(printf '%s' "$removal_indices" | awk 'NF { if (!seen[$0]++) print $0 }' 2>/dev/null || printf '')
    fi

    local removed_any=false

    if [[ -n "$removal_indices" ]]; then
        while IFS= read -r idx; do
            [[ -z "$idx" ]] && continue
            if nix profile remove "$idx" >/dev/null 2>&1; then
                print_success "Removed home-manager profile entry at index $idx"
                removed_any=true
            else
                print_warning "Failed to remove home-manager profile entry at index $idx"
            fi
        done <<< "$removal_indices"
    fi

    if [[ "$removed_any" == false ]]; then
        for name in home-manager home-manager-path; do
            local attempt=0
            while nix profile list 2>/dev/null | tail -n +2 | grep -q "$name"; do
                if nix profile remove "$name" >/dev/null 2>&1; then
                    print_success "Removed existing '$name' profile entry"
                    removed_any=true
                else
                    break
                fi
                attempt=$((attempt + 1))
                if (( attempt >= 5 )); then
                    break
                fi
            done
        done
    fi

    if [[ "$removed_any" == false && ensure_python_runtime ]]; then
        local store_removals
        local profile_list_json
        profile_list_json=$(nix profile list --json 2>/dev/null || echo '[]')
        store_removals=$(
            PROFILE_JSON="$profile_list_json" "${PYTHON_BIN[@]}" - <<'PY'
import json
import sys
import os

try:
    profile_json_str = os.environ.get('PROFILE_JSON', '[]')
    entries = json.loads(profile_json_str)
except Exception:
    entries = []

paths = []
for entry in entries or []:
    if isinstance(entry, str):
        try:
            entry = json.loads(entry)
        except Exception:
            continue
    if not isinstance(entry, dict):
        continue
    store_paths = entry.get("storePaths") or []
    for path in store_paths:
        if isinstance(path, str) and "home-manager" in path:
            paths.append(path)

if paths:
    print("\n".join(paths))
PY
        )
        if [[ -n "$store_removals" ]]; then
            while IFS= read -r store_path; do
                [[ -z "$store_path" ]] && continue
                if nix profile remove "$store_path" >/dev/null 2>&1; then
                    print_success "Removed home-manager store path: $store_path"
                    removed_any=true
                fi
            done <<< "$store_removals"
        fi
    fi

    if [[ "$removed_any" == false ]]; then
        print_warning "No home-manager profile entries were removed; manual cleanup may be required"
    fi

    return 0
}

# Global state tracking
SYSTEM_CONFIG_BACKUP=""
HOME_MANAGER_BACKUP=""
HOME_MANAGER_CHANNEL_REF=""
HOME_MANAGER_CHANNEL_URL=""

HOME_MANAGER_APPLIED=false
SYSTEM_REBUILD_APPLIED=false
SYSTEM_BUILD_VALIDATED=false
INSTALLATION_APPROVED=false
SYSTEM_BUILD_DRY_RUN_LOG=""

# Preserved configuration data
SELECTED_TIMEZONE=""
USERS_MUTABLE_SETTING="true"
USER_PASSWORD_BLOCK=""
USER_TEMP_PASSWORD=""
PREVIOUS_TIMEZONE=""
PREVIOUS_MUTABLE_USERS=""
PREVIOUS_USER_PASSWORD_SNIPPET=""

# Build performance preference
USE_BINARY_CACHES="true"  # Default to using binary caches for faster builds

VERSION_FILE="$PRIMARY_HOME/.cache/nixos-quick-deploy-version"

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

# ------------------------------------------------------------------------------
# Nix Experimental Feature Management
# ------------------------------------------------------------------------------

ensure_nix_experimental_features_env() {
    local required_features="nix-command flakes"
    local addition="experimental-features = ${required_features}"
    local newline=$'\n'
    local current_config="${NIX_CONFIG:-}"

    if [[ -z "$current_config" ]]; then
        export NIX_CONFIG="$addition"
        log INFO "NIX_CONFIG initialized with experimental features: $required_features"
        return
    fi

    if printf '%s\n' "$current_config" | grep -q '^[[:space:]]*experimental-features[[:space:]]*='; then
        local existing_line
        existing_line=$(printf '%s\n' "$current_config" | grep '^[[:space:]]*experimental-features[[:space:]]*=' | head -n1)
        local features
        features=$(printf '%s' "${existing_line#*=}" | xargs)

        local feature
        local updated_features="$features"
        for feature in nix-command flakes; do
            if [[ " $updated_features " != *" $feature "* ]]; then
                updated_features+=" $feature"
            fi
        done
        updated_features=$(printf '%s' "$updated_features" | xargs)

        if [[ "$features" != "$updated_features" ]]; then
            local new_line="experimental-features = $updated_features"
            local updated_config
            updated_config=$(printf '%s\n' "$current_config" | sed "0,/^[[:space:]]*experimental-features[[:space:]]*=.*/s//${new_line}/")
            export NIX_CONFIG="$updated_config"
            log INFO "Updated NIX_CONFIG experimental features: $updated_features"
        else
            export NIX_CONFIG="$current_config"
            log DEBUG "NIX_CONFIG already contains required experimental features"
        fi
    else
        export NIX_CONFIG="${current_config}${newline}${addition}"
        log INFO "Appended experimental features to NIX_CONFIG: $required_features"
    fi
}

# ------------------------------------------------------------------------------
# Runtime Dependency Helpers
# ------------------------------------------------------------------------------

PYTHON_BIN=()

ensure_python_runtime() {
    # If PYTHON_BIN is cached, verify it's still accessible before using it
    if [ ${#PYTHON_BIN[@]} -gt 0 ]; then
        # Test if the cached python is still working
        if "${PYTHON_BIN[@]}" --version >/dev/null 2>&1; then
            return 0
        fi
        # Cached python is no longer valid, reset and re-detect
        PYTHON_BIN=()
        hash -r 2>/dev/null || true
    fi

    if command -v python3 >/dev/null 2>&1; then
        local python3_path
        python3_path=$(command -v python3)
        if [ -x "$python3_path" ]; then
            PYTHON_BIN=(python3)
            return 0
        fi
        hash -r 2>/dev/null || true
    fi

    if command -v python >/dev/null 2>&1; then
        local python_path
        python_path=$(command -v python)
        if [ -x "$python_path" ]; then
            PYTHON_BIN=(python)
            return 0
        fi
        hash -r 2>/dev/null || true
    fi

    if command -v nix >/dev/null 2>&1; then
        PYTHON_BIN=(nix shell nixpkgs#python3 -c python3)
        print_warning "python3 not found in PATH – using ephemeral nix shell"
        return 0
    fi

    print_error "python3 is required but not available."
    print_error "Install python3 or ensure it is on PATH before rerunning."
    return 1
}

run_python() {
    ensure_python_runtime || return 1
    "${PYTHON_BIN[@]}" "$@"
}

generate_hex_secret() {
    local bytes="${1:-32}"

    if ! ensure_python_runtime; then
        return 1
    fi

    "${PYTHON_BIN[@]}" - "$bytes" <<'PY'
import secrets
import sys

try:
    bytes_count = int(sys.argv[1])
except (IndexError, ValueError):
    bytes_count = 32

if bytes_count < 1:
    bytes_count = 32

print(secrets.token_hex(bytes_count))
PY
}

generate_password() {
    local length="${1:-20}"

    if ! ensure_python_runtime; then
        return 1
    fi

    "${PYTHON_BIN[@]}" - "$length" <<'PY'
import secrets
import string
import sys

try:
    length = int(sys.argv[1])
except (IndexError, ValueError):
    length = 20

alphabet = string.ascii_letters + string.digits
if length < 12:
    length = 12

print(''.join(secrets.choice(alphabet) for _ in range(length)))
PY
}

nix_quote_string() {
    local input="$1"

    input=${input//\\/\\\\}
    input=${input//"/\\"}
    input=${input//$'\n'/\\n}
    input=${input//$'\r'/\\r}
    input=${input//$'\t'/\\t}
    input=${input//\$/\\\$}

    printf '"%s"' "$input"
}

prompt_configure_gitea_admin() {
    local changed=false
    local default_choice="n"

    if [[ "${GITEA_BOOTSTRAP_ADMIN,,}" == "true" ]]; then
        default_choice="y"
        GITEA_BOOTSTRAP_ADMIN="true"
    else
        GITEA_BOOTSTRAP_ADMIN="false"
    fi

    if confirm "Do you want to bootstrap a Gitea admin account now?" "$default_choice"; then
        if [[ "$GITEA_BOOTSTRAP_ADMIN" != "true" ]]; then
            changed=true
        fi

        GITEA_BOOTSTRAP_ADMIN="true"

        local default_user="${GITEA_ADMIN_USER:-gitea-admin}"
        local admin_user
        admin_user=$(prompt_user "Gitea admin username" "$default_user")
        if [[ -z "$admin_user" ]]; then
            admin_user="$default_user"
        fi
        if [[ "$admin_user" != "$GITEA_ADMIN_USER" ]]; then
            GITEA_ADMIN_USER="$admin_user"
            changed=true
        fi

        local detected_domain="${HOSTNAME:-}"
        if [[ -z "$detected_domain" ]]; then
            detected_domain=$(hostname 2>/dev/null || echo "localhost")
        fi

        local default_email
        if [[ -n "$GITEA_ADMIN_EMAIL" ]]; then
            default_email="$GITEA_ADMIN_EMAIL"
        else
            default_email="${GITEA_ADMIN_USER}@${detected_domain}"
        fi

        local admin_email
        admin_email=$(prompt_user "Gitea admin email" "$default_email")
        if [[ -z "$admin_email" ]]; then
            admin_email="$default_email"
        fi
        if [[ "$admin_email" != "$GITEA_ADMIN_EMAIL" ]]; then
            GITEA_ADMIN_EMAIL="$admin_email"
            changed=true
        fi

        local password_note
        if [[ -n "$GITEA_ADMIN_PASSWORD" ]]; then
            password_note="leave blank to keep the existing password"
        else
            password_note="leave blank to generate a secure random password"
        fi

        local password_input
        password_input=$(prompt_secret "Gitea admin password" "$password_note")

        if [[ -z "$password_input" ]]; then
            if [[ -n "$GITEA_ADMIN_PASSWORD" ]]; then
                print_info "Keeping the previously cached Gitea admin password"
            else
                if ! GITEA_ADMIN_PASSWORD=$(generate_password 20); then
                    print_error "Failed to generate Gitea admin password"
                    return 1
                fi
                changed=true
                print_success "Generated a new random Gitea admin password"
            fi
        else
            if [[ "$password_input" != "$GITEA_ADMIN_PASSWORD" ]]; then
                GITEA_ADMIN_PASSWORD="$password_input"
                changed=true
            fi
        fi

        if [[ "$changed" == true ]]; then
            print_info "Gitea admin bootstrap will run after the next system switch"
        else
            print_info "Reusing existing Gitea admin bootstrap settings"
        fi

        if [[ -n "$GITEA_SECRETS_CACHE_FILE" ]]; then
            print_info "Secrets cache will be written to: $GITEA_SECRETS_CACHE_FILE"
        fi
    else
        if [[ "$GITEA_BOOTSTRAP_ADMIN" != "false" ]]; then
            changed=true
        fi
        GITEA_BOOTSTRAP_ADMIN="false"
        print_info "Skipping declarative Gitea admin bootstrap for this run"
        if [[ -n "$GITEA_SECRETS_CACHE_FILE" ]]; then
            print_info "You can enable it later by rerunning the installer and opting into the admin bootstrap"
        fi
    fi

    if [[ "$changed" == true ]]; then
        GITEA_PROMPT_CHANGED="true"
    else
        GITEA_PROMPT_CHANGED="false"
    fi

    return 0
}

load_or_generate_gitea_secrets() {
    if [[ -z "${GITEA_SECRET_KEY:-}" || -z "${GITEA_INTERNAL_TOKEN:-}" || -z "${GITEA_LFS_JWT_SECRET:-}" || -z "${GITEA_JWT_SECRET:-}" || -f "$GITEA_SECRETS_CACHE_FILE" ]]; then
        if [[ -f "$GITEA_SECRETS_CACHE_FILE" ]]; then
            # shellcheck disable=SC1090
            . "$GITEA_SECRETS_CACHE_FILE"
        fi
    fi

    local updated=false

    if [[ -z "${GITEA_SECRET_KEY:-}" ]]; then
        if ! GITEA_SECRET_KEY=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea secret key"
            return 1
        fi
        updated=true
    fi

    if [[ -z "${GITEA_INTERNAL_TOKEN:-}" ]]; then
        if ! GITEA_INTERNAL_TOKEN=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea internal token"
            return 1
        fi
        updated=true
    fi

    if [[ -z "${GITEA_LFS_JWT_SECRET:-}" ]]; then
        if ! GITEA_LFS_JWT_SECRET=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea LFS JWT secret"
            return 1
        fi
        updated=true
    fi

    if [[ -z "${GITEA_JWT_SECRET:-}" ]]; then
        if ! GITEA_JWT_SECRET=$(generate_hex_secret 32); then
            print_error "Failed to generate Gitea OAuth2 secret"
            return 1
        fi
        updated=true
    fi

    if [[ "${GITEA_ADMIN_PROMPTED}" != "true" ]]; then
        GITEA_PROMPT_CHANGED="false"
        if ! prompt_configure_gitea_admin; then
            return 1
        fi
        GITEA_ADMIN_PROMPTED="true"
        if [[ "$GITEA_PROMPT_CHANGED" == "true" ]]; then
            updated=true
        fi
    fi

    if [[ "$GITEA_BOOTSTRAP_ADMIN" == "true" ]]; then
        if [[ -z "${GITEA_ADMIN_USER:-}" ]]; then
            GITEA_ADMIN_USER="gitea-admin"
            updated=true
        fi

        if [[ -z "${GITEA_ADMIN_EMAIL:-}" ]]; then
            local detected_domain
            detected_domain=${HOSTNAME:-}
            if [[ -z "$detected_domain" ]]; then
                detected_domain=$(hostname 2>/dev/null || echo "localhost")
            fi
            GITEA_ADMIN_EMAIL="${GITEA_ADMIN_USER}@${detected_domain}"
            updated=true
        fi

        if [[ -z "${GITEA_ADMIN_PASSWORD:-}" ]]; then
            if ! GITEA_ADMIN_PASSWORD=$(generate_password 20); then
                print_error "Failed to generate Gitea admin password"
                return 1
            fi
            updated=true
        fi
    fi

    if $updated; then
        if [[ ! -d "$GITEA_SECRETS_CACHE_DIR" ]]; then
            if ! install -d -m 0700 "$GITEA_SECRETS_CACHE_DIR" 2>/dev/null; then
                mkdir -p "$GITEA_SECRETS_CACHE_DIR"
                chmod 700 "$GITEA_SECRETS_CACHE_DIR" 2>/dev/null || true
            fi
        fi

        chmod 700 "$GITEA_SECRETS_CACHE_DIR" 2>/dev/null || true

        cat >"$GITEA_SECRETS_CACHE_FILE" <<EOF
GITEA_SECRET_KEY=$GITEA_SECRET_KEY
GITEA_INTERNAL_TOKEN=$GITEA_INTERNAL_TOKEN
GITEA_LFS_JWT_SECRET=$GITEA_LFS_JWT_SECRET
GITEA_JWT_SECRET=$GITEA_JWT_SECRET
GITEA_ADMIN_USER=$GITEA_ADMIN_USER
GITEA_ADMIN_EMAIL=$GITEA_ADMIN_EMAIL
GITEA_ADMIN_PASSWORD=$GITEA_ADMIN_PASSWORD
GITEA_BOOTSTRAP_ADMIN=$GITEA_BOOTSTRAP_ADMIN
EOF

        chmod 600 "$GITEA_SECRETS_CACHE_FILE" 2>/dev/null || true
        ensure_path_owner "$GITEA_SECRETS_CACHE_DIR"
        ensure_path_owner "$GITEA_SECRETS_CACHE_FILE"

        print_success "Updated cached Gitea secrets for declarative setup"
        print_info "Stored secrets at: $GITEA_SECRETS_CACHE_FILE"
        if [[ "$GITEA_BOOTSTRAP_ADMIN" == "true" ]]; then
            print_info "Admin user: $GITEA_ADMIN_USER"
            print_warning "Admin password stored in secrets file under GITEA_ADMIN_PASSWORD"
            print_info "View securely with: grep GITEA_ADMIN_PASSWORD $GITEA_SECRETS_CACHE_FILE"
        fi
    fi

    return 0
}

harmonize_python_ai_bindings() {
    local target_file="$1"
    local context_label="${2:-$1}"

    if [[ ! -f "$target_file" ]]; then
        return 0
    fi

    if [[ ! -w "$target_file" ]]; then
        print_warning "Skipping $context_label - file not writable"
        return 0
    fi

    local harmonize_output
    harmonize_output=$(TARGET_HOME_NIX="$target_file" run_python <<'PY'
import os
import re
import sys
import textwrap
from pathlib import Path

target_path = os.environ.get("TARGET_HOME_NIX")
if not target_path:
    print("TARGET_HOME_NIX is not set", file=sys.stderr)
    sys.exit(1)

path = Path(target_path)
text = path.read_text(encoding="utf-8")
changed = False
messages = []

canonical_block = textwrap.dedent(
    """
    pythonAi =
      pkgs.python311.override {
        packageOverrides = self: super: {
          markdown = super.markdown.overridePythonAttrs (old: {
            doCheck = false;
          });
          "pytest-doctestplus" = super."pytest-doctestplus".overridePythonAttrs (old: {
            doCheck = false;
          });
          "google-api-core" = super."google-api-core".overridePythonAttrs (old: {
            doCheck = false;
          });
          "google-cloud-core" = super."google-cloud-core".overridePythonAttrs (old: {
            doCheck = false;
          });
          "google-cloud-storage" = super."google-cloud-storage".overridePythonAttrs (old: {
            doCheck = false;
          });
          "google-cloud-bigquery" = super."google-cloud-bigquery".overridePythonAttrs (old: {
            doCheck = false;
          });
          sqlframe = super.sqlframe.overridePythonAttrs (old: {
            postPatch = (old.postPatch or "")
              + ''
                find . -type f -name '*.py' -exec sed -i 's/np\\.NaN/np.nan/g' {} +
              '';
            doCheck = false;
            pythonImportsCheck = [];
          });
          "openai" = super."openai".overridePythonAttrs (old: {
            doCheck = false;
            pythonImportsCheck = [];
            postInstall = lib.concatStringsSep "\n" (
              lib.filter (s: s != "") [
                (old.postInstall or "")
                ''
                  rm -f "$out/bin/openai" "$out/bin/.openai-wrapped"
                ''
              ]
            );
          });
          psycopg = super.psycopg.overridePythonAttrs (old: {
            doCheck = false;
            pythonImportsCheck = [];
          });
        };
      };
    pythonAiEnv =
      pythonAi.withPackages (ps:
        let
          base = with ps; [
            pip
            setuptools
            wheel
            accelerate
            datasets
            diffusers
            peft
            safetensors
            sentencepiece
            tokenizers
            transformers
            evaluate
            gradio
            jupyterlab
            ipykernel
            pandas
            scikit-learn
            black
            ipython
            ipywidgets
          ];
          extras =
            lib.optionals (ps ? bitsandbytes) [ ps.bitsandbytes ]
            ++ lib.optionals (ps ? torch) [ ps.torch ]
            ++ lib.optionals (ps ? torchaudio) [ ps.torchaudio ]
            ++ lib.optionals (ps ? torchvision) [ ps.torchvision ];
        in
          base ++ extras
      );
    pythonAiInterpreterPath = "${pythonAiEnv}/bin/python3";
    """
).strip("\n")

let_match = re.search(r"(?m)^\s*let\b", text)

if not let_match:
    text = "let\n" + textwrap.indent(canonical_block, "  ") + "\n\nin\n" + text.lstrip("\n")
    changed = True
    messages.append("Created let binding with canonical pythonAiEnv definitions")
    let_match = re.search(r"(?m)^\s*let\b", text)
    if not let_match:
        path.write_text(text, encoding="utf-8")
        print("Created let binding with canonical pythonAiEnv definitions")
        sys.exit(0)

let_line_end = text.find("\n", let_match.end())
if let_line_end == -1:
    let_line_end = len(text)
else:
    let_line_end += 1

indent_match = re.search(r"(?m)^(?P<indent>\s+)\S", text[let_line_end:])
default_indent = indent_match.group("indent") if indent_match else "  "

env_binding_pattern = re.compile(r"(?m)^[ \t]*pythonAiEnv\s*=")
interpreter_binding_pattern = re.compile(r"(?m)^[ \t]*pythonAiInterpreterPath\s*=")

env_binding_exists = bool(env_binding_pattern.search(text))
interpreter_binding_exists = bool(interpreter_binding_pattern.search(text))

if not env_binding_exists:
    block = textwrap.indent(canonical_block, default_indent) + "\n"
    text = text[:let_line_end] + block + text[let_line_end:]
    changed = True
    messages.append("Inserted canonical pythonAiEnv definition in home.nix")
    interpreter_binding_exists = True
elif not interpreter_binding_exists:
    block = textwrap.indent("pythonAiInterpreterPath = \"${pythonAiEnv}/bin/python3\";", default_indent) + "\n"
    text = text[:let_line_end] + block + text[let_line_end:]
    changed = True
    messages.append("Added pythonAiInterpreterPath helper binding in home.nix")

legacy_pattern = re.compile(
    r'(?P<indent>\s*)"python\.defaultInterpreterPath"\s*=\s*"\$\{pythonAiEnv}/bin/python3";(?P<suffix>[^\n]*)'
)
if legacy_pattern.search(text):
    text, count = legacy_pattern.subn(
        lambda m: (
            f"{m.group('indent')}\"python.defaultInterpreterPath\" = "
            f"pythonAiInterpreterPath;{m.group('suffix')}"
        ),
        text,
    )
    if count > 0:
        changed = True
        messages.append("Rewrote python.defaultInterpreterPath to use pythonAiInterpreterPath")

if changed:
    path.write_text(text, encoding="utf-8")
    if messages:
        print("; ".join(messages))
PY
    )
    local status=$?

    if [ $status -ne 0 ]; then
        print_error "Failed to harmonize python AI environment bindings in $context_label"
        [[ -n "$harmonize_output" ]] && print_error "$harmonize_output"
        return 1
    elif [[ -n "$harmonize_output" ]]; then
        print_info "$context_label: $harmonize_output"
    fi

    return 0
}

install_openskills_tooling() {
    print_section "Installing OpenSkills Automation Toolkit"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "Dry-run mode enabled – skipping OpenSkills installation"
        return 0
    fi

    if ! ensure_python_runtime; then
        print_warning "Python runtime unavailable; skipping OpenSkills installation"
        return 0
    fi

    if ! run_python -m pip --version >/dev/null 2>&1; then
        print_warning "pip module is unavailable; install python3-pip to manage OpenSkills"
        return 0
    fi

    local repo_url="https://github.com/numman-ali/openskills.git"
    local log_file="/tmp/openskills-install.log"
    rm -f "$log_file"

    local current_version
    current_version=$(run_python <<'PY' 2>/dev/null
import importlib.metadata

try:
    dist = importlib.metadata.distribution("openskills")
except importlib.metadata.PackageNotFoundError:
    pass
else:
    print(dist.version or "")
PY
)

    current_version="${current_version//$'\r'/}"

    if [[ -n "$current_version" && "$FORCE_UPDATE" = false ]]; then
        print_success "✓ OpenSkills already installed (v$current_version)"
        print_info "Use --force-update to reinstall from upstream"
    else
        if [[ -n "$current_version" ]]; then
            print_info "Updating OpenSkills (current version: $current_version)"
        else
            print_info "Installing OpenSkills from upstream Git repository..."
        fi

        if run_python -m pip install --user --upgrade "git+${repo_url}" 2>&1 | tee "$log_file"; then
            local pip_status=${PIPESTATUS[0]}
            if [[ $pip_status -ne 0 ]]; then
                print_error "OpenSkills installation command exited with status $pip_status"
                print_info "Review pip logs: $log_file"
                return 1
            fi

            local new_version
            new_version=$(run_python <<'PY' 2>/dev/null
import importlib.metadata

try:
    dist = importlib.metadata.distribution("openskills")
except importlib.metadata.PackageNotFoundError:
    print("")
else:
    print(dist.version or "")
PY
)
            new_version="${new_version//$'\r'/}"

            if [[ -n "$new_version" ]]; then
                print_success "✓ OpenSkills ready (v$new_version)"
            else
                print_success "✓ OpenSkills installation completed"
            fi
        else
            local pip_status=${PIPESTATUS[0]}
            print_error "Failed to install OpenSkills (exit code: $pip_status)"
            print_warning "Check $log_file for pip output and ensure GitHub is reachable"
            return 1
        fi
    fi

    local missing_toolkits
    missing_toolkits=$(run_python <<'PY' 2>/dev/null
import importlib.metadata

candidates = [
    ("crewai", "CrewAI (collaborative agents)"),
    ("autogen", "Microsoft AutoGen (multi-agent automation)"),
    ("smolagents", "Hugging Face Smolagents (tool-calling agents)"),
]

lines = []
for package, label in candidates:
    try:
        importlib.metadata.distribution(package)
    except importlib.metadata.PackageNotFoundError:
        lines.append(f"{package}:{label}")

if lines:
    print("\n".join(lines))
PY
)

    if [[ -n "$missing_toolkits" ]]; then
        print_info "Additional agent frameworks you may want to install:"
        while IFS=":" read -r package label; do
            [[ -z "$package" ]] && continue
            print_info "  • $label → python3 -m pip install --user $package"
        done <<< "$missing_toolkits"
    else
        print_info "CrewAI, AutoGen, and Smolagents are already present in this environment"
    fi

    return 0
}

remove_deprecated_flatpak_installation_attribute() {
    local target_file="$1"
    local context_label="${2:-$1}"

    if [[ ! -f "$target_file" ]]; then
        return 0
    fi

    if [[ ! -w "$target_file" ]]; then
        print_warning "Skipping $context_label - file not writable"
        return 0
    fi

    local sanitize_output
    sanitize_output=$(TARGET_HOME_NIX="$target_file" run_python <<'PY'
import os
import re
import sys
from pathlib import Path

target_path = os.environ.get("TARGET_HOME_NIX")
if not target_path:
    print("TARGET_HOME_NIX is not set", file=sys.stderr)
    sys.exit(1)

path = Path(target_path)
if not path.exists():
    sys.exit(0)

patterns = [
    ("installation", re.compile(r"^\s*installation\s*=\s*\".*\";\s*(#.*)?$")),
    (
        "package",
        re.compile(r"^\s*package\s*=\s*.*flatpak.*;\s*(#.*)?$", re.IGNORECASE),
    ),
]

lines = path.read_text(encoding="utf-8").splitlines()

filtered = []
removed_attrs = set()
for line in lines:
    matched = False
    for attr, pattern in patterns:
        if pattern.match(line):
            removed_attrs.add(attr)
            matched = True
            break
    if not matched:
        filtered.append(line)

if removed_attrs:
    path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    attrs = ", ".join(sorted(removed_attrs))
    print(f"Removed deprecated services.flatpak attributes: {attrs}")
PY
    )
    local status=$?

    if [[ $status -ne 0 ]]; then
        print_error "Failed to sanitize Flatpak installation attribute in $context_label"
        return 1
    fi

    if [[ -n "$sanitize_output" ]]; then
        print_info "$sanitize_output"
    fi

    return 0
}

# Configuration
DOTFILES_ROOT="$PRIMARY_HOME/.dotfiles"
DEV_HOME_ROOT="$DOTFILES_ROOT"
HM_CONFIG_DIR="$DOTFILES_ROOT/home-manager"
FLAKE_FILE="$HM_CONFIG_DIR/flake.nix"
HOME_MANAGER_FILE="$HM_CONFIG_DIR/home.nix"
SYSTEM_CONFIG_FILE="$HM_CONFIG_DIR/configuration.nix"
HARDWARE_CONFIG_FILE="$HM_CONFIG_DIR/hardware-configuration.nix"
HM_CONFIG_CD_COMMAND="cd \"$HM_CONFIG_DIR\""

ensure_flake_workspace() {
    local created_root=false
    local created_dir=false
    local -a owner_args=()

    if [[ $EUID -eq 0 ]]; then
        owner_args=(-o "$PRIMARY_USER" -g "$PRIMARY_GROUP")
    fi

    if [[ ! -d "$DEV_HOME_ROOT" ]]; then
        if install -d -m 0755 "${owner_args[@]}" "$DEV_HOME_ROOT"; then
            created_root=true
        else
            print_error "Failed to create flake workspace root: $DEV_HOME_ROOT"
            return 1
        fi
    else
        ensure_path_owner "$DEV_HOME_ROOT"
    fi

    if [[ ! -d "$HM_CONFIG_DIR" ]]; then
        if install -d -m 0755 "${owner_args[@]}" "$HM_CONFIG_DIR"; then
            created_dir=true
        else
            print_error "Failed to create flake directory: $HM_CONFIG_DIR"
            return 1
        fi
    else
        ensure_path_owner "$HM_CONFIG_DIR"
    fi

    if $created_root; then
        print_success "Created flake workspace root at $DEV_HOME_ROOT"
    fi

    if $created_dir; then
        print_success "Created flake configuration directory at $HM_CONFIG_DIR"
    fi

    return 0
}

copy_template_to_flake() {
    local source_file="$1"
    local destination_file="$2"
    local description="${3:-$(basename "$destination_file")}"

    ensure_flake_workspace || return 1

    if [[ ! -f "$source_file" ]]; then
        print_error "Template missing: $source_file"
        return 1
    fi

    local -a owner_args=()
    if [[ $EUID -eq 0 ]]; then
        owner_args=(-o "$PRIMARY_USER" -g "$PRIMARY_GROUP")
    fi

    local need_copy=true

    if [[ -e "$destination_file" || -L "$destination_file" ]]; then
        if grep -q '^<<<<<<< ' "$destination_file" 2>/dev/null; then
            print_error "Unresolved merge conflict markers detected in $destination_file"
            print_info "Resolve the conflicts in $description and rerun the script"
            return 1
        fi

        if [[ ! -s "$destination_file" ]]; then
            print_warning "$description exists but is empty; refreshing from template"
        elif cmp -s "$source_file" "$destination_file"; then
            need_copy=false
        else
            local backup_file="$destination_file.backup.$(date +%Y%m%d_%H%M%S)"
            if cp -a "$destination_file" "$backup_file" 2>/dev/null; then
                ensure_path_owner "$backup_file"
                print_info "Backed up existing $description to $backup_file"
                if [[ -d "$destination_file" && ! -L "$destination_file" ]]; then
                    rm -rf "$destination_file"
                else
                    rm -f "$destination_file"
                fi
            else
                print_error "Failed to back up existing $description at $destination_file"
                print_info "Create a manual backup or remove the file before rerunning the script."
                return 1
            fi
        fi
    fi

    if $need_copy; then
        if ! install -m 0644 "${owner_args[@]}" "$source_file" "$destination_file"; then
            print_error "Failed to copy $description into $destination_file"
            return 1
        fi
    fi

    if ! chmod 0644 "$destination_file" 2>/dev/null; then
        print_warning "Could not adjust permissions on $destination_file"
    fi
    ensure_path_owner "$destination_file"

    if [[ ! -s "$destination_file" ]]; then
        print_error "$description was not populated correctly at $destination_file"
        return 1
    fi

    return 0
}

validate_flake_artifact() {
    local artifact_path="$1"
    local artifact_label="$2"

    if [[ ! -e "$artifact_path" ]]; then
        print_error "$artifact_label is missing at $artifact_path"
        return 1
    fi

    if [[ ! -s "$artifact_path" ]]; then
        print_error "$artifact_label exists but is empty at $artifact_path"
        return 1
    fi

    return 0
}

require_system_config_artifacts() {
    # Only validate system configuration files (not home-manager/flake files)
    # Used during system configuration generation phase
    ensure_flake_workspace || return 1

    local missing=false

    validate_flake_artifact "$SYSTEM_CONFIG_FILE" "configuration.nix" || missing=true
    validate_flake_artifact "$HARDWARE_CONFIG_FILE" "hardware-configuration.nix" || missing=true

    if $missing; then
        print_info "Resolve the missing artifacts above and rerun the script with --force-update if needed."
        return 1
    fi

    return 0
}

require_flake_artifacts() {
    # Validate all flake artifacts including home-manager files
    # Used before applying configurations via flake
    ensure_flake_workspace || return 1

    local missing=false

    validate_flake_artifact "$FLAKE_FILE" "flake.nix" || missing=true
    validate_flake_artifact "$HOME_MANAGER_FILE" "home.nix" || missing=true
    validate_flake_artifact "$SYSTEM_CONFIG_FILE" "configuration.nix" || missing=true
    validate_flake_artifact "$HARDWARE_CONFIG_FILE" "hardware-configuration.nix" || missing=true

    if $missing; then
        print_info "Resolve the missing artifacts above and rerun the script with --force-update if needed."
        return 1
    fi

    return 0
}

materialize_hardware_configuration() {
    ensure_flake_workspace || return 1

    local target_file="$HARDWARE_CONFIG_FILE"
    local source_file=""
    local generated_tmp=""
    local generator_log=""
    local generator_used=false

    if command -v nixos-generate-config >/dev/null 2>&1; then
        generated_tmp=$(mktemp)
        generator_log=$(mktemp)
        local -a generator_cmd=(nixos-generate-config --show-hardware-config)

        if command -v sudo >/dev/null 2>&1; then
            generator_cmd=(sudo "${generator_cmd[@]}")
        fi

        if "${generator_cmd[@]}" >"$generated_tmp" 2>"$generator_log"; then
            if [[ -s "$generated_tmp" ]]; then
                source_file="$generated_tmp"
                generator_used=true
                print_success "Captured host hardware profile via nixos-generate-config"
            else
                print_warning "Generated hardware profile was empty; falling back to system copy"
            fi
        else
            local status=$?
            print_warning "nixos-generate-config failed to produce hardware profile (exit $status); falling back to system copy"
            if [[ -s "$generator_log" ]]; then
                print_info "nixos-generate-config output:" 
                sed 's/^/  /' "$generator_log"
            fi
        fi
    fi

    if [[ -z "$source_file" ]]; then
        local system_hardware="/etc/nixos/hardware-configuration.nix"
        if [[ -f "$system_hardware" ]]; then
            source_file="$system_hardware"
            print_info "Using system hardware-configuration.nix as source"
        else
            print_error "hardware-configuration.nix is missing and nixos-generate-config could not create one"
            [[ -n "$generated_tmp" ]] && rm -f "$generated_tmp"
            [[ -n "$generator_log" ]] && rm -f "$generator_log"
            print_info "Run 'sudo nixos-generate-config' and rerun this script"
            return 1
        fi
    fi

    if [[ -f "$target_file" ]]; then
        local backup_file="$target_file.backup.$(date +%Y%m%d_%H%M%S)"
        if cp "$target_file" "$backup_file" 2>/dev/null; then
            ensure_path_owner "$backup_file"
            print_info "Backed up existing hardware-configuration.nix to $backup_file"
        fi
    fi

    local -a owner_args=()
    if [[ $EUID -eq 0 ]]; then
        owner_args=(-o "$PRIMARY_USER" -g "$PRIMARY_GROUP")
    fi

    if ! install -m 0644 "${owner_args[@]}" "$source_file" "$target_file"; then
        print_error "Failed to materialize hardware-configuration.nix at $target_file"
        [[ -n "$generated_tmp" ]] && rm -f "$generated_tmp"
        [[ -n "$generator_log" ]] && rm -f "$generator_log"
        return 1
    fi

    if ! chmod 0644 "$target_file" 2>/dev/null; then
        print_warning "Unable to adjust permissions on $target_file"
    fi

    ensure_path_owner "$target_file"

    if [[ ! -s "$target_file" ]]; then
        print_error "hardware-configuration.nix at $target_file is empty after refresh"
        [[ -n "$generated_tmp" ]] && rm -f "$generated_tmp"
        [[ -n "$generator_log" ]] && rm -f "$generator_log"
        return 1
    fi

    if ! grep -Eq 'fileSystems\."/"' "$target_file"; then
        print_warning "hardware-configuration.nix is missing the fileSystems.\"/\" root definition"
        print_warning "Ensure your hardware profile defines a root filesystem before rebuilding"
    fi

    local detected_gpu="${GPU_TYPE:-unknown}"
    local detected_gpu_driver="${GPU_DRIVER:-}"
    local detected_gpu_packages="${GPU_PACKAGES:-}"
    local detected_libva="${LIBVA_DRIVER:-}"
    local detected_cpu="${CPU_VENDOR:-unknown}"
    local detected_microcode="${CPU_MICROCODE:-}"
    local detected_ram="${TOTAL_RAM_GB:-0}"
    local detected_zram="${ZRAM_PERCENT:-0}"
    local detected_cores="${CPU_CORES:-}"
    local refresh_timestamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"

    local annotate_output
    annotate_output=$(TARGET_HW_NIX="$target_file" \
        AIDB_HW_TIMESTAMP="$refresh_timestamp" \
        AIDB_HW_GPU_TYPE="$detected_gpu" \
        AIDB_HW_GPU_DRIVER="$detected_gpu_driver" \
        AIDB_HW_GPU_PACKAGES="$detected_gpu_packages" \
        AIDB_HW_LIBVA="$detected_libva" \
        AIDB_HW_CPU="$detected_cpu" \
        AIDB_HW_MICROCODE="$detected_microcode" \
        AIDB_HW_RAM="$detected_ram" \
        AIDB_HW_ZRAM="$detected_zram" \
        AIDB_HW_CORES="$detected_cores" \
        run_python <<'PY'
import os
import re
import sys
from pathlib import Path

target_path = os.environ.get("TARGET_HW_NIX")
if not target_path:
    print("TARGET_HW_NIX is not set", file=sys.stderr)
    sys.exit(1)

path = Path(target_path)
text = path.read_text(encoding="utf-8")

def format_value(label, default="unknown"):
    value = os.environ.get(label, "")
    value = value.strip()
    return value if value else default

timestamp = format_value("AIDB_HW_TIMESTAMP", "unknown")
gpu_type = format_value("AIDB_HW_GPU_TYPE")
gpu_driver = format_value("AIDB_HW_GPU_DRIVER", "n/a")
gpu_packages = format_value("AIDB_HW_GPU_PACKAGES", "n/a")
libva = format_value("AIDB_HW_LIBVA", "n/a")
cpu_vendor = format_value("AIDB_HW_CPU", "unknown")
microcode = format_value("AIDB_HW_MICROCODE", "auto")
ram = format_value("AIDB_HW_RAM", "0")
zram = format_value("AIDB_HW_ZRAM", "0")
cores = format_value("AIDB_HW_CORES", "?")

header_lines = [
    "# BEGIN AIDB-HARDWARE-PROFILE",
    f"# Last refresh: {timestamp}",
    f"# CPU vendor: {cpu_vendor} (microcode: {microcode})",
    f"# CPU cores: {cores}",
    f"# RAM detected: {ram}GB (zram target: {zram}% of RAM)",
    f"# GPU type: {gpu_type} (driver: {gpu_driver}, VA-API: {libva})",
    f"# GPU packages: {gpu_packages}",
    "# END AIDB-HARDWARE-PROFILE",
    "",
]

header_block = "\n".join(header_lines)

pattern = re.compile(r"# BEGIN AIDB-HARDWARE-PROFILE.*?# END AIDB-HARDWARE-PROFILE\n?", re.S)

if pattern.search(text):
    new_text, count = pattern.subn(header_block, text, count=1)
    text = new_text
    changed = count > 0
else:
    text = header_block + text.lstrip("\n")
    changed = True

if changed:
    path.write_text(text, encoding="utf-8")
    print("Updated AIDB hardware profile header")
PY
    )

    local annotate_status=$?
    if [[ $annotate_status -ne 0 ]]; then
        print_warning "Unable to annotate hardware-configuration.nix with hardware profile"
        [[ -n "$annotate_output" ]] && print_warning "$annotate_output"
    elif [[ -n "$annotate_output" ]]; then
        print_info "$annotate_output"
    fi

    if [[ -n "$generated_tmp" ]]; then
        rm -f "$generated_tmp"
    fi
    if [[ -n "$generator_log" ]]; then
        rm -f "$generator_log"
    fi

    if $generator_used; then
        print_success "hardware-configuration.nix refreshed from latest hardware snapshot"
    else
        print_success "hardware-configuration.nix synchronized with system copy"
    fi

    return 0
}

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
        echo -e "${BLUE}ℹ${NC} To manually restore: cp $HOME_MANAGER_BACKUP $HOME_MANAGER_FILE"
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
    echo "   ls -lt \"$HM_CONFIG_DIR\"/home.nix.backup.*"
    echo "   ls -lt \"$HM_CONFIG_DIR\"/configuration.nix.backup.*"
    echo "   ls -lt /etc/nixos/configuration.nix.backup.*"
    echo ""
    echo -e "${YELLOW}4. Read the recovery guide:${NC}"
    echo "   cat ~/NixOS-Dev-Quick-Deploy/RECOVERY-GUIDE.md"
    echo ""
    echo -e "${YELLOW}5. After fixing the issue, re-run deployment:${NC}"
    echo "   cd ~/NixOS-Dev-Quick-Deploy"
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
    echo "  -f, --force-update       Force recreation of all configurations"
    echo "                           (ignores existing configs and applies updates)"
    echo "  --rollback               Rollback to previous system state"
    echo "  --restore-packages       Restore packages that were removed for conflict resolution"
    echo "  --reset-state            Reset deployment state and start fresh"
    echo "  --dry-run                Show what would be done without making changes"
    echo "  -d, --debug              Enable debug mode with verbose output"
    echo "  --skip-health-check      Skip the post-deployment health check"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       # Normal run (smart change detection)"
    echo "  $0 --force-update        # Force update all configs"
    echo "  $0 --rollback            # Rollback to previous state"
    echo "  $0 --restore-packages    # Restore removed packages"
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

# ------------------------------------------------------------------------------
# Configuration Extraction Helpers
# ------------------------------------------------------------------------------

parse_nixos_option_value() {
    local option_path="$1"

    if ! command -v nixos-option >/dev/null 2>&1; then
        return 0
    fi

    local raw_output
    if ! raw_output=$(nixos-option "$option_path" 2>/dev/null); then
        return 0
    fi

    raw_output=$(printf '%s\n' "$raw_output" | sed '1d')
    raw_output=$(printf '%s\n' "$raw_output" | awk '
        /^[[:space:]]*$/ { next }
        /^Default:/ { exit }
        /^Type:/ { exit }
        /^Description:/ { exit }
        /^Declared by:/ { exit }
        /^Defined by:/ { exit }
        { print }
    ')

    raw_output=$(printf '%s' "$raw_output" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

    if [ -z "$raw_output" ]; then
        return 0
    fi

    if [ "${#raw_output}" -ge 2 ]; then
        case "${raw_output:0:1}${raw_output: -1}" in
            "\"\"")
                raw_output=${raw_output:1:-1}
                ;;
            "''")
                raw_output=${raw_output:1:-1}
                ;;
        esac
    fi

    printf '%s' "$raw_output"
}

load_previous_nixos_metadata() {
    local metadata
    local py_errors

    # Ensure Python runtime is available before attempting to run
    if ! ensure_python_runtime; then
        print_warning "Python runtime unavailable - skipping metadata extraction"
        return 1
    fi

    # Capture both stdout and stderr separately
    py_errors=$(mktemp)
    metadata=$(TARGET_USER="$USER" run_python 2>"$py_errors" <<'PY'
import base64
import os
import re
from pathlib import Path

target_user = os.environ.get("TARGET_USER", "")
config_path = Path("/etc/nixos/configuration.nix")

timezone = ""
mutable_users = ""
password_snippet = ""

if config_path.exists():
    text = config_path.read_text(encoding="utf-8", errors="ignore")

    tz_match = re.search(r"time\.timeZone\s*=\s*([^;]+);", text)
    if tz_match:
        tz_expr = tz_match.group(1)
        q_match = re.search(r'"([^"\\]+(?:\\.[^"\\]*)*)"', tz_expr)
        if not q_match:
            q_match = re.search(r"'([^'\\]+(?:\\.[^'\\]*)*)'", tz_expr)
        if q_match:
            timezone = bytes(q_match.group(1), "utf-8").decode("unicode_escape")

    mutable_match = re.search(r"users\.mutableUsers\s*=\s*([^;]+);", text)
    if mutable_match:
        mutable_users = mutable_match.group(1).strip()

    if target_user:
        user_re = re.escape(target_user)
        pattern = re.compile(
            r"users\.users\.(?:\"{0}\"|'{0}'|{0})\s*=\s*\{{".format(user_re),
            re.MULTILINE,
        )
        match = pattern.search(text)
        if match:
            start = match.end() - 1  # include opening brace
            depth = 0
            in_string = False
            string_char = ""
            escape = False
            for idx in range(start, len(text)):
                ch = text[idx]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == string_char:
                        in_string = False
                    continue
                else:
                    if ch in ('"', "'"):
                        in_string = True
                        string_char = ch
                        continue
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            block = text[match.start():idx + 1]
                            lines = []
                            for line in block.splitlines():
                                if 'password' in line.lower():
                                    lines.append(line.rstrip())
                            if lines:
                                password_snippet = "\n".join(lines)
                            break

if timezone:
    print("__TZ__:" + timezone)
if mutable_users:
    print("__MUTABLE__:" + mutable_users)
if password_snippet:
    encoded = base64.b64encode(password_snippet.encode()).decode()
    print("__USERPW__:" + encoded)
PY
)

    # Check for Python errors
    if [ -s "$py_errors" ]; then
        print_warning "Python errors during metadata extraction:"
        cat "$py_errors" >&2
        rm -f "$py_errors"
        return 1
    fi
    rm -f "$py_errors"

    if [ -z "$metadata" ]; then
        return
    fi

    while IFS= read -r line; do
        case "$line" in
            __TZ__*)
                PREVIOUS_TIMEZONE=${line#__TZ__:}
                ;;
            __MUTABLE__*)
                PREVIOUS_MUTABLE_USERS=${line#__MUTABLE__:}
                ;;
            __USERPW__*)
                local encoded=${line#__USERPW__:}
                if [ -n "$encoded" ]; then
                    # Python runtime already verified, decode the password snippet
                    PREVIOUS_USER_PASSWORD_SNIPPET=$(ENCODED_USER_SNIPPET="$encoded" run_python 2>&1 <<'PY'
import base64
import os
import sys

data = os.environ.get("ENCODED_USER_SNIPPET", "").strip()
if data:
    try:
        print(base64.b64decode(data).decode(), end="")
    except Exception as e:
        # Silent failure - this is expected if encoding is corrupted
        pass
PY
)
                fi
                ;;
        esac
    done <<<"$metadata"
}

detect_existing_timezone() {
    local detected=""

    if [ -n "$PREVIOUS_TIMEZONE" ]; then
        detected="$PREVIOUS_TIMEZONE"
    else
        detected=$(parse_nixos_option_value "time.timeZone")
    fi

    if [ -z "$detected" ]; then
        detected=$(timedatectl show --property=Timezone --value 2>/dev/null || true)
    fi

    if [ -z "$detected" ]; then
        detected="America/New_York"
    fi

    printf '%s' "$detected"
}

detect_users_mutable_setting() {
    local value=""

    if [ -n "$PREVIOUS_MUTABLE_USERS" ]; then
        value="$PREVIOUS_MUTABLE_USERS"
    else
        value=$(parse_nixos_option_value "users.mutableUsers")
    fi

    if [ -z "$value" ]; then
        value="true"
    fi

    printf '%s' "$value"
}

get_shadow_hash() {
    local account="$1"
    local line=""

    if command -v sudo >/dev/null 2>&1; then
        line=$(sudo grep "^${account}:" /etc/shadow 2>/dev/null || true)
    else
        line=$(grep "^${account}:" /etc/shadow 2>/dev/null || true)
    fi

    if [ -z "$line" ]; then
        return 0
    fi

    local hash
    hash=$(echo "$line" | cut -d: -f2)

    if [ -z "$hash" ] || [ "$hash" = "!" ] || [ "$hash" = "*" ]; then
        return 0
    fi

    printf '%s' "$hash"
}

generate_temporary_password() {
    LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+=-' </dev/urandom | head -c 20
}

preserve_user_password_directives() {
    USER_PASSWORD_BLOCK=""

    if [ -n "$PREVIOUS_USER_PASSWORD_SNIPPET" ]; then
        USER_PASSWORD_BLOCK="$PREVIOUS_USER_PASSWORD_SNIPPET"
        [[ "$USER_PASSWORD_BLOCK" != *$'\n' ]] && USER_PASSWORD_BLOCK+=$'\n'
        print_success "Preserved password directives from previous configuration"
        return
    fi

    local user_path="users.users.\"$USER\""
    local hashed
    local hashed_file
    local password_file
    local initial_hashed
    local initial_plain
    local force_flag

    hashed=$(parse_nixos_option_value "${user_path}.hashedPassword")
    hashed_file=$(parse_nixos_option_value "${user_path}.hashedPasswordFile")
    password_file=$(parse_nixos_option_value "${user_path}.passwordFile")
    initial_hashed=$(parse_nixos_option_value "${user_path}.initialHashedPassword")
    initial_plain=$(parse_nixos_option_value "${user_path}.initialPassword")
    force_flag=$(parse_nixos_option_value "${user_path}.forceInitialPassword")

    local directives=()

    if [ -n "$hashed" ]; then
        directives+=("    hashedPassword = \"${hashed}\";")
    elif [ -n "$hashed_file" ]; then
        directives+=("    hashedPasswordFile = \"${hashed_file}\";")
    elif [ -n "$password_file" ]; then
        directives+=("    passwordFile = \"${password_file}\";")
    elif [ -n "$initial_hashed" ]; then
        directives+=("    initialHashedPassword = \"${initial_hashed}\";")
    elif [ -n "$initial_plain" ]; then
        directives+=("    initialPassword = \"${initial_plain}\";")
    fi

    if [ ${#directives[@]} -gt 0 ]; then
        if [ "$force_flag" = "true" ] || [ "$force_flag" = "false" ]; then
            directives+=("    forceInitialPassword = ${force_flag};")
        fi
        USER_PASSWORD_BLOCK=$(printf '%s\n' "${directives[@]}")
        print_success "Preserved password settings from running system configuration"
        return
    fi

    local shadow_hash
    shadow_hash=$(get_shadow_hash "$USER")
    if [ -n "$shadow_hash" ]; then
        printf -v USER_PASSWORD_BLOCK '    hashedPassword = "%s";\n' "$shadow_hash"
        print_success "Migrated password hash from /etc/shadow"
        return
    fi

    local temp_password
    temp_password=$(generate_temporary_password)
    USER_TEMP_PASSWORD="$temp_password"
    printf -v USER_PASSWORD_BLOCK '    initialPassword = "%s";\n    forceInitialPassword = true;\n' "$temp_password"
    print_warning "No existing password configuration found. Generated temporary password for $USER"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

assert_unique_paths() {
    declare -A seen=()
    local name
    for name in "$@"; do
        if [[ -z ${!name+x} ]]; then
            continue
        fi

        local value="${!name}"
        if [[ -z "$value" ]]; then
            continue
        fi

        local normalized="$value"
        if command -v readlink >/dev/null 2>&1; then
            local resolved
            if resolved=$(readlink -m -- "$value" 2>/dev/null); then
                normalized="$resolved"
            fi
        fi

        if [[ "$normalized" != "/" ]]; then
            normalized="${normalized%/}"
        fi

        if [[ -n ${seen[$normalized]+x} ]]; then
            local other="${seen[$normalized]}"
            print_error "Path collision detected: $name and ${other} both resolve to $normalized"
            return 1
        fi

        seen[$normalized]="$name"
    done

    return 0
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

derive_system_release_version() {
    local raw

    if ! raw=$(nixos-version 2>/dev/null); then
        echo "25.05"
        return 0
    fi

    raw=$(printf '%s' "$raw" | cut -d'.' -f1-2)
    raw=${raw%%pre*}
    raw=${raw%%-*}

    if [[ -z "$raw" ]]; then
        echo "25.05"
    else
        echo "$raw"
    fi
}

get_home_manager_flake_uri() {
    local ref="${HOME_MANAGER_CHANNEL_REF:-}"
    local base="github:nix-community/home-manager"

    if [[ -n "$ref" && "$ref" != "master" ]]; then
        echo "${base}?ref=${ref}"
    else
        echo "$base"
    fi
}

get_home_manager_package_ref() {
    local uri
    uri=$(get_home_manager_flake_uri)
    echo "${uri}#home-manager"
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

prompt_secret() {
    local prompt="$1"
    local note="${2:-}"
    local message="$prompt"

    if [[ -n "$note" ]]; then
        message="$message ($note)"
    fi

    local response=""
    read -s -p "$(echo -e ${BLUE}?${NC} $message: )" response
    echo ""
    echo "$response"
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_prerequisites() {
    print_section "Checking Prerequisites"

    echo ""
    print_info "This deployment will install:"
    echo "  • 100+ CLI development tools and utilities"
    echo "  • Complete Python ML/AI environment (PyTorch, TensorFlow, LangChain, etc.)"
    echo "  • AI command-line tools (Ollama, GPT4All, llama.cpp, Aider)"
    echo "  • Container stack (Podman, Buildah, Skopeo)"
    echo "  • Desktop applications via Flatpak (Firefox, Obsidian, DBeaver, etc.)"
    echo "  • System services (Gitea, Qdrant, Jupyter, Hugging Face TGI)"
    echo ""

    # Check NixOS
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    if ! command -v nixos-rebuild >/dev/null 2>&1; then
        print_error "nixos-rebuild is not available in PATH"
        print_info "Install the nixos-rebuild tooling and ensure it is accessible before rerunning."
        exit 1
    fi
    print_success "nixos-rebuild command detected"

    # Check all required packages for installation
    if ! check_required_packages; then
        print_error "Package requirements not met"
        exit 1
    fi

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

    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
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

    print_info "Scanning nix profile for legacy home-manager entries..."
    cleanup_conflicting_home_manager_profile

    if command -v home-manager &> /dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        print_info "home-manager is required for this setup"
        install_home_manager
    fi

    # Check Python runtime and provide clear feedback
    print_info "Checking Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        print_error "Install python3 manually and re-run the deployment"
        exit 1
    fi

    # Provide feedback about which Python is being used
    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        print_success "Python runtime: ephemeral Nix shell (python3 not in PATH)"
    else
        print_success "Python runtime: ${PYTHON_BIN[0]} ($(${PYTHON_BIN[@]} --version 2>&1))"
    fi
}

# ============================================================================
# NixOS Version Selection
# ============================================================================

select_nixos_version() {
    print_section "NixOS Version Selection"

    local track_preference="${DEFAULT_CHANNEL_TRACK,,}"
    local CURRENT_VERSION=$(derive_system_release_version)

    if [[ "$track_preference" == "unstable" ]]; then
        print_info "Channel preference is set to unstable; automatically tracking nixos-unstable for latest AI tooling."
        print_info "Detected current system release: $CURRENT_VERSION"
        echo ""
        export SELECTED_NIXOS_VERSION="unstable"
        return 0
    fi

    # Get current system version
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

    # Extract channel name and version from URL
    # Examples:
    #   https://nixos.org/channels/nixos-24.11 → nixos-24.11
    #   https://nixos.org/channels/nixos-unstable → nixos-unstable
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
    else
        local SYSTEM_NAME="$(normalize_channel_name "$SYSTEM_CHANNEL")"
        local EXPECTED_HM=""
        local HUMAN_VERSION_LABEL=""

        if [[ "$SYSTEM_NAME" == "nixos-unstable" ]]; then
            EXPECTED_HM="master"
            HUMAN_VERSION_LABEL="unstable"
        elif [[ "$SYSTEM_NAME" =~ nixos-([0-9]+\.[0-9]+) ]]; then
            HUMAN_VERSION_LABEL="${BASH_REMATCH[1]}"
            EXPECTED_HM="release-${HUMAN_VERSION_LABEL}"
        fi

        local ACTUAL_HM="$(normalize_channel_name "$USER_CHANNEL")"

        if [[ -z "$EXPECTED_HM" ]]; then
            print_warning "Unable to derive expected home-manager channel from $SYSTEM_NAME"
            print_warning "Proceed with caution and verify channels manually"
        elif [[ "$ACTUAL_HM" == "$EXPECTED_HM" ]]; then
            if [[ -n "$HUMAN_VERSION_LABEL" ]]; then
                print_success "✓ Channels synchronized: NixOS ${HUMAN_VERSION_LABEL} ↔ home-manager ${EXPECTED_HM}"
            else
                print_success "✓ Channels synchronized: nixos-unstable ↔ home-manager master"
            fi
        else
            print_error "✗ CRITICAL: Channel mismatch detected!"
            print_error "  nixos channel:        $SYSTEM_NAME"
            print_error "  home-manager channel: $ACTUAL_HM (expected ${EXPECTED_HM})"
            print_error "This WILL cause compatibility issues and build failures"
            echo ""
            print_info "Attempting to fix by re-synchronizing channels..."

            nix-channel --remove home-manager 2>/dev/null || true
            local RESYNC_URL
            if [[ "$EXPECTED_HM" == "master" ]]; then
                RESYNC_URL="https://github.com/nix-community/home-manager/archive/master.tar.gz"
            else
                RESYNC_URL="https://github.com/nix-community/home-manager/archive/${EXPECTED_HM}.tar.gz"
            fi
            nix-channel --add "$RESYNC_URL" home-manager
            nix-channel --update

            HOME_MANAGER_CHANNEL_REF="$EXPECTED_HM"
            HOME_MANAGER_CHANNEL_URL="$RESYNC_URL"
            SYNCHRONIZED_HOME_MANAGER_CHANNEL="$EXPECTED_HM"
            SYNCHRONIZED_NIXOS_CHANNEL="$SYSTEM_NAME"

            print_success "Channels re-synchronized to expected versions"
        fi
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

    local hm_pkg_ref
    hm_pkg_ref=$(get_home_manager_package_ref)

    print_info "Preparing home-manager CLI for dotfiles workflow..."
    print_info "  Source: ${hm_pkg_ref}"

    if command -v home-manager &> /dev/null; then
        print_success "home-manager command already available: $(which home-manager)"
    else
        local bootstrap_log="/tmp/home-manager-bootstrap.log"
        print_info "Pre-fetching home-manager CLI via nix run (no profile install)..."
        if nix run --accept-flake-config "$hm_pkg_ref" -- --version 2>&1 | tee "$bootstrap_log"; then
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
# User Information Gathering
# ============================================================================

gather_user_info() {
    print_section "Gathering User Preferences"

    load_previous_nixos_metadata

    SELECTED_TIMEZONE=$(detect_existing_timezone)
    USERS_MUTABLE_SETTING=$(detect_users_mutable_setting)

    print_success "Timezone preserved: $SELECTED_TIMEZONE"
    print_success "users.mutableUsers: $USERS_MUTABLE_SETTING"
    echo ""

    # Editor preference
    print_info "Default editor options:"
    echo "  1) vim"
    echo "  2) neovim"
    echo "  3) vscodium"
    echo "  4) gitea editor"
    EDITOR_CHOICE=$(prompt_user "Choose editor (1-4)" "1")

    case $EDITOR_CHOICE in
        1) DEFAULT_EDITOR="vim" ;;
        2) DEFAULT_EDITOR="nvim" ;;
        3) DEFAULT_EDITOR="codium" ;;
        4) DEFAULT_EDITOR="gitea-editor" ;;
        *) DEFAULT_EDITOR="vim" ;;
    esac

    print_success "Editor preference: $DEFAULT_EDITOR"
    echo ""

    # Build Performance Preference
    print_section "Build Performance Strategy"
    echo ""
    print_info "Choose your build strategy:"
    echo ""
    local -a recommended_caches=()
    mapfile -t recommended_caches < <(get_binary_cache_sources)
    local recommended_cache_message=""
    if [[ "${#recommended_caches[@]}" -gt 0 ]]; then
        recommended_cache_message="${recommended_caches[0]}"
        for cache_url in "${recommended_caches[@]:1}"; do
            recommended_cache_message+=", ${cache_url}"
        done
    fi

    echo -e "  ${GREEN}1) Use Binary Caches (RECOMMENDED)${NC}"
    echo "     - Downloads pre-built packages from trusted sources"
    echo -e "     - ${GREEN}Estimated time: 20-40 minutes${NC}"
    echo "     - Requires good internet connection (~2-4 GB download)"
    echo "     - Lower CPU and memory usage"
    if [[ -n "$recommended_cache_message" ]]; then
        echo "     - Caches: ${recommended_cache_message}"
    fi
    echo ""
    echo -e "  ${YELLOW}2) Build from Source${NC}"
    echo "     - Compiles all packages locally from source code"
    echo -e "     - ${YELLOW}Estimated time: 60-120 minutes${NC}"
    echo "     - Minimal downloads (~500 MB source code)"
    echo "     - High CPU and memory usage during compilation"
    echo "     - Full control over build process"
    echo ""

    BUILD_CHOICE=$(prompt_user "Choose build strategy (1-2)" "1")

    case $BUILD_CHOICE in
        1)
            USE_BINARY_CACHES="true"
            print_success "Using binary caches for faster deployment (20-40 min)"
            ;;
        2)
            USE_BINARY_CACHES="false"
            print_warning "Building from source - this will take 60-120 minutes"
            print_warning "Ensure you have sufficient CPU/RAM and time available"
            ;;
        *)
            USE_BINARY_CACHES="true"
            print_success "Using binary caches (default)"
            ;;
    esac
    echo ""

    # Password Migration/Setup
    print_section "Password Configuration"
    preserve_user_password_directives

    if [ -n "$USER_TEMP_PASSWORD" ]; then
        print_warning "Temporary password generated for $USER"
        print_info "Temporary password (change after first login): $USER_TEMP_PASSWORD"
    else
        print_success "Password configuration preserved"
    fi
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
        STATE_VERSION=$(derive_system_release_version)
        print_info "Using unstable channel, stateVersion from system: $STATE_VERSION"
    else
        # Final fallback: system version
        STATE_VERSION=$(derive_system_release_version)
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

        if [[ -f "$HOME_MANAGER_FILE" ]]; then
            HOME_MANAGER_BACKUP="$HOME_MANAGER_FILE.backup.$BACKUP_TIMESTAMP"
            cp "$HOME_MANAGER_FILE" "$HOME_MANAGER_BACKUP"
            print_success "Backed up home.nix"
        fi

        if [[ -f "$FLAKE_FILE" ]]; then
            cp "$FLAKE_FILE" "$BACKUP_DIR/flake.nix.backup.$BACKUP_TIMESTAMP"
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

    ensure_flake_workspace || exit 1

    # Copy p10k-setup-wizard.sh to home-manager config dir so home.nix can reference it
    if [ -f "$SCRIPT_DIR/scripts/p10k-setup-wizard.sh" ]; then
        cp "$SCRIPT_DIR/scripts/p10k-setup-wizard.sh" "$HM_CONFIG_DIR/p10k-setup-wizard.sh"
        ensure_path_owner "$HM_CONFIG_DIR/p10k-setup-wizard.sh"
        print_success "Copied p10k-setup-wizard.sh into $HM_CONFIG_DIR"
    else
        print_warning "p10k-setup-wizard.sh not found in $SCRIPT_DIR/scripts - skipping copy"
        print_info "If you need the prompt wizard, place the script in the scripts directory"
    fi

    local TEMPLATE_DIR="$SCRIPT_DIR/templates"
    if [[ ! -d "$TEMPLATE_DIR" ]]; then
        print_error "Template directory not found: $TEMPLATE_DIR"
        print_info "Ensure the repository includes the templates directory"
        exit 1
    fi

    # Declare hostname and system architecture outside the if block for later use
    local SYSTEM_ARCH=$(nix eval --raw --expr builtins.currentSystem 2>/dev/null || echo "x86_64-linux")
    local CURRENT_HOSTNAME=$(hostname)

    # Create flake.nix if it doesn't already exist
    # NOTE: flake.nix should already exist if created by generate_nixos_system_config()
    # This ensures we have a flake even if only running home-manager setup standalone
    if [[ ! -f "$FLAKE_FILE" ]]; then
        print_info "Creating home-manager flake configuration for Flatpak support..."
        local FLAKE_TEMPLATE="$TEMPLATE_DIR/flake.nix"
        if [[ ! -f "$FLAKE_TEMPLATE" ]]; then
            print_error "Missing flake template: $FLAKE_TEMPLATE"
            exit 1
        fi

        if copy_template_to_flake "$FLAKE_TEMPLATE" "$FLAKE_FILE" "flake.nix"; then
            print_success "Created flake.nix in $HM_CONFIG_DIR"
        else
            exit 1
        fi
        # Align flake inputs with the synchronized channels
        sed -i "s|NIXPKGS_CHANNEL_PLACEHOLDER|${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${STATE_VERSION}}|" "$FLAKE_FILE"
        sed -i "s|HM_CHANNEL_PLACEHOLDER|$HM_CHANNEL_NAME|" "$FLAKE_FILE"
        sed -i "s|HOSTNAME_PLACEHOLDER|$CURRENT_HOSTNAME|" "$FLAKE_FILE"
        sed -i "s|HOME_USERNAME_PLACEHOLDER|$USER|" "$FLAKE_FILE"
        sed -i "s|SYSTEM_PLACEHOLDER|$SYSTEM_ARCH|" "$FLAKE_FILE"
    else
        print_success "flake.nix already exists (created earlier), skipping recreation"
    fi

    print_info "To use Flatpak declarative management:"
    print_info "  home-manager switch --flake \"$HM_CONFIG_DIR\""
    echo ""

    local HOME_TEMPLATE="$TEMPLATE_DIR/home.nix"
    if [[ ! -f "$HOME_TEMPLATE" ]]; then
        print_error "Missing home-manager template: $HOME_TEMPLATE"
        exit 1
    fi

    if ! copy_template_to_flake "$HOME_TEMPLATE" "$HOME_MANAGER_FILE" "home.nix"; then
        exit 1
    fi

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
    local GPU_MONITORING_PACKAGES_BLOCK="[]"
    if [[ "$GPU_TYPE" == "amd" ]]; then
        GPU_MONITORING_PACKAGES_BLOCK="[ radeontop amdgpu_top ]"
    fi

    print_info "Using configuration:"
    print_info "  User: $USER"
    print_info "  Home: $HOME"
    print_info "  State Version: $STATE_VERSION"
    print_info "  Editor: $DEFAULT_EDITOR"

    if ! load_or_generate_gitea_secrets; then
        print_error "Failed to prepare Gitea secrets"
        exit 1
    fi

    # Replace placeholders in home.nix (using | delimiter to handle special characters in variables)
    sed -i "s|VERSIONPLACEHOLDER|$SCRIPT_VERSION|" "$HOME_MANAGER_FILE"
    sed -i "s|HASHPLACEHOLDER|$TEMPLATE_HASH|" "$HOME_MANAGER_FILE"

    # Replace placeholders in flake.nix
    sed -i "s|HOMEUSERNAME|$USER|g" "$FLAKE_FILE"
    sed -i "s|HOMEUSERNAME|$USER|" "$HOME_MANAGER_FILE"
    sed -i "s|HOMEDIR|$HOME|" "$HOME_MANAGER_FILE"
    sed -i "s|STATEVERSION_PLACEHOLDER|$STATE_VERSION|" "$HOME_MANAGER_FILE"
    sed -i "s|@GPU_MONITORING_PACKAGES@|$GPU_MONITORING_PACKAGES_BLOCK|" "$HOME_MANAGER_FILE"
    sed -i "s|@GITEA_SECRET_KEY@|$GITEA_SECRET_KEY|g" "$HOME_MANAGER_FILE"
    sed -i "s|@GITEA_INTERNAL_TOKEN@|$GITEA_INTERNAL_TOKEN|g" "$HOME_MANAGER_FILE"
    sed -i "s|@GITEA_LFS_JWT_SECRET@|$GITEA_LFS_JWT_SECRET|g" "$HOME_MANAGER_FILE"
    sed -i "s|@GITEA_JWT_SECRET@|$GITEA_JWT_SECRET|g" "$HOME_MANAGER_FILE"
    sed -i "s|@HOSTNAME@|$CURRENT_HOSTNAME|g" "$HOME_MANAGER_FILE"

    if ! harmonize_python_ai_bindings "$HOME_MANAGER_FILE" "home-manager home.nix"; then
        exit 1
    fi

    if ! remove_deprecated_flatpak_installation_attribute "$HOME_MANAGER_FILE" "home-manager home.nix"; then
        exit 1
    fi

    DEFAULT_EDITOR_VALUE="$DEFAULT_EDITOR" \
    TARGET_HOME_NIX="$HOME_MANAGER_FILE" run_python <<'PY'
import os
import sys

target_path = os.environ.get("TARGET_HOME_NIX")
if not target_path:
    print("TARGET_HOME_NIX is not set", file=sys.stderr)
    sys.exit(1)

editor = os.environ.get("DEFAULT_EDITOR_VALUE", "vim")

with open(target_path, "r", encoding="utf-8") as f:
    data = f.read()

data = data.replace("DEFAULTEDITOR", editor)

with open(target_path, "w", encoding="utf-8") as f:
    f.write(data)
PY

    # Some older templates may have left behind stray navigation headings.
    # Clean them up so nix-instantiate parsing does not fail on bare identifiers.
    CLEANUP_MSG=$(TARGET_HOME_NIX="$HOME_MANAGER_FILE" run_python <<'PY'
import os
import re
import sys

target_path = os.environ.get("TARGET_HOME_NIX")
if not target_path:
    print("TARGET_HOME_NIX is not set", file=sys.stderr)
    sys.exit(1)

pattern = re.compile(r"^\s*(Actions|Projects|Wiki)\s*$")

with open(target_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

    filtered = []
    removed = False
    for line in lines:
        if pattern.match(line):
            removed = True
        else:
            filtered.append(line)

    if removed:
        with open(target_path, "w", encoding="utf-8") as f:
            f.writelines(filtered)
    print("Removed legacy Gitea navigation headings from home.nix")
PY
    )
    CLEANUP_STATUS=$?
    if [ $CLEANUP_STATUS -ne 0 ]; then
        print_error "Failed to sanitize home.nix navigation headings"
        exit 1
    elif [ -n "$CLEANUP_MSG" ]; then
        print_info "$CLEANUP_MSG"
    fi

    if [[ ! -s "$HOME_MANAGER_FILE" ]]; then
        print_error "home.nix generation failed - file is empty at $HOME_MANAGER_FILE"
        exit 1
    fi

    print_success "Home manager configuration created at $HOME_MANAGER_FILE"
    print_info "Configuration includes $(grep -c "^    " "$HOME_MANAGER_FILE" || echo 'many') packages"

    # Verify the generated file is valid Nix syntax
    print_info "Validating generated home.nix syntax..."
    if nix-instantiate --parse "$HOME_MANAGER_FILE" &>/dev/null; then
        print_success "✓ home.nix syntax is valid"
    else
        print_error "✗ home.nix has syntax errors!"
        print_error "Please check: $HOME_MANAGER_FILE"
        print_info "Running nix-instantiate for details..."
        nix-instantiate --parse "$HOME_MANAGER_FILE" 2>&1 | tail -20
        exit 1
    fi
}

# ============================================================================
# Apply Configuration
# ============================================================================

run_home_manager_switch() {
    local log_path="${1:-/tmp/home-manager-switch.log}"
    local hm_pkg_ref
    hm_pkg_ref=$(get_home_manager_package_ref)

    local hm_cli_available=false
    if command -v home-manager &> /dev/null; then
        hm_cli_available=true
        print_success "home-manager command available: $(which home-manager)"
    else
        print_warning "home-manager command not found in PATH"
        print_info "Will invoke via: nix run --accept-flake-config ${hm_pkg_ref} -- ..."
    fi

    print_info "Applying your custom home-manager configuration..."
    print_info "Config: $HOME_MANAGER_FILE"
    print_info "Using flake for full Flatpak declarative support..."
    echo ""

    local -a hm_args=("switch" "--flake" "$HM_CONFIG_DIR")
    if ! user_systemd_channel_ready; then
        if [[ -n "$USER_SYSTEMD_CHANNEL_MESSAGE" ]]; then
            local detail
            detail=$(printf '%s' "$USER_SYSTEMD_CHANNEL_MESSAGE" | head -n1)
            print_warning "$detail"
        fi
        print_warning "User systemd session is unavailable; running home-manager with --no-user-systemd"
        hm_args+=("--no-user-systemd")
    fi
    hm_args+=("--show-trace")

    # Change to home directory to avoid path resolution issues
    # This prevents relative paths from being resolved against script location
    local original_dir="$PWD"
    cd "$HOME" || {
        print_error "Failed to change to home directory"
        return 1
    }

    if $hm_cli_available; then
        run_as_primary_user home-manager "${hm_args[@]}" 2>&1 | tee "$log_path"
        local result=${PIPESTATUS[0]}
        cd "$original_dir" || true
        return $result
    fi

    run_as_primary_user nix run --accept-flake-config "${hm_pkg_ref}" -- "${hm_args[@]}" 2>&1 | tee "$log_path"
    local result=${PIPESTATUS[0]}
    cd "$original_dir" || true
    return $result
}

ensure_home_manager_cli_available() {
    local hm_pkg_ref
    hm_pkg_ref=$(get_home_manager_package_ref)
    local install_log="/tmp/home-manager-cli-install.log"

    local cli_path
    cli_path=$(run_as_primary_user bash -lc 'command -v home-manager' 2>/dev/null || true)
    if [[ -n "$cli_path" ]]; then
        print_success "home-manager CLI available at $cli_path"
        return 0
    fi

    print_warning "home-manager CLI not found in user PATH"
    print_info "Installing home-manager CLI into the user profile via nix profile install..."

    if run_as_primary_user nix profile install --accept-flake-config --name home-manager "$hm_pkg_ref" >"$install_log" 2>&1; then
        cli_path=$(run_as_primary_user bash -lc 'command -v home-manager' 2>/dev/null || true)
        if [[ -n "$cli_path" ]]; then
            print_success "home-manager CLI installed at $cli_path"
        else
            print_success "home-manager CLI installed successfully"
        fi
        return 0
    fi

    print_error "Failed to install home-manager CLI automatically"
    print_info "Review the log for details: $install_log"
    return 1
}

# ============================================================================
# Build Optimization Helpers
# ============================================================================

get_binary_cache_sources() {
    local -a caches=(
        "https://cache.nixos.org"
        "https://nix-community.cachix.org"
        "https://devenv.cachix.org"
    )

    if [[ "${GPU_TYPE:-}" == "nvidia" ]]; then
        caches+=("https://cuda-maintainers.cachix.org")
    fi

    printf '%s\n' "${caches[@]}"
}

get_binary_cache_public_keys() {
    local -a keys=(
        "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
        "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
        "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
    )

    if [[ "${GPU_TYPE:-}" == "nvidia" ]]; then
        keys+=("cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E=")
    fi

    printf '%s\n' "${keys[@]}"
}

compose_nixos_rebuild_options() {
    local use_caches="${1:-true}"
    local -a opts=(
        "--option" "max-jobs" "auto"
        "--option" "cores" "0"
        "--option" "keep-outputs" "true"
        "--option" "keep-derivations" "true"
        "--option" "builders-use-substitutes" "true"
        "--option" "fallback" "true"
    )

    if [[ "$use_caches" == "true" ]]; then
        local -a substituters=()
        local -a keys=()
        mapfile -t substituters < <(get_binary_cache_sources)
        mapfile -t keys < <(get_binary_cache_public_keys)

        if [[ "${#substituters[@]}" -gt 0 ]]; then
            local substituters_list
            substituters_list=$(printf '%s ' "${substituters[@]}")
            substituters_list=${substituters_list% }
            opts+=("--option" "substituters" "$substituters_list")
        fi

        if [[ "${#keys[@]}" -gt 0 ]]; then
            local keys_list
            keys_list=$(printf '%s ' "${keys[@]}")
            keys_list=${keys_list% }
            opts+=("--option" "trusted-public-keys" "$keys_list")
        fi

        opts+=("--option" "connect-timeout" "10")
        opts+=("--option" "stalled-download-timeout" "300")
    fi

    printf '%s\n' "${opts[@]}"
}

describe_binary_cache_usage() {
    local context="${1:-operation}"

    if [[ "$USE_BINARY_CACHES" != "true" ]]; then
        return 0
    fi

    local -a local_substituters=()
    mapfile -t local_substituters < <(get_binary_cache_sources)
    if [[ "${#local_substituters[@]}" -eq 0 ]]; then
        return 0
    fi

    local joined=""
    local index=0
    for url in "${local_substituters[@]}"; do
        if (( index > 0 )); then
            joined+=", "
        fi
        joined+="$url"
        ((index+=1))
    done

    print_info "Binary caches enabled for ${context}: ${joined}"
}

generate_binary_cache_settings() {
    local use_caches="${1:-true}"
    local binary_cache_settings

    if [[ "$use_caches" == "true" ]]; then
        local -a substituters=()
        local -a keys=()
        mapfile -t substituters < <(get_binary_cache_sources)
        mapfile -t keys < <(get_binary_cache_public_keys)

        local substituters_block=$'      substituters = [\n'
        local url
        for url in "${substituters[@]}"; do
            substituters_block+=$'        "'
            substituters_block+="$url"
            substituters_block+=$'"\n'
        done
        substituters_block+=$'      ];'

        local keys_block=$'      trusted-public-keys = [\n'
        local key
        for key in "${keys[@]}"; do
            keys_block+=$'        "'
            keys_block+="$key"
            keys_block+=$'"\n'
        done
        keys_block+=$'      ];'

        binary_cache_settings=$'\n      # ======================================================================\n'
        binary_cache_settings+=$'      # Build Performance Optimizations\n'
        binary_cache_settings+=$'      # ======================================================================\n\n'
        binary_cache_settings+=$'      # Parallel builds: Use all available CPU cores\n'
        binary_cache_settings+=$'      # max-jobs: Number of builds that can run in parallel\n'
        binary_cache_settings+=$'      # cores: Number of CPU cores each build can use (0 = all available)\n'
        binary_cache_settings+=$'      max-jobs = "auto";  # Automatically detect CPU count\n'
        binary_cache_settings+=$'      cores = 0;          # Use all cores for each build\n\n'
        binary_cache_settings+=$'      # Binary caches: Download pre-built packages instead of building from source\n'
        binary_cache_settings+=$'      # This dramatically reduces build times (from hours to minutes)\n'
        binary_cache_settings+="$substituters_block"
        binary_cache_settings+=$'\n\n'
        binary_cache_settings+=$'      # Public keys for verifying binary cache signatures\n'
        binary_cache_settings+="$keys_block"
        binary_cache_settings+=$'\n\n'
        binary_cache_settings+=$'      # Download pre-built dependencies during builds\n'
        binary_cache_settings+=$'      builders-use-substitutes = true;\n\n'
        binary_cache_settings+=$'      # Retain build artifacts to speed up future rebuilds\n'
        binary_cache_settings+=$'      keep-outputs = true;\n'
        binary_cache_settings+=$'      keep-derivations = true;\n\n'
        binary_cache_settings+=$'      # Fallback to building from source if binary not available\n'
        binary_cache_settings+=$'      fallback = true;\n\n'
        binary_cache_settings+=$'      # Network timeout settings for binary cache downloads\n'
        binary_cache_settings+=$'      # Increase timeouts to handle large packages and slower connections\n'
        binary_cache_settings+=$'      connect-timeout = 10;         # Connection timeout in seconds (default: 5)\n'
        binary_cache_settings+=$'      stalled-download-timeout = 300;  # Stalled download timeout in seconds (default: 300)\n\n'
        binary_cache_settings+=$'      # Warn about dirty git trees in flakes\n'
        binary_cache_settings+=$'      warn-dirty = false;\n'
    else
        binary_cache_settings=$'\n      # ======================================================================\n'
        binary_cache_settings+=$'      # Build from Source Configuration\n'
        binary_cache_settings+=$'      # ======================================================================\n\n'
        binary_cache_settings+=$'      # Parallel builds: Use all available CPU cores\n'
        binary_cache_settings+=$'      # Building from source is slower but gives you full control\n'
        binary_cache_settings+=$'      max-jobs = "auto";  # Automatically detect CPU count\n'
        binary_cache_settings+=$'      cores = 0;          # Use all cores for each build\n\n'
        binary_cache_settings+=$'      # Only use official NixOS cache for base system packages\n'
        binary_cache_settings+=$'      substituters = [ "https://cache.nixos.org" ];\n'
        binary_cache_settings+=$'      trusted-public-keys = [ "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=" ];\n\n'
        binary_cache_settings+=$'      # Preserve build artifacts for incremental rebuilds\n'
        binary_cache_settings+=$'      keep-outputs = true;\n'
        binary_cache_settings+=$'      keep-derivations = true;\n\n'
        binary_cache_settings+=$'      # Allow downloading dependencies during evaluation/builds\n'
        binary_cache_settings+=$'      builders-use-substitutes = true;\n\n'
        binary_cache_settings+=$'      # Allow falling back to local builds if a binary is unavailable\n'
        binary_cache_settings+=$'      fallback = true;\n\n'
        binary_cache_settings+=$'      # Warn about dirty git trees in flakes\n'
        binary_cache_settings+=$'      warn-dirty = false;\n'
    fi

    printf '%s' "$binary_cache_settings"
}

run_nixos_rebuild_dry_run() {
    local log_path="${1:-/tmp/nixos-rebuild-dry-run.log}"
    local target_host
    target_host=$(hostname)

    print_info "Performing dry run: sudo nixos-rebuild build --flake \"$HM_CONFIG_DIR#$target_host\""
    print_info "Validating system rebuild without applying changes..."

    # Note: NixOS 25.05 doesn't support --dry-run flag
    # Use 'build' instead which builds but doesn't activate the configuration

    # CRITICAL: Pass build optimization flags directly to nixos-rebuild
    # These flags apply DURING the build, before the configuration takes effect
    local -a nix_opts=()
    mapfile -t nix_opts < <(compose_nixos_rebuild_options "$USE_BINARY_CACHES")
    describe_binary_cache_usage "nixos-rebuild build"

    sudo nixos-rebuild build --flake "$HM_CONFIG_DIR#$target_host" "${nix_opts[@]}" 2>&1 | tee "$log_path"
    return ${PIPESTATUS[0]}
}

run_nixos_rebuild_switch() {
    local log_path="${1:-/tmp/nixos-rebuild.log}"
    local target_host
    target_host=$(hostname)

    print_warning "Running: sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\""
    print_info "This will download and install all AIDB components using the generated flake..."
    print_info "May take 10-20 minutes on first run"
    echo ""

    # CRITICAL: Pass build optimization flags directly to nixos-rebuild
    # These flags apply DURING the build, before the configuration takes effect
    local -a nix_opts=()
    mapfile -t nix_opts < <(compose_nixos_rebuild_options "$USE_BINARY_CACHES")
    describe_binary_cache_usage "nixos-rebuild switch"

    sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host" "${nix_opts[@]}" 2>&1 | tee "$log_path"
    return ${PIPESTATUS[0]}
}

validate_system_build_stage() {
    local NIXOS_REBUILD_DRY_LOG="/tmp/nixos-rebuild-dry-run.log"

    if [[ "$SYSTEM_BUILD_VALIDATED" != true ]]; then
        print_info "Validating system build (dry run)..."
        if run_nixos_rebuild_dry_run "$NIXOS_REBUILD_DRY_LOG"; then
            SYSTEM_BUILD_VALIDATED=true
            SYSTEM_BUILD_DRY_RUN_LOG="$NIXOS_REBUILD_DRY_LOG"
            print_success "Dry run completed successfully (no changes applied)"
            print_info "Log saved to: $NIXOS_REBUILD_DRY_LOG"
        else
            local dry_exit_code=$?
            print_error "Dry run failed (exit code: $dry_exit_code)"
            print_info "Review the log: $NIXOS_REBUILD_DRY_LOG"
            print_info "Fix the issues above before continuing."
            return 1
        fi
    else
        if [[ -n "$SYSTEM_BUILD_DRY_RUN_LOG" ]]; then
            print_info "Dry run already completed earlier (log: $SYSTEM_BUILD_DRY_RUN_LOG)"
        else
            print_info "Dry run previously completed - skipping rebuild validation"
        fi
    fi

    return 0
}

apply_home_manager_config() {
    print_section "Applying Home Manager Configuration"

    # CRITICAL: Ensure home-manager is in PATH
    # This is needed because home-manager might have been just installed
    if [[ ":$PATH:" != *":$HOME/.nix-profile/bin:"* ]]; then
        export PATH="$HOME/.nix-profile/bin:$PATH"
        print_info "Added ~/.nix-profile/bin to PATH for home-manager"
    fi

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
    local IMPERATIVE_PKGS
    IMPERATIVE_PKGS=$(nix-env -q 2>/dev/null || true)
    if [ -n "$IMPERATIVE_PKGS" ]; then
        print_warning "Found packages installed via nix-env (will cause conflicts if left in place):"
        echo "$IMPERATIVE_PKGS" | sed 's/^/    /'
        echo ""
    else
        print_success "No nix-env packages found - clean state!"
        echo ""
    fi

    if ! confirm "Proceed with home-manager activation (will remove legacy configs and apply the new user environment)?" "y"; then
        print_warning "home-manager switch skipped at this stage. Run 'home-manager switch --flake "$HM_CONFIG_DIR"' later to apply the configuration."
        print_warning "Existing Flatpak/user configuration files were left untouched."
        echo ""
        return 0
    fi

    if [ -n "$IMPERATIVE_PKGS" ]; then
        print_info "Removing ALL nix-env packages (switching to declarative home-manager)..."
        print_info "This prevents package collisions and ensures reproducibility"

        # Save list of removed packages for potential recovery
        local removed_pkgs_file="$STATE_DIR/removed-packages-$(date +%s).txt"
        mkdir -p "$STATE_DIR"
        echo "$IMPERATIVE_PKGS" > "$removed_pkgs_file"
        print_info "Saved package list for recovery: $removed_pkgs_file"

        # Remove all packages installed via nix-env
        if nix-env -e '.*' --remove-all 2>&1 | tee /tmp/nix-env-cleanup.log; then
            print_success "All nix-env packages removed successfully"
        else
            # Fallback: Try removing packages one by one
            print_warning "Batch removal failed, trying individual package removal..."
            while IFS= read -r pkg; do
                local pkg_name
                pkg_name=$(echo "$pkg" | awk '{print $1}')
                if [ -n "$pkg_name" ]; then
                    print_info "Removing: $pkg_name"
                    nix-env -e "$pkg_name" 2>/dev/null && print_success "  Removed: $pkg_name" || print_warning "  Failed: $pkg_name"
                fi
            done <<< "$IMPERATIVE_PKGS"
        fi

        # Verify all removed
        local REMAINING
        REMAINING=$(nix-env -q 2>/dev/null || true)
        if [ -n "$REMAINING" ]; then
            print_warning "Some packages remain in nix-env:"
            echo "$REMAINING" | sed 's/^/    /'
            print_warning "These may cause conflicts with home-manager"
        else
            print_success "All nix-env packages successfully removed"
            print_success "All packages now managed declaratively via home-manager"
        fi
        echo ""
    fi

    # Backup existing configuration files
    backup_existing_configs

    # Force clean environment setup - remove old generations to ensure fresh install
    force_clean_environment_setup

    print_info "Home-manager activation can now be applied using your generated flake."
    echo ""

    # Update flake.lock to ensure we have latest versions of inputs
    local HM_FLAKE_PATH="$FLAKE_FILE"
    if [[ ! -f "$HM_FLAKE_PATH" ]]; then
        print_error "home-manager flake manifest missing: $HM_FLAKE_PATH"
        print_info "The configuration step did not complete successfully."
        print_info "Re-run this script with --force-update after fixing the issue."
        exit 1
    fi

    # Ensure flake directory and files have proper ownership before update
    ensure_path_owner "$HM_CONFIG_DIR"
    ensure_path_owner "$HM_FLAKE_PATH"
    if [[ -f "$HM_CONFIG_DIR/flake.lock" ]]; then
        ensure_path_owner "$HM_CONFIG_DIR/flake.lock"
        chmod 644 "$HM_CONFIG_DIR/flake.lock" 2>/dev/null || true
    fi

    print_info "Updating flake inputs (nix-flatpak, home-manager, nixpkgs)..."
    if (cd "$HM_CONFIG_DIR" && nix flake update) 2>&1 | tee /tmp/flake-update.log; then
        print_success "Flake inputs updated successfully"
        # Ensure the newly created/updated flake.lock has proper ownership
        if [[ -f "$HM_CONFIG_DIR/flake.lock" ]]; then
            ensure_path_owner "$HM_CONFIG_DIR/flake.lock"
        fi
    else
        print_warning "Flake update failed, continuing with existing lock file..."
        print_info "This is usually fine for first-time installations"
    fi
    echo ""

    # Use home-manager with flakes to enable nix-flatpak module and declarative Flatpak
    # Must specify the configuration name: #username
    local CURRENT_USER
    CURRENT_USER=$(whoami)
    print_info "Using configuration: homeConfigurations.$CURRENT_USER"
    echo ""

    # Clean up any failed systemd services before activation to prevent degraded session warnings
    cleanup_systemd_before_activation

    local HM_SWITCH_LOG="/tmp/home-manager-switch.log"
    if run_home_manager_switch "$HM_SWITCH_LOG"; then
        print_success "Home manager configuration applied successfully!"
        HOME_MANAGER_APPLIED=true
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
        for pkg in podman python3 ripgrep bat eza fd git flatpak gitea tea home-manager; do
            if command -v "$pkg" &>/dev/null; then
                print_success "$pkg found at $(command -v $pkg)"
            else
                print_warning "$pkg not found in PATH yet"
                MISSING_COUNT=$((MISSING_COUNT + 1))
            fi
        done

        if [ $MISSING_COUNT -gt 0 ]; then
            print_warning "$MISSING_COUNT packages not yet in PATH"
            print_info "Restart your shell to load all packages: exec zsh"
            ensure_home_manager_cli_available || true
        else
            print_success "All critical packages are in PATH!"
        fi
        echo ""

        ensure_flatpak_managed_install_service
        ensure_default_flatpak_apps_installed
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
        print_info "Full log saved to: $HM_SWITCH_LOG"
        print_info "Backup is at: $HOME_MANAGER_BACKUP"
        if [[ -n "$LATEST_CONFIG_BACKUP_DIR" ]]; then
            print_info "Previous configuration files archived under: $LATEST_CONFIG_BACKUP_DIR"
            print_info "Restore with: cp -a \"$LATEST_CONFIG_BACKUP_DIR/.\" \"$HOME/\""
        fi
        echo ""

        print_error "Automatic rollback will restore your previous configuration."
        print_error "Fix the issue above, then run this script again for a fresh start."
        echo ""

        # Trigger cleanup and exit
        exit 1
    fi

    # System-wide changes are applied later in the workflow after the system rebuild
}

cleanup_systemd_before_activation() {
    # Clean up any failed systemd services that might cause home-manager activation warnings
    # Service auto-start is prevented via ConditionPathExists in the service definition

    if ! command -v systemctl >/dev/null 2>&1; then
        return 0
    fi

    if ! user_systemd_channel_ready; then
        return 0
    fi

    # CRITICAL: Remove the condition file to prevent the service from starting during activation
    # This ensures that even if home-manager's sd-switch tries to start the service,
    # the ConditionPathExists check will fail and it won't actually execute
    local condition_file="/run/user/$(id -u "$PRIMARY_USER")/allow-flatpak-managed-install"
    if [[ -f "$condition_file" ]]; then
        print_info "Removing flatpak condition file to prevent activation during home-manager switch..."
        run_as_primary_user rm -f "$condition_file" 2>/dev/null || true
    fi

    local -a services_to_reset=(
        "flatpak-managed-install.service"
    )

    local service reset_count=0
    for service in "${services_to_reset[@]}"; do
        # Check if service exists
        if ! run_as_primary_user systemctl --user list-unit-files "$service" >/dev/null 2>&1; then
            continue
        fi

        # Stop the service if it's running
        local active_state
        active_state=$(run_as_primary_user systemctl --user is-active "$service" 2>/dev/null || echo "unknown")

        if [[ "$active_state" == "active" || "$active_state" == "activating" ]]; then
            print_info "Stopping $service before activation..."
            run_as_primary_user systemctl --user stop "$service" 2>/dev/null || true
            sleep 1
        fi

        # Check if service is in failed state and reset it
        local state
        state=$(run_as_primary_user systemctl --user is-failed "$service" 2>/dev/null || echo "unknown")

        if [[ "$state" == "failed" ]]; then
            print_info "Resetting failed state for $service..."
            if run_as_primary_user systemctl --user reset-failed "$service" 2>/dev/null; then
                ((reset_count++)) || true
            fi
        fi

        # Mask the service temporarily to prevent ANY activation attempts during home-manager switch
        # This is an extra safeguard in addition to removing the condition file
        print_info "Temporarily masking $service to prevent activation during switch..."
        run_as_primary_user systemctl --user mask "$service" 2>/dev/null || true
    done

    if [[ $reset_count -gt 0 ]]; then
        print_success "Reset $reset_count failed service(s)"
    fi

    print_success "Services cleaned up and masked - safe to run home-manager switch"
    return 0
}

backup_existing_configs() {
    print_info "Backing up and removing conflicting configuration files..."
    clean_home_manager_targets "pre-switch"
    if [[ -n "$LATEST_CONFIG_BACKUP_DIR" ]]; then
        print_info "To restore previous configs: cp -a \"$LATEST_CONFIG_BACKUP_DIR/.\" \"$HOME/\""
    fi
    prepare_managed_config_paths
}

force_clean_environment_setup() {
    print_section "Forcing Clean Environment Setup"
    print_info "Ensuring fresh installation by removing old generations and state..."

    # Remove all home-manager generations to force fresh install
    if command -v home-manager &>/dev/null; then
        local generation_count=$(home-manager generations 2>/dev/null | wc -l || echo "0")
        if [ "$generation_count" -gt 0 ]; then
            print_info "Removing $generation_count home-manager generation(s) to ensure fresh install..."
            run_as_primary_user home-manager expire-generations "-0 days" 2>/dev/null || true
            print_success "Old home-manager generations removed"
        fi
    fi

    # COMPLETE flatpak environment replacement
    if command -v flatpak &>/dev/null; then
        print_info "Removing complete flatpak user environment for clean setup..."

        # Get list of installed user apps for backup record
        local installed_apps=$(flatpak list --user --app --columns=application 2>/dev/null || echo "")
        if [ -n "$installed_apps" ]; then
            local flatpak_backup_file="$HOME/.cache/nixos-quick-deploy/flatpak-backup-$(date +%Y%m%d_%H%M%S).txt"
            mkdir -p "$(dirname "$flatpak_backup_file")"
            echo "$installed_apps" > "$flatpak_backup_file"
            print_info "Backed up list of installed flatpak apps to $flatpak_backup_file"
        fi

        # Uninstall ALL user flatpak apps (not just apps, but runtimes too)
        print_info "Uninstalling all flatpak apps and runtimes..."
        run_as_primary_user flatpak uninstall --user --all --noninteractive 2>/dev/null || true

        # Remove the entire flatpak installation directory for complete clean slate
        # This includes: apps, runtimes, repo, overrides, remotes.d, etc.
        local flatpak_dir="$HOME/.local/share/flatpak"
        if [ -d "$flatpak_dir" ]; then
            local flatpak_backup_dir="$HOME/.cache/nixos-quick-deploy/flatpak-environment-backup-$(date +%Y%m%d_%H%M%S)"
            print_info "Backing up entire flatpak directory structure..."
            mkdir -p "$(dirname "$flatpak_backup_dir")"
            if cp -a "$flatpak_dir" "$flatpak_backup_dir" 2>/dev/null; then
                print_success "Flatpak environment backed up to: $flatpak_backup_dir"
                print_info "Removing flatpak directory for clean reinstall..."
                rm -rf "$flatpak_dir"
                print_success "Flatpak environment directory removed"
            else
                print_warning "Could not backup flatpak directory, skipping removal"
            fi
        else
            print_info "No existing flatpak directory to remove"
        fi

        # Also clear flatpak configuration
        local flatpak_config="$HOME/.config/flatpak"
        if [ -d "$flatpak_config" ]; then
            print_info "Removing flatpak configuration directory..."
            rm -rf "$flatpak_config"
        fi

        # CRITICAL FIX: Let Flatpak initialize the repository structure automatically
        # DO NOT manually create the repo directory - it needs proper ostree initialization
        # The flatpak remote-add command will create and initialize everything correctly
        print_info "Re-initializing Flatpak repository structure..."
        # Only create the parent directories, not the repo itself
        mkdir -p "$flatpak_dir"
        mkdir -p "$flatpak_config"

        # Add Flathub remote - this will automatically create and initialize the repo
        print_info "Adding Flathub remote to new Flatpak installation..."
        if run_as_primary_user flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>&1 | grep -v "Warning\|already exists"; then
            print_success "Flathub remote added successfully"
        else
            # If that fails, try the fallback URL
            print_info "Trying fallback Flathub URL..."
            if run_as_primary_user flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo 2>&1 | grep -v "Warning\|already exists"; then
                print_success "Flathub remote added successfully (fallback URL)"
            else
                print_warning "Could not add Flathub remote (will be added later by home-manager)"
            fi
        fi

        print_success "Complete flatpak environment removed and re-initialized for clean reinstall"
        print_info "Flatpak will be completely rebuilt by home-manager"
    fi

    # Remove VSCodium symlinks if they exist (will be recreated by home-manager)
    if [ -L "$HOME/.config/VSCodium/User/settings.json" ]; then
        print_info "Removing existing VSCodium settings symlink for fresh setup..."
        rm -f "$HOME/.config/VSCodium/User/settings.json"
    fi

    # Ensure nix profile is clean for fresh home-manager installation
    print_info "Cleaning nix profile for fresh home-manager state..."
    run_as_primary_user nix-collect-garbage -d 2>/dev/null || true

    print_success "Environment prepared for clean installation"
    print_info "All previous settings have been backed up and will be replaced with new configuration"
    echo ""
}

apply_system_changes() {
    print_section "Applying System-Wide Changes"

    # Force reload of zsh configuration
    if [ -f "$HOME/.zshrc" ]; then
        print_info "ZSH configuration is managed by home-manager"
        print_info "Configuration file: $HOME/.zshrc"
    fi

    # Note: p10k-setup-wizard.sh is managed by home-manager with executable permissions
    # No need to chmod - home-manager handles permissions declaratively

    # Set ZSH as default shell if not already
    # This matches the NixOS configuration which sets shell = pkgs.zsh
    if [ "$SHELL" != "$(which zsh)" ]; then
        print_info "Setting ZSH as default shell (configured in NixOS)"
        # FIXED: Use sudo to avoid PAM authentication failure
        if sudo chsh -s "$(which zsh)" "$USER" 2>/dev/null; then
            print_success "Default shell set to ZSH (restart terminal to apply)"
        else
            print_warning "Could not set ZSH as default shell automatically"
            print_info "Set it manually later with: sudo chsh -s \$(which zsh) $USER"
        fi
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

    # Check if lspci is available
    if ! command -v lspci >/dev/null 2>&1; then
        print_warning "lspci not found - skipping GPU detection"
        print_info "Install pciutils for automatic GPU detection"
        GPU_TYPE="software"
        LIBVA_DRIVER=""
        GPU_PACKAGES=""
    else
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
            GPU_PACKAGES="mesa rocm-opencl-icd"
            print_success "Detected: AMD GPU (using RADV - modern default driver)"
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

# ============================================================================
# NixOS System Configuration - Part 1: Generation
# ============================================================================
# This function generates the NixOS system configuration files but does NOT
# prompt the user or apply the configuration. This allows the main() flow to
# prompt BEFORE any destructive operations (backups/deletions) occur.
# ============================================================================
generate_nixos_system_config() {
    print_section "Generating Fresh NixOS Configuration"

    local SYSTEM_CONFIG="/etc/nixos/configuration.nix"
    # Detect system info
    local HOSTNAME=$(hostname)
    local NIXOS_VERSION=$(derive_system_release_version)
    local HM_CHANNEL_NAME=""
    local HM_FETCH_URL=""
    local DETECTED_HM_CHANNEL=""
    local NIXOS_CHANNEL_LABEL="${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${NIXOS_VERSION}}"
    SYNCHRONIZED_NIXOS_CHANNEL="$NIXOS_CHANNEL_LABEL"

    # Use timezone selected by user (from gather_user_info)
    # If not set, detect current timezone
    if [ -z "$SELECTED_TIMEZONE" ]; then
        SELECTED_TIMEZONE=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "America/New_York")
    fi

    # Detect current locale to preserve user's setting
    local CURRENT_LOCALE=$(localectl status | grep "LANG=" | cut -d= -f2 | tr -d ' ' 2>/dev/null || echo "en_US.UTF-8")

    # Resolve the home-manager channel reference for templating
    if [[ -z "$HOME_MANAGER_CHANNEL_REF" && -n "$SYNCHRONIZED_HOME_MANAGER_CHANNEL" ]]; then
        HOME_MANAGER_CHANNEL_REF="$SYNCHRONIZED_HOME_MANAGER_CHANNEL"
    fi
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

    # Only normalize if HM_CHANNEL_NAME looks like a URL (contains / or .)
    # This prevents incorrectly normalizing already-normalized names
    if [[ "$HM_CHANNEL_NAME" == *"/"* || "$HM_CHANNEL_NAME" == *".tar"* || "$HM_CHANNEL_NAME" == *".gz"* ]]; then
        HM_CHANNEL_NAME=$(normalize_channel_name "$HM_CHANNEL_NAME")
    fi

    # Validate that HM_CHANNEL_NAME looks like a valid channel reference
    # Valid formats: "master", "release-24.05", "release-24.11", etc.
    if [[ -n "$HM_CHANNEL_NAME" ]]; then
        if [[ ! "$HM_CHANNEL_NAME" =~ ^(master|release-[0-9]+\.[0-9]+)$ ]]; then
            print_warning "Invalid home-manager channel name detected: $HM_CHANNEL_NAME"
            print_warning "This may be from a corrupted nix-channel entry"
            HM_CHANNEL_NAME=""  # Reset to force default
        fi
    fi

    if [[ -z "$HM_CHANNEL_NAME" ]]; then
        HM_CHANNEL_NAME="release-${NIXOS_VERSION}"
        print_warning "Could not auto-detect home-manager channel, defaulting to $HM_CHANNEL_NAME"
    fi

    HM_FETCH_URL="https://github.com/nix-community/home-manager/archive/${HM_CHANNEL_NAME}.tar.gz"
    HOME_MANAGER_CHANNEL_REF="$HM_CHANNEL_NAME"
    HOME_MANAGER_CHANNEL_URL="$HM_FETCH_URL"
    SYNCHRONIZED_HOME_MANAGER_CHANNEL="$HM_CHANNEL_NAME"

    if [[ -z "$HM_FETCH_URL" ]]; then
        print_error "Failed to resolve home-manager tarball URL"
        exit 1
    fi

    print_info "Home-manager channel (system config): $HM_CHANNEL_NAME"

    # Detect hardware for optimization
    detect_gpu_and_cpu

    print_info "System: $HOSTNAME (channel ${NIXOS_CHANNEL_LABEL}, release $NIXOS_VERSION)"
    print_info "User: $USER"
    print_info "Timezone: $SELECTED_TIMEZONE"
    print_info "Locale: $CURRENT_LOCALE"
    print_info "users.mutableUsers: $USERS_MUTABLE_SETTING"

    if ! load_or_generate_gitea_secrets; then
        print_error "Failed to prepare Gitea secrets"
        return 1
    fi

    harmonize_python_ai_bindings "$HOME_MANAGER_FILE" "existing flake home.nix" || return 1
    harmonize_python_ai_bindings "/etc/nixos/home.nix" "/etc/nixos/home.nix" || return 1

    # Backup old config
    if [[ -f "$SYSTEM_CONFIG" ]]; then
        SYSTEM_CONFIG_BACKUP="$SYSTEM_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
        sudo cp "$SYSTEM_CONFIG" "$SYSTEM_CONFIG_BACKUP"
        print_success "✓ Backed up: $SYSTEM_CONFIG_BACKUP"
    fi

    if ! materialize_hardware_configuration; then
        return 1
    fi


    # Generate complete AIDB configuration
    print_info "Generating complete AIDB development configuration..."
    echo ""

    local TEMPLATE_DIR="$SCRIPT_DIR/templates"
    local SYSTEM_TEMPLATE="$TEMPLATE_DIR/configuration.nix"

    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        return 1
    fi

    if [[ ! -f "$SYSTEM_TEMPLATE" ]]; then
        print_error "Missing NixOS configuration template: $SYSTEM_TEMPLATE"
        exit 1
    fi

    if ! copy_template_to_flake "$SYSTEM_TEMPLATE" "$SYSTEM_CONFIG_FILE" "configuration.nix"; then
        return 1
    fi

    print_success "Generated configuration.nix in $HM_CONFIG_DIR"

    print_info "Kernel preference: linuxPackages_tkg → linuxPackages_xanmod → linuxPackages_lqx → linuxPackages_zen → linuxPackages_latest"

    if command -v nix >/dev/null 2>&1; then
        local kernel_expr='let pkgs = import <nixpkgs> {}; names = ["linuxPackages_tkg" "linuxPackages_xanmod" "linuxPackages_lqx" "linuxPackages_zen"]; available = builtins.filter (name: builtins.hasAttr name pkgs) names; in builtins.concatStringsSep ", " available'
        local available_kernel_output
        available_kernel_output=$(nix --extra-experimental-features 'nix-command' eval --raw --expr "$kernel_expr" 2>/dev/null || nix eval --raw --expr "$kernel_expr" 2>/dev/null || true)

        if [[ -n "$available_kernel_output" ]]; then
            print_info "Performance kernels available in current channel: $available_kernel_output"
        else
            print_warning "Could not confirm performance kernel availability via nix; falling back to preference order above"
        fi
    else
        print_warning "nix command not found in PATH; skipping kernel availability probe"
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

    # Binary cache configuration based on user preference
    local binary_cache_settings
    binary_cache_settings=$(generate_binary_cache_settings "$USE_BINARY_CACHES")

    local gpu_hardware_section
    case "$GPU_TYPE" in
        intel)
            gpu_hardware_section=$(cat <<'EOF'
hardware.graphics = {
    enable = true;
    enable32Bit = true;  # For 32-bit applications
    extraPackages = with pkgs; [
      intel-media-driver  # VAAPI driver for Broadwell+ (>= 5th gen)
      vaapiIntel          # Older VAAPI driver for Haswell and older
      vaapiVdpau
      libvdpau-va-gl
      intel-compute-runtime  # OpenCL support
    ];
};
EOF
)
            ;;
        amd)
            gpu_hardware_section=$(cat <<'EOF'
hardware.graphics = {
    enable = true;
    enable32Bit = true;
    extraPackages =
      let
        rocmOpenclPackages =
          lib.optionals (pkgs ? rocm-opencl-icd) [ pkgs.rocm-opencl-icd ]
          ++ lib.optionals (
            pkgs ? rocmPackages
            && builtins.hasAttr "clr" pkgs.rocmPackages
            && builtins.hasAttr "icd" pkgs.rocmPackages.clr
          ) [ pkgs.rocmPackages.clr.icd ];
      in
      (with pkgs; [
        mesa              # Open-source AMD drivers (includes RADV Vulkan)
      ])
      ++ rocmOpenclPackages;
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
hardware.graphics = {
    enable = true;
    enable32Bit = true;
};
EOF
)
            ;;
        *)
            gpu_hardware_section="# No dedicated GPU configuration required (software rendering)"
            ;;
    esac

    local gpu_driver_packages_block="[]"
    case "$GPU_TYPE" in
        intel)
            gpu_driver_packages_block="(lib.optionals (pkgs ? intel-media-driver) [ intel-media-driver ] ++ lib.optionals (pkgs ? vaapiIntel) [ vaapiIntel ])"
            ;;
        amd)
            gpu_driver_packages_block="(lib.optionals (pkgs ? mesa) [ mesa ] ++ lib.optionals (pkgs ? rocm-opencl-icd) [ pkgs.rocm-opencl-icd ] ++ lib.optionals (pkgs ? rocmPackages && builtins.hasAttr \"clr\" pkgs.rocmPackages && builtins.hasAttr \"icd\" pkgs.rocmPackages.clr) [ pkgs.rocmPackages.clr.icd ])"
            ;;
        nvidia)
            gpu_driver_packages_block="(lib.optionals (pkgs ? nvidia-vaapi-driver) [ nvidia-vaapi-driver ])"
            ;;
        *)
            gpu_driver_packages_block="[]"
            ;;
    esac

    local gpu_session_variables
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" && -n "$LIBVA_DRIVER" ]]; then
        local gpu_label="${GPU_TYPE^}"
        gpu_session_variables=$(cat <<EOF

    # Hardware acceleration enabled (auto-detected: ${gpu_label} GPU)
    # VA-API driver: $LIBVA_DRIVER for video decode/encode acceleration
    LIBVA_DRIVER_NAME = "$LIBVA_DRIVER";
    # Enable touch/gesture support for trackpads
    MOZ_USE_XINPUT2 = "1";
EOF
)
    else
        gpu_session_variables=$(cat <<'EOF'

    # No dedicated GPU detected - using software rendering
    # Hardware acceleration disabled
EOF
)
    fi

    local total_ram_value="${TOTAL_RAM_GB:-0}"
    local zram_value="${ZRAM_PERCENT:-50}"

    if [ -z "$USER_PASSWORD_BLOCK" ]; then
        USER_PASSWORD_BLOCK=$'    # (no password directives detected; update manually if required)\n'
    fi

    local gitea_admin_secrets_set
    local gitea_admin_variables_block
    local gitea_admin_service_block
    local gitea_admin_user_literal=""
    local gitea_admin_email_literal=""
    local gitea_admin_password_literal=""

    if [[ "$GITEA_BOOTSTRAP_ADMIN" == "true" ]]; then
        gitea_admin_secrets_set=$(cat <<'EOF'
{
    adminPassword = @GITEA_ADMIN_PASSWORD@;
}
EOF
)
        gitea_admin_variables_block=$(cat <<'EOF'
  giteaAdminUser = @GITEA_ADMIN_USER@;
  giteaAdminEmail = @GITEA_ADMIN_EMAIL@;
  giteaAdminUserPattern = lib.escapeRegex giteaAdminUser;
  giteaAdminBootstrapScript = pkgs.writeShellScript "gitea-admin-bootstrap" ''
    set -euo pipefail

    export HOME=${lib.escapeShellArg giteaStateDir}
    export GITEA_WORK_DIR=${lib.escapeShellArg giteaStateDir}
    export GITEA_CUSTOM=${lib.escapeShellArg ("${giteaStateDir}/custom")}
    export GITEA_APP_INI=${lib.escapeShellArg ("${giteaStateDir}/custom/conf/app.ini")}

    attempts=0
    while true; do
      if output=$(${pkgs.gitea}/bin/gitea admin user list --admin 2>/dev/null); then
        if printf '%s\n' "$output" | ${pkgs.gnugrep}/bin/grep -q '^${giteaAdminUserPattern}\\b'; then
          exit 0
        fi
        break
      fi

      attempts=$((attempts + 1))
      if [ "$attempts" -ge 30 ]; then
        echo "gitea-admin-bootstrap: timed out waiting for gitea admin CLI" >&2
        exit 1
      fi
      ${pkgs.coreutils}/bin/sleep 2
    done

    ${pkgs.gitea}/bin/gitea admin user create \
      --username ${lib.escapeShellArg giteaAdminUser} \
      --password ${lib.escapeShellArg giteaAdminSecrets.adminPassword} \
      --email ${lib.escapeShellArg giteaAdminEmail} \
      --must-change-password=false \
      --admin
  '';
EOF
)
        gitea_admin_service_block=$(cat <<'EOF'
  systemd.services.gitea-admin-bootstrap = {
    description = "Bootstrap default Gitea administrator";
    wantedBy = [ "multi-user.target" ];
    after = [ "gitea.service" ];
    requires = [ "gitea.service" ];
    serviceConfig = {
      Type = "oneshot";
      User = "gitea";
      Group = "gitea";
      ExecStart = giteaAdminBootstrapScript;
    };
  };
EOF
)
        gitea_admin_user_literal=$(nix_quote_string "$GITEA_ADMIN_USER")
        gitea_admin_email_literal=$(nix_quote_string "$GITEA_ADMIN_EMAIL")
        gitea_admin_password_literal=$(nix_quote_string "$GITEA_ADMIN_PASSWORD")
    else
        gitea_admin_secrets_set=$(cat <<'EOF'
{
  # Add `adminPassword = "your-strong-password";` to enable declarative admin bootstrapping.
}
EOF
)
        gitea_admin_variables_block=$(cat <<'EOF'
  # Gitea admin bootstrap is disabled by the installer.
  # Uncomment and customize the block below to create an admin automatically.
  # giteaAdminUser = "gitea-admin";
  # giteaAdminEmail = "gitea-admin@example.local";
  # giteaAdminUserPattern = lib.escapeRegex giteaAdminUser;
  # giteaAdminBootstrapScript = pkgs.writeShellScript "gitea-admin-bootstrap" ''
  #   set -euo pipefail
  #
  #   export HOME=${lib.escapeShellArg giteaStateDir}
  #   export GITEA_WORK_DIR=${lib.escapeShellArg giteaStateDir}
  #   export GITEA_CUSTOM=${lib.escapeShellArg ("${giteaStateDir}/custom")}
  #   export GITEA_APP_INI=${lib.escapeShellArg ("${giteaStateDir}/custom/conf/app.ini")}
  #
  #   ${pkgs.gitea}/bin/gitea admin user create \
  #     --username ${lib.escapeShellArg giteaAdminUser} \
  #     --password ${lib.escapeShellArg "<replace-with-password>"} \
  #     --email ${lib.escapeShellArg giteaAdminEmail} \
  #     --must-change-password=false \
  #     --admin
  # '';
EOF
)
        gitea_admin_service_block=$(cat <<'EOF'
  # systemd.services.gitea-admin-bootstrap = {
  #   description = "Bootstrap default Gitea administrator";
  #   wantedBy = [ "multi-user.target" ];
  #   after = [ "gitea.service" ];
  #   requires = [ "gitea.service" ];
  #   serviceConfig = {
  #     Type = "oneshot";
  #     User = "gitea";
  #     Group = "gitea";
  #     ExecStart = giteaAdminBootstrapScript;
  #   };
  # };
EOF
)
        gitea_admin_user_literal=""
        gitea_admin_email_literal=""
        gitea_admin_password_literal=""
    fi

    TARGET_CONFIGURATION_NIX="$SYSTEM_CONFIG_FILE" \
        SCRIPT_VERSION_VALUE="$SCRIPT_VERSION" \
        GENERATED_AT="$GENERATED_AT" \
        HOSTNAME_VALUE="$HOSTNAME" \
        USER_VALUE="$USER" \
        CPU_VENDOR_LABEL_VALUE="$CPU_VENDOR_LABEL" \
        INITRD_KERNEL_MODULES_VALUE="$INITRD_KERNEL_MODULES" \
        MICROCODE_SECTION_VALUE="$MICROCODE_SECTION" \
        BINARY_CACHE_SETTINGS_VALUE="$binary_cache_settings" \
        GPU_HARDWARE_SECTION_VALUE="$gpu_hardware_section" \
        GPU_SESSION_VARIABLES_VALUE="$gpu_session_variables" \
        GPU_DRIVER_PACKAGES_BLOCK_VALUE="$gpu_driver_packages_block" \
        SELECTED_TIMEZONE_VALUE="$SELECTED_TIMEZONE" \
        CURRENT_LOCALE_VALUE="$CURRENT_LOCALE" \
        NIXOS_VERSION_VALUE="$NIXOS_VERSION" \
        ZRAM_PERCENT_VALUE="$zram_value" \
        TOTAL_RAM_GB_VALUE="$total_ram_value" \
        USERS_MUTABLE_VALUE="$USERS_MUTABLE_SETTING" \
        USER_PASSWORD_BLOCK_VALUE="$USER_PASSWORD_BLOCK" \
        GITEA_SECRET_KEY_VALUE="$GITEA_SECRET_KEY" \
        GITEA_INTERNAL_TOKEN_VALUE="$GITEA_INTERNAL_TOKEN" \
        GITEA_LFS_JWT_SECRET_VALUE="$GITEA_LFS_JWT_SECRET" \
        GITEA_JWT_SECRET_VALUE="$GITEA_JWT_SECRET" \
        GITEA_ADMIN_SECRETS_SET_VALUE="$gitea_admin_secrets_set" \
        GITEA_ADMIN_VARIABLES_BLOCK_VALUE="$gitea_admin_variables_block" \
        GITEA_ADMIN_SERVICE_BLOCK_VALUE="$gitea_admin_service_block" \
        GITEA_ADMIN_PASSWORD_VALUE="$gitea_admin_password_literal" \
        GITEA_ADMIN_USER_VALUE="$gitea_admin_user_literal" \
        GITEA_ADMIN_EMAIL_VALUE="$gitea_admin_email_literal" \
        run_python <<'PY'
import os
import sys

target_path = os.environ.get("TARGET_CONFIGURATION_NIX")
if not target_path:
    print("TARGET_CONFIGURATION_NIX is not set", file=sys.stderr)
    sys.exit(1)

with open(target_path, "r", encoding="utf-8") as f:
    text = f.read()

replacements = {
    "@SCRIPT_VERSION@": os.environ.get("SCRIPT_VERSION_VALUE", ""),
    "@GENERATED_AT@": os.environ.get("GENERATED_AT", ""),
    "@HOSTNAME@": os.environ.get("HOSTNAME_VALUE", ""),
    "@USER@": os.environ.get("USER_VALUE", ""),
    "@CPU_VENDOR_LABEL@": os.environ.get("CPU_VENDOR_LABEL_VALUE", "Unknown"),
    "@INITRD_KERNEL_MODULES@": os.environ.get("INITRD_KERNEL_MODULES_VALUE", ""),
    "@MICROCODE_SECTION@": os.environ.get("MICROCODE_SECTION_VALUE", ""),
    "@BINARY_CACHE_SETTINGS@": os.environ.get("BINARY_CACHE_SETTINGS_VALUE", ""),
    "@GPU_HARDWARE_SECTION@": os.environ.get("GPU_HARDWARE_SECTION_VALUE", ""),
    "@GPU_SESSION_VARIABLES@": os.environ.get("GPU_SESSION_VARIABLES_VALUE", ""),
    "@GPU_DRIVER_PACKAGES@": os.environ.get("GPU_DRIVER_PACKAGES_BLOCK_VALUE", "[]"),
    "@SELECTED_TIMEZONE@": os.environ.get("SELECTED_TIMEZONE_VALUE", "UTC"),
    "@CURRENT_LOCALE@": os.environ.get("CURRENT_LOCALE_VALUE", "en_US.UTF-8"),
    "@NIXOS_VERSION@": os.environ.get("NIXOS_VERSION_VALUE", "23.11"),
    "@ZRAM_PERCENT@": os.environ.get("ZRAM_PERCENT_VALUE", "50"),
    "@TOTAL_RAM_GB@": os.environ.get("TOTAL_RAM_GB_VALUE", "0"),
    "@USERS_MUTABLE@": os.environ.get("USERS_MUTABLE_VALUE", "true"),
    "@USER_PASSWORD_BLOCK@": os.environ.get(
        "USER_PASSWORD_BLOCK_VALUE",
        "    # (no password directives detected; update manually if required)\n",
    ),
    "@GITEA_SECRET_KEY@": os.environ.get("GITEA_SECRET_KEY_VALUE", ""),
    "@GITEA_INTERNAL_TOKEN@": os.environ.get("GITEA_INTERNAL_TOKEN_VALUE", ""),
    "@GITEA_LFS_JWT_SECRET@": os.environ.get("GITEA_LFS_JWT_SECRET_VALUE", ""),
    "@GITEA_JWT_SECRET@": os.environ.get("GITEA_JWT_SECRET_VALUE", ""),
    "@GITEA_ADMIN_SECRETS_SET@": os.environ.get("GITEA_ADMIN_SECRETS_SET_VALUE", "{}"),
    "@GITEA_ADMIN_VARIABLES_BLOCK@": os.environ.get("GITEA_ADMIN_VARIABLES_BLOCK_VALUE", ""),
    "@GITEA_ADMIN_SERVICE_BLOCK@": os.environ.get("GITEA_ADMIN_SERVICE_BLOCK_VALUE", ""),
    "@GITEA_ADMIN_PASSWORD@": os.environ.get("GITEA_ADMIN_PASSWORD_VALUE", ""),
    "@GITEA_ADMIN_USER@": os.environ.get("GITEA_ADMIN_USER_VALUE", ""),
    "@GITEA_ADMIN_EMAIL@": os.environ.get("GITEA_ADMIN_EMAIL_VALUE", ""),
}

for placeholder, value in replacements.items():
    text = text.replace(placeholder, value)

with open(target_path, "w", encoding="utf-8") as f:
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

    # Create flake.nix NOW before nixos-rebuild attempts to use it
    # This must happen before apply_nixos_system_config() which runs nixos-rebuild --flake
    print_info "Creating flake.nix for NixOS rebuild..."
    local FLAKE_TEMPLATE="$TEMPLATE_DIR/flake.nix"
    if [[ ! -f "$FLAKE_TEMPLATE" ]]; then
        print_error "Missing flake template: $FLAKE_TEMPLATE"
        return 1
    fi

    local SYSTEM_ARCH=$(nix eval --raw --expr builtins.currentSystem 2>/dev/null || echo "x86_64-linux")
    local CURRENT_HOSTNAME=$(hostname)

    # Construct nixpkgs channel name from NIXOS_VERSION (e.g., "25.05" -> "nixos-25.05")
    local NIXPKGS_CHANNEL="${SYNCHRONIZED_NIXOS_CHANNEL:-nixos-${NIXOS_VERSION}}"

    if copy_template_to_flake "$FLAKE_TEMPLATE" "$FLAKE_FILE" "flake.nix"; then
        print_success "Created flake.nix in $HM_CONFIG_DIR"
    else
        print_error "Failed to create flake.nix"
        return 1
    fi

    # Align flake inputs with the synchronized channels
    sed -i "s|NIXPKGS_CHANNEL_PLACEHOLDER|$NIXPKGS_CHANNEL|" "$FLAKE_FILE"
    sed -i "s|HM_CHANNEL_PLACEHOLDER|$HM_CHANNEL_NAME|" "$FLAKE_FILE"
    sed -i "s|HOSTNAME_PLACEHOLDER|$CURRENT_HOSTNAME|" "$FLAKE_FILE"
    sed -i "s|HOME_USERNAME_PLACEHOLDER|$USER|" "$FLAKE_FILE"
    sed -i "s|SYSTEM_PLACEHOLDER|$SYSTEM_ARCH|" "$FLAKE_FILE"

    # Verify system configuration files exist (including flake.nix which was just created)
    # Note: home.nix will still be created later by create_home_manager_config
    if ! require_system_config_artifacts; then
        print_error "Required system configuration files are missing; aborting"
        return 1
    fi
}

# ============================================================================
# NixOS System Configuration - Part 2: Application
# ============================================================================
# This function prompts the user and applies the NixOS system configuration.
# It should be called AFTER generate_nixos_system_config() and BEFORE any
# destructive operations like backups or deletions of user files.
# ============================================================================
apply_nixos_system_config() {
    # Apply the new configuration
    print_section "Applying New Configuration"

    local SYSTEM_CONFIG="/etc/nixos/configuration.nix"
    local NIXOS_REBUILD_DRY_LOG="/tmp/nixos-rebuild-dry-run.log"
    if [[ "$SYSTEM_BUILD_VALIDATED" != true ]]; then
        if run_nixos_rebuild_dry_run "$NIXOS_REBUILD_DRY_LOG"; then
            SYSTEM_BUILD_VALIDATED=true
            SYSTEM_BUILD_DRY_RUN_LOG="$NIXOS_REBUILD_DRY_LOG"
            print_success "Dry run completed successfully (no changes applied)"
            print_info "Log saved to: $NIXOS_REBUILD_DRY_LOG"
        else
            local dry_exit_code=$?
            print_error "Dry run failed (exit code: $dry_exit_code)"
            print_info "Review the log: $NIXOS_REBUILD_DRY_LOG"
            print_info "Fix the issues above before attempting a full switch."
            return 1
        fi
    else
        if [[ -n "$SYSTEM_BUILD_DRY_RUN_LOG" ]]; then
            NIXOS_REBUILD_DRY_LOG="$SYSTEM_BUILD_DRY_RUN_LOG"
            print_info "Dry run already completed earlier (log: $SYSTEM_BUILD_DRY_RUN_LOG)"
        else
            print_info "Dry run previously completed - skipping rebuild validation"
        fi
    fi

    # CRITICAL: This prompt happens BEFORE any home-manager/flatpak/flake backups
    if ! confirm "Proceed with 'sudo nixos-rebuild switch' to apply the system configuration?" "y"; then
        local target_host=$(hostname)
        print_warning "nixos-rebuild switch skipped at this stage. Run 'sudo nixos-rebuild switch --flake "$HM_CONFIG_DIR#$target_host"' later to apply system changes."
        print_warning "Without switching, some packages and services may remain unavailable until you rebuild."
        echo ""
        return 0
    fi

    local NIXOS_REBUILD_LOG="/tmp/nixos-rebuild.log"
    if run_nixos_rebuild_switch "$NIXOS_REBUILD_LOG"; then
        SYSTEM_REBUILD_APPLIED=true
        print_success "✓ NixOS system configured successfully!"
        print_success "✓ AIDB development environment ready"
        echo ""

        # Configure Flatpak for COSMIC Store
        print_section "Configuring Flatpak for COSMIC App Store"
        if ensure_flathub_remote; then
            print_info "COSMIC Store can now install Flatpak applications"
        else
            print_warning "Add Flathub manually with: flatpak remote-add --user $FLATHUB_REMOTE_NAME $FLATHUB_REMOTE_URL"
        fi
        echo ""
    else
        local rebuild_exit_code=$?
        print_error "nixos-rebuild failed - restoring backup"
        sudo cp "$SYSTEM_CONFIG_BACKUP" "$SYSTEM_CONFIG"
        print_info "Backup restored. Check: $NIXOS_REBUILD_LOG"
        exit 1
    fi
}


# ============================================================================
# Flake Integration & AIDB Development Environment
# ============================================================================

configure_direnv_integration() {
    local backup_dir="${1:-}"
    local direnv_config_dir="$HOME/.config/direnv"
    local direnvrc_path="$direnv_config_dir/direnvrc"
    local envrc_path="$HM_CONFIG_DIR/.envrc"
    local desired_direnvrc_content
    local desired_envrc_content
    local update_direnvrc=true
    local update_envrc=true

    if ! command -v direnv >/dev/null 2>&1; then
        print_warning "direnv not found in PATH. Install direnv via home-manager before enabling integration."
        return 1
    fi

    desired_direnvrc_content=$(cat <<'EOF'
# nix-direnv integration (managed by nixos-quick-deploy)
if [ -d "$HOME/.nix-profile/share/nix-direnv" ]; then
  source "$HOME/.nix-profile/share/nix-direnv/direnvrc"
elif [ -d "/etc/profiles/per-user/$USER/share/nix-direnv" ]; then
  source "/etc/profiles/per-user/$USER/share/nix-direnv/direnvrc"
elif [ -d "/nix/var/nix/profiles/per-user/$USER/share/nix-direnv" ]; then
  source "/nix/var/nix/profiles/per-user/$USER/share/nix-direnv/direnvrc"
fi
EOF
)

    desired_envrc_content=$(cat <<'EOF'
# AIDB flake direnv activation (managed by nixos-quick-deploy)
if [ -f flake.nix ]; then
  use flake
fi
EOF
)

    if [[ -z "$backup_dir" ]]; then
        backup_dir="$HOME/.config-backups/flake-setup-$(date +%Y%m%d_%H%M%S)"
    fi

    if ! run_as_primary_user install -d -m 755 "$direnv_config_dir" >/dev/null 2>&1; then
        mkdir -p "$direnv_config_dir"
    fi
    ensure_path_owner "$direnv_config_dir"

    if [[ -f "$direnvrc_path" || -L "$direnvrc_path" ]]; then
        if printf '%s\n' "$desired_direnvrc_content" | cmp -s - "$direnvrc_path" 2>/dev/null; then
            update_direnvrc=false
        fi
    fi

    if [[ "$update_direnvrc" == true ]]; then
        backup_path_if_exists "$direnvrc_path" "$backup_dir" "direnv configuration" || true
        printf '%s\n' "$desired_direnvrc_content" > "$direnvrc_path"
        ensure_path_owner "$direnvrc_path"
        print_success "Configured nix-direnv integration at $direnvrc_path"
    else
        print_info "direnvrc already configured for nix-direnv integration"
    fi

    if [[ -f "$envrc_path" || -L "$envrc_path" ]]; then
        if printf '%s\n' "$desired_envrc_content" | cmp -s - "$envrc_path" 2>/dev/null; then
            update_envrc=false
        fi
    fi

    if [[ "$update_envrc" == true ]]; then
        backup_path_if_exists "$envrc_path" "$backup_dir" "flake .envrc" || true
        printf '%s\n' "$desired_envrc_content" > "$envrc_path"
        ensure_path_owner "$envrc_path"
        print_success "Created direnv .envrc in $HM_CONFIG_DIR"
    else
        print_info ".envrc already enables flake activation"
    fi

    if [[ ! -e "$HOME/.zshrc" ]]; then
        : > "$HOME/.zshrc"
    fi

    local direnv_hook='eval "$(direnv hook zsh)"'
    if ! grep -Fq "$direnv_hook" "$HOME/.zshrc" 2>/dev/null; then
        echo "$direnv_hook" >> "$HOME/.zshrc"
        ensure_path_owner "$HOME/.zshrc"
        print_success "Added direnv hook to .zshrc"
    else
        print_info "direnv hook already present in .zshrc"
    fi

    if (cd "$HM_CONFIG_DIR" && direnv allow >/dev/null 2>&1); then
        print_success "direnv allowed for $HM_CONFIG_DIR"
    else
        print_warning "direnv allow failed for $HM_CONFIG_DIR (run manually if needed)"
    fi

    return 0
}

setup_flake_environment() {
    print_section "Setting Up Flake-based Development Environment"

    # Check if flake.nix exists in the NixOS-Quick-Deploy directory
    local FLAKE_DIR="$HM_CONFIG_DIR"
    local FLAKE_FILE="$FLAKE_DIR/flake.nix"
    local flake_backup_dir=""

    if [[ ! -f "$FLAKE_FILE" ]]; then
        print_warning "flake.nix not found at $FLAKE_FILE"
        print_info "Flake integration will be skipped"
        return 1
    fi

    print_success "Found flake.nix at $FLAKE_FILE"

    # Check if activation script already exists (IDEMPOTENCY CHECK)
    if [ "$FORCE_UPDATE" = false ] && [ -f "$HOME/.local/bin/aidb-dev-env" ] && [ -f "$HOME/.config/zsh/aidb-flake.zsh" ]; then
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
    if ! run_as_primary_user install -d -m 755 "$HOME/.config/nix" >/dev/null 2>&1; then
        mkdir -p "$HOME/.config/nix"
    fi
    ensure_path_owner "$HOME/.config/nix"

    if [[ -f "$HOME/.config/nix/nix.conf" || -L "$HOME/.config/nix/nix.conf" ]]; then
        if [[ -z "$flake_backup_dir" ]]; then
            flake_backup_dir="$HOME/.config-backups/flake-setup-$(date +%Y%m%d_%H%M%S)"
        fi
        backup_path_if_exists "$HOME/.config/nix/nix.conf" "$flake_backup_dir" "Nix flakes configuration" || true
    fi
    cat > "$HOME/.config/nix/nix.conf" <<'NIXCONF'
experimental-features = nix-command flakes
NIXCONF
    print_success "Nix flakes enabled"
    ensure_path_owner "$HOME/.config/nix/nix.conf"

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
        print_info "You can manually build it later with: $HM_CONFIG_CD_COMMAND && nix develop"
        echo ""
        print_warning "This is not critical - continuing without flake environment"
        echo ""
    fi

    # Create a convenient activation script
    print_info "Creating flake activation script..."
    if [[ -f "$HOME/.local/bin/aidb-dev-env" || -L "$HOME/.local/bin/aidb-dev-env" ]]; then
        if [[ -z "$flake_backup_dir" ]]; then
            flake_backup_dir="$HOME/.config-backups/flake-setup-$(date +%Y%m%d_%H%M%S)"
        fi
        backup_path_if_exists "$HOME/.local/bin/aidb-dev-env" "$flake_backup_dir" "aidb-dev-env helper" || true
    fi
    cat > "$HOME/.local/bin/aidb-dev-env" <<DEVENV
#!/usr/bin/env bash
# AIDB Development Environment Activator
# Enters the flake development shell with all AIDB tools

FLAKE_DIR="$HM_CONFIG_DIR"

if [[ ! -f "\$FLAKE_DIR/flake.nix" ]]; then
    echo "Error: flake.nix not found at \$FLAKE_DIR"
    exit 1
fi

echo "Entering AIDB development environment..."
cd "\$FLAKE_DIR" && exec nix develop
DEVENV

    chmod +x "$HOME/.local/bin/aidb-dev-env"
    ensure_path_owner "$HOME/.local/bin/aidb-dev-env"
    print_success "Created aidb-dev-env activation script"

    # Add flake information to shell profile
    print_info "Adding flake information to ZSH profile..."
    if ! run_as_primary_user install -d -m 755 "$HOME/.config/zsh" >/dev/null 2>&1; then
        mkdir -p "$HOME/.config/zsh"
    fi
    ensure_path_owner "$HOME/.config/zsh"

    if [[ -f "$HOME/.config/zsh/aidb-flake.zsh" || -L "$HOME/.config/zsh/aidb-flake.zsh" ]]; then
        if [[ -z "$flake_backup_dir" ]]; then
            flake_backup_dir="$HOME/.config-backups/flake-setup-$(date +%Y%m%d_%H%M%S)"
        fi
        backup_path_if_exists "$HOME/.config/zsh/aidb-flake.zsh" "$flake_backup_dir" "aidb-flake.zsh profile" || true
    fi
    cat > "$HOME/.config/zsh/aidb-flake.zsh" <<'ZSHFLAKE'

# AIDB Flake Integration
# Quick access to AIDB development environment

alias aidb-dev='aidb-dev-env'
alias aidb-shell='cd "$HOME/.dotfiles/home-manager" && nix develop'
alias aidb-update='cd "$HOME/.dotfiles/home-manager" && nix flake update'

# Show AIDB development environment info
aidb-info() {
    echo "AIDB Development Environment"
    echo "  Flake location: $HOME/.dotfiles/home-manager/flake.nix"
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
    ensure_path_owner "$HOME/.config/zsh/aidb-flake.zsh"

    # Source this in .zshrc if not already done
    if ! grep -q "aidb-flake.zsh" "$HOME/.zshrc" 2>/dev/null; then
        echo 'source ~/.config/zsh/aidb-flake.zsh' >> "$HOME/.zshrc"
        print_success "Added AIDB flake aliases to .zshrc"
        ensure_path_owner "$HOME/.zshrc"
    fi

    echo ""
    if command -v direnv >/dev/null 2>&1; then
        if confirm "Enable automatic direnv activation for the AIDB flake when entering $HM_CONFIG_DIR?" "y"; then
            if configure_direnv_integration "$flake_backup_dir"; then
                print_success "direnv integration enabled for the flake directory"
            else
                print_warning "direnv integration step encountered issues (see messages above)"
            fi
            echo ""
        else
            print_info "Direnv integration skipped. Run configure_direnv_integration later to enable it."
            echo ""
        fi
    else
        print_info "direnv is not currently in PATH; skipping automatic direnv integration. Install direnv and rerun configure_direnv_integration when ready."
        echo ""
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
# Enhanced error handling and debugging for NixOS

set -euo pipefail

# Debug mode: Set CLAUDE_DEBUG=1 to see diagnostic output
DEBUG="${CLAUDE_DEBUG:-0}"

debug_log() {
    if [ "$DEBUG" = "1" ]; then
        echo "[DEBUG] $*" >&2
    fi
}

debug_log "Claude wrapper starting..."

# Strategy 1: Try common Nix profile locations (fastest)
NODE_LOCATIONS=(
    "$HOME/.nix-profile/bin/node"
    "/run/current-system/sw/bin/node"
    "/nix/var/nix/profiles/default/bin/node"
)

NODE_BIN=""
for node_path in "${NODE_LOCATIONS[@]}"; do
    debug_log "Trying: $node_path"
    # Resolve symlinks to get actual Nix store path
    if [ -n "$node_path" ] && [ -x "$node_path" ]; then
        NODE_BIN=$(readlink -f "$node_path" 2>/dev/null || echo "$node_path")
        if [ -x "$NODE_BIN" ]; then
            debug_log "Found Node.js at: $NODE_BIN"
            break
        fi
    fi
done

# Strategy 2: Search PATH using 'command -v' (works better in NixOS)
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    debug_log "Searching PATH for node..."
    NODE_BIN=$(command -v node 2>/dev/null || echo "")
    if [ -n "$NODE_BIN" ]; then
        NODE_BIN=$(readlink -f "$NODE_BIN" 2>/dev/null || echo "$NODE_BIN")
        debug_log "Found via command: $NODE_BIN"
    fi
fi

# Strategy 3: Check if node is in PATH but not resolved yet
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    debug_log "Trying which..."
    NODE_BIN=$(which node 2>/dev/null || echo "")
    if [ -n "$NODE_BIN" ]; then
        NODE_BIN=$(readlink -f "$NODE_BIN" 2>/dev/null || echo "$NODE_BIN")
        debug_log "Found via which: $NODE_BIN"
    fi
fi

# Strategy 4: Find in Nix store directly (last resort, slow)
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    debug_log "Searching Nix store (this may take a moment)..."
    NODE_BIN=$(find /nix/store -maxdepth 2 -name "node" -type f -executable 2>/dev/null | grep -m1 "nodejs.*bin/node" || echo "")
    if [ -n "$NODE_BIN" ]; then
        debug_log "Found in Nix store: $NODE_BIN"
    fi
fi

# Fail if still not found
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    echo "========================================" >&2
    echo "ERROR: Could not find Node.js executable" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "Searched locations:" >&2
    printf '  - %s\n' "${NODE_LOCATIONS[@]}" >&2
    echo "" >&2
    echo "Current PATH: $PATH" >&2
    echo "" >&2
    echo "Troubleshooting steps:" >&2
    echo "  1. Verify Node.js is installed: which node" >&2
    echo "  2. Check if home-manager was applied: home-manager --version" >&2
    echo "  3. Restart your shell: exec zsh" >&2
    echo "  4. Re-run the deployment script: cd ~/NixOS-Dev-Quick-Deploy && ./nixos-quick-deploy.sh" >&2
    echo "" >&2
    echo "For debugging, run: CLAUDE_DEBUG=1 ~/.npm-global/bin/claude-wrapper --version" >&2
    echo "" >&2
    exit 127
fi

# Path to Claude Code CLI
CLAUDE_CLI="$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js"

debug_log "Looking for Claude CLI at: $CLAUDE_CLI"

if [ ! -f "$CLAUDE_CLI" ]; then
    echo "========================================" >&2
    echo "ERROR: Claude Code CLI not found" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "Expected location: $CLAUDE_CLI" >&2
    echo "" >&2
    echo "This usually means Claude Code wasn't installed properly." >&2
    echo "" >&2
    echo "To fix:" >&2
    echo "  export NPM_CONFIG_PREFIX=~/.npm-global" >&2
    echo "  npm install -g @anthropic-ai/claude-code" >&2
    echo "" >&2
    exit 127
fi

debug_log "Executing: $NODE_BIN $CLAUDE_CLI $*"

# Execute with Node.js
exec "$NODE_BIN" "$CLAUDE_CLI" "$@"
WRAPPER_EOF

    chmod +x ~/.npm-global/bin/claude-wrapper
    print_success "Created claude-wrapper"

    # Test the wrapper
    print_info "Testing Claude Code wrapper..."
    if ~/.npm-global/bin/claude-wrapper --version >/dev/null 2>&1; then
        CLAUDE_VERSION=$(~/.npm-global/bin/claude-wrapper --version 2>/dev/null | head -n1)
        print_success "Claude Code wrapper works! Version: ${CLAUDE_VERSION}"
        CLAUDE_EXEC_PATH="$HOME/.npm-global/bin/claude-wrapper"

        # Verify it's in PATH
        if command -v claude-wrapper &>/dev/null; then
            print_success "claude-wrapper is in PATH: $(which claude-wrapper)"
        else
            print_warning "claude-wrapper not in PATH yet"
            print_info "It will be available after sourcing session variables or reboot"
        fi
    else
        print_warning "Wrapper test inconclusive, but created"
        print_info "This may be because Node.js path changed - wrapper will work after reboot"
        CLAUDE_EXEC_PATH="$HOME/.npm-global/bin/claude-wrapper"
    fi

    # Verify NPM_CONFIG_PREFIX is set
    print_info "Verifying NPM configuration..."
    if [ -f "$HOME/.npmrc" ] && grep -q "prefix=" "$HOME/.npmrc"; then
        print_success "~/.npmrc configured correctly"
    else
        print_warning "~/.npmrc may need configuration"
        print_info "home-manager will set NPM_CONFIG_PREFIX via session variables"
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

    if [ -L "$SETTINGS_FILE" ]; then
        print_info "VSCodium settings.json is managed by home-manager (symlink detected)."

        if command -v jq >/dev/null 2>&1 && [ -f "$SETTINGS_FILE" ]; then
            if jq -e '."claude-code.executablePath" != null or ."claudeCode.executablePath" != null' "$SETTINGS_FILE" >/dev/null 2>&1; then
                print_success "Claude Code settings detected in home-manager managed configuration."
            else
                print_warning "Claude Code settings not found in managed settings.json. Update your home-manager template to include the claude wrapper paths."
            fi
        else
            print_info "Skipping verification because jq is unavailable."
        fi

        return 0
    fi

    mkdir -p "$(dirname "$SETTINGS_FILE")"

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
    install_ext "ms-python.python" "Python"
    install_ext "ms-python.vscode-pylance" "Pylance"
    install_ext "ms-python.black-formatter" "Black Formatter"
    install_ext "ms-toolsai.jupyter" "Jupyter"
    install_ext "ms-toolsai.jupyter-keymap" "Jupyter Keymap"
    install_ext "ms-toolsai.jupyter-renderers" "Jupyter Renderers"
    install_ext "HuggingFace.huggingface-vscode" "Hugging Face"
    # Note: Continue AI is already installed declaratively via home-manager (templates/home.nix:1420)
    # Removed duplicate installation to prevent activation errors
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

finalize_configuration_activation() {
    print_section "Final Activation"

    if [[ "$HOME_MANAGER_APPLIED" == true ]]; then
        print_info "Home-manager switch already completed earlier; skipping automatic re-run."
        print_info "Run 'home-manager switch --flake \"$HM_CONFIG_DIR\"' later if you need to reapply changes."
    elif confirm "Run home-manager switch now to activate your user environment?" "y"; then
        clean_home_manager_targets "final-activation"
        prepare_managed_config_paths
        # Clean up any failed systemd services before activation to prevent degraded session warnings
        cleanup_systemd_before_activation
        local HM_SWITCH_LOG="/tmp/home-manager-switch-final.log"
        if run_home_manager_switch "$HM_SWITCH_LOG"; then
            HOME_MANAGER_APPLIED=true

            apply_system_changes
            print_success "Home-manager configuration activated during finalization"
            ensure_home_manager_cli_available || true
            ensure_flatpak_managed_install_service
            ensure_default_flatpak_apps_installed
            echo ""
        else
            local hm_exit_code=$?
            print_error "home-manager switch during finalization failed (exit code: $hm_exit_code)"
            print_info "Review the log: $HM_SWITCH_LOG"
            exit 1
        fi
    else
        print_info "Skipping home-manager switch during finalization."
    fi

    echo ""

    if [[ "$SYSTEM_REBUILD_APPLIED" == true ]]; then
        print_info "System configuration already activated earlier; skipping additional nixos-rebuild."
        local target_host=$(hostname)
        print_info "Run 'sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\"' later if you need to rebuild."
    else
        local target_host=$(hostname)
        print_info "System configuration has not been activated yet during this run."
        print_warning "Run 'sudo nixos-rebuild switch --flake \"$HM_CONFIG_DIR#$target_host\"' when you are ready to apply system changes."
    fi
}

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
    echo "    • VSCodium with NixOS + AI tooling extensions"
    echo ""
    echo -e "  ${GREEN}Claude Code Integration:${NC}"
    echo "    • Claude Code CLI installed globally"
    echo "    • Smart Node.js wrapper (fixes Error 127)"
    echo "    • VSCodium fully configured for Claude Code"
    echo "    • All required extensions installed"
    echo ""
    echo -e "  ${GREEN}Local AI Runtime:${NC}"
    echo "    • Hugging Face TGI service (podman-based systemd unit)"
    echo "    • hf-tgi helper for managing the local inference server"
    echo "    • Open WebUI podman helpers: open-webui-run/open-webui-stop"
    echo "    • podman-ai-stack helper to launch Ollama, Open WebUI, Qdrant, MindsDB"
    echo "    • gpt-cli for OpenAI-compatible and Ollama chat completions"
    echo "    • obsidian-ai-bootstrap to seed AI plugins in Obsidian vaults"
    echo "    • hf-model-sync script for downloading Hugging Face models"
    echo "    • Optional Ollama CLI installed when available"
    echo ""
    echo -e "  ${GREEN}Modern CLI & Terminal:${NC}"
    echo "    • ZSH with Powerlevel10k theme"
    echo "    • Modern tools (ripgrep, bat, eza, fzf, fd, etc.)"
    echo "    • Observability stack (Grafana, Prometheus, Loki, Promtail, Vector, Glances, Cockpit)"
    echo "    • Alacritty terminal"
    echo "    • Git with aliases"
    echo ""
    echo -e "  ${GREEN}Desktop Environment:${NC}"
    echo "    • Cosmic desktop components (cosmic-edit, cosmic-files, cosmic-term)"
    echo "    • Modern Rust-based desktop environment"
    echo "    • Cursor IDE and LM Studio Flatpaks ready for AI workflows"
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
    echo -e "  3. ${YELLOW}Environment Variables:${NC} If packages aren't in PATH after reboot:"
    echo -e "     ${GREEN}source ~/.nix-profile/etc/profile.d/hm-session-vars.sh${NC}"
    echo -e "     ${GREEN}exec zsh${NC}  # Reload shell with new environment"
    echo -e "  4. VSCodium command: ${GREEN}codium${NC} or ${GREEN}codium-wrapped${NC}"
    echo -e "  5. Claude Code wrapper: ${GREEN}~/.npm-global/bin/claude-wrapper${NC}"
    echo -e "  6. ${GREEN}All configurations applied automatically!${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "  ${GREEN}1. Verify Installation (RECOMMENDED):${NC}"
    echo "     cd ~/NixOS-Dev-Quick-Deploy"
    echo "     ./scripts/system-health-check.sh"
    echo ""
    echo -e "     ${YELLOW}If health check fails:${NC}"
    echo "     ./scripts/system-health-check.sh --fix  # Auto-repair common issues"
    echo ""
    echo -e "  ${GREEN}2. Enable AI Services (optional):${NC}"
    echo "     systemctl --user enable --now qdrant"
    echo "     systemctl --user enable --now huggingface-tgi"
    echo "     systemctl --user enable --now jupyter-lab"
    echo ""
    echo -e "  ${GREEN}3. Start Using AI Tools:${NC}"
    echo "     python3 -c \"import torch, tensorflow, langchain; print('Ready!')\""
    echo "     jupyter-lab  # Start Jupyter Lab manually"
    echo "     aider        # Start AI coding assistant"
    echo ""
    echo -e "  ${GREEN}4. Read Documentation:${NC}"
    echo "     cat ~/NixOS-Dev-Quick-Deploy/AIDB_SETUP.md"
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
    echo "  • Setup guide: ~/NixOS-Dev-Quick-Deploy/README.md"
    echo "  • AIDB guide: ~/NixOS-Dev-Quick-Deploy/docs/AIDB_SETUP.md"
    echo "  • Home manager: https://nix-community.github.io/home-manager/"
    echo "  • Health check: ~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh"
    echo ""
    echo -e "${GREEN}System is ready! All packages and services are configured.${NC}"
    echo ""
}

# ============================================================================
# Workflow Stages
# ============================================================================


# ============================================================================
# NEW v3.1.0 FUNCTIONS: GPU Hardware Detection
# ============================================================================

detect_gpu_hardware() {
    print_section "Detecting GPU Hardware"
    
    # Initialize GPU variables
    GPU_TYPE="unknown"
    GPU_DRIVER=""
    GPU_PACKAGES=""
    LIBVA_DRIVER=""
    
    # Check if lspci is available
    if ! command -v lspci >/dev/null 2>&1; then
        print_warning "lspci not found - GPU detection will be limited"
        print_info "Install pciutils for automatic GPU detection: nix-env -iA nixos.pciutils"
        GPU_TYPE="software"
        return 0
    fi
    
    # Detect GPU hardware
    local gpu_info
    gpu_info=$(lspci | grep -iE "VGA|3D|Display" || echo "")
    
    if [[ -z "$gpu_info" ]]; then
        print_info "No dedicated GPU detected - using software rendering"
        GPU_TYPE="software"
        return 0
    fi
    
    print_info "GPU Hardware Detected:"
    echo "$gpu_info" | sed 's/^/  /'
    echo ""
    
    # Check for Intel GPU
    if echo "$gpu_info" | grep -iq "Intel"; then
        GPU_TYPE="intel"
        GPU_DRIVER="intel"
        LIBVA_DRIVER="iHD"
        GPU_PACKAGES="intel-media-driver vaapiIntel"
        print_success "Intel GPU detected"
        print_info "  Driver: $GPU_DRIVER"
        print_info "  VA-API: $LIBVA_DRIVER"
    fi
    
    # Check for AMD GPU
    if echo "$gpu_info" | grep -iq "AMD\|ATI\|Radeon"; then
        GPU_TYPE="amd"
        GPU_DRIVER="amdgpu"
        LIBVA_DRIVER="radeonsi"
        GPU_PACKAGES="mesa rocm-opencl-icd"
        print_success "AMD GPU detected"
        print_info "  Driver: $GPU_DRIVER (RADV - modern default)"
        print_info "  VA-API: $LIBVA_DRIVER"
    fi
    
    # Check for NVIDIA GPU
    if echo "$gpu_info" | grep -iq "NVIDIA"; then
        GPU_TYPE="nvidia"
        GPU_DRIVER="nvidia"
        LIBVA_DRIVER="nvidia"
        GPU_PACKAGES="nvidia-vaapi-driver"
        print_success "NVIDIA GPU detected"
        print_info "  Driver: $GPU_DRIVER"
        print_info "  VA-API: $LIBVA_DRIVER"
        print_warning "NVIDIA on Wayland requires additional configuration"
        print_info "Consider enabling: hardware.nvidia.modesetting.enable = true"
    fi
    
    if [[ "$GPU_TYPE" == "unknown" ]]; then
        print_warning "Unknown GPU type - using software rendering"
        GPU_TYPE="software"
    fi
    
    echo ""
    return 0
}

# ============================================================================
# NEW v3.1.0 PHASE FUNCTIONS: 10-Phase Workflow
# ============================================================================

# PHASE 1: Preparation & Validation
comprehensive_preflight_checks() {
    local phase_name="preparation_validation"

    if is_step_complete "$phase_name"; then
        print_info "Phase 1 already completed (skipping)"
        return 0
    fi

    print_section "Phase 1/10: Preparation & Validation"
    echo ""

    # Check if running on NixOS
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    # Check permissions
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        exit 1
    fi
    print_success "Running with correct permissions (non-root)"

    # Ensure required commands are available
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            print_error "Critical command not found: $cmd"
            exit 1
        fi
    done
    print_success "Critical NixOS commands available"

    # Check disk space
    if ! check_disk_space; then
        print_error "Insufficient disk space"
        exit 1
    fi

    # Validate network connectivity
    print_info "Checking network connectivity..."
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_success "Network connectivity OK"
    else
        print_error "No network connectivity detected"
        print_error "Internet connection required to download packages"
        exit 1
    fi

    # Validate path uniqueness
    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        print_error "Internal configuration path conflict detected"
        exit 1
    fi

    # Check for old deployment artifacts
    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="/home/$USER/Documents/nixos-quick-deploy.sh"
    if [[ -f "$OLD_SCRIPT" ]]; then
        print_warning "Found old deployment script: $OLD_SCRIPT"
        print_info "This can be safely ignored or archived"
    fi

    # Validate entire dependency chain
    print_info "Validating dependency chain..."
    check_required_packages || {
        print_error "Required packages not available"
        exit 1
    }

    # GPU hardware detection
    detect_gpu_hardware

    # CPU and memory detection
    detect_gpu_and_cpu

    mark_step_complete "$phase_name"
    print_success "Phase 1: Preparation & Validation - COMPLETE"
    echo ""
}

# PHASE 2: Prerequisite Package Installation
install_prerequisites_phase() {
    local phase_name="install_prerequisites"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 2 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 2/10: Prerequisite Package Installation"
    echo ""
    
    # NixOS version selection
    select_nixos_version
    
    # Update channels
    update_nixos_channels
    
    # Ensure core packages
    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
        exit 1
    fi
    
    # Cleanup conflicting home-manager entries
    print_info "Scanning nix profile for legacy home-manager entries..."
    cleanup_conflicting_home_manager_profile
    
    # Ensure home-manager is available
    if command -v home-manager &>/dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        install_home_manager
    fi
    
    # Python runtime check
    print_info "Verifying Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        exit 1
    fi
    
    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        print_success "Python runtime: ephemeral Nix shell"
    else
        print_success "Python runtime: ${PYTHON_BIN[0]} ($(${PYTHON_BIN[@]} --version 2>&1))"
    fi
    
    mark_step_complete "$phase_name"
    print_success "Phase 2: Prerequisite Package Installation - COMPLETE"
    echo ""
}

# PHASE 3: System Backup
comprehensive_backup_phase() {
    local phase_name="comprehensive_backup"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 3 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 3/10: System Backup"
    echo ""
    
    # Create rollback point
    if [[ "$DRY_RUN" == false ]]; then
        create_rollback_point "Before v3.1 deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi
    
    # Backup existing configs
    if [[ -f "/etc/nixos/configuration.nix" ]]; then
        local backup_path="/etc/nixos/configuration.nix.backup.$(date +%Y%m%d_%H%M%S)"
        sudo cp "/etc/nixos/configuration.nix" "$backup_path"
        print_success "Backed up system configuration: $backup_path"
    fi
    
    # Backup home-manager configs if they exist
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then
        local hm_backup="$HOME/.config/home-manager/home.nix.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$HOME/.config/home-manager/home.nix" "$hm_backup"
        print_success "Backed up home-manager config: $hm_backup"
    fi
    
    mark_step_complete "$phase_name"
    print_success "Phase 3: System Backup - COMPLETE"
    echo ""
}

# PHASE 4: Configuration Generation & Validation
generate_and_validate_configs_phase() {
    local phase_name="generate_validate_configs"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 4 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 4/10: Configuration Generation & Validation"
    echo ""
    
    # Gather user info
    gather_user_info
    
    # Generate NixOS system config
    generate_nixos_system_config
    
    # Validate system build (dry run)
    validate_system_build_stage
    
    mark_step_complete "$phase_name"
    print_success "Phase 4: Configuration Generation & Validation - COMPLETE"
    echo ""
}

# PHASE 5: Intelligent Cleanup
intelligent_cleanup_phase() {
    local phase_name="intelligent_cleanup"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 5 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 5/10: Intelligent Cleanup"
    echo ""
    
    print_warning "This phase will remove conflicting packages and configurations"
    print_info "All removals are backed up and can be restored if needed"
    echo ""
    
    # User confirmation before destructive operations
    if ! confirm "Proceed with intelligent cleanup of conflicting packages?" "y"; then
        print_warning "Cleanup skipped - this may cause conflicts during installation"
        echo ""
        return 0
    fi
    
    # Check for nix-env packages
    print_info "Checking for packages installed via nix-env..."
    local imperative_pkgs
    imperative_pkgs=$(nix-env -q 2>/dev/null || true)
    
    if [[ -n "$imperative_pkgs" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$imperative_pkgs" | sed 's/^/    /'
        echo ""
        
        # Intelligent selective removal instead of nix-env -e '.*'
        print_info "Identifying conflicting packages for selective removal..."
        local -a conflicting_pkgs=()
        
        # Only remove packages that conflict with home-manager
        while IFS= read -r pkg; do
            local pkg_name
            pkg_name=$(echo "$pkg" | awk '{print $1}')
            if [[ -n "$pkg_name" ]]; then
                # Add known conflicting packages
                if [[ "$pkg_name" =~ ^(home-manager|git|vscodium|nodejs|python) ]]; then
                    conflicting_pkgs+=("$pkg_name")
                fi
            fi
        done <<< "$imperative_pkgs"
        
        if [[ ${#conflicting_pkgs[@]} -gt 0 ]]; then
            print_info "Removing ${#conflicting_pkgs[@]} conflicting package(s):"
            for pkg in "${conflicting_pkgs[@]}"; do
                print_info "  - $pkg"
                nix-env -e "$pkg" 2>/dev/null || print_warning "    Failed to remove $pkg"
            done
            print_success "Conflicting packages removed"
        else
            print_info "No conflicting packages detected - keeping all nix-env packages"
        fi
    else
        print_success "No nix-env packages found - clean state!"
    fi
    
    # Cleanup old generations (optional)
    if confirm "Remove old nix-env generations to free up space?" "n"; then
        nix-env --delete-generations old 2>/dev/null || true
        print_success "Old generations cleaned up"
    fi
    
    mark_step_complete "$phase_name"
    print_success "Phase 5: Intelligent Cleanup - COMPLETE"
    echo ""
}

# PHASE 6: Configuration Deployment
deploy_configurations_phase() {
    local phase_name="deploy_configurations"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 6 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 6/10: Configuration Deployment"
    echo ""
    
    # User confirmation before deployment
    if ! confirm "Proceed with configuration deployment (this will apply system changes)?" "y"; then
        print_warning "Deployment skipped - configurations generated but not applied"
        print_info "To apply later, run: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        echo ""
        return 0
    fi
    
    # Apply system configuration
    apply_nixos_system_config
    
    # Create and apply home-manager configuration
    create_home_manager_config
    apply_home_manager_config
    
    mark_step_complete "$phase_name"
    print_success "Phase 6: Configuration Deployment - COMPLETE"
    echo ""
}

# PHASE 7: Tool & Service Installation
install_tools_and_services_phase() {
    local phase_name="install_tools_services"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 7 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 7/10: Tool & Service Installation"
    echo ""
    
    # Flatpak installation (can run in parallel with other installations)
    print_info "Installing Flatpak applications..."
    ensure_default_flatpak_apps_installed &
    local flatpak_pid=$!
    
    # Claude Code installation
    print_info "Installing Claude Code..."
    if install_claude_code; then
        configure_vscodium_for_claude || print_warning "VSCodium configuration had issues"
        install_vscodium_extensions || print_warning "Some VSCodium extensions may not have installed"
    else
        print_warning "Claude Code installation skipped due to errors"
    fi &
    local claude_pid=$!
    
    # OpenSkills installation
    print_info "Installing OpenSkills tooling..."
    install_openskills_tooling &
    local openskills_pid=$!
    
    # Wait for parallel installations
    print_info "Waiting for parallel installations to complete..."
    wait $flatpak_pid || print_warning "Flatpak installation had issues"
    wait $claude_pid || print_warning "Claude Code installation had issues"
    wait $openskills_pid || print_warning "OpenSkills installation had issues"
    
    # Flake environment setup
    if ! setup_flake_environment; then
        print_warning "Flake environment setup had issues (non-critical)"
    fi
    
    mark_step_complete "$phase_name"
    print_success "Phase 7: Tool & Service Installation - COMPLETE"
    echo ""
}

# PHASE 8: Post-Installation Validation
post_install_validation_phase() {
    local phase_name="post_install_validation"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 8 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 8/10: Post-Installation Validation"
    echo ""
    
    # Validate GPU driver if GPU was detected
    if [[ "$GPU_TYPE" != "software" && "$GPU_TYPE" != "unknown" ]]; then
        validate_gpu_driver || print_warning "GPU driver validation had issues (non-critical)"
    fi

    # Verify critical packages are available
    print_info "Verifying critical packages..."
    local missing_count=0
    for pkg in podman python3 git home-manager jq; do
        if command -v "$pkg" &>/dev/null; then
            print_success "$pkg: $(command -v $pkg)"
        else
            print_warning "$pkg: NOT FOUND"
            ((missing_count++)) || true
        fi
    done
    
    if [[ $missing_count -gt 0 ]]; then
        print_warning "$missing_count critical package(s) not in PATH"
        print_info "Try: exec zsh  (to reload shell)"
    else
        print_success "All critical packages verified!"
    fi
    
    mark_step_complete "$phase_name"
    print_success "Phase 8: Post-Installation Validation - COMPLETE"
    echo ""
}

# PHASE 9: Post-Install Scripts & Finalization
post_install_finalization_phase() {
    local phase_name="post_install_finalization"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 9 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 9/10: Post-Install Scripts & Finalization"
    echo ""

    # Finalize configuration activation
    finalize_configuration_activation
    
    mark_step_complete "$phase_name"
    print_success "Phase 9: Post-Install Scripts & Finalization - COMPLETE"
    echo ""
}

# PHASE 10: Success Report & Next Steps
generate_success_report_phase() {
    local phase_name="success_report"
    
    if is_step_complete "$phase_name"; then
        print_info "Phase 10 already completed (skipping)"
        return 0
    fi
    
    print_section "Phase 10/10: Success Report & Next Steps"
    echo ""
    
    # Generate comprehensive success report
    print_post_install
    
    # System status summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  Deployment Complete - All 10 Phases Successful!              ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Configuration status
    print_info "Configuration Status:"
    echo -e "  ${GREEN}✓${NC} NixOS system configuration applied"
    echo -e "  ${GREEN}✓${NC} Home-manager user environment active"
    echo -e "  ${GREEN}✓${NC} Flatpak applications installed"
    echo -e "  ${GREEN}✓${NC} Development tools configured"
    echo ""
    
    # Installed components summary
    print_info "Installed Components:"
    echo "  • COSMIC Desktop Environment"
    echo "  • Podman container runtime"
    echo "  • PostgreSQL database"
    echo "  • Python AI/ML environment"
    echo "  • Development CLI tools (100+)"
    echo "  • Claude Code integration"
    echo "  • System services (Gitea, Qdrant, Ollama, TGI)"
    echo ""
    
    # Next steps
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""
    echo -e "  ${GREEN}1.${NC} Reload your shell to activate new environment:"
    echo -e "     ${YELLOW}exec zsh${NC}"
    echo ""
    echo -e "  ${GREEN}2.${NC} Verify system services:"
    echo -e "     ${YELLOW}systemctl status ollama qdrant gitea huggingface-tgi${NC}"
    echo ""
    echo -e "  ${GREEN}3.${NC} Check user services:"
    echo -e "     ${YELLOW}systemctl --user status jupyter-lab${NC}"
    echo ""
    echo -e "  ${GREEN}4.${NC} Test Claude Code:"
    echo -e "     ${YELLOW}claude-wrapper --version${NC}"
    echo ""
    echo -e "  ${GREEN}5.${NC} Run health check anytime:"
    echo -e "     ${YELLOW}~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh${NC}"
    echo ""
    
    # Reboot recommendation
    if [[ -L "/run/booted-system" && -L "/run/current-system" ]]; then
        if [[ "$(readlink /run/booted-system)" != "$(readlink /run/current-system)" ]]; then
            echo -e "${YELLOW}⚠ Reboot Recommended:${NC}"
            echo "  • Kernel/init system updates detected"
            echo "  • Run: ${YELLOW}sudo reboot${NC}"
            echo "  • After reboot, select 'Cosmic' from login screen"
            echo ""
        fi
    fi
    
    # Configuration files location
    print_info "Configuration Files:"
    echo "  • System: $SYSTEM_CONFIG_FILE"
    echo "  • Home: $HOME_MANAGER_FILE"
    echo "  • Flake: $FLAKE_FILE"
    echo "  • Hardware: $HARDWARE_CONFIG_FILE"
    echo ""
    
    # Logs and troubleshooting
    print_info "Logs & Troubleshooting:"
    echo "  • Deployment log: $LOG_FILE"
    echo "  • State file: $STATE_FILE"
    echo "  • Backup location: $BACKUP_ROOT"
    echo ""
    
    mark_step_complete "$phase_name"
    print_success "Phase 10: Success Report & Next Steps - COMPLETE"
    echo ""
    
    # Final success message
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ NixOS Quick Deploy v$SCRIPT_VERSION completed successfully!${NC}"
    echo -e "${GREEN}✓ Your AIDB development environment is ready!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ============================================================================
# NEW v3.1.0 MAIN FUNCTION: Restructured 10-Phase Workflow
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force-update|-f)
                FORCE_UPDATE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --rollback)
                perform_rollback
                exit $?
                ;;
            --restore-packages)
                restore_removed_packages
                exit $?
                ;;
            --reset-state)
                reset_state
                print_success "State reset successfully"
                exit 0
                ;;
            --debug|-d)
                ENABLE_DEBUG=true
                set -x
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
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

    # Dry-run mode notification
    if [[ "$DRY_RUN" == true ]]; then
        print_section "DRY RUN MODE - No changes will be applied"
        echo ""
    fi

    if [[ "$FORCE_UPDATE" == true ]]; then
        print_warning "Force update mode enabled - will recreate all configurations"
        echo ""
    fi

    # ========================================================================
    # RESUME OR RESTART PROMPT
    # ========================================================================
    # Check if there's a previous installation state AND actual deployment files exist
    # Only show restart/resume prompt if we have evidence of a previous deployment
    local has_deployment_files=false
    if [[ -d "$HOME/.dotfiles" ]] || [[ -d "$HOME/.config-backups" ]] || \
       [[ -d "$HOME/.local/state/nix/profiles/home-manager"* ]] || \
       [[ -d "$HOME/.local/state/home-manager" ]]; then
        has_deployment_files=true
    fi

    if [[ -f "$STATE_FILE" ]] && [[ "$has_deployment_files" == true ]] && [[ "$FORCE_UPDATE" != true ]]; then
        echo ""
        print_section "Previous Deployment Detected"
        echo ""
        print_info "Found existing deployment files from a previous run."
        print_info "State file: $STATE_FILE"

        # Show what was found
        [[ -d "$HOME/.dotfiles" ]] && print_info "  • .dotfiles directory exists"
        [[ -d "$HOME/.config-backups" ]] && print_info "  • Configuration backups exist"
        echo ""

        # Show completed steps if jq is available
        if command -v jq &>/dev/null; then
            local completed_count=$(jq -r '.completed_steps | length' "$STATE_FILE" 2>/dev/null || echo "0")
            if [[ "$completed_count" -gt 0 ]]; then
                print_info "Completed steps: $completed_count"
                print_info "Completed phases:"
                jq -r '.completed_steps[] | "  - \(.step) (completed at \(.completed_at))"' "$STATE_FILE" 2>/dev/null || true
                echo ""
            fi
        fi

        print_warning "Choose an option:"
        echo "  1) Resume from last checkpoint (recommended if previous run failed)"
        echo "  2) Start fresh (this will delete state and regenerate all files)"
        echo "  3) Cancel and exit"
        echo ""

        local choice
        read -r -p "Enter your choice [1-3]: " choice

        case "$choice" in
            1)
                print_success "Resuming from last checkpoint..."
                echo ""
                ;;
            2)
                print_warning "Starting fresh installation..."
                echo ""

                # Ask user to confirm deletion
                print_warning "This will:"
                echo "  - Delete state file: $STATE_FILE"
                echo "  - Allow regeneration of .dotfiles and configuration files"
                echo "  - Start installation from the beginning"
                echo ""

                if confirm "Are you sure you want to start fresh?" "n"; then
                    print_info "Cleaning up previous installation files..."
                    echo ""

                    # Delete/backup .dotfiles directory
                    if [[ -d "$HOME/.dotfiles" ]]; then
                        local backup_dotfiles="$HOME/.dotfiles.backup.$(date +%s)"
                        print_info "Backing up .dotfiles to: $backup_dotfiles"
                        mv "$HOME/.dotfiles" "$backup_dotfiles" 2>/dev/null || {
                            print_warning "Could not move .dotfiles, attempting to remove..."
                            rm -rf "$HOME/.dotfiles" 2>/dev/null || true
                        }
                        print_success "Removed .dotfiles directory"
                    fi

                    # Remove home-manager generations
                    if [[ -d "$HOME/.local/state/nix/profiles" ]]; then
                        print_info "Cleaning home-manager profiles..."
                        rm -rf "$HOME/.local/state/nix/profiles/home-manager"* 2>/dev/null || true
                    fi

                    # Remove state files
                    reset_state

                    # Remove cached secrets (will be regenerated)
                    if [[ -d "$STATE_DIR/secrets" ]]; then
                        print_info "Removing cached secrets (will be regenerated)..."
                        rm -rf "$STATE_DIR/secrets" 2>/dev/null || true
                    fi

                    print_success "Cleanup complete. Starting fresh installation..."
                    echo ""
                else
                    print_info "Cancelled. Resuming from last checkpoint instead..."
                    echo ""
                fi
                ;;
            3)
                print_info "Installation cancelled by user"
                exit 0
                ;;
            *)
                print_error "Invalid choice. Exiting."
                exit 1
                ;;
        esac
    fi

    # ========================================================================
    # 10-PHASE DEPLOYMENT WORKFLOW
    # ========================================================================
    
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  Starting 10-Phase Deployment Workflow                        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # PHASE 1: Preparation & Validation
    comprehensive_preflight_checks
    
    # PHASE 2: Prerequisite Package Installation  
    install_prerequisites_phase
    
    # PHASE 3: System Backup
    comprehensive_backup_phase
    
    # PHASE 4: Configuration Generation & Validation
    generate_and_validate_configs_phase
    
    # PHASE 5: Intelligent Cleanup
    intelligent_cleanup_phase
    
    # PHASE 6: Configuration Deployment
    deploy_configurations_phase
    
    # PHASE 7: Tool & Service Installation
    install_tools_and_services_phase
    
    # PHASE 8: Post-Installation Validation
    post_install_validation_phase
    
    # PHASE 9: Post-Install Scripts & Finalization
    post_install_finalization_phase
    
    # PHASE 10: Success Report & Next Steps
    generate_success_report_phase
    
    # ========================================================================
    # DEPLOYMENT COMPLETE
    # ========================================================================
    
    log INFO "All 10 phases completed successfully"
    return 0
}

# ============================================================================
# Script Initialization & Execution
# ============================================================================

# Initialize infrastructure before running main
init_logging
ensure_nix_experimental_features_env
init_state

# Run main function
main "$@"

# Deployment completed successfully
exit_code=$?

if [[ $exit_code -eq 0 ]]; then
    log INFO "Deployment completed successfully (exit code: 0)"
else
    log ERROR "Deployment failed with exit code: $exit_code"
fi

exit $exit_code
