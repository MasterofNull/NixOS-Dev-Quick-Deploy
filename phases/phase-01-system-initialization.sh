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

    local phase_name="system_initialization"  # State tracking identifier for this phase

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state file for completion marker
        print_info "Phase 1 already completed (skipping)"
            return 0  # Skip phase execution
    fi

    print_section "Phase 1/8: System Initialization"  # Display phase header
        echo ""

    # Allow temporary imperative package installs for this phase
    local previous_imperative_flag="${IMPERATIVE_INSTALLS_ALLOWED:-false}"  # Save previous state
        export IMPERATIVE_INSTALLS_ALLOWED=true  # Enable nix-env usage temporarily

    # ========================================================================
    # PART 1: SYSTEM VALIDATION
    # ========================================================================

    # ========================================================================
    # Step 1.1: Verify Running on NixOS
    # ========================================================================
    # Why: This script uses NixOS-specific commands (nixos-rebuild, etc.)
    # How: Check for /etc/NIXOS file which exists only on NixOS
    if [[ ! -f /etc/NIXOS ]]; then  # /etc/NIXOS marker file missing
        print_error "This script must be run on NixOS"
            exit 1  # Fatal - cannot proceed on non-NixOS
    fi
    print_success "Running on NixOS"

    # ========================================================================
    # Step 1.2: Verify NOT Running as Root
    # ========================================================================
    # Why: Running as root causes permission issues (files owned by root)
    # Script will use 'sudo' when needed for specific commands
    if [[ $EUID -eq 0 ]]; then  # Effective UID is 0 (root user)
        print_error "This script should NOT be run as root"
            print_info "It will use sudo when needed for system operations"
        exit 1  # Fatal - prevents root-owned file creation
    fi
    print_success "Running with correct permissions (non-root)"

    # ========================================================================
    # Step 1.3: Verify Critical NixOS Commands Available
    # ========================================================================
    # Essential commands: nixos-rebuild, nix-env, nix-channel
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")  # Required NixOS tools
        for cmd in "${critical_commands[@]}"; do  # Check each command
        if ! command -v "$cmd" &>/dev/null; then  # Command not in PATH
            print_error "Critical command not found: $cmd"
                exit 1  # Fatal - cannot deploy without these tools
        fi
    done
    print_success "Critical NixOS commands available"

    # ========================================================================
    # Step 1.4: Verify Sufficient Disk Space
    # ========================================================================
    # NixOS deployment requires significant disk space for packages,
    # builds, and multiple system generations
    if ! check_disk_space; then  # Disk space check failed (defined in lib/validation.sh)
        print_error "Insufficient disk space"
            exit 1  # Fatal - need space for packages and generations
    fi

    # ========================================================================
    # Step 1.5: Validate Network Connectivity
    # ========================================================================
    # Need internet to download packages from NixOS binary cache
    print_info "Checking network connectivity..."
    if ping -c 1 -W 5 cache.nixos.org &>/dev/null || ping -c 1 -W 5 8.8.8.8 &>/dev/null; then  # Try NixOS cache, fallback to Google DNS
        print_success "Network connectivity OK"
    else
        print_error "No network connectivity detected"
            print_error "Internet connection required to download packages"
        exit 1  # Fatal - cannot download packages without network
    fi

    # ========================================================================
    # Step 1.6: Validate Configuration Path Uniqueness
    # ========================================================================
    # Ensure no two config files try to use the same path
    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then  # Check for path conflicts
        print_error "Internal configuration path conflict detected"
            exit 1  # Fatal - would cause file collisions
    fi

    # ========================================================================
    # Step 1.7: Check for Old Deployment Artifacts
    # ========================================================================
    # Warn about old monolithic script from v2.x
    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="/home/$USER/Documents/nixos-quick-deploy.sh"  # Path to v2.x monolithic script
        if [[ -f "$OLD_SCRIPT" ]]; then  # Old script found
        print_warning "Found old deployment script: $OLD_SCRIPT"
            print_info "This can be safely ignored or archived"  # Not a fatal issue
    fi

    # ========================================================================
    # Step 1.8: Validate Entire Dependency Chain
    # ========================================================================
    # Ensure all required packages available in Nix channels
    print_info "Validating dependency chain..."
    check_required_packages || {  # Validate packages available (from lib/validation.sh)
        print_error "Required packages not available"
            exit 1  # Fatal - need packages for deployment
    }

    # ========================================================================
    # Step 1.9: Hardware Detection - GPU
    # ========================================================================
    # Detect GPU type to install correct drivers:
    # - NVIDIA: Proprietary nvidia drivers + CUDA
    # - AMD: Mesa + AMDGPU drivers + ROCm
    # - Intel: Mesa + i915/Xe drivers + oneAPI
    # - Software: No GPU, CPU-only rendering
    detect_gpu_hardware  # Sets GPU_TYPE, GPU_DRIVER, GPU_PACKAGES, LIBVA_DRIVER

    # ========================================================================
    # Step 1.10: Hardware Detection - CPU and Memory
    # ========================================================================
    # Optimize configuration based on available resources
    detect_gpu_and_cpu  # Sets CPU_COUNT, MEMORY_GB for tuning

    # ========================================================================
    # Step 1.11: Plan Swap and Hibernation Capacity
    # ========================================================================
    # Detect if previous deployment used swap-backed hibernation with zswap.
    # If found, carry forward the config. User can override with CLI flags.
    print_section "Swap & Hibernation Planning"
    echo ""

    # Initialize swap/hibernation detection flags
    ENABLE_ZSWAP_CONFIGURATION="false"  # Default: don't configure zswap
        local previous_swap_detected="false"  # Was swap configured in previous deployment?
    local previous_hibernation_detected="false"  # Was hibernation configured previously?
        local zswap_override_mode="${ZSWAP_CONFIGURATION_OVERRIDE:-auto}"  # User override: enable/disable/auto

    # Detect previous swap configuration from existing config files
    if declare -F detect_previous_swap_configuration >/dev/null 2>&1 && detect_previous_swap_configuration; then
        previous_swap_detected="true"  # Found swap devices in previous config
    fi

    # Detect previous hibernation configuration from boot parameters
    if declare -F detect_previous_hibernation_configuration >/dev/null 2>&1 && detect_previous_hibernation_configuration; then
        previous_hibernation_detected="true"  # Found resume= kernel parameter
    fi

    # Decide whether to enable zswap configuration based on detection
    if [[ "$previous_swap_detected" == "true" && "$previous_hibernation_detected" == "true" ]]; then  # Both swap and hibernation found
        ENABLE_ZSWAP_CONFIGURATION="true"  # Carry forward existing configuration
            print_success "Detected existing swap-backed hibernation; carrying the configuration forward with zswap."
    else  # Missing swap or hibernation config
        print_info "Previous deployment lacked hibernation-ready swap; leaving swap and zswap settings unchanged."
            # Provide diagnostic info about what was missing
            if [[ "$previous_swap_detected" == "true" && "$previous_hibernation_detected" != "true" ]]; then
            print_info "Swap was present but hibernation support was not detected."
        elif [[ "$previous_swap_detected" != "true" && "$previous_hibernation_detected" == "true" ]]; then
            print_info "Hibernation hints were found but no active swap device is available."
        fi
        # Suggest manual override if in auto mode
        if [[ "$zswap_override_mode" == "auto" ]]; then
            print_info "Re-run with --enable-zswap to carry swap-backed hibernation forward manually."
        fi
    fi

    # Handle user override flags (--enable-zswap, --disable-zswap, --zswap-auto)
    case "$zswap_override_mode" in
        enable)  # Force-enable zswap configuration
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" != "true" ]]; then  # Override detection result
                print_warning "Manual zswap override requested; enabling configuration despite missing legacy detection."
            else  # Confirming existing detection
                print_info "Manual zswap override requested; detection already confirmed compatibility."
            fi
            ENABLE_ZSWAP_CONFIGURATION="true"  # Force enable
            ;;
        disable)  # Force-disable zswap configuration
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then  # Override detection result
                print_warning "Manual zswap override disabled swap prompts for this run."
            else  # Already disabled
                print_info "Manual zswap override set to disable; leaving swap configuration unchanged."
            fi
            ENABLE_ZSWAP_CONFIGURATION="false"  # Force disable
            ;;
    esac

    # Try to discover resume device from previous deployment
    local resume_device_hint=""  # Will store /dev/XXX path
        if declare -F discover_resume_device_hint >/dev/null 2>&1; then  # Function exists
        resume_device_hint=$(discover_resume_device_hint 2>/dev/null || echo "")  # Get resume device path
            if [[ -n "$resume_device_hint" ]]; then  # Resume device found
            RESUME_DEVICE_HINT="$resume_device_hint"  # Store for config generation
                export RESUME_DEVICE_HINT  # Make available to all phases
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then  # Only show if zswap enabled
                print_info "Detected resume device from previous deployment: $RESUME_DEVICE_HINT"
            fi
        fi
    fi

    export ENABLE_ZSWAP_CONFIGURATION  # Make flag available to config generation phases

    # If zswap configuration is enabled, prompt user for swap size
    if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then
        # Calculate current active swap size
        local current_swap_gb  # Size of currently active swap in GB
            current_swap_gb=$(calculate_active_swap_total_gb)  # Parse from swapon output

        # Calculate recommended swap size based on RAM
        local recommended_swap_gb  # Recommended size = RAM + buffer for hibernation
            recommended_swap_gb=$(suggest_hibernation_swap_size "${TOTAL_RAM_GB:-0}")  # Function from lib/
        if ! [[ "$recommended_swap_gb" =~ ^[0-9]+$ ]] || (( recommended_swap_gb <= 0 )); then  # Invalid or zero
            recommended_swap_gb=8  # Fallback to 8GB default
        fi

        # Display system memory information to user
        if [[ "${TOTAL_RAM_GB:-}" =~ ^[0-9]+$ && ${TOTAL_RAM_GB} -gt 0 ]]; then  # Valid RAM detection
            print_info "Detected system memory: ${TOTAL_RAM_GB}GB."
        else  # RAM detection failed
            print_warning "Unable to determine total system memory; swap sizing suggestions may be inaccurate."
        fi

        # Display current swap information
        if (( current_swap_gb > 0 )); then  # Swap is active
            print_info "Active swap currently configured: ${current_swap_gb}GB."
        else  # No swap detected
            print_warning "No active swap space detected on this system."
        fi

        # Show recommended size and load previous user preference (if any)
        print_info "Recommended zswap-backed swap size for reliable hibernation: ${recommended_swap_gb}GB."
        local previous_swap_pref=""  # Previously configured swap size from cache
            if declare -F load_cached_hibernation_swap_size >/dev/null 2>&1; then  # Cache function exists
            previous_swap_pref=$(load_cached_hibernation_swap_size 2>/dev/null || echo "")  # Load from cache file
        fi

        # Determine default value for swap size prompt
        local swap_prompt_default="$recommended_swap_gb"  # Start with recommendation
            if [[ "$previous_swap_pref" =~ ^[0-9]+$ && $previous_swap_pref -gt 0 ]]; then  # Previous preference found
            swap_prompt_default="$previous_swap_pref"  # Use previous choice as default
                if (( current_swap_gb > 0 && current_swap_gb != previous_swap_pref )); then  # Active swap differs from previous
                print_info "Previously configured swap size detected: ${previous_swap_pref}GB (active swap: ${current_swap_gb}GB)."
            else  # Previous matches active or no active swap
                print_info "Previously configured swap size detected: ${previous_swap_pref}GB."
            fi
        elif (( current_swap_gb > 0 )); then  # No previous pref, but active swap exists
            swap_prompt_default="$current_swap_gb"  # Default to current active size
        fi

        # Display prompt instructions based on whether swap exists
        if (( current_swap_gb > 0 )); then  # Active swap exists
            print_info "Press Enter to keep ${swap_prompt_default}GB, type 'current' to use ${current_swap_gb}GB, or enter a new size in GB."
        else  # No active swap
            print_info "Press Enter to keep ${swap_prompt_default}GB or enter a new size in GB."
        fi

        # Interactive prompt loop for swap size input
        local raw_swap_input=""  # User's input string
            while true; do  # Loop until valid input received
            # Prompt user for swap size with default value
            raw_swap_input=$(prompt_user "Desired swap size in GB for zswap-backed hibernation" "$swap_prompt_default")

            # Handle empty input (user pressed Enter)
            if [[ -z "$raw_swap_input" ]]; then  # Empty input
                raw_swap_input="$swap_prompt_default"  # Use default value
            fi

            # Handle "current" keyword to use active swap size
            if [[ "${raw_swap_input,,}" == "current" ]]; then  # User typed "current" (case-insensitive)
                if (( current_swap_gb > 0 )); then  # Active swap exists
                    HIBERNATION_SWAP_SIZE_GB="$current_swap_gb"  # Use current active size
                        print_success "Keeping current swap allocation (${current_swap_gb}GB)."
                    break  # Exit prompt loop
                else  # No active swap to use
                    print_warning "No active swap detected. Please enter a numeric size."
                        continue  # Re-prompt
                fi
            fi

            # Validate numeric input
            if [[ "$raw_swap_input" =~ ^[0-9]+$ ]]; then  # Valid integer
                if (( raw_swap_input <= 0 )); then  # Zero or negative
                    print_warning "Swap size must be greater than zero to support hibernation."
                        continue  # Re-prompt
                fi
                # Accept valid size
                HIBERNATION_SWAP_SIZE_GB="$raw_swap_input"  # Store user's choice
                    if (( raw_swap_input == recommended_swap_gb )); then  # User chose recommended size
                    print_success "Using recommended swap size of ${raw_swap_input}GB."
                else  # User chose custom size
                    print_success "Using custom swap size of ${raw_swap_input}GB."
                fi
                break  # Exit prompt loop
            fi

            # Invalid input - re-prompt
            print_warning "Invalid input. Enter a whole number of gigabytes or type 'current'."
        done

        export HIBERNATION_SWAP_SIZE_GB  # Make available to config generation

        # Persist user's choice to cache file for future runs
        if declare -F persist_hibernation_swap_size >/dev/null 2>&1; then  # Cache function exists
            persist_hibernation_swap_size "$HIBERNATION_SWAP_SIZE_GB" || true
        fi

        if [[ -z "$RESUME_DEVICE_HINT" ]]; then
            print_warning "No resume device hint detected; verify boot.resumeDevice after generation."
        fi

        local default_zswap="${ZSWAP_MAX_POOL_PERCENT:-20}"
        print_info "Zswap keeps a compressed cache of swapped pages in RAM to reduce disk thrashing."
        print_info "Current heuristic pool limit: ${default_zswap}% of RAM."
        print_info "Larger values retain more compressed pages (using more RAM); smaller values fall back to disk swap sooner."

        local zswap_input=""
        while true; do
            zswap_input=$(prompt_user "Maximum zswap pool percent (5-40)" "$default_zswap")

            if [[ "${zswap_input,,}" == "auto" ]]; then
                ZSWAP_MAX_POOL_PERCENT="$default_zswap"
                print_success "Keeping recommended zswap pool limit of ${ZSWAP_MAX_POOL_PERCENT}% of RAM."
                break
            fi

            if [[ "$zswap_input" =~ ^[0-9]+$ ]]; then
                if (( zswap_input < 5 || zswap_input > 40 )); then
                    print_warning "Enter a value between 5 and 40, or type 'auto' to keep ${default_zswap}%."
                    continue
                fi

                ZSWAP_MAX_POOL_PERCENT="$zswap_input"
                if [[ "$ZSWAP_MAX_POOL_PERCENT" == "$default_zswap" ]]; then
                    print_success "Using recommended zswap pool limit of ${ZSWAP_MAX_POOL_PERCENT}% of RAM."
                else
                    print_success "Zswap pool limit set to ${ZSWAP_MAX_POOL_PERCENT}% of RAM."
                fi
                break
            fi

            print_warning "Invalid input. Enter a whole number between 5 and 40 or type 'auto'."
        done
        export ZSWAP_MAX_POOL_PERCENT
    else
        HIBERNATION_SWAP_SIZE_GB=""
        export HIBERNATION_SWAP_SIZE_GB
    fi

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
