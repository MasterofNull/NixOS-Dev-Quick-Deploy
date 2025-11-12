#!/usr/bin/env bash
#
# Common Utility Functions
# Purpose: Shared helper functions used throughout the deployment
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/colors.sh → Color codes
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/validation.sh → Validation functions
#   - lib/retry.sh → Retry logic
#   - lib/state-management.sh → State tracking
#
# Required Variables:
#   - LOG_DIR → Directory for logs
#   - DRY_RUN → Dry run flag
#   - PRIMARY_USER → Primary user name
#   - PRIMARY_RUNTIME_DIR → User runtime directory
#   - PRIMARY_PROFILE_BIN → User profile bin directory
#   - PRIMARY_ETC_PROFILE_BIN → User etc profile bin directory
#   - PRIMARY_LOCAL_BIN → User local bin directory
#
# Exports:
#   - ensure_package_available() → Ensure package is available
#   - ensure_prerequisite_installed() → Install prerequisite package
#   - check_required_packages() → Check all required packages
#   - build_primary_user_path() → Build PATH for primary user
#   - run_as_primary_user() → Run command as primary user
#   - detect_gpu_and_cpu() → Detect GPU and CPU hardware
#   - flatpak_cli_available() → Check if flatpak is available
#   - (Many more utility functions...)
#
# ============================================================================

# ============================================================================
# Podman diagnostics state
# ============================================================================

declare -a PODMAN_STORAGE_WARNINGS=()
declare -a PODMAN_STORAGE_ERRORS=()
OVERLAY_METACOPY_SUPPORTED_CACHE=""

extract_storage_driver_from_conf() {
    local conf_path="$1"

    if [[ -z "$conf_path" || ! -r "$conf_path" ]]; then
        return 1
    fi

    local parsed_driver
    parsed_driver=$(awk -F= '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*driver[[:space:]]*=/ {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
            gsub(/"/, "", $2)
            gsub(/;.*/, "", $2)
            print $2
            exit
        }
    ' "$conf_path" 2>/dev/null || true)

    if [[ -n "$parsed_driver" ]]; then
        printf '%s' "$parsed_driver"
        return 0
    fi

    return 1
}

# ============================================================================
# Package Management Functions
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

    if [[ "${IMPERATIVE_INSTALLS_ALLOWED:-false}" != "true" ]]; then
        case "$priority" in
            CRITICAL)
                print_error "$description not found and imperative installs are disabled. Declare it in configuration.nix or home.nix and rerun."
                ;;
            IMPORTANT)
                print_warning "$description not found and imperative installs are disabled. Add it to configuration.nix or home.nix."
                ;;
            OPTIONAL)
                print_info "$description not found and imperative installs are disabled. Add it declaratively if desired."
                ;;
        esac
        log INFO "Skipping imperative installation for $cmd because IMPERATIVE_INSTALLS_ALLOWED is not true"
        return 1
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

    if [[ "${IMPERATIVE_INSTALLS_ALLOWED:-false}" != "true" ]]; then
        print_error "$description cannot be installed automatically because imperative installs are disabled. Declare it in configuration.nix or home.nix."
        log INFO "Skipping nix-env install for $cmd because IMPERATIVE_INSTALLS_ALLOWED is not true"
        return 1
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
    fi

    # which - Command location (used in multiple places)
    if ! ensure_package_available "which" "which" "IMPORTANT" "which (command locator)"; then
        MISSING_IMPORTANT+=("which")
    fi

    # readlink - Path resolution (used for symlink following)
    if ! ensure_package_available "readlink" "coreutils" "IMPORTANT" "readlink (path resolver)"; then
        MISSING_IMPORTANT+=("coreutils")
    fi

    # timeout - Command timeouts (used for service checks)
    if ! ensure_package_available "timeout" "coreutils" "IMPORTANT" "timeout (command timeout utility)"; then
        MISSING_IMPORTANT+=("coreutils (timeout)")
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

# ============================================================================
# User & Path Management
# ============================================================================

build_primary_user_path() {
    local -a path_parts=()

    local primary_profile_bin="${PRIMARY_PROFILE_BIN:-${PRIMARY_HOME:-$HOME}/.nix-profile/bin}"
    local primary_etc_profile_bin="${PRIMARY_ETC_PROFILE_BIN:-/etc/profiles/per-user/${PRIMARY_USER:-$USER}/bin}"
    local primary_local_bin="${PRIMARY_LOCAL_BIN:-${PRIMARY_HOME:-$HOME}/.local/bin}"
    local primary_npm_bin="${PRIMARY_NPM_BIN:-${PRIMARY_HOME:-$HOME}/.npm-global/bin}"

    if [[ -d "$primary_profile_bin" ]]; then
        path_parts+=("$primary_profile_bin")
    fi

    if [[ -d "$primary_etc_profile_bin" ]]; then
        path_parts+=("$primary_etc_profile_bin")
    fi

    if [[ -n "$primary_local_bin" ]]; then
        install -d -m 755 "$primary_local_bin" >/dev/null 2>&1 || true
        path_parts+=("$primary_local_bin")
    fi

    if [[ -n "$primary_npm_bin" ]]; then
        install -d -m 755 "$primary_npm_bin" >/dev/null 2>&1 || true
        path_parts+=("$primary_npm_bin")
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

synchronize_primary_user_path() {
    local combined_path
    combined_path=$(build_primary_user_path)
    if [[ -n "$combined_path" ]]; then
        export PATH="$combined_path"
    fi
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

    if [[ -n "${NPM_CONFIG_PREFIX:-}" ]]; then
        env_args+=("NPM_CONFIG_PREFIX=$NPM_CONFIG_PREFIX")
    fi

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

resolve_user_runtime_directory() {
    local target_user="$1"

    if [[ -z "$target_user" ]]; then
        return 1
    fi

    if [[ -n "$PRIMARY_USER" && -n "$PRIMARY_RUNTIME_DIR" && "$target_user" == "$PRIMARY_USER" ]]; then
        printf '%s' "$PRIMARY_RUNTIME_DIR"
        return 0
    fi

    local user_uid=""

    if command -v getent >/dev/null 2>&1; then
        user_uid=$(getent passwd "$target_user" 2>/dev/null | cut -d: -f3)
    fi

    if [[ -z "$user_uid" ]]; then
        user_uid=$(id -u "$target_user" 2>/dev/null || echo "")
    fi

    if [[ -z "$user_uid" ]]; then
        return 1
    fi

    local candidate="/run/user/$user_uid"
    if [[ -d "$candidate" ]]; then
        printf '%s' "$candidate"
        return 0
    fi

    return 1
}

run_as_user() {
    local user="$1"
    shift || true
    local -a cmd=("$@")

    if [[ ${#cmd[@]} -eq 0 ]]; then
        return 1
    fi

    local -a env_args=("PATH=$PATH")

    local runtime_dir=""
    if [[ -n "$user" ]]; then
        runtime_dir=$(resolve_user_runtime_directory "$user" 2>/dev/null || echo "")
    fi

    if [[ -z "$runtime_dir" && -n "$XDG_RUNTIME_DIR" ]]; then
        if command -v stat >/dev/null 2>&1; then
            local runtime_owner=""
            runtime_owner=$(stat -c '%U' "$XDG_RUNTIME_DIR" 2>/dev/null || echo "")
            if [[ -n "$runtime_owner" && -n "$user" && "$runtime_owner" == "$user" ]]; then
                runtime_dir="$XDG_RUNTIME_DIR"
            fi
        fi
    fi

    if [[ -n "$runtime_dir" ]]; then
        env_args+=("XDG_RUNTIME_DIR=$runtime_dir")
        if [[ -S "$runtime_dir/bus" ]]; then
            env_args+=("DBUS_SESSION_BUS_ADDRESS=unix:path=$runtime_dir/bus")
        fi
    fi

    if [[ -z "$user" ]]; then
        if (( ${#env_args[@]} > 0 )); then
            env "${env_args[@]}" "${cmd[@]}"
        else
            "${cmd[@]}"
        fi
        return $?
    fi

    local current_user
    current_user=$(id -un 2>/dev/null || echo "")

    if [[ -n "$current_user" && "$current_user" == "$user" ]]; then
        if (( ${#env_args[@]} > 0 )); then
            env "${env_args[@]}" "${cmd[@]}"
        else
            "${cmd[@]}"
        fi
        return $?
    fi

    if command -v sudo >/dev/null 2>&1; then
        if (( ${#env_args[@]} > 0 )); then
            sudo -H -u "$user" env "${env_args[@]}" "${cmd[@]}"
        else
            sudo -H -u "$user" "${cmd[@]}"
        fi
        return $?
    fi

    if command -v runuser >/dev/null 2>&1; then
        if (( ${#env_args[@]} > 0 )); then
            runuser -u "$user" -- env "${env_args[@]}" "${cmd[@]}"
        else
            runuser -u "$user" -- "${cmd[@]}"
        fi
        return $?
    fi

    return 1
}

# ============================================================================
# Hardware Detection
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

    # Heuristic for zswap pool usage (percentage of RAM kept for compressed pages)
    local zswap_percent=20
    if [[ "$TOTAL_RAM_GB" =~ ^[0-9]+$ ]]; then
        if (( TOTAL_RAM_GB >= 64 )); then
            zswap_percent=15
        elif (( TOTAL_RAM_GB >= 16 )); then
            zswap_percent=20
        elif (( TOTAL_RAM_GB >= 8 )); then
            zswap_percent=25
        else
            zswap_percent=30
        fi
    fi

    ZSWAP_MAX_POOL_PERCENT="$zswap_percent"
    print_info "Zswap pool limit: ${ZSWAP_MAX_POOL_PERCENT}% of RAM"

    select_zswap_memory_pool

    echo ""
    print_success "Hardware detection complete"
    echo ""
}

# ==========================================================================
# Container storage assessment
# ==========================================================================

reset_podman_storage_messages() {
    PODMAN_STORAGE_WARNINGS=()
    PODMAN_STORAGE_ERRORS=()
}

record_podman_storage_warning() {
    local message="$1"

    if [[ -z "$message" ]]; then
        return 0
    fi

    local existing
    for existing in "${PODMAN_STORAGE_WARNINGS[@]}"; do
        if [[ "$existing" == "$message" ]]; then
            return 0
        fi
    done

    PODMAN_STORAGE_WARNINGS+=("$message")
}

record_podman_storage_error() {
    local message="$1"

    if [[ -z "$message" ]]; then
        return 0
    fi

    local existing
    for existing in "${PODMAN_STORAGE_ERRORS[@]}"; do
        if [[ "$existing" == "$message" ]]; then
            return 0
        fi
    done

    PODMAN_STORAGE_ERRORS+=("$message")
}

repair_system_storage_conf_driver() {
    local desired_driver="$1"
    local current_driver="$2"
    local config_path="/etc/containers/storage.conf"
    local central_backup_path=""
    local central_backup_status=""

    PODMAN_SYSTEM_STORAGE_REPAIR_NOTE=""

    if [[ "${PODMAN_AUTO_REPAIR_SYSTEM_STORAGE_CONF:-true}" != true ]]; then
        return 1
    fi

    if [[ -z "$desired_driver" || ! -e "$config_path" ]]; then
        return 1
    fi

    if [[ -n "${BACKUP_ROOT:-}" ]] && [[ -n "${BACKUP_MANIFEST:-}" ]]; then
        if [[ "$(type -t centralized_backup 2>/dev/null)" == "function" ]]; then
            if centralized_backup "$config_path" "${config_path} (pre-driver repair)" >/dev/null 2>&1; then
                local sanitized_path
                sanitized_path="${config_path#/}"
                central_backup_path="${BACKUP_ROOT%/}/${sanitized_path}"
                central_backup_status="Archived pre-repair copy under ${central_backup_path}."
                log INFO "Backed up ${config_path} to ${central_backup_path} before repair"
            else
                central_backup_status="Failed to archive ${config_path} under ${BACKUP_ROOT}."
                log WARNING "Failed to archive ${config_path} under ${BACKUP_ROOT}"
            fi
        fi
    fi

    local python_script
    python_script=$(cat <<'PY'
import os
import re
import shutil
import sys
import tempfile
import time

config_path = sys.argv[1]
desired = sys.argv[2]
current = sys.argv[3] if len(sys.argv) > 3 else ""

if not os.path.exists(config_path):
    sys.stderr.write(f"{config_path} missing; unable to update storage driver to {desired}.\n")
    sys.exit(1)

with open(config_path, "r", encoding="utf-8") as handle:
    original = handle.read()

patterns = [
    re.compile(r'^(\s*driver\s*=\s*")(.*?)(".*)$', re.MULTILINE),
    re.compile(r'^(\s*driver\s*=\s*)(\S+)(.*)$', re.MULTILINE),
]

new_content = None
for pattern in patterns:
    candidate, count = pattern.subn(lambda match: f"{match.group(1)}{desired}{match.group(3)}", original, count=1)
    if count:
        new_content = candidate
        break

if new_content is None:
    sys.stderr.write("Unable to locate driver entry in storage.conf; no changes made.\n")
    sys.exit(1)

timestamp = time.strftime("%Y%m%d%H%M%S")
backup_path = f"{config_path}.bak.{timestamp}"
shutil.copy2(config_path, backup_path)

tmp_fd, tmp_path = tempfile.mkstemp(
    prefix=f"{os.path.basename(config_path)}.tmp.",
    dir=os.path.dirname(config_path) or ".",
    text=True,
)

with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
    handle.write(new_content)

shutil.copystat(config_path, tmp_path, follow_symlinks=False)
os.replace(tmp_path, config_path)

note = f"Patched driver from {current or 'unknown'} to {desired}; backup at {backup_path}."
sys.stdout.write(note)
PY
)

    local python_cmd=(python3)

    if [[ ! -w "$config_path" ]]; then
        local uid
        uid=$(id -u 2>/dev/null || echo "")
        if [[ "${uid:-}" != "0" ]]; then
            if command -v sudo >/dev/null 2>&1; then
                python_cmd=(sudo python3)
            else
                PODMAN_SYSTEM_STORAGE_REPAIR_NOTE="Unable to update ${config_path}; insufficient permissions and sudo not available."
                return 1
            fi
        fi
    fi

    local python_output
    if python_output=$(printf '%s\n' "$python_script" | "${python_cmd[@]}" - "$config_path" "$desired_driver" "$current_driver" 2>&1); then
        if [[ -n "$central_backup_status" ]]; then
            python_output+=" ${central_backup_status}"
        fi
        PODMAN_SYSTEM_STORAGE_REPAIR_NOTE="$python_output"
        return 0
    fi

    if [[ -n "$central_backup_status" ]]; then
        python_output=$(printf '%s\n%s' "$python_output" "$central_backup_status")
    fi
    PODMAN_SYSTEM_STORAGE_REPAIR_NOTE="$python_output"
    return 1
}

resolve_user_home_directory() {
    local target_user="$1"

    if [[ -z "$target_user" ]]; then
        return 1
    fi

    local passwd_entry
    passwd_entry=$(getent passwd "$target_user" 2>/dev/null || true)

    if [[ -n "$passwd_entry" ]]; then
        local home_path
        home_path=$(printf '%s' "$passwd_entry" | cut -d: -f6)
        if [[ -n "$home_path" ]]; then
            printf '%s' "$home_path"
            return 0
        fi
    fi

    if [[ "$target_user" == "${USER:-}" && -n "$HOME" ]]; then
        printf '%s' "$HOME"
        return 0
    fi

    return 1
}

detect_container_storage_backend() {
    reset_podman_storage_messages

    local forced_driver=""
    local forced_source=""
    local default_driver="${DEFAULT_PODMAN_STORAGE_DRIVER:-vfs}"

    if [[ -n "${PODMAN_STORAGE_DRIVER_OVERRIDE:-}" ]]; then
        forced_driver="$PODMAN_STORAGE_DRIVER_OVERRIDE"
        forced_source="PODMAN_STORAGE_DRIVER_OVERRIDE"
    fi

    case "$default_driver" in
        vfs|btrfs|zfs)
            ;;
        ""|auto)
            default_driver="vfs"
            ;;
        *)
            print_warning "DEFAULT_PODMAN_STORAGE_DRIVER=${default_driver} unsupported; falling back to vfs."
            default_driver="vfs"
            ;;
    esac

    if [[ -n "$forced_driver" ]]; then
        case "$forced_driver" in
            vfs|btrfs|zfs)
                ;;
            *)
                print_warning "PODMAN_STORAGE_DRIVER_OVERRIDE=${forced_driver} unsupported; ignoring and reverting to ${default_driver}."
                forced_driver=""
                forced_source=""
                ;;
        esac
    fi

    # Determine which filesystem backs the Podman graphroot so we can
    # automatically select a compatible storage driver.
    local preferred_path="/var/lib/containers"
    local probe_target="$preferred_path"

    if [[ ! -e "$probe_target" ]]; then
        probe_target="/var/lib"
    fi
    if [[ ! -e "$probe_target" ]]; then
        probe_target="/"
    fi

    local fstype=""
    local source=""

    if command -v findmnt >/dev/null 2>&1; then
        fstype=$(findmnt -n -o FSTYPE --target "$probe_target" 2>/dev/null || true)
        source=$(findmnt -n -o SOURCE --target "$probe_target" 2>/dev/null || true)
    fi

    if [[ -z "$fstype" ]] && command -v df >/dev/null 2>&1; then
        local df_line
        df_line=$(df -PT "$probe_target" 2>/dev/null | awk 'NR==2 {print $2 "::" $1}')
        if [[ -n "$df_line" ]]; then
            fstype="${df_line%%::*}"
            source="${df_line##*::}"
        fi
    fi

    if [[ -z "$fstype" ]] && [[ -r /proc/mounts ]]; then
        fstype=$(awk -v target="$probe_target" '$2 == target {print $3; exit}' /proc/mounts 2>/dev/null)
    fi

    if [[ -z "$fstype" ]]; then
        fstype="unknown"
    fi

    CONTAINER_STORAGE_FS_TYPE="$fstype"
    CONTAINER_STORAGE_SOURCE="${source:-unknown}"

    local driver="$default_driver"
    local detail="Detected ${CONTAINER_STORAGE_FS_TYPE} filesystem backing ${probe_target}"
    if [[ -n "$CONTAINER_STORAGE_SOURCE" && "$CONTAINER_STORAGE_SOURCE" != "unknown" ]]; then
        detail+=" (device ${CONTAINER_STORAGE_SOURCE})"
    fi

    local comment=""

    if [[ -n "$forced_driver" ]]; then
        driver="$forced_driver"
        comment="$detail; container storage driver forced via ${forced_source}=${forced_driver}."
    else
        comment="$detail; using ${driver} storage driver by default."
        case "$CONTAINER_STORAGE_FS_TYPE" in
            zfs|zfs_member)
                driver="zfs"
                comment="$detail; overlayfs unsupported so the zfs storage driver will be used."
                ;;
            btrfs)
                driver="btrfs"
                comment="$detail; using Podman's native btrfs storage driver."
                ;;
        esac
    fi

    if [[ "$CONTAINER_STORAGE_FS_TYPE" == "xfs" ]]; then
        local xfs_info_output=""

        if command -v xfs_info >/dev/null 2>&1; then
            xfs_info_output=$(xfs_info "$probe_target" 2>/dev/null || true)
            if [[ -n "$xfs_info_output" && "$xfs_info_output" == *"ftype=0"* ]]; then
                record_podman_storage_error \
                    "XFS volume backing ${probe_target} reports ftype=0; recreate the filesystem with 'mkfs.xfs -n ftype=1' before running Podman."
            elif [[ -z "$xfs_info_output" ]]; then
                record_podman_storage_warning \
                    "Unable to inspect XFS metadata for ${probe_target}; ensure the filesystem was created with ftype=1."
            fi
        else
            record_podman_storage_warning \
                "xfs_info unavailable; manually confirm that the XFS filesystem for ${probe_target} uses ftype=1."
        fi
    elif [[ "$CONTAINER_STORAGE_FS_TYPE" == "tmpfs" ]]; then
        record_podman_storage_error \
            "Detected tmpfs backing ${probe_target}; container storage requires a persistent filesystem."
    fi

    if [[ -n "$forced_driver" ]]; then
        local recommended_driver=""
        case "$CONTAINER_STORAGE_FS_TYPE" in
            zfs|zfs_member)
                recommended_driver="zfs"
                ;;
            btrfs)
                recommended_driver="btrfs"
                ;;
            unknown)
                recommended_driver=""
                ;;
            *)
                recommended_driver="$default_driver"
                ;;
        esac

        if [[ -n "$recommended_driver" && "$forced_driver" != "$recommended_driver" ]]; then
            record_podman_storage_warning \
                "${CONTAINER_STORAGE_FS_TYPE} typically uses the ${recommended_driver} storage driver, but ${forced_source} forces ${forced_driver}. Ensure this override is intentional."
        fi
    fi

    local existing_system_driver=""
    existing_system_driver=$(extract_storage_driver_from_conf \
        "/etc/containers/storage.conf" 2>/dev/null || true)

    if [[ -n "$existing_system_driver" && "$existing_system_driver" != "$driver" ]]; then
        if repair_system_storage_conf_driver "$driver" "$existing_system_driver"; then
            local repair_note="${PODMAN_SYSTEM_STORAGE_REPAIR_NOTE:-}"
            if [[ -n "$repair_note" ]]; then
                print_success "$repair_note"
            else
                print_success "Updated /etc/containers/storage.conf driver from ${existing_system_driver} to ${driver}."
            fi
            PODMAN_SYSTEM_STORAGE_REPAIR_NOTE=""
        else
            record_podman_storage_warning \
                "Existing /etc/containers/storage.conf still sets driver=${existing_system_driver}; regenerate the configuration so it matches ${driver} before the next reboot."

            if [[ -n "${PODMAN_SYSTEM_STORAGE_REPAIR_NOTE:-}" ]]; then
                record_podman_storage_warning "$PODMAN_SYSTEM_STORAGE_REPAIR_NOTE"
            fi
            PODMAN_SYSTEM_STORAGE_REPAIR_NOTE=""
        fi
    fi

    PODMAN_STORAGE_DRIVER="$driver"
    PODMAN_STORAGE_COMMENT="$comment"
    PODMAN_STORAGE_COMMENT=${PODMAN_STORAGE_COMMENT//$'\n'/ }
    PODMAN_STORAGE_COMMENT=${PODMAN_STORAGE_COMMENT//\'/}
    PODMAN_STORAGE_DETECTION_RUN=true

    if [[ -n "$forced_driver" ]]; then
        print_warning "$comment"
    elif [[ "$driver" == "zfs" ]]; then
        print_warning "$comment"
    else
        print_success "$comment"
    fi
}

ensure_gitea_state_directory_ready() {
    if [[ "${GITEA_ENABLE,,}" != "true" ]]; then
        return 0
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        print_error "sudo is required to prepare /var/lib/gitea but is not available."
        return 1
    fi

    local state_root="/var/lib/gitea"
    local -a required_dirs=(
        "$state_root"
        "$state_root/custom"
        "$state_root/custom/conf"
        "$state_root/data"
        "$state_root/log"
    )

    local dir
    for dir in "${required_dirs[@]}"; do
        if ! sudo install -d -m 0750 -o gitea -g gitea "$dir" 2>/dev/null; then
            print_error "Failed to provision Gitea state directory: $dir"
            return 1
        fi
    done

    local app_ini="$state_root/custom/conf/app.ini"
    if [[ ! -f "$app_ini" ]]; then
        if ! sudo touch "$app_ini" 2>/dev/null; then
            print_error "Unable to create $app_ini"
            return 1
        fi
    fi

    if ! sudo chown gitea:gitea "$app_ini" 2>/dev/null || ! sudo chmod 0640 "$app_ini" 2>/dev/null; then
        print_error "Failed to set ownership or permissions on $app_ini"
        return 1
    fi

    return 0
}

verify_podman_storage_cleanliness() {
    local mode="${1:-enforce}"
    local warn_only="false"
    if [[ "$mode" == "--warn-only" ]]; then
        warn_only="true"
    fi

    if [[ "${PODMAN_STORAGE_DETECTION_RUN:-false}" != true ]] \
        && declare -F detect_container_storage_backend >/dev/null 2>&1; then
        detect_container_storage_backend
    fi

    local configured_driver="${PODMAN_STORAGE_DRIVER:-}"
    if [[ -z "$configured_driver" || "$configured_driver" == "overlay" ]]; then
        return 0
    fi

    local user_cleanup_hint="podman system reset --force && rm -rf ~/.local/share/containers/storage ~/.local/share/containers/cache"
    local system_cleanup_hint="sudo podman system reset --force && sudo rm -rf /var/lib/containers/storage"

    local -a overlay_paths=()
    local system_overlay="/var/lib/containers/storage/overlay"
    local user_root="${PRIMARY_HOME:-$HOME}/.local/share/containers/storage/overlay"

    if [[ -d "$system_overlay" ]] && find "$system_overlay" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
        overlay_paths+=("$system_overlay")
    fi

    if [[ -d "$user_root" ]] && find "$user_root" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
        overlay_paths+=("$user_root")
    fi

    if (( ${#overlay_paths[@]} > 0 )); then
        local joined_paths
        joined_paths=$(printf '%s, ' "${overlay_paths[@]}")
        joined_paths=${joined_paths%%, }

        if [[ "$warn_only" == "true" ]]; then
            print_warning "Detected legacy overlay data under: ${joined_paths}. Clean the stores before applying the declarative Podman (driver=${configured_driver}) configuration."
            print_detail "User store cleanup: ${user_cleanup_hint}"
            print_detail "System store cleanup: ${system_cleanup_hint}"
            print_detail "Refer to docs/ROOTLESS_PODMAN.md for full instructions."
            return 0
        fi

        print_error "Podman storage check failed: legacy overlay data still exists under ${joined_paths} while the generated configuration uses driver '${configured_driver}'."
        print_detail "User cleanup: ${user_cleanup_hint}"
        print_detail "System cleanup: ${system_cleanup_hint}"
        print_detail "See docs/ROOTLESS_PODMAN.md for recovery steps, then rerun the deployer."
        return 1
    fi

    local -a driver_probe_cmd=()
    if command -v podman >/dev/null 2>&1; then
        local current_uid=""
        current_uid=$(id -u 2>/dev/null || echo "")
        if [[ "$current_uid" == "0" ]]; then
            driver_probe_cmd=(podman info --format '{{.Store.GraphDriverName}}')
        elif command -v sudo >/dev/null 2>&1; then
            driver_probe_cmd=(sudo podman info --format '{{.Store.GraphDriverName}}')
        fi
    fi

    if (( ${#driver_probe_cmd[@]} > 0 )); then
        local driver_probe_output=""
        if ! driver_probe_output=$("${driver_probe_cmd[@]}" 2>&1); then
            local probe_msg="Failed to probe system Podman storage backend: ${driver_probe_output:-unknown error}."
            if [[ "$warn_only" == "true" ]]; then
                print_warning "$probe_msg"
                print_detail "User cleanup: ${user_cleanup_hint}"
                print_detail "System cleanup: ${system_cleanup_hint}"
                print_detail "Refer to docs/ROOTLESS_PODMAN.md for recovery steps."
                return 0
            fi

            print_error "$probe_msg"
            print_detail "User cleanup: ${user_cleanup_hint}"
            print_detail "System cleanup: ${system_cleanup_hint}"
            print_detail "See docs/ROOTLESS_PODMAN.md for remediation guidance."
            return 1
        fi

        local active_driver
        active_driver=$(printf '%s' "$driver_probe_output" | tr -d '\r' | tail -n 1)
        active_driver=${active_driver//[$'\t ']/}

        if [[ -z "$active_driver" ]]; then
            if [[ "$warn_only" == "true" ]]; then
                print_warning "Podman storage probe returned an empty driver result. Clean the stores before rerunning the deployer."
                print_detail "User cleanup: ${user_cleanup_hint}"
                print_detail "System cleanup: ${system_cleanup_hint}"
                return 0
            fi

            print_error "Podman storage probe returned an empty driver result. Clean the stores before rerunning the deployer."
            print_detail "User cleanup: ${user_cleanup_hint}"
            print_detail "System cleanup: ${system_cleanup_hint}"
            print_detail "See docs/ROOTLESS_PODMAN.md for recovery steps."
            return 1
        fi

        if [[ "$active_driver" != "$configured_driver" ]]; then
            local mismatch_msg="Podman storage driver mismatch: configuration expects '${configured_driver}' but the current store reports '${active_driver}'."
            if [[ "$warn_only" == "true" ]]; then
                print_warning "$mismatch_msg"
                print_detail "User cleanup: ${user_cleanup_hint}"
                print_detail "System cleanup: ${system_cleanup_hint}"
                print_detail "Refer to docs/ROOTLESS_PODMAN.md for the reset procedure."
                return 0
            fi

            print_error "$mismatch_msg"
            print_detail "User cleanup: ${user_cleanup_hint}"
            print_detail "System cleanup: ${system_cleanup_hint}"
            print_detail "See docs/ROOTLESS_PODMAN.md for the cleanup sequence, then rerun the deployer."
            return 1
        fi
    fi

    return 0
}

declare -ag NQD_STOPPED_SYSTEM_UNITS=()
declare -ag NQD_STOPPED_USER_UNITS=()

stop_managed_services_before_switch() {
    NQD_STOPPED_SYSTEM_UNITS=()
    NQD_STOPPED_USER_UNITS=()

    local -a system_units=(
        "qdrant.service"
        "huggingface-tgi.service"
        "ollama.service"
        "gitea.service"
        "podman.service"
        "podman.socket"
        "podman-auto-update.service"
        "podman-restart.service"
        "podman-clean-transient.service"
    )

    print_info "Pausing managed services before system switch..."
    local unit
    for unit in "${system_units[@]}"; do
        if sudo systemctl is-active --quiet "$unit" >/dev/null 2>&1; then
            if sudo systemctl stop "$unit" >/dev/null 2>&1; then
                NQD_STOPPED_SYSTEM_UNITS+=("$unit")
                print_detail "Stopped $unit"
            else
                print_warning "Failed to stop $unit; continue with caution."
            fi
        fi
    done

    if systemctl --user --version >/dev/null 2>&1; then
        local -a user_podman_units=()
        local -a user_network_units=()
        mapfile -t user_podman_units < <(systemctl --user list-units --state=active 'podman-*.service' --no-legend --no-pager 2>/dev/null | awk '{print $1}') || true
        mapfile -t user_network_units < <(systemctl --user list-units --state=active 'podman-*.network' --no-legend --no-pager 2>/dev/null | awk '{print $1}') || true
        for unit in "${user_podman_units[@]}" "${user_network_units[@]}"; do
            if [[ -n "$unit" ]] && systemctl --user stop "$unit" >/dev/null 2>&1; then
                NQD_STOPPED_USER_UNITS+=("$unit")
                print_detail "Stopped user unit $unit"
            fi
        done
        local -a optional_user_units=(
            "gitea-dev.service"
            "jupyter-lab.service"
        )
        for unit in "${optional_user_units[@]}"; do
            if systemctl --user is-active --quiet "$unit" >/dev/null 2>&1; then
                if systemctl --user stop "$unit" >/dev/null 2>&1; then
                    NQD_STOPPED_USER_UNITS+=("$unit")
                    print_detail "Stopped user unit $unit"
                fi
            fi
        done
    fi
}

restart_managed_services_after_switch() {
    if (( ${#NQD_STOPPED_SYSTEM_UNITS[@]} == 0 && ${#NQD_STOPPED_USER_UNITS[@]} == 0 )); then
        return 0
    fi

    print_info "Reinitializing services paused for the system switch..."
    local unit
    for unit in "${NQD_STOPPED_SYSTEM_UNITS[@]}"; do
        if sudo systemctl start "$unit" >/dev/null 2>&1; then
            print_detail "Restarted $unit"
        else
            print_warning "Failed to restart $unit; check systemctl status manually."
        fi
    done
    if (( ${#NQD_STOPPED_USER_UNITS[@]} > 0 )) && systemctl --user --version >/dev/null 2>&1; then
        for unit in "${NQD_STOPPED_USER_UNITS[@]}"; do
            if systemctl --user start "$unit" >/dev/null 2>&1; then
                print_detail "Restarted user unit $unit"
            else
                print_warning "Failed to restart user unit $unit"
            fi
        done
    fi
    NQD_STOPPED_SYSTEM_UNITS=()
    NQD_STOPPED_USER_UNITS=()
}

auto_remediate_podman_storage() {
    local status=0
    print_info "Attempting automated Podman storage cleanup..."

    if command -v findmnt >/dev/null 2>&1; then
        local target
        while IFS= read -r target; do
            if [[ -n "$target" ]]; then
                if sudo umount -lf "$target" >/dev/null 2>&1; then
                    print_detail "Detached stale mount $target"
                else
                    print_warning "Failed to detach $target"
                    status=1
                fi
            fi
        done < <(sudo findmnt -rn -t overlay -o TARGET 2>/dev/null | grep -E '^/var/lib/containers/storage/overlay/.+/merged$' || true)
    fi

    if command -v podman >/dev/null 2>&1; then
        podman system reset --force >/dev/null 2>&1 || status=1
        rm -rf "${HOME}/.local/share/containers/storage" "${HOME}/.local/share/containers/cache" >/dev/null 2>&1 || true
    fi

    if command -v sudo >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
        sudo podman system reset --force >/dev/null 2>&1 || status=1
    fi

    if sudo test -d /var/lib/containers/storage >/dev/null 2>&1; then
        sudo rm -rf /var/lib/containers/storage >/dev/null 2>&1 || status=1
    fi

    return $status
}

ensure_podman_storage_ready() {
    if verify_podman_storage_cleanliness; then
        return 0
    fi

    print_warning "Legacy Podman overlay data detected; running automated remediation..."
    local remediation_status=0
    if ! auto_remediate_podman_storage; then
        remediation_status=$?
        print_warning "Automatic Podman storage remediation reported errors; attempting verification anyway."
    fi

    if verify_podman_storage_cleanliness; then
        print_success "Podman storage cleaned successfully."
        return 0
    fi

    if (( remediation_status != 0 )); then
        print_error "Automatic Podman storage remediation reported errors and the health check still fails; manual cleanup required."
    else
        print_error "Automatic Podman storage remediation completed but the health check still fails; manual cleanup required."
    fi

    return 1
}

resolve_subid_entry() {
    local database="$1"
    local target_user="$2"

    case "$database" in
        subuid|subgid)
            ;;
        *)
            return 1
            ;;
    esac

    local entry=""

    if command -v getent >/dev/null 2>&1; then
        if entry=$(getent "$database" "$target_user" 2>/dev/null); then
            if [[ -n "$entry" ]]; then
                printf '%s\n' "$entry"
                return 0
            fi
        fi
    fi

    local fallback_path="/etc/${database}"
    if [[ -r "$fallback_path" ]]; then
        entry=$(awk -F: -v user="$target_user" '$1 == user {print $0}' "$fallback_path")
        if [[ -n "$entry" ]]; then
            printf '%s\n' "$entry"
            return 0
        fi
    fi

    return 1
}

run_rootless_podman_diagnostics() {
    local target_user="${1:-${PRIMARY_USER:-$USER}}"
    local status=0

    if [[ "${PODMAN_STORAGE_DETECTION_RUN:-false}" != true ]]; then
        detect_container_storage_backend
    fi

    local effective_driver="${PODMAN_STORAGE_DRIVER:-${DEFAULT_PODMAN_STORAGE_DRIVER:-vfs}}"
    print_info "Podman storage backend: ${PODMAN_STORAGE_DRIVER:-unknown} on ${CONTAINER_STORAGE_FS_TYPE:-unknown}"

    if [[ "$effective_driver" == "overlay" ]]; then
        print_error "Overlay storage driver support has been removed; rerun the deployer with DEFAULT_PODMAN_STORAGE_DRIVER=vfs."
        status=1
    fi

    local sysctl_value
    sysctl_value=$(sysctl -n kernel.unprivileged_userns_clone 2>/dev/null || cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "")
    if [[ "$sysctl_value" == "1" ]]; then
        print_success "kernel.unprivileged_userns_clone=1"
    else
        print_error "kernel.unprivileged_userns_clone is ${sysctl_value:-unset}; rootless Podman requires it set to 1."
        status=1
    fi

    if command -v podman >/dev/null 2>&1; then
        print_success "Podman CLI available: $(command -v podman)"
    else
        print_warning "Podman CLI not found on PATH; ensure virtualisation.podman.enable is applied."
    fi

    if command -v slirp4netns >/dev/null 2>&1; then
        print_success "slirp4netns available: $(command -v slirp4netns)"
    else
        print_warning "slirp4netns not found; rootless container networking may be degraded."
    fi

    local subuid_entry=""
    if subuid_entry=$(resolve_subid_entry subuid "$target_user"); then
        print_success "Subordinate UID range: $subuid_entry"
    else
        print_error "No subordinate UID range configured for ${target_user}; enable autoSubUidGidRange or define users.users.${target_user}.subUidRanges."
        status=1
    fi

    local subgid_entry=""
    if subgid_entry=$(resolve_subid_entry subgid "$target_user"); then
        print_success "Subordinate GID range: $subgid_entry"
    else
        print_error "No subordinate GID range configured for ${target_user}; enable autoSubUidGidRange or define users.users.${target_user}.subGidRanges."
        status=1
    fi

    local message
    for message in "${PODMAN_STORAGE_WARNINGS[@]}"; do
        print_warning "$message"
    done
    for message in "${PODMAN_STORAGE_ERRORS[@]}"; do
        print_error "$message"
        status=1
    done

    return $status
}





# ===========================================================================
# Filesystem helpers
# ===========================================================================

# Determine the filesystem type for a given path. Falls back to "unknown"
# when detection fails so callers can decide how to react.
get_filesystem_type_for_path() {
    local probe_path="$1"
    local fallback="${2:-unknown}"

    if [[ -z "$probe_path" ]]; then
        echo "$fallback"
        return 1
    fi

    local target="$probe_path"

    # Walk up the directory tree until we find an existing path. This allows
    # callers to pass paths that may not exist yet (e.g., future storage roots).
    while [[ ! -e "$target" ]]; do
        local parent
        parent=$(dirname "$target")

        if [[ -z "$parent" || "$parent" == "$target" ]]; then
            target="/"
            break
        fi

        target="$parent"
    done

    local fstype=""

    if command -v findmnt >/dev/null 2>&1; then
        fstype=$(findmnt -n -o FSTYPE --target "$target" 2>/dev/null || true)
    fi

    if [[ -z "$fstype" ]] && [[ -r /proc/mounts ]]; then
        fstype=$(awk -v target="$target" '$2 == target {print $3; exit}' /proc/mounts 2>/dev/null)
    fi

    if [[ -z "$fstype" ]] && command -v df >/dev/null 2>&1; then
        fstype=$(df -PT "$target" 2>/dev/null | awk 'NR==2 {print $2}' 2>/dev/null)
    fi

    if [[ -z "$fstype" ]]; then
        echo "$fallback"
        return 1
    fi

    echo "$fstype"
    return 0
}

# Determine the ZFS dataset backing a given path. Returns the dataset name
# or an empty string when the path is not on ZFS or the command is
# unavailable. Prefers the dataset with the longest matching mountpoint so
# nested datasets resolve correctly.
get_zfs_dataset_for_path() {
    local probe_path="$1"

    if [[ -z "$probe_path" ]] || ! command -v zfs >/dev/null 2>&1; then
        return 1
    fi

    local best_dataset=""
    local best_mount=""

    while IFS=$'\t' read -r dataset mountpoint; do
        if [[ -z "$dataset" || -z "$mountpoint" ]]; then
            continue
        fi

        case "$mountpoint" in
            -|legacy)
                continue
                ;;
        esac

        if [[ "$probe_path" == "$mountpoint" || "$probe_path" == "$mountpoint"/* ]]; then
            if (( ${#mountpoint} > ${#best_mount} )); then
                best_dataset="$dataset"
                best_mount="$mountpoint"
            fi
        fi
    done < <(zfs list -H -o name,mountpoint 2>/dev/null)

    if [[ -n "$best_dataset" ]]; then
        printf '%s\n' "$best_dataset"
        return 0
    fi

    return 1
}

# ==========================================================================
# Kernel feature detection helpers
# ==========================================================================

kernel_module_available() {
    local module="$1"

    if [[ -z "$module" ]]; then
        return 1
    fi

    # Module already loaded
    if [[ -d "/sys/module/$module" ]]; then
        return 0
    fi

    # Prefer modprobe's dry-run because it accounts for builtin modules, aliases,
    # and compressed module formats.
    if command -v modprobe >/dev/null 2>&1; then
        if modprobe --dry-run --first-time "$module" >/dev/null 2>&1; then
            return 0
        fi
    fi

    local uname_r
    uname_r=$(uname -r 2>/dev/null || echo "")
    if [[ -n "$uname_r" ]]; then
        # Check for builtin modules recorded by the running kernel.
        if grep -qw "$module" "/lib/modules/${uname_r}/modules.builtin" 2>/dev/null; then
            return 0
        fi
        if grep -qw "$module" "/lib/modules/${uname_r}/modules.builtin.modinfo" 2>/dev/null; then
            return 0
        fi

        # Look for loadable modules (including compressed .ko files).
        if find "/lib/modules/${uname_r}" \( -name "${module}.ko" -o -name "${module}.ko.*" \) -print -quit 2>/dev/null |
            grep -q .; then
            return 0
        fi
    fi

    if command -v modinfo >/dev/null 2>&1; then
        if modinfo "$module" >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

select_zswap_memory_pool() {
    # Decide which zswap zpool implementation to use based on kernel support.
    # Preference order matches upstream guidance: z3fold → zbud → zsmalloc.
    local -a zpools=("z3fold" "zbud" "zsmalloc")
    local selected=""

    for candidate in "${zpools[@]}"; do
        if kernel_module_available "$candidate"; then
            selected="$candidate"
            break
        fi
    done

    if [[ -z "$selected" ]]; then
        selected="zsmalloc"
    fi

    if [[ "$selected" != "${ZSWAP_ZPOOL:-}" ]]; then
        ZSWAP_ZPOOL="$selected"
        print_info "Detected zswap zpool support: using ${ZSWAP_ZPOOL}."
    else
        print_info "Using previously selected zswap zpool: ${ZSWAP_ZPOOL}."
    fi
}

# ===========================================================================
# Swap Sizing Helpers
# ===========================================================================

suggest_hibernation_swap_size() {
    # Compute a suggested swap size (in GiB) suitable for hibernation when using
    # zswap-backed swap. Returns a conservative value of roughly 125% of RAM with
    # an additional buffer to accommodate kernel overhead.
    # Args: $1 = total RAM in GiB (integer)
    local ram_gb="${1:-0}"

    if ! [[ "$ram_gb" =~ ^[0-9]+$ ]] || (( ram_gb <= 0 )); then
        echo 8
        return
    fi

    local extra_buffer=$(( ram_gb + 4 ))
    local scaled=$(( (ram_gb * 125 + 99) / 100 ))  # ceil(ram * 1.25)

    if (( scaled > extra_buffer )); then
        echo "$scaled"
    else
        echo "$extra_buffer"
    fi
}

calculate_active_swap_total_gb() {
    # Sum active swap devices (in GiB, rounded up) using /proc/swaps.
    if [[ ! -r /proc/swaps ]]; then
        echo 0
        return
    fi

    local total_kib=0
    local filename type size_kib used_kib priority

    while read -r filename type size_kib used_kib priority; do
        if [[ "$filename" == "Filename" ]]; then
            continue
        fi
        total_kib=$(( total_kib + size_kib ))
    done < /proc/swaps

    if (( total_kib <= 0 )); then
        echo 0
        return
    fi

    local gib=$(( (total_kib + 1024 * 1024 - 1) / (1024 * 1024) ))
    echo "$gib"
}

load_cached_hibernation_swap_size() {
    local cached_value=""

    if [[ -n "${HIBERNATION_SWAP_SIZE_GB:-}" && "${HIBERNATION_SWAP_SIZE_GB}" =~ ^[0-9]+$ ]]; then
        if (( HIBERNATION_SWAP_SIZE_GB > 0 )); then
            echo "$HIBERNATION_SWAP_SIZE_GB"
            return 0
        fi
    fi

    if [[ -n "${HIBERNATION_SWAP_PREFERENCE_FILE:-}" && -f "$HIBERNATION_SWAP_PREFERENCE_FILE" ]]; then
        cached_value=$(awk -F'=' '/^HIBERNATION_SWAP_SIZE_GB=/{print $2}' "$HIBERNATION_SWAP_PREFERENCE_FILE" 2>/dev/null | tr -d '\r[:space:]')
        if [[ "$cached_value" =~ ^[0-9]+$ ]]; then
            if (( cached_value > 0 )); then
                echo "$cached_value"
                return 0
            fi
        fi
    fi

    if [[ -n "${SYSTEM_CONFIG_FILE:-}" && -f "$SYSTEM_CONFIG_FILE" ]]; then
        cached_value=$(awk '
            /Target disk-backed swap capacity:/ {
                for (i = 1; i <= NF; i++) {
                    if ($i ~ /^~[0-9]+GB$/) {
                        gsub("^~", "", $i)
                        gsub("GB$", "", $i)
                        print $i
                        exit
                    }
                }
            }
        ' "$SYSTEM_CONFIG_FILE" 2>/dev/null | head -n1)

        if [[ "$cached_value" =~ ^[0-9]+$ ]]; then
            if (( cached_value > 0 )); then
                echo "$cached_value"
                return 0
            fi
        fi
    fi

    return 1
}

persist_hibernation_swap_size() {
    local swap_value="$1"

    if [[ -z "$swap_value" || ! "$swap_value" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    if (( swap_value <= 0 )); then
        return 1
    fi

    if [[ -z "${HIBERNATION_SWAP_PREFERENCE_FILE:-}" ]]; then
        return 1
    fi

    if ! safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR"; then
        log WARNING "Unable to persist swap preference: could not prepare $DEPLOYMENT_PREFERENCES_DIR"
        return 1
    fi

    local tmp_file
    tmp_file=$(mktemp "${HIBERNATION_SWAP_PREFERENCE_FILE}.XXXXXX" 2>/dev/null || echo "${HIBERNATION_SWAP_PREFERENCE_FILE}.tmp")

    if cat >"$tmp_file" <<EOF
HIBERNATION_SWAP_SIZE_GB=$swap_value
EOF
    then
        if mv "$tmp_file" "$HIBERNATION_SWAP_PREFERENCE_FILE" 2>/dev/null; then
            chmod 600 "$HIBERNATION_SWAP_PREFERENCE_FILE" 2>/dev/null || true
            safe_chown_user_dir "$HIBERNATION_SWAP_PREFERENCE_FILE" || true
            log INFO "Persisted hibernation swap size preference: ${swap_value}GB"
            return 0
        fi
    fi

    rm -f "$tmp_file" 2>/dev/null || true
    log WARNING "Failed to persist hibernation swap size preference at $HIBERNATION_SWAP_PREFERENCE_FILE"
    return 1
}

persist_zswap_configuration_override() {
    local override_value="$1"

    if [[ -z "${ZSWAP_OVERRIDE_PREFERENCE_FILE:-}" ]]; then
        return 1
    fi

    if [[ -z "$override_value" ]]; then
        return 1
    fi

    case "$override_value" in
        enable|disable)
            if ! safe_mkdir "$DEPLOYMENT_PREFERENCES_DIR"; then
                log WARNING "Unable to persist zswap override preference: could not prepare $DEPLOYMENT_PREFERENCES_DIR"
                return 1
            fi

            local tmp_file
            tmp_file=$(mktemp "${ZSWAP_OVERRIDE_PREFERENCE_FILE}.XXXXXX" 2>/dev/null || echo "${ZSWAP_OVERRIDE_PREFERENCE_FILE}.tmp")

            if cat >"$tmp_file" <<EOF
ZSWAP_CONFIGURATION_OVERRIDE=$override_value
EOF
            then
                if mv "$tmp_file" "$ZSWAP_OVERRIDE_PREFERENCE_FILE" 2>/dev/null; then
                    chmod 600 "$ZSWAP_OVERRIDE_PREFERENCE_FILE" 2>/dev/null || true
                    safe_chown_user_dir "$ZSWAP_OVERRIDE_PREFERENCE_FILE" || true
                    log INFO "Persisted zswap override preference: $override_value"
                    return 0
                fi
            fi

            rm -f "$tmp_file" 2>/dev/null || true
            log WARNING "Failed to persist zswap override preference at $ZSWAP_OVERRIDE_PREFERENCE_FILE"
            return 1
            ;;
        auto)
            if [[ -f "$ZSWAP_OVERRIDE_PREFERENCE_FILE" ]]; then
                if rm -f "$ZSWAP_OVERRIDE_PREFERENCE_FILE" 2>/dev/null; then
                    log INFO "Cleared persisted zswap override preference (auto detection enabled)"
                    return 0
                fi
                log WARNING "Unable to remove $ZSWAP_OVERRIDE_PREFERENCE_FILE while resetting zswap override"
                return 1
            fi
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

discover_resume_device_hint() {
    local resume_value=""

    if [[ -r /sys/power/resume ]]; then
        resume_value=$(tr -d '\r\n[:space:]' </sys/power/resume 2>/dev/null || echo "")
        if [[ "$resume_value" =~ ^[0-9]+:[0-9]+$ ]]; then
            local sysfs_node="/sys/dev/block/$resume_value"
            if [[ -r "$sysfs_node/uevent" ]]; then
                local devname
                devname=$(awk -F'=' '/^DEVNAME=/{print $2}' "$sysfs_node/uevent" 2>/dev/null | head -n1 | tr -d '\r')
                if [[ -n "$devname" ]]; then
                    echo "/dev/$devname"
                    return 0
                fi
            fi

            if [[ -L "$sysfs_node" ]]; then
                local resolved
                resolved=$(readlink -f "$sysfs_node" 2>/dev/null || echo "")
                if [[ -n "$resolved" && -r "$resolved/uevent" ]]; then
                    local devname_resolved
                    devname_resolved=$(awk -F'=' '/^DEVNAME=/{print $2}' "$resolved/uevent" 2>/dev/null | head -n1 | tr -d '\r')
                    if [[ -n "$devname_resolved" ]]; then
                        echo "/dev/$devname_resolved"
                        return 0
                    fi
                fi
            fi
        elif [[ -n "$resume_value" && "$resume_value" == /* ]]; then
            echo "$resume_value"
            return 0
        fi
    fi

    local resume_paths=(
        "${SYSTEM_CONFIG_FILE:-}"
        "/etc/nixos/configuration.nix"
        "/etc/nixos/hardware-configuration.nix"
    )

    local path
    for path in "${resume_paths[@]}"; do
        if [[ -f "$path" ]]; then
            local candidate
            candidate=$(awk -F'"' '/resumeDevice[[:space:]]*=/ { for (i = 2; i <= NF; i += 2) { if ($i ~ /^\//) { print $i; exit } } }' "$path" 2>/dev/null | head -n1)
            if [[ -n "$candidate" ]]; then
                echo "$candidate"
                return 0
            fi
        fi
    done

    return 1
}

detect_previous_swap_configuration() {
    # Return success when the host already has swap configured.
    local active_swap
    active_swap=$(calculate_active_swap_total_gb 2>/dev/null || echo 0)

    if [[ "$active_swap" =~ ^[0-9]+$ ]] && (( active_swap > 0 )); then
        log DEBUG "Detected active swap devices totaling ${active_swap}GiB"
        return 0
    fi

    if command -v lsblk >/dev/null 2>&1; then
        if lsblk -nr -o TYPE | grep -q '^swap$'; then
            log DEBUG "Detected swap-capable block device via lsblk"
            return 0
        fi
    fi

    local swap_paths=(
        "/etc/nixos/configuration.nix"
        "/etc/nixos/hardware-configuration.nix"
        "/etc/fstab"
    )

    local path
    for path in "${swap_paths[@]}"; do
        if [[ -f "$path" ]]; then
            if grep -Eqs 'swapDevices\s*=\s*(lib\.mkForce\s*)?\[' "$path"; then
                log DEBUG "Detected swapDevices declaration in $path"
                return 0
            fi
            if grep -Eqs 'type\s*=\s*"swap"' "$path"; then
                log DEBUG "Detected swap type declaration in $path"
                return 0
            fi
            if grep -Eqi '\bswapfile\b' "$path"; then
                log DEBUG "Detected swapfile reference in $path"
                return 0
            fi
        fi
    done

    log DEBUG "No existing swap configuration detected"
    return 1
}

detect_previous_hibernation_configuration() {
    # Return success when the host previously enabled hibernation.
    if [[ -r /sys/power/resume ]]; then
        local resume_value
        resume_value=$(tr -d '\r\n[:space:]' </sys/power/resume 2>/dev/null || echo "")
        if [[ -n "$resume_value" && "$resume_value" != "0:0" ]]; then
            log DEBUG "Resume device configured via /sys/power/resume: $resume_value"
            return 0
        fi
    fi

    if command -v systemctl >/dev/null 2>&1; then
        local can_hibernate
        can_hibernate=$(systemctl show --property=CanHibernate --value systemd-logind 2>/dev/null | tr '[:upper:]' '[:lower:]')
        if [[ "$can_hibernate" == "yes" ]]; then
            log DEBUG "systemd-logind reports hibernation capability"
            return 0
        fi
    fi

    local hint_paths=(
        "/etc/systemd/logind.conf"
        "/etc/systemd/sleep.conf"
        "/etc/nixos/configuration.nix"
    )

    local config_path
    for config_path in "${hint_paths[@]}"; do
        if [[ -f "$config_path" ]] && grep -Eqi 'hibernate|resumeDevice' "$config_path"; then
            log DEBUG "Detected hibernation hints in $config_path"
            return 0
        fi
    done

    log DEBUG "No previous hibernation configuration detected"
    return 1
}

# ===========================================================================
# Flatpak Helper Functions
# ============================================================================

flatpak_cli_available() {
    run_as_primary_user flatpak --version >/dev/null 2>&1
}

# ============================================================================
# Safe File System Operations
# ============================================================================
# Purpose: Provide consistent, safe wrappers for common file operations
# Benefits:
#   - Centralized error handling
#   - Consistent sudo/permission handling
#   - DRY principle (Don't Repeat Yourself)
#   - Easier to test and maintain
#   - Prevents silent failures
#
# These functions replace direct use of mkdir, chown, cp with verified
# versions that:
#   - Check for errors
#   - Provide clear error messages
#   - Handle sudo/root scenarios correctly
#   - Verify operations succeeded
# ============================================================================

safe_mkdir() {
    # Create directory with error checking and proper permissions
    # Args: $1 = directory path
    # Returns: 0 on success, 1 on failure
    # Usage: safe_mkdir "/path/to/dir" || return 1
    local dir="$1"

    if [[ -z "$dir" ]]; then
        print_error "safe_mkdir: No directory specified"
        return 1
    fi

    # Already exists is success
    if [[ -d "$dir" ]]; then
        return 0
    fi

    # Attempt to create with parents
    if ! mkdir -p "$dir" 2>/dev/null; then
        print_error "Failed to create directory: $dir"
        print_error "Check permissions and available disk space"
        return 1
    fi

    # Verify directory was created
    if [[ ! -d "$dir" ]]; then
        print_error "Directory was not created: $dir"
        return 1
    fi

    return 0
}

safe_chown_user_dir() {
    # Set ownership to appropriate user with sudo handling
    # Args: $1 = directory/file path
    # Returns: 0 on success, 1 on failure (warnings don't fail)
    # Usage: safe_chown_user_dir "/path/to/dir"
    #
    # Handles three scenarios:
    # 1. Running with sudo (SUDO_USER exists): chown to original user
    # 2. Running as root without sudo: chown to PRIMARY_USER
    # 3. Running as normal user: no-op (ownership already correct)
    local target="$1"

    if [[ -z "$target" ]]; then
        print_error "safe_chown_user_dir: No target specified"
        return 1
    fi

    if [[ ! -e "$target" ]]; then
        if [[ -L "$target" ]]; then
            print_detail "safe_chown_user_dir: Target is a symlink with missing referent; skipping ownership fix: $target"
            return 0
        fi
        print_error "safe_chown_user_dir: Target does not exist: $target"
        return 1
    fi

    # Running as normal user - ownership already correct
    if [[ "$EUID" -ne 0 ]]; then
        return 0
    fi

    # Determine correct ownership
    local owner
    local sudo_user="${SUDO_USER:-}"
    if [[ -n "$sudo_user" ]]; then
        # Running with sudo - set ownership to original user
        local sudo_group
        sudo_group=$(id -gn "$sudo_user" 2>/dev/null || echo "users")
        owner="$sudo_user:$sudo_group"
    else
        # Running as root without sudo - use PRIMARY_USER (fallback to USER)
        local target_user="${PRIMARY_USER:-${USER:-}}"
        if [[ -z "$target_user" ]]; then
            target_user="$(id -un 2>/dev/null || echo "root")"
        fi
        local target_group
        target_group=$(id -gn "$target_user" 2>/dev/null || echo "users")
        owner="$target_user:$target_group"
    fi

    # Attempt to set ownership
    if ! chown -R "$owner" "$target" 2>/dev/null; then
        print_warning "Could not set ownership of $target to $owner"
        # Don't fail - this is often not critical
        return 0
    fi

    return 0
}

safe_copy_file() {
    # Copy file with verification
    # Args: $1 = source, $2 = destination
    # Returns: 0 on success, 1 on failure
    # Usage: safe_copy_file "/src/file" "/dest/file" || return 1
    local src="$1"
    local dest="$2"

    if [[ -z "$src" ]] || [[ -z "$dest" ]]; then
        print_error "safe_copy_file: Source and destination required"
        return 1
    fi

    if [[ ! -f "$src" ]]; then
        print_error "safe_copy_file: Source file not found: $src"
        return 1
    fi

    # Ensure destination directory exists
    local dest_dir=$(dirname "$dest")
    if ! safe_mkdir "$dest_dir"; then
        return 1
    fi

    # Attempt to copy
    if ! cp "$src" "$dest" 2>/dev/null; then
        print_error "Failed to copy file"
        print_error "  Source: $src"
        print_error "  Destination: $dest"
        return 1
    fi

    # Verify file was created
    if [[ ! -f "$dest" ]]; then
        print_error "Verification failed: File not created at $dest"
        return 1
    fi

    return 0
}

safe_copy_file_silent() {
    # Copy file silently (for backups where failure is non-critical)
    # Args: $1 = source, $2 = destination
    # Returns: 0 on success, 1 on failure (but doesn't print errors)
    # Usage: safe_copy_file_silent "/src/file" "/dest/file" || true
    local src="$1"
    local dest="$2"

    [[ -f "$src" ]] || return 1

    local dest_dir=$(dirname "$dest")
    mkdir -p "$dest_dir" 2>/dev/null || return 1

    cp "$src" "$dest" 2>/dev/null || return 1
    [[ -f "$dest" ]] || return 1

    return 0
}

backup_path_if_exists() {
    local target_path="$1"
    local backup_root="$2"
    local label="$3"

    if [[ -z "$target_path" || -z "$backup_root" ]]; then
        return 1
    fi

    if [[ ! -e "$target_path" && ! -L "$target_path" ]]; then
        return 1
    fi

    if ! safe_mkdir "$backup_root"; then
        print_warning "Unable to create backup directory: $backup_root"
        return 2
    fi
    if [[ -e "$backup_root" || -L "$backup_root" ]]; then
        safe_chown_user_dir "$backup_root" || true
    fi

    local relative_path=""
    if [[ "$target_path" == "$HOME" ]]; then
        relative_path="home-root"
    elif [[ "$target_path" == "$HOME"/* ]]; then
        relative_path="${target_path#$HOME/}"
    else
        relative_path="${target_path#/}"
    fi

    local destination="$backup_root/$relative_path"
    local destination_parent
    destination_parent=$(dirname "$destination")
    if ! safe_mkdir "$destination_parent"; then
        print_warning "Failed to prepare backup destination for ${label:-$relative_path}"
        return 2
    fi
    if [[ -e "$destination_parent" || -L "$destination_parent" ]]; then
        safe_chown_user_dir "$destination_parent" || true
    fi

    if cp -a "$target_path" "$destination" 2>/dev/null; then
        if [[ -e "$destination" ]]; then
            safe_chown_user_dir "$destination" || true
        fi
        if [[ -d "$target_path" && ! -L "$target_path" ]]; then
            rm -rf "$target_path" 2>/dev/null || true
        else
            rm -f "$target_path" 2>/dev/null || true
        fi

        local display_label="${label:-$relative_path}"
        print_success "Backed up and removed $display_label"
        print_info "  → Backup saved to: $destination"
        return 0
    fi

    print_warning "Failed to back up ${label:-$target_path}"
    return 2
}

ensure_path_symlink() {
    # Ensure a symlink exists from link_path to target_path, replacing any existing
    # directory or link at the destination.
    # Args: $1 = target path (dotfiles location), $2 = link path (home location)
    # Returns: 0 on success, 1 on failure
    ENSURE_PATH_SYMLINK_STATUS="unchanged"

    local target_path="$1"
    local link_path="$2"

    if [[ -z "$target_path" || -z "$link_path" ]]; then
        print_error "ensure_path_symlink: target and link paths are required"
        ENSURE_PATH_SYMLINK_STATUS="failed"
        return 1
    fi

    if [[ ! -e "$target_path" ]]; then
        print_error "ensure_path_symlink: target does not exist: $target_path"
        ENSURE_PATH_SYMLINK_STATUS="failed"
        return 1
    fi

    if [[ -L "$link_path" ]]; then
        local current_target
        current_target=$(readlink "$link_path" 2>/dev/null || true)
        if [[ "$current_target" == "$target_path" ]]; then
            return 0
        fi

        if ! rm -f "$link_path" 2>/dev/null; then
            print_error "Failed to remove existing symlink: $link_path"
            ENSURE_PATH_SYMLINK_STATUS="failed"
            return 1
        fi
    elif [[ -e "$link_path" ]]; then
        if ! rm -rf "$link_path" 2>/dev/null; then
            print_error "Failed to replace existing path: $link_path"
            ENSURE_PATH_SYMLINK_STATUS="failed"
            return 1
        fi
    fi

    local parent_dir
    parent_dir=$(dirname "$link_path")
    if ! safe_mkdir "$parent_dir"; then
        ENSURE_PATH_SYMLINK_STATUS="failed"
        return 1
    fi

    if ln -s "$target_path" "$link_path" 2>/dev/null; then
        ENSURE_PATH_SYMLINK_STATUS="created"
        return 0
    fi

    print_error "Failed to create symlink: $link_path -> $target_path"
    ENSURE_PATH_SYMLINK_STATUS="failed"
    return 1
}

prepare_home_manager_targets() {
    local phase_tag="${1:-pre-switch}"
    local timestamp
    timestamp="$(date +%Y%m%d_%H%M%S)"
    local backup_dir="$HOME/.config-backups/${phase_tag}-${timestamp}"
    local cleaned_any=false
    local encountered_error=false

    local preserve_flatpak_state=false
    local flatpak_installed_count=0

    _is_flatpak_state_path() {
        local candidate="$1"
        if [[ -z "$candidate" ]]; then
            return 1
        fi

        case "$candidate" in
            "$PRIMARY_HOME/.config/flatpak"|"$PRIMARY_HOME/.config/flatpak/"*| \
            "$PRIMARY_HOME/.local/share/flatpak"|"$PRIMARY_HOME/.local/share/flatpak/"*| \
            "$PRIMARY_HOME/.var/app"|"$PRIMARY_HOME/.var/app/"*| \
            "$DOTFILES_ROOT/.config/flatpak"|"$DOTFILES_ROOT/.config/flatpak/"*| \
            "$DOTFILES_ROOT/.local/share/flatpak"|"$DOTFILES_ROOT/.local/share/flatpak/"*| \
            "$DOTFILES_ROOT/.var/app"|"$DOTFILES_ROOT/.var/app/"*)
                return 0
                ;;
        esac
        return 1
    }

    if command -v flatpak >/dev/null 2>&1; then
        local flatpak_list_output=""
        if flatpak_list_output=$(run_as_primary_user flatpak list --user --app --columns=application 2>/dev/null || true); then
            flatpak_installed_count=$(printf '%s\n' "$flatpak_list_output" | awk '$0 != "Application" && NF {count++} END {print count+0}')
            if [[ "$flatpak_installed_count" -gt 0 ]]; then
                preserve_flatpak_state=true
                print_info "Detected ${flatpak_installed_count} existing Flatpak application(s); preserving user Flatpak directories."
            fi
        fi
    fi

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
        "$HOME/.config/containers/storage.conf::Rootless Podman storage.conf"
        "$HOME/.npmrc::.npmrc"
    )

    local entry path label result

    if [[ "$preserve_flatpak_state" == true ]]; then
        local -a filtered_directories=()
        for entry in "${directory_targets[@]}"; do
            path="${entry%%::*}"
            if _is_flatpak_state_path "$path"; then
                continue
            fi
            filtered_directories+=("$entry")
        done
        directory_targets=("${filtered_directories[@]}")
    fi

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
        export LATEST_CONFIG_BACKUP_DIR
        persist_config_backup_hint "$backup_dir"
        print_success "Archived conflicting configuration to: $backup_dir"
        print_info "Restore with: cp -a \"$backup_dir/.\" \"$HOME/\""
    else
        rm -rf "$backup_dir" 2>/dev/null || true
        LATEST_CONFIG_BACKUP_DIR=""
        export LATEST_CONFIG_BACKUP_DIR
        persist_config_backup_hint ""
        print_info "No pre-existing configuration files required backup."
    fi

    if [[ "$encountered_error" == true ]]; then
        print_warning "Some configuration paths could not be backed up automatically (see messages above)."
    fi

    local -a symlink_targets=(
        "$LOCAL_BIN_DIR::755"
        "$PRIMARY_HOME/.config/flatpak::700"
        "$PRIMARY_HOME/.local/share/flatpak::750"
        "$AIDER_CONFIG_DIR::700"
        "$TEA_CONFIG_DIR::700"
        "$HUGGINGFACE_CONFIG_DIR::700"
        "$HUGGINGFACE_CACHE_DIR::700"
        "$OPEN_WEBUI_DATA_DIR::750"
        "$PRIMARY_HOME/.local/share/podman-ai-stack::750"
        "$GITEA_NATIVE_CONFIG_DIR::700"
        "$GITEA_NATIVE_DATA_DIR::750"
        "$GITEA_SECRETS_CACHE_DIR::700"
        "$PRIMARY_HOME/.config/obsidian/ai-integrations::700"
        "$PRIMARY_HOME/.var/app::755"
    )

    local dotfiles_created=false
    local symlinks_created=false

    if [[ "$preserve_flatpak_state" == true ]]; then
        local -a filtered_symlink_targets=()
        for entry in "${symlink_targets[@]}"; do
            path="${entry%%::*}"
            if _is_flatpak_state_path "$path"; then
                continue
            fi
            filtered_symlink_targets+=("$entry")
        done
        symlink_targets=("${filtered_symlink_targets[@]}")
    fi

    for entry in "${symlink_targets[@]}"; do
        path="${entry%%::*}"
        local mode="${entry##*::}"
        if [[ "$mode" == "$path" ]]; then
            mode="755"
        fi

        if [[ "$path" != "$PRIMARY_HOME"/* ]]; then
            continue
        fi

        local relative="${path#"$PRIMARY_HOME/"}"
        local dotfiles_path="$DOTFILES_ROOT/$relative"

        local created_here=false
        if [[ ! -d "$dotfiles_path" ]]; then
            if safe_mkdir "$dotfiles_path"; then
                created_here=true
            else
                print_warning "Unable to create directory: $dotfiles_path"
                encountered_error=true
                continue
            fi
        fi

        if ! chmod "$mode" "$dotfiles_path" 2>/dev/null; then
            print_warning "Unable to set permissions $mode on $dotfiles_path"
        fi
        safe_chown_user_dir "$dotfiles_path" || true

        if [[ "$created_here" == true ]]; then
            dotfiles_created=true
        fi

        if ! ensure_path_symlink "$dotfiles_path" "$path"; then
            encountered_error=true
            print_warning "Unable to link $path to managed dotfiles directory"
            continue
        fi

        if [[ "${ENSURE_PATH_SYMLINK_STATUS:-unchanged}" == "created" ]]; then
            symlinks_created=true
            print_success "Linked $path → $dotfiles_path"
        fi
    done

    local -a nested_dotfiles_dirs=(
        "$DOTFILES_ROOT/.local/share/flatpak/overrides::750"
        "$DOTFILES_ROOT/.local/share/flatpak/remotes.d::750"
        "$DOTFILES_ROOT/.var/app/$GITEA_FLATPAK_APP_ID/config/gitea::700"
        "$DOTFILES_ROOT/.var/app/$GITEA_FLATPAK_APP_ID/data/gitea::750"
    )

    if [[ "$preserve_flatpak_state" == true ]]; then
        local -a filtered_nested_dirs=()
        for entry in "${nested_dotfiles_dirs[@]}"; do
            path="${entry%%::*}"
            if _is_flatpak_state_path "$path"; then
                continue
            fi
            filtered_nested_dirs+=("$entry")
        done
        nested_dotfiles_dirs=("${filtered_nested_dirs[@]}")
    fi

    for entry in "${nested_dotfiles_dirs[@]}"; do
        path="${entry%%::*}"
        local mode="${entry##*::}"
        if [[ "$mode" == "$path" ]]; then
            mode="755"
        fi

        if [[ ! -d "$path" ]]; then
            if safe_mkdir "$path"; then
                dotfiles_created=true
            else
                print_warning "Unable to create directory: $path"
                encountered_error=true
                continue
            fi
        fi

        if ! chmod "$mode" "$path" 2>/dev/null; then
            print_warning "Unable to set permissions $mode on $path"
        fi
        safe_chown_user_dir "$path" || true
    done

    if [[ "$dotfiles_created" == true ]]; then
        print_success "Prepared dotfiles workspace for managed configuration files"
    fi

    if [[ "$symlinks_created" == true ]]; then
        print_success "Linked managed configuration directories into $PRIMARY_HOME"
    fi

    if [[ "$encountered_error" == true ]]; then
        return 1
    fi

    return 0
}

persist_config_backup_hint() {
    local backup_dir="$1"

    if [[ -z "${ROLLBACK_INFO_FILE:-}" || ! -f "$ROLLBACK_INFO_FILE" ]]; then
        return 0
    fi

    if command -v python3 >/dev/null 2>&1; then
        if ROLLBACK_INFO_FILE="$ROLLBACK_INFO_FILE" BACKUP_DIR="$backup_dir" python3 <<'PY'
import json
import os
import stat
import sys
import tempfile

rollback_file = os.environ.get("ROLLBACK_INFO_FILE")
backup_dir = os.environ.get("BACKUP_DIR", "")

if not rollback_file:
    sys.exit(1)

with open(rollback_file, "r", encoding="utf-8") as handle:
    data = json.load(handle)

if backup_dir:
    data["config_backup_dir"] = backup_dir
else:
    data.pop("config_backup_dir", None)

directory = os.path.dirname(rollback_file) or "."
prefix = f"{os.path.basename(rollback_file)}."
fd, tmp_path = tempfile.mkstemp(prefix=prefix, dir=directory)

try:
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_handle:
        json.dump(data, tmp_handle, indent=2)
        tmp_handle.write("\n")

    try:
        mode = stat.S_IMODE(os.stat(rollback_file).st_mode)
    except FileNotFoundError:
        mode = 0o600
    os.chmod(tmp_path, mode)
    os.replace(tmp_path, rollback_file)
except Exception:
    os.unlink(tmp_path)
    raise
PY
        then
            return 0
        fi
        log WARNING "Python-based rollback hint update failed; attempting jq fallback"
    else
        log DEBUG "python3 unavailable – falling back to jq for rollback hint update"
    fi

    if ! command -v jq >/dev/null 2>&1; then
        log WARNING "Neither python3 nor jq available to update rollback hints"
        return 0
    fi

    local tmp_file
    tmp_file=$(mktemp "${ROLLBACK_INFO_FILE}.XXXXXX" 2>/dev/null || echo "${ROLLBACK_INFO_FILE}.tmp")

    if [[ -z "$backup_dir" ]]; then
        if jq 'del(.config_backup_dir)' "$ROLLBACK_INFO_FILE" >"$tmp_file" 2>/dev/null && \
           mv "$tmp_file" "$ROLLBACK_INFO_FILE" 2>/dev/null; then
            return 0
        fi
    else
        if jq --arg dir "$backup_dir" '.config_backup_dir = $dir' "$ROLLBACK_INFO_FILE" >"$tmp_file" 2>/dev/null && \
           mv "$tmp_file" "$ROLLBACK_INFO_FILE" 2>/dev/null; then
            return 0
        fi
    fi

    rm -f "$tmp_file" 2>/dev/null || true
    log WARNING "Failed to update rollback info with configuration backup hint"
    return 1
}

restore_latest_config_backup() {
    local backup_dir="$1"
    local target_dir="${2:-$HOME}"

    if [[ -z "$backup_dir" ]]; then
        return 1
    fi

    if [[ ! -d "$backup_dir" ]]; then
        print_warning "Configuration backup directory not found: $backup_dir"
        log WARNING "Configuration backup directory missing: $backup_dir"
        return 1
    fi

    if [[ -z "$target_dir" || ! -d "$target_dir" ]]; then
        print_warning "Cannot restore backup – target directory missing: ${target_dir:-unknown}"
        log WARNING "Restore skipped: target directory missing (${target_dir:-unset})"
        return 1
    fi

    print_info "Restoring configuration backup from $backup_dir"
    if cp -a "$backup_dir/." "$target_dir/" 2>/dev/null; then
        safe_chown_user_dir "$target_dir" || true
        print_success "Restored configuration backup from $backup_dir"
        log INFO "Restored configuration backup from $backup_dir to $target_dir"
        return 0
    fi

    print_warning "Failed to restore configuration backup from $backup_dir"
    log WARNING "Failed to restore configuration backup from $backup_dir to $target_dir"
    return 1
}

verify_file_created() {
    # Verify file exists, is readable, and has content
    # Args: $1 = file path, $2 = description (optional)
    # Returns: 0 on success, 1 on failure
    # Usage: verify_file_created "/path/file" "config file" || return 1
    local file="$1"
    local desc="${2:-File}"

    if [[ ! -f "$file" ]]; then
        print_error "$desc does not exist: $file"
        return 1
    fi

    if [[ ! -r "$file" ]]; then
        print_error "$desc is not readable: $file"
        return 1
    fi

    local size=$(stat -c%s "$file" 2>/dev/null || echo "0")
    if [[ "$size" -eq 0 ]]; then
        print_error "$desc is empty: $file"
        return 1
    fi

    return 0
}

# ============================================================================
# NOTE: Additional utility functions should be extracted from the main
# script and added here, including:
# - Flatpak management functions
# - NixOS helper functions
# - Home Manager functions
# - Configuration generation helpers
# - And many more...
#
# This is a foundational common.sh with the most critical shared functions.
# Continue extracting functions from nixos-quick-deploy.sh as needed.
# ============================================================================
