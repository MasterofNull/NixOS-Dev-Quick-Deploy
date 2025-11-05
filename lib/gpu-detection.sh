#!/usr/bin/env bash
#
# GPU Detection
# Purpose: Detect GPU hardware and set appropriate variables
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/user-interaction.sh → print_* functions
#
# Required Variables:
#   - None (sets GPU_TYPE, GPU_DRIVER, GPU_PACKAGES, LIBVA_DRIVER)
#
# Exports:
#   - detect_gpu_hardware() → Detect GPU and set variables
#   - GPU_TYPE → Detected GPU type (intel/amd/nvidia/software/unknown)
#   - GPU_DRIVER → Driver name
#   - GPU_PACKAGES → Required packages for GPU
#   - LIBVA_DRIVER → VA-API driver name
#
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
