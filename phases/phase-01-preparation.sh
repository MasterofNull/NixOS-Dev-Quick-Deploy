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
    # ========================================================================
    # Phase 1: Preparation & Validation
    # ========================================================================
    # This is the first and most critical phase of deployment.
    # It validates that the system meets ALL requirements before making any
    # changes. Think of it as a "preflight checklist" - if anything fails
    # here, we stop immediately rather than partially completing a deployment.
    #
    # This phase performs "fail-fast" validation:
    # - System environment checks (NixOS, permissions)
    # - Required command availability
    # - Resource checks (disk space, network)
    # - Configuration validation (no path conflicts)
    # - Hardware detection (GPU, CPU, memory)
    #
    # Exit early if ANY check fails - it's better to stop before changes
    # than to fail midway through deployment with a partially configured system.
    # ========================================================================

    local phase_name="preparation_validation"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    # Check state.json to see if this phase already completed successfully.
    # This enables resume-from-failure: if deployment crashes at phase 7,
    # rerunning the script will skip phases 1-6 that already succeeded.
    #
    # Why: Saves time and prevents redundant system checks
    # State file: ~/.config/nixos-quick-deploy/state.json
    if is_step_complete "$phase_name"; then
        print_info "Phase 1 already completed (skipping)"
        return 0
    fi

    # Print phase header for user visibility
    print_section "Phase 1/10: Preparation & Validation"
    echo ""

    # ========================================================================
    # Step 1.1: Verify Running on NixOS
    # ========================================================================
    # Why: This script is specifically for NixOS and uses nixos-rebuild,
    #      nix-env, and other NixOS-specific commands that don't exist on
    #      other Linux distributions or operating systems
    # How: Check for /etc/NIXOS file which exists only on NixOS systems
    # What if it fails: Exit immediately - cannot proceed on non-NixOS
    #
    # Note: Other distros (Arch, Ubuntu, etc.) use different package managers
    #       and system configuration approaches, so this script won't work
    if [[ ! -f /etc/NIXOS ]]; then
        print_error "This script must be run on NixOS"
        exit 1
    fi
    print_success "Running on NixOS"

    # ========================================================================
    # Step 1.2: Verify NOT Running as Root
    # ========================================================================
    # Why: Running as root can cause permission issues later:
    #      1. Files created would be owned by root, not the user
    #      2. home-manager configs in /root instead of /home/user
    #      3. Security risk - don't need full root for entire script
    # How: Check EUID (Effective User ID) - 0 means root
    # What: Script will use 'sudo' for specific commands that need elevation
    #
    # EUID vs UID:
    # - UID: Real user ID (who you logged in as)
    # - EUID: Effective user ID (what permissions you currently have)
    # - EUID=0 means running with root privileges (via sudo or as root)
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_info "It will use sudo when needed for system operations"
        exit 1
    fi
    print_success "Running with correct permissions (non-root)"

    # ========================================================================
    # Step 1.3: Verify Critical NixOS Commands Available
    # ========================================================================
    # Why: These commands are essential for deployment:
    #      - nixos-rebuild: Applies system configuration changes
    #      - nix-env: Manages user environment packages
    #      - nix-channel: Manages package repositories
    # How: Use 'command -v' to check if command exists in PATH
    # What if missing: Exit - core NixOS installation may be broken
    #
    # Why use array: Makes it easy to add/remove commands to check
    # Why local -a: 'local' = function scope, '-a' = array variable
    local -a critical_commands=("nixos-rebuild" "nix-env" "nix-channel")
    for cmd in "${critical_commands[@]}"; do
        # command -v: POSIX-compliant way to check if command exists
        # &>/dev/null: Redirect both stdout and stderr to /dev/null (suppress output)
        if ! command -v "$cmd" &>/dev/null; then
            print_error "Critical command not found: $cmd"
            exit 1
        fi
    done
    print_success "Critical NixOS commands available"

    # ========================================================================
    # Step 1.4: Verify Sufficient Disk Space
    # ========================================================================
    # Why: NixOS deployment requires significant disk space:
    #      - Package downloads (several GB from cache.nixos.org)
    #      - Build artifacts (if packages need compilation)
    #      - Multiple system generations (rollback capability)
    #      - /nix/store can grow large over time
    # How: check_disk_space() function checks / and /nix partitions
    # Typical requirement: 10GB+ free recommended
    #
    # What if insufficient: Exit before downloading - prevents partial install
    if ! check_disk_space; then
        print_error "Insufficient disk space"
        exit 1
    fi

    # ========================================================================
    # Step 1.5: Validate Network Connectivity
    # ========================================================================
    # Why: Need internet to download packages from NixOS binary cache
    #      Without network, deployment will fail when trying to fetch packages
    # How: Ping two targets in order of preference:
    #      1. cache.nixos.org - Official NixOS binary cache (primary source)
    #      2. 8.8.8.8 - Google DNS (verifies basic internet connectivity)
    # Flags: -c 1 (send 1 packet), -W 5 (wait max 5 seconds for response)
    #
    # Why two targets: cache.nixos.org might be down, but internet still works
    # Why ping: Simple, reliable, works without DNS if using IP addresses
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
    # Why: Ensure no two config files try to use the same path
    #      Example conflict: Both system and home-manager configs at same path
    # How: assert_unique_paths() checks that all paths are different
    # Variables checked:
    #      - HOME_MANAGER_FILE: ~/.config/home-manager/home.nix
    #      - SYSTEM_CONFIG_FILE: /etc/nixos/configuration.nix
    #      - HARDWARE_CONFIG_FILE: /etc/nixos/hardware-configuration.nix
    #
    # What if conflict: Exit - indicates configuration error in variables.sh
    # This is a "sanity check" to catch programming errors in the script itself
    if ! assert_unique_paths HOME_MANAGER_FILE SYSTEM_CONFIG_FILE HARDWARE_CONFIG_FILE; then
        print_error "Internal configuration path conflict detected"
        exit 1
    fi

    # ========================================================================
    # Step 1.7: Check for Old Deployment Artifacts
    # ========================================================================
    # Why: Previous versions of this script used different paths
    # What: Look for old monolithic script that's been replaced by modular version
    # Action: Just warn - doesn't affect new deployment, but user may want to archive
    #
    # Historical context: v3.2.0 moved from single script to modular architecture
    # Old location: ~/Documents/nixos-quick-deploy.sh (monolithic v2.x)
    # New location: ~/NixOS-Dev-Quick-Deploy/ (modular v3.x)
    print_info "Checking for old deployment artifacts..."
    local OLD_SCRIPT="/home/$USER/Documents/nixos-quick-deploy.sh"
    if [[ -f "$OLD_SCRIPT" ]]; then
        print_warning "Found old deployment script: $OLD_SCRIPT"
        print_info "This can be safely ignored or archived"
    fi

    # ========================================================================
    # Step 1.8: Validate Entire Dependency Chain
    # ========================================================================
    # Why: Ensure all required packages are available in Nix channels
    #      before attempting deployment
    # How: check_required_packages() validates dependency graph:
    #      - Core system packages (kernel, systemd, etc.)
    #      - Desktop environment (COSMIC)
    #      - Development tools (git, python, etc.)
    #      - Container runtime (podman)
    # What: Checks nixpkgs channel for package availability
    #
    # Why fail here: Better to know upfront that packages are missing
    #                than to fail 30 minutes into deployment
    print_info "Validating dependency chain..."
    check_required_packages || {
        print_error "Required packages not available"
        exit 1
    }

    # ========================================================================
    # Step 1.9: Hardware Detection - GPU
    # ========================================================================
    # Why: Need to know GPU type to install correct drivers:
    #      - NVIDIA: Proprietary nvidia drivers + CUDA
    #      - AMD: Mesa + AMDGPU drivers + ROCm
    #      - Intel: Mesa + i915/Xe drivers + oneAPI
    #      - Software: No GPU, CPU-only rendering
    # How: detect_gpu_hardware() scans lspci and /sys/class/drm
    # Output: Sets global variables:
    #         - GPU_TYPE (nvidia/amd/intel/software)
    #         - GPU_DRIVER (package name)
    #         - GPU_PACKAGES (additional packages)
    #         - LIBVA_DRIVER (hardware video acceleration)
    #
    # Why important: Wrong drivers = no display or poor performance
    # Used later in: Phase 4 (config generation) and Phase 8 (validation)
    detect_gpu_hardware

    # ========================================================================
    # Step 1.10: Hardware Detection - CPU and Memory
    # ========================================================================
    # Why: Optimize configuration based on available resources:
    #      - CPU cores: Parallel build jobs (nix.settings.cores)
    #      - Memory: Java heap sizes, cache sizes, VM settings
    #      - CPU vendor: Intel/AMD specific optimizations
    # How: detect_gpu_and_cpu() reads /proc/cpuinfo and /proc/meminfo
    # Output: Sets global variables:
    #         - CPU_CORES (number of logical cores)
    #         - MEMORY_GB (total RAM in GB)
    #         - CPU_VENDOR (GenuineIntel/AuthenticAMD)
    #
    # Why important: Prevents over-committing resources or underutilizing hardware
    # Example: Don't set 32 parallel builds on a 4-core CPU
    detect_gpu_and_cpu

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Record in state.json that this phase completed successfully.
    # This enables resume capability - if script crashes later,
    # it won't re-run this phase on next execution.
    # The state file persists across script runs.
    #
    # State file location: ~/.config/nixos-quick-deploy/state.json
    # Format: {"completed_steps": ["preparation_validation", ...], ...}
    mark_step_complete "$phase_name"
    print_success "Phase 1: Preparation & Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_01_preparation
