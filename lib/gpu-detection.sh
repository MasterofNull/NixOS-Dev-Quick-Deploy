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

# ============================================================================
# Detect GPU Hardware Function
# ============================================================================
# Purpose: Auto-detect GPU hardware and set appropriate configuration variables
# Parameters: None
# Returns: 0 (always succeeds, sets global variables)
#
# Sets global variables:
#   GPU_TYPE - Type of GPU (intel/amd/nvidia/software/unknown)
#   GPU_DRIVER - Driver name for NixOS configuration
#   GPU_PACKAGES - Required packages for GPU support
#   LIBVA_DRIVER - VA-API driver for hardware video acceleration
#
# How it works:
# 1. Check if lspci is available (from pciutils package)
# 2. Query PCI devices for VGA/Display adapters
# 3. Parse output to identify GPU vendor
# 4. Set appropriate variables for each GPU type
# 5. Handle fallback to software rendering if no GPU found
#
# Why auto-detect GPU?
# - Different GPUs need different drivers and packages
# - Intel, AMD, and NVIDIA have completely different driver stacks
# - Reduces manual configuration burden
# - Ensures correct video acceleration setup
# - Optimizes system for available hardware
#
# GPU Detection Challenge:
# Some systems have multiple GPUs (integrated + dedicated)
# This function detects all GPUs and prioritizes dedicated GPU
# Last match wins (NVIDIA > AMD > Intel in typical detection order)
# ============================================================================
detect_gpu_hardware() {
    # Display section header
    print_section "Detecting GPU Hardware"

    # ========================================================================
    # Initialize GPU variables to default values
    # ========================================================================
    # These will be overwritten if specific GPU is detected
    # Starting with "unknown" provides safe fallback
    GPU_TYPE="unknown"        # Type of GPU detected
    GPU_DRIVER=""             # Driver name (for NixOS config)
    GPU_PACKAGES=""           # Required packages
    LIBVA_DRIVER=""           # VA-API driver for video acceleration

    # ========================================================================
    # Check if lspci command is available
    # ========================================================================
    # lspci is provided by pciutils package
    # It lists all PCI devices including GPUs
    # command -v returns path if command exists, empty if not
    if ! command -v lspci >/dev/null 2>&1; then
        # lspci not available - can't auto-detect GPU
        # This is common on minimal/fresh installations
        print_warning "lspci not found - GPU detection will be limited"
        print_info "Install pciutils for automatic GPU detection: nix-env -iA nixos.pciutils"

        # Fall back to software rendering
        # System will work but without hardware acceleration
        GPU_TYPE="software"
        return 0  # Not an error, just limited detection
    fi

    # ========================================================================
    # Query PCI devices for graphics hardware
    # ========================================================================
    # lspci lists all PCI devices
    # grep filters for graphics-related devices:
    # - VGA: Standard VGA-compatible controller
    # - 3D: 3D graphics controller
    # - Display: Display controller
    #
    # -i = case insensitive
    # -E = extended regex
    # || echo "" = fallback to empty string if no GPU found
    local gpu_info
    gpu_info=$(lspci | grep -iE "VGA|3D|Display" || echo "")

    # Check if any GPU was detected
    # -z tests if string is empty
    if [[ -z "$gpu_info" ]]; then
        # No GPU found in PCI devices
        # This happens on some VMs, embedded systems, or very old hardware
        print_info "No dedicated GPU detected - using software rendering"
        GPU_TYPE="software"
        return 0  # Not an error, just no GPU
    fi

    # ========================================================================
    # Display detected GPU information to user
    # ========================================================================
    print_info "GPU Hardware Detected:"

    # Indent each line of GPU info with 2 spaces
    # sed 's/^/  /' adds 2 spaces to start of each line
    # Makes output more readable as sub-item
    echo "$gpu_info" | sed 's/^/  /'
    echo ""  # Blank line for visual separation

    # ========================================================================
    # Detect Intel GPU
    # ========================================================================
    # Check if GPU info contains "Intel"
    # grep -iq = case insensitive, quiet (just exit code)
    if echo "$gpu_info" | grep -iq "Intel"; then
        GPU_TYPE="intel"
        GPU_DRIVER="intel"

        # VA-API driver for Intel:
        # iHD = Intel Media Driver (for Gen 8+ / Broadwell and newer)
        # i965 = older driver (for Gen 7 and earlier)
        # iHD is the modern choice for recent Intel GPUs
        LIBVA_DRIVER="iHD"

        # Required packages for Intel GPU support:
        # intel-media-driver: Modern VA-API driver (iHD)
        # vaapiIntel: Legacy VA-API driver (i965) for compatibility
        GPU_PACKAGES="intel-media-driver vaapiIntel"

        print_success "Intel GPU detected"
        print_info "  Driver: $GPU_DRIVER"
        print_info "  VA-API: $LIBVA_DRIVER"
    fi

    # ========================================================================
    # Detect AMD GPU
    # ========================================================================
    # AMD has multiple brand names: AMD, ATI (older), Radeon
    # grep -iq checks for any of these
    # \| is OR operator in extended regex
    if echo "$gpu_info" | grep -iq "AMD\|ATI\|Radeon"; then
        GPU_TYPE="amd"

        # AMD GPU driver:
        # amdgpu = modern open-source driver for AMD GPUs
        # Supports GCN 1.0+ (Radeon HD 7000 series and newer)
        GPU_DRIVER="amdgpu"

        # VA-API driver for AMD:
        # radeonsi = RadeonSI Gallium driver (part of Mesa)
        # This is the standard open-source driver for AMD GPUs
        LIBVA_DRIVER="radeonsi"

        # Required packages for AMD GPU support:
        # mesa: Open-source graphics drivers (includes RADV Vulkan driver)
        # rocm-opencl-icd: ROCm OpenCL driver for compute workloads
        GPU_PACKAGES="mesa rocm-opencl-icd"

        print_success "AMD GPU detected"

        # RADV is the Vulkan driver in Mesa (modern default for AMD)
        # Alternative is AMDVLK (AMD's official Vulkan driver)
        # RADV generally has better performance and compatibility
        print_info "  Driver: $GPU_DRIVER (RADV - modern default)"
        print_info "  VA-API: $LIBVA_DRIVER"
    fi

    # ========================================================================
    # Detect NVIDIA GPU
    # ========================================================================
    if echo "$gpu_info" | grep -iq "NVIDIA"; then
        GPU_TYPE="nvidia"
        GPU_DRIVER="nvidia"

        # NVIDIA has proprietary driver stack
        # The nvidia package provides OpenGL, Vulkan, CUDA, etc.
        LIBVA_DRIVER="nvidia"

        # Required packages for NVIDIA GPU support:
        # nvidia-vaapi-driver: VA-API wrapper for NVIDIA GPUs
        # This allows NVIDIA GPUs to work with VA-API applications
        # (VA-API is primarily designed for Intel/AMD)
        GPU_PACKAGES="nvidia-vaapi-driver"

        print_success "NVIDIA GPU detected"
        print_info "  Driver: $GPU_DRIVER"
        print_info "  VA-API: $LIBVA_DRIVER"

        # NVIDIA on Wayland needs special configuration
        # Wayland is the modern display server (successor to X11)
        # NVIDIA support for Wayland requires modesetting to be enabled
        print_warning "NVIDIA on Wayland requires additional configuration"
        print_info "Consider enabling: hardware.nvidia.modesetting.enable = true"
    fi

    # ========================================================================
    # Handle unknown GPU type
    # ========================================================================
    # If GPU was detected but not Intel/AMD/NVIDIA
    # This is rare but possible with exotic hardware
    if [[ "$GPU_TYPE" == "unknown" ]]; then
        print_warning "Unknown GPU type - using software rendering"
        GPU_TYPE="software"
    fi

    # Preserve package metadata for callers sourcing this library.
    : "${GPU_PACKAGES}"

    echo ""  # Blank line for visual separation
    return 0  # Always return success
}

# ============================================================================
# GPU Detection Notes and Context
# ============================================================================
# VA-API (Video Acceleration API):
# - Standard Linux API for hardware video decode/encode
# - Supported by Intel and AMD out of the box
# - NVIDIA requires wrapper (nvidia-vaapi-driver)
# - Used by browsers, media players, video editors
#
# GPU Driver Stacks:
# Intel: Open source, in kernel, good Linux support
# AMD: Open source (amdgpu/RADV), excellent Linux support
# NVIDIA: Proprietary, requires manual install, improving Linux support
#
# Why separate packages for each vendor?
# - Each GPU vendor has different driver architecture
# - Different acceleration APIs (VA-API vs NVENC vs etc)
# - Different Vulkan implementations
# - Different compute platforms (ROCm vs CUDA)
#
# Multi-GPU systems:
# Some systems have integrated + dedicated GPU (hybrid graphics)
# This detection will set variables for the "last" GPU detected
# For more complex multi-GPU setups, manual configuration may be needed
#
# Software rendering fallback:
# If no GPU detected or lspci unavailable, system uses software rendering
# Mesa's llvmpipe provides CPU-based OpenGL
# Works but much slower than hardware acceleration
# Sufficient for basic desktop use, not for gaming or video work
# ============================================================================
