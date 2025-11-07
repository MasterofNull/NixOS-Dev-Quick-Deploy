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

# ===========================================================================
# Swap Sizing Helpers
# ===========================================================================

suggest_hibernation_swap_size() {
    # Compute a suggested swap size (in GiB) suitable for hibernation when using
    # zram-backed swap. Returns a conservative value of roughly 125% of RAM with
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

compute_zram_percent_for_swap() {
    # Convert a desired swap capacity (GiB) into a zram memoryPercent value.
    # Args: $1 = target swap GiB, $2 = total RAM GiB
    local target_swap_gb="${1:-0}"
    local ram_gb="${2:-0}"

    if ! [[ "$target_swap_gb" =~ ^[0-9]+$ ]] || (( target_swap_gb <= 0 )); then
        echo 0
        return
    fi

    if ! [[ "$ram_gb" =~ ^[0-9]+$ ]] || (( ram_gb <= 0 )); then
        echo 0
        return
    fi

    local percent=$(( (target_swap_gb * 100 + ram_gb - 1) / ram_gb ))

    if (( percent < 1 )); then
        percent=1
    fi

    echo "$percent"
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
        print_error "safe_chown_user_dir: Target does not exist: $target"
        return 1
    fi

    # Running as normal user - ownership already correct
    if [[ "$EUID" -ne 0 ]]; then
        return 0
    fi

    # Determine correct ownership
    local owner
    if [[ -n "$SUDO_USER" ]]; then
        # Running with sudo - set ownership to original user
        owner="$SUDO_USER:$(id -gn "$SUDO_USER" 2>/dev/null || echo "users")"
    else
        # Running as root without sudo - use PRIMARY_USER
        owner="${PRIMARY_USER:-$USER}:$(id -gn "${PRIMARY_USER:-$USER}" 2>/dev/null || echo "users")"
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
