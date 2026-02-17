#!/usr/bin/env bash
#
# Phase 01: System Initialization
# Purpose: Validate system requirements and install temporary deployment tools
# Version: Uses SCRIPT_VERSION from main script
#
# ============================================================================
# DEPENDENCIES
#
# Container orchestration: K3s only (Podman removed in v6.1.0)
# All container workloads run in K3s cluster deployed in Phase 9.
# ============================================================================

# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/validation.sh → check_disk_space(), check_required_packages(), assert_unique_paths()
#   - lib/hardware.sh → detect_gpu_hardware(), detect_gpu_and_cpu()
#   - lib/nixos.sh → select_nixos_version(), update_nixos_channels()
#   - lib/packages.sh → ensure_preflight_core_packages()
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

phase_01_require_nixos() {
    if [[ ! -e /etc/NIXOS ]]; then
        if [[ -f /etc/os-release ]] && grep -Eq '^ID=nixos' /etc/os-release; then
            return 0
        fi
        print_error "This script must be run on NixOS"
        return "${ERR_NOT_NIXOS:-13}"
    fi
    print_success "Running on NixOS"
}

phase_01_require_non_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        return "${ERR_RUNNING_AS_ROOT:-14}"
    fi
    print_success "Running with correct permissions (non-root)"
}

phase_01_check_critical_commands() {
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")
    local cmd
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            print_error "Critical command not found: $cmd"
            return "${ERR_MISSING_COMMAND:-15}"
        fi
    done
    print_success "Critical NixOS commands available"
}

phase_01_validate_environment() {
    print_section "Part 1: System Validation"
    echo ""

    phase_01_require_nixos || return $?
    phase_01_require_non_root || return $?
    phase_01_check_critical_commands || return $?

    if ! check_disk_space; then
        print_error "Insufficient disk space"
        return "${ERR_DISK_SPACE:-11}"
    fi

    if ! check_network_connectivity; then
        return "${ERR_NETWORK:-10}"
    fi

    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        print_error "Internal configuration path conflict detected"
        return "${ERR_CONFIG_PATH_CONFLICT:-33}"
    fi

    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="${HOME}/Documents/nixos-quick-deploy.sh"
    if [[ -f "$OLD_SCRIPT" ]]; then
        print_warning "Found old deployment script: $OLD_SCRIPT"
        print_info "This can be safely ignored or archived"
    fi

    print_info "Validating dependency chain..."
    check_required_packages || {
        print_error "Required packages not available"
        return 1
    }

    detect_gpu_hardware
    detect_gpu_and_cpu

    print_info "Container orchestration: K3s (configured in Phase 9)"
    if command -v kubectl >/dev/null 2>&1; then
        print_success "kubectl available for K3s management"
    else
        print_info "kubectl will be installed during NixOS configuration"
    fi
}

phase_01_plan_swap_and_hibernation() {
    print_section "Swap & Hibernation Planning"
    echo ""

    ENABLE_ZSWAP_CONFIGURATION="false"
    local previous_swap_detected="false"
    local previous_hibernation_detected="false"
    local zswap_override_mode="${ZSWAP_CONFIGURATION_OVERRIDE:-auto}"

    if declare -F detect_previous_swap_configuration >/dev/null 2>&1 && detect_previous_swap_configuration; then
        previous_swap_detected="true"
    fi

    if declare -F detect_previous_hibernation_configuration >/dev/null 2>&1 && detect_previous_hibernation_configuration; then
        previous_hibernation_detected="true"
    fi

    if [[ "$previous_swap_detected" == "true" && "$previous_hibernation_detected" == "true" ]]; then
        ENABLE_ZSWAP_CONFIGURATION="true"
        print_success "Detected existing swap-backed hibernation; carrying the configuration forward with zswap."
    else
        print_info "Previous deployment lacked hibernation-ready swap; leaving swap and zswap settings unchanged."
        if [[ "$previous_swap_detected" == "true" && "$previous_hibernation_detected" != "true" ]]; then
            print_info "Swap was present but hibernation support was not detected."
        elif [[ "$previous_swap_detected" != "true" && "$previous_hibernation_detected" == "true" ]]; then
            print_info "Hibernation hints were found but no active swap device is available."
        fi
        if [[ "$zswap_override_mode" == "auto" ]]; then
            print_info "Re-run with --enable-zswap to carry swap-backed hibernation forward manually."
        fi
    fi

    case "$zswap_override_mode" in
        enable)
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" != "true" ]]; then
                print_warning "Manual zswap override requested; enabling configuration despite missing legacy detection."
            else
                print_info "Manual zswap override requested; detection already confirmed compatibility."
            fi
            ENABLE_ZSWAP_CONFIGURATION="true"
            ;;
        disable)
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then
                print_warning "Manual zswap override disabled swap prompts for this run."
            else
                print_info "Manual zswap override set to disable; leaving swap configuration unchanged."
            fi
            ENABLE_ZSWAP_CONFIGURATION="false"
            ;;
    esac

    local resume_device_hint=""
    if declare -F discover_resume_device_hint >/dev/null 2>&1; then
        resume_device_hint=$(discover_resume_device_hint 2>/dev/null || echo "")
        if [[ -n "$resume_device_hint" ]]; then
            RESUME_DEVICE_HINT="$resume_device_hint"
            export RESUME_DEVICE_HINT
            if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then
                print_info "Detected resume device from previous deployment: $RESUME_DEVICE_HINT"
            fi
        fi
    fi

    if declare -F discover_resume_offset_hint >/dev/null 2>&1; then
        local resume_offset_hint=""
        resume_offset_hint=$(discover_resume_offset_hint 2>/dev/null || echo "")
        if [[ -n "$resume_offset_hint" ]]; then
            RESUME_OFFSET_HINT="$resume_offset_hint"
            export RESUME_OFFSET_HINT
            print_info "Detected resume offset hint: $RESUME_OFFSET_HINT"
        fi
    fi

    if [[ "$ENABLE_ZSWAP_CONFIGURATION" != "true" && "$zswap_override_mode" == "auto" ]]; then
        if confirm "Enable zswap-backed swap with hibernation support for this deployment?" "y"; then
            ENABLE_ZSWAP_CONFIGURATION="true"
            print_success "Zswap-backed swap configuration enabled."
        else
            print_info "Zswap-backed swap configuration skipped per user choice."
        fi
    fi

    export ENABLE_ZSWAP_CONFIGURATION

    if [[ "$ENABLE_ZSWAP_CONFIGURATION" == "true" ]]; then
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

        print_info "Recommended zswap-backed swap size for reliable hibernation: ${recommended_swap_gb}GB."
        local previous_swap_pref=""
        if declare -F load_cached_hibernation_swap_size >/dev/null 2>&1; then
            previous_swap_pref=$(load_cached_hibernation_swap_size 2>/dev/null || echo "")
        fi

        local swap_prompt_default="$recommended_swap_gb"
        if [[ "$previous_swap_pref" =~ ^[0-9]+$ && $previous_swap_pref -gt 0 ]]; then
            swap_prompt_default="$previous_swap_pref"
            if (( current_swap_gb > 0 && current_swap_gb != previous_swap_pref )); then
                print_info "Previously configured swap size detected: ${previous_swap_pref}GB (active swap: ${current_swap_gb}GB)."
            else
                print_info "Previously configured swap size detected: ${previous_swap_pref}GB."
            fi
        elif (( current_swap_gb > 0 )); then
            swap_prompt_default="$current_swap_gb"
        fi

        if (( current_swap_gb > 0 )); then
            print_info "Press Enter to keep ${swap_prompt_default}GB, type 'current' to use ${current_swap_gb}GB, or enter a new size in GB."
        else
            print_info "Press Enter to keep ${swap_prompt_default}GB or enter a new size in GB."
        fi

        local swap_guard_min=""
        local swap_guard_max=""
        if [[ "${TOTAL_RAM_GB:-}" =~ ^[0-9]+$ && ${TOTAL_RAM_GB} -gt 0 ]]; then
            swap_guard_min="${TOTAL_RAM_GB}"
            local guard_max_candidate=$(( TOTAL_RAM_GB * 2 ))
            if [[ "$recommended_swap_gb" =~ ^[0-9]+$ && $recommended_swap_gb -gt "$guard_max_candidate" ]]; then
                guard_max_candidate="$recommended_swap_gb"
            fi
            swap_guard_max="$guard_max_candidate"
            print_info "Hibernation requires swap at least as large as installed RAM (${swap_guard_min}GB)."
            print_info "Swap requests above roughly ${swap_guard_max}GB exceed the supported memory footprint and waste disk space."
        fi

        local raw_swap_input=""
        while true; do
            raw_swap_input=$(prompt_user "Desired swap size in GB for zswap-backed hibernation" "$swap_prompt_default")

            if [[ -z "$raw_swap_input" ]]; then
                raw_swap_input="$swap_prompt_default"
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

                if [[ -n "$swap_guard_min" ]] && (( raw_swap_input < swap_guard_min )); then
                    print_warning "Swap capacity must be at least the total system memory (${swap_guard_min}GB) to resume from hibernation."
                    continue
                fi

                if [[ -n "$swap_guard_max" ]] && (( raw_swap_input > swap_guard_max )); then
                    print_warning "Requested swap exceeds the supported guard (${swap_guard_max}GB). Choose a value between ${swap_guard_min}GB and ${swap_guard_max}GB."
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

        if declare -F persist_hibernation_swap_size >/dev/null 2>&1; then
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
}

phase_01_start_tool_installation() {
    echo ""
    print_section "Part 2: Temporary Tool Installation"
    echo ""
}

phase_01_select_build_strategy() {
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
    echo "  3) Offload builds to remote builders or private Cachix caches"
    echo "     - Keeps binary caches enabled while layering SSH builders"
    echo "     - Optionally authenticates against private Cachix substituters"
    echo "     - Ideal for low-power hardware or centralized build farms"
    echo ""

    local build_choice
    local default_choice="1"
    if [[ "${USE_BINARY_CACHES:-true}" != "true" ]]; then
        default_choice="2"
    fi
    build_choice=$(prompt_user "Choose build strategy (1-3)" "$default_choice")

    case "$build_choice" in
        3)
            USE_BINARY_CACHES="true"
            # shellcheck disable=SC2034
            REMOTE_BUILD_ACCELERATION_MODE="remote-builders"
            print_success "Remote build acceleration selected – binary caches plus remote builders"
            if declare -F gather_remote_build_acceleration_preferences >/dev/null 2>&1; then
                gather_remote_build_acceleration_preferences
            fi
            ;;
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

    if declare -F describe_remote_build_context >/dev/null 2>&1; then
        describe_remote_build_context
    fi

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
}

phase_01_select_nixos_release() {
    select_nixos_version
    update_nixos_channels
}

phase_01_install_prerequisites() {
    if ! ensure_preflight_core_packages; then
        print_error "Failed to install core prerequisite packages"
        return 1
    fi

    print_info "Verifying Python runtime..."
    if ! ensure_python_runtime; then
        print_error "Unable to locate or provision a python interpreter"
        return 1
    fi

    if [[ "${PYTHON_BIN[0]}" == "nix" ]]; then
        print_success "Python runtime: ephemeral Nix shell"
    else
        print_success "Python runtime: ${PYTHON_BIN[0]} ($("${PYTHON_BIN[@]}" --version 2>&1))"
    fi
}

phase_01_collect_user_preferences() {
    print_section "User Preferences & Integrations"
    echo ""
    if ! ensure_user_settings_ready --interactive; then
        print_error "Failed to collect user preferences and integrations"
        return 1
    fi
}

phase_01_detect_hardware() {
    print_section "Hardware Auto-Detection"
    echo ""

    local hw_hostname
    hw_hostname=$(hostname)
    local hw_user="${PRIMARY_USER:-${USER:-$(id -un)}}"
    local hw_profile="${FLAKE_FIRST_PROFILE:-minimal}"
    local hw_project_root="${BOOTSTRAP_SCRIPT_DIR:-${SCRIPT_DIR}}"
    local hw_enable_hibernation="${ENABLE_ZSWAP_CONFIGURATION:-false}"
    local hw_swap_gb="${HIBERNATION_SWAP_SIZE_GB:-0}"

    if ! declare -F detect_and_write_hardware_facts >/dev/null 2>&1; then
        print_warning "detect_and_write_hardware_facts not available; skipping hardware detection"
        return 0
    fi

    if ! detect_and_write_hardware_facts \
            "$hw_hostname" \
            "$hw_user" \
            "$hw_profile" \
            "$hw_project_root" \
            "$hw_enable_hibernation" \
            "$hw_swap_gb"; then
        print_warning "Hardware detection encountered errors; facts.nix may be incomplete"
        return 0
    fi

    print_success "Hardware facts written to nix/hosts/${hw_hostname}/facts.nix"
    echo ""
}

phase_01_setup_secrets_infrastructure() {
    print_section "Secrets Infrastructure Setup"
    echo ""

    print_info "Installing secrets management dependencies..."

    if ! command -v age-keygen >/dev/null 2>&1; then
        print_info "Installing age..."
        if nix-env -iA nixpkgs.age > >(tee -a "$LOG_FILE") 2>&1; then
            print_success "age installed"
        else
            print_warning "age installation via nix-env failed, trying nix profile..."
            if ! nix profile install nixpkgs#age > >(tee -a "$LOG_FILE") 2>&1; then
                print_warning "Failed to install age"
            fi
        fi
    else
        print_success "age already installed"
    fi

    if ! command -v sops >/dev/null 2>&1; then
        print_info "Installing sops..."
        if nix-env -iA nixpkgs.sops > >(tee -a "$LOG_FILE") 2>&1; then
            print_success "sops installed"
        else
            print_warning "sops installation via nix-env failed, trying nix profile..."
            if ! nix profile install nixpkgs#sops > >(tee -a "$LOG_FILE") 2>&1; then
                print_warning "Failed to install sops"
            fi
        fi
    else
        print_success "sops already installed"
    fi

    if declare -F init_sops >/dev/null 2>&1; then
        print_info "Initializing sops infrastructure..."
        if init_sops > >(tee -a "$LOG_FILE") 2>&1; then
            print_success "Secrets infrastructure initialized"
        else
            print_warning "Secrets initialization had issues (non-fatal, will retry in Phase 3)"
        fi
    else
        print_info "Secrets management will be initialized in Phase 3"
    fi
}

phase_01_run() {
    phase_01_validate_environment || return $?
    phase_01_plan_swap_and_hibernation || return $?
    phase_01_detect_hardware || return $?
    phase_01_start_tool_installation
    phase_01_select_build_strategy || return $?
    phase_01_select_nixos_release || return $?
    phase_01_install_prerequisites || return $?
    phase_01_collect_user_preferences || return $?
    phase_01_setup_secrets_infrastructure || return $?
}

phase_01_system_initialization() {
    local phase_name="system_initialization"

    if is_step_complete "$phase_name"; then
        print_info "Phase 1 already completed (skipping)"
        return 0
    fi

    print_section "Phase 1/8: System Initialization"
    echo ""

    local previous_imperative_flag="${IMPERATIVE_INSTALLS_ALLOWED:-false}"
    export IMPERATIVE_INSTALLS_ALLOWED=true

    local phase_status=0
    if ! phase_01_run; then
        phase_status=$?
    fi

    export IMPERATIVE_INSTALLS_ALLOWED="$previous_imperative_flag"

    if (( phase_status != 0 )); then
        return "$phase_status"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 1: System Initialization - COMPLETE"
    echo ""
}


# Execute phase
phase_01_system_initialization
