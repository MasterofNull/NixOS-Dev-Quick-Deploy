#!/usr/bin/env bash
#
# Phase 01: System Initialization
# Purpose: Validate system requirements and install temporary deployment tools
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/validation.sh → check_disk_space(), check_required_packages(), assert_unique_paths()
#   - lib/hardware.sh → detect_gpu_hardware(), detect_gpu_and_cpu()
#   - lib/nixos.sh → select_nixos_version(), update_nixos_channels()
#   - lib/packages.sh → ensure_preflight_core_packages(), cleanup_conflicting_home_manager_profile()
#   - lib/home-manager.sh → install_home_manager()
#   - lib/python.sh → ensure_python_runtime()
#
# Required Variables (from config/variables.sh):
#   - USER → Current user name
#   - EUID → Effective user ID
#   - PYTHON_BIN → Python interpreter path (array)
#
# Requires Phases (must complete before this):
#   - None (first phase)
#
# Produces (for later phases):
#   - GPU_TYPE → Detected GPU type (nvidia/amd/intel/software)
#   - GPU_DRIVER → GPU driver package name
#   - GPU_PACKAGES → Additional GPU packages
#   - LIBVA_DRIVER → VA-API driver for hardware acceleration
#   - PREREQUISITES_INSTALLED → Flag indicating prerequisites ready
#   - PYTHON_BIN → Python interpreter path
#   - State: "system_initialization" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_01_system_initialization() {
    # ========================================================================
    # Phase 1: System Initialization
    # ========================================================================
    # This is the first phase - it validates the system and installs
    # temporary tools needed for deployment automation.
    #
    # Part 1: Validation (from old Phase 1)
    # - Verify running on NixOS
    # - Check permissions (not root)
    # - Validate network connectivity
    # - Check disk space
    # - Detect hardware (GPU, CPU, memory)
    # - Validate dependency chain
    #
    # Part 2: Temporary Tool Installation (from old Phase 2)
    # - Install git, jq via nix-env (temporary)
    # - Install home-manager
    # - Verify Python runtime
    # - These will be replaced by declarative packages in Phase 5
    #
    # Why merge these phases:
    # - Both are initialization/setup tasks
    # - No system changes yet (just validation + temp tools)
    # - Streamlines workflow from 10 → 8 phases
    # ========================================================================

    local phase_name="system_initialization"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 1 already completed (skipping)"
        return 0
    fi

    print_section "Phase 1/8: System Initialization"
    echo ""

    local previous_imperative_flag="${IMPERATIVE_INSTALLS_ALLOWED:-false}"
    export IMPERATIVE_INSTALLS_ALLOWED=true

    # ========================================================================
    # PART 1: SYSTEM VALIDATION
    # ========================================================================

    # ========================================================================
    # Step 1.1: Verify Running on NixOS
    # ========================================================================
    # Why: This script uses NixOS-specific commands (nixos-rebuild, etc.)
    # How: Check for /etc/NIXOS file which exists only on NixOS
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    # ========================================================================
    # Step 1.2: Verify NOT Running as Root
    # ========================================================================
    # Why: Running as root causes permission issues (files owned by root)
    # Script will use 'sudo' when needed for specific commands
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        exit 1
    fi
    print_success "Running with correct permissions (non-root)"

    # ========================================================================
    # Step 1.3: Verify Critical NixOS Commands Available
    # ========================================================================
    # Essential commands: nixos-rebuild, nix-env, nix-channel
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            print_error "Critical command not found: $cmd"
            exit 1
        fi
    done
    print_success "Critical NixOS commands available"

    # ========================================================================
    # Step 1.4: Verify Sufficient Disk Space
    # ========================================================================
    # NixOS deployment requires significant disk space for packages,
    # builds, and multiple system generations
    if ! check_disk_space; then
        print_error "Insufficient disk space"
        exit 1
    fi

    # ========================================================================
    # Step 1.5: Validate Network Connectivity
    # ========================================================================
    # Need internet to download packages from NixOS binary cache
    print_info "Checking network connectivity..."
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_success "Network connectivity OK"
    else
        print_error "No network connectivity detected"
        print_error "Internet connection required to download packages"
        exit 1
    fi

    # ========================================================================
    # Step 1.6: Validate Configuration Path Uniqueness
    # ========================================================================
    # Ensure no two config files try to use the same path
    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        print_error "Internal configuration path conflict detected"
        exit 1
    fi

    # ========================================================================
    # Step 1.7: Check for Old Deployment Artifacts
    # ========================================================================
    # Warn about old monolithic script from v2.x
    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="/home/$USER/Documents/nixos-quick-deploy.sh"
    if [[ -f "$OLD_SCRIPT" ]]; then
        print_warning "Found old deployment script: $OLD_SCRIPT"
        print_info "This can be safely ignored or archived"
    fi

    # ========================================================================
    # Step 1.8: Validate Entire Dependency Chain
    # ========================================================================
    # Ensure all required packages available in Nix channels
    print_info "Validating dependency chain..."
    check_required_packages || {
        print_error "Required packages not available"
        exit 1
    }

    # ========================================================================
    # Step 1.9: Hardware Detection - GPU
    # ========================================================================
    # Detect GPU type to install correct drivers:
    # - NVIDIA: Proprietary nvidia drivers + CUDA
    # - AMD: Mesa + AMDGPU drivers + ROCm
    # - Intel: Mesa + i915/Xe drivers + oneAPI
    # - Software: No GPU, CPU-only rendering
    detect_gpu_hardware

    # ========================================================================
    # Step 1.10: Hardware Detection - CPU and Memory
    # ========================================================================
    # Optimize configuration based on available resources
    detect_gpu_and_cpu

    # ========================================================================
    # Step 1.11: Plan Swap and Hibernation Capacity
    # ========================================================================
    print_section "Swap & Hibernation Planning"
    echo ""

    local current_swap_gb
    current_swap_gb=$(calculate_active_swap_total_gb)

    local recommended_swap_gb
    recommended_swap_gb=$(suggest_hibernation_swap_size "${TOTAL_RAM_GB:-0}")
    if ! [[ "$recommended_swap_gb" =~ ^[0-9]+$ ]] || (( recommended_swap_gb <= 0 )); then
        recommended_swap_gb=8
    fi

    if [[ "${TOTAL_RAM_GB:-}" =~ ^[0-9]+$ && ${TOTAL_RAM_GB} -gt 0 ]]; then
        print_info "Detected system memory: ${TOTAL_RAM_GB}GB."
    else
        print_warning "Unable to determine total system memory; swap sizing suggestions may be inaccurate."
    fi

    if (( current_swap_gb > 0 )); then
        print_info "Active swap currently configured: ${current_swap_gb}GB."
    else
        print_warning "No active swap space detected on this system."
    fi

    print_info "Recommended zram-backed swap size for reliable hibernation: ${recommended_swap_gb}GB."
    if (( current_swap_gb > 0 )); then
        print_info "Press Enter to accept ${recommended_swap_gb}GB, type 'current' to keep ${current_swap_gb}GB, or enter a new size in GB."
    else
        print_info "Press Enter to accept ${recommended_swap_gb}GB or enter a new size in GB."
    fi

    local raw_swap_input=""
    while true; do
        raw_swap_input=$(prompt_user "Desired swap size in GB for zram-backed hibernation" "$recommended_swap_gb")

        if [[ -z "$raw_swap_input" ]]; then
            raw_swap_input="$recommended_swap_gb"
        fi

        if [[ "${raw_swap_input,,}" == "current" ]]; then
            if (( current_swap_gb > 0 )); then
                HIBERNATION_SWAP_SIZE_GB="$current_swap_gb"
                print_success "Keeping current swap allocation (${current_swap_gb}GB)."
                break
            else
                print_warning "No active swap detected. Please enter a numeric size."
                continue
            fi
        fi

        if [[ "$raw_swap_input" =~ ^[0-9]+$ ]]; then
            if (( raw_swap_input <= 0 )); then
                print_warning "Swap size must be greater than zero to support hibernation."
                continue
            fi
            HIBERNATION_SWAP_SIZE_GB="$raw_swap_input"
            if (( raw_swap_input == recommended_swap_gb )); then
                print_success "Using recommended swap size of ${raw_swap_input}GB."
            else
                print_success "Using custom swap size of ${raw_swap_input}GB."
            fi
            break
        fi

        print_warning "Invalid input. Enter a whole number of gigabytes or type 'current'."
    done

    export HIBERNATION_SWAP_SIZE_GB

    local zram_percent_override
    zram_percent_override=$(compute_zram_percent_for_swap "$HIBERNATION_SWAP_SIZE_GB" "${TOTAL_RAM_GB:-0}")
    if [[ "$zram_percent_override" =~ ^[0-9]+$ && "$zram_percent_override" -gt 0 ]]; then
        if (( zram_percent_override > 400 )); then
            print_warning "Requested swap size is very large; capping zram allocation at 400% of RAM to avoid exhaustion."
            zram_percent_override=400
        fi
        if [[ "$zram_percent_override" != "${ZRAM_PERCENT:-}" ]]; then
            ZRAM_PERCENT="$zram_percent_override"
            print_info "Configuring zram swap to target approximately ${HIBERNATION_SWAP_SIZE_GB}GB (~${ZRAM_PERCENT}% of RAM)."
        else
            print_info "Retaining auto-detected zram target of ${ZRAM_PERCENT}% (~${HIBERNATION_SWAP_SIZE_GB}GB)."
        fi
    else
        print_warning "Unable to compute a zram allocation from the provided size; keeping default ${ZRAM_PERCENT}% target."
    fi
    export ZRAM_PERCENT

    echo ""
    print_section "Part 2: Temporary Tool Installation"
    echo ""

    # ========================================================================
    # PART 2: TEMPORARY TOOL INSTALLATION
    # ========================================================================
    # These tools are installed via nix-env (imperative) for immediate use
    # during deployment. They will be REMOVED in Phase 5 and replaced with
    # declarative packages from configuration.nix and home.nix
    # ========================================================================

    # ========================================================================
    # Step 1.12: Select Build Strategy for Initial Deployment
    # ========================================================================
    print_section "Build Strategy Selection"
    echo ""
    print_info "Choose how nixos-rebuild should source packages during the initial switch."
    echo ""

    local -a recommended_caches=()
    if declare -F get_binary_cache_sources >/dev/null 2>&1; then
        mapfile -t recommended_caches < <(get_binary_cache_sources)
    fi

    echo "  1) Use pre-built binary caches (recommended)"
    echo "     - Downloads trusted substitutes for faster deployment"
    echo "     - Minimal local compilation workload"
    echo "     - Requires reliable internet access"
    if (( ${#recommended_caches[@]} > 0 )); then
        local cache_overview=""
        local cache
        for cache in "${recommended_caches[@]}"; do
            if [[ -n "$cache_overview" ]]; then
                cache_overview+="; "
            fi
            cache_overview+="$cache"
        done
        echo "     - Caches: ${cache_overview}"
    fi
    echo ""
    echo "  2) Build every package locally"
    echo "     - Disables binary caches for a reproducible source build"
    echo "     - Significantly longer build times (hours on slower systems)"
    echo "     - High CPU and memory usage during compilation"
    echo ""

    local build_choice
    local default_choice="1"
    if [[ "${USE_BINARY_CACHES:-true}" != "true" ]]; then
        default_choice="2"
    fi
    build_choice=$(prompt_user "Choose build strategy (1-2)" "$default_choice")

    case "$build_choice" in
        2)
            USE_BINARY_CACHES="false"
            print_warning "Binary caches disabled – all packages will be built from source."
            print_info "Ensure adequate time, CPU resources, and thermal management before continuing."
            ;;
        1|*)
            USE_BINARY_CACHES="true"
            print_success "Binary caches enabled – leveraging trusted substitutes for faster deployment."
            ;;
    esac

    if [[ -n "${BINARY_CACHE_PREFERENCE_FILE:-}" ]]; then
        local preference_dir
        preference_dir=$(dirname "$BINARY_CACHE_PREFERENCE_FILE")
        if safe_mkdir "$preference_dir"; then
            if cat >"$BINARY_CACHE_PREFERENCE_FILE" <<EOF
# Stored deployment preference – automatically updated by phase 1
USE_BINARY_CACHES=$USE_BINARY_CACHES
EOF
            then
                chmod 600 "$BINARY_CACHE_PREFERENCE_FILE" 2>/dev/null || true
                safe_chown_user_dir "$BINARY_CACHE_PREFERENCE_FILE" || true
                print_info "Saved build strategy preference for future runs."
            else
                print_warning "Unable to persist build strategy preference (continuing with current session setting)."
            fi
        else
            print_warning "Could not prepare preference directory at $preference_dir; preference will not be cached."
        fi
    fi

    # ========================================================================
    # Step 1.13: NixOS Version Selection
    # ========================================================================
    # Let user choose stable (24.05) or unstable (rolling)
    select_nixos_version

    # ========================================================================
    # Step 1.14: Update NixOS Channels
    # ========================================================================
    # Fetch latest package metadata and security updates
    update_nixos_channels

    # ========================================================================
    # Step 1.15: Install Core Prerequisite Packages
    # ========================================================================
    # Install git, jq, curl, wget via nix-env for immediate availability
    # These are temporary and will be removed in Phase 5
    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
        exit 1
    fi

    # ========================================================================
    # Step 1.16: Cleanup Conflicting Home-Manager Profiles
    # ========================================================================
    # Remove legacy home-manager installations that could conflict
    print_info "Scanning nix profile for legacy home-manager entries..."
    cleanup_conflicting_home_manager_profile

    # ========================================================================
    # Step 1.17: Ensure Home-Manager is Available
    # ========================================================================
    # home-manager manages user environment (dotfiles, packages, services)
    if command -v home-manager &>/dev/null; then
        print_success "home-manager is installed: $(which home-manager)"
    else
        print_warning "home-manager not found - installing automatically"
        install_home_manager
    fi

    # ========================================================================
    # Step 1.18: Verify Python Runtime Available
    # ========================================================================
    # Python needed for configuration generation scripts
    print_info "Verifying Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        exit 1
    fi

    # Display Python runtime information
    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        print_success "Python runtime: ephemeral Nix shell"
    else
        print_success "Python runtime: ${PYTHON_BIN[0]} ($(${PYTHON_BIN[@]} --version 2>&1))"
    fi

    export IMPERATIVE_INSTALLS_ALLOWED="$previous_imperative_flag"

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 1: System Initialization - COMPLETE"
    echo ""
}

# Execute phase
phase_01_system_initialization
