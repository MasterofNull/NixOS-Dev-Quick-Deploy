#!/usr/bin/env bash
#
# Phase 01: Preparation & Validation
# Purpose: Validate system meets all requirements before starting deployment
# Version: 3.2.0
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
#
# Required Variables (from config/variables.sh):
#   - USER → Current user name
#   - EUID → Effective user ID
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - print_info() → Print info message
#   - print_success() → Print success message
#   - print_error() → Print error message
#   - print_warning() → Print warning message
#   - check_disk_space() → Validate sufficient disk space
#   - check_required_packages() → Validate dependency chain
#   - assert_unique_paths() → Validate no path conflicts
#   - detect_gpu_hardware() → Detect GPU hardware
#   - detect_gpu_and_cpu() → Detect CPU and memory
#
# Requires Phases (must complete before this):
#   - None (first phase)
#
# Produces (for later phases):
#   - GPU_TYPE → Detected GPU type (nvidia/amd/intel/software)
#   - GPU_DRIVER → GPU driver package name
#   - GPU_PACKAGES → Additional GPU packages
#   - LIBVA_DRIVER → VA-API driver for hardware acceleration
#   - State: "preparation_validation" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_01_preparation() {
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

# Execute phase
phase_01_preparation
