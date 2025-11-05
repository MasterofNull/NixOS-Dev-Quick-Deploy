#!/usr/bin/env bash
#
# Phase 04: Configuration Generation & Validation
# Purpose: Generate all configuration files and validate with dry-run
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/config.sh → generate_nixos_system_config(), validate_system_build_stage()
#   - lib/user.sh → gather_user_info()
#
# Required Variables (from config/variables.sh):
#   - GPU_TYPE → Detected GPU type (from Phase 1)
#   - SYSTEM_CONFIG_FILE → Path to system configuration
#   - HOME_MANAGER_FILE → Path to home-manager configuration
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - gather_user_info() → Collect user information
#   - generate_nixos_system_config() → Generate system config
#   - validate_system_build_stage() → Dry-run build validation
#
# Requires Phases (must complete before this):
#   - Phase 1: GPU_TYPE detection needed
#   - Phase 3: Backup must be created first
#
# Produces (for later phases):
#   - CONFIGS_GENERATED → Flag indicating configs ready
#   - SYSTEM_CONFIG_FILE → Generated system configuration
#   - HOME_MANAGER_FILE → Generated home-manager configuration
#   - State: "generate_validate_configs" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_04_config_generation() {
    # ========================================================================
    # Phase 4: Configuration Generation & Validation
    # ========================================================================
    # This is the "blueprint creation" phase - generate ALL NixOS configuration
    # files that define the system, then validate them BEFORE applying.
    #
    # NixOS declarative configuration philosophy:
    # - Everything is code: System state defined in .nix files
    # - Reproducible: Same config = same system state
    # - Validated: Catch errors before deployment
    # - Version-controlled: Track config changes in git
    #
    # Configuration files generated in this phase:
    # 1. /etc/nixos/configuration.nix - System configuration
    #    - Boot loader (GRUB/systemd-boot)
    #    - Kernel and drivers
    #    - System services (PostgreSQL, Gitea, etc.)
    #    - Network configuration
    #    - User accounts
    #    - System packages
    #
    # 2. /etc/nixos/hardware-configuration.nix - Hardware-specific
    #    - Filesystem mounts
    #    - CPU microcode
    #    - Hardware modules
    #    - GPU drivers
    #
    # 3. ~/.config/home-manager/home.nix - User environment
    #    - User packages (CLI tools, dev tools)
    #    - Dotfiles (.bashrc, .zshrc, etc.)
    #    - User services (jupyter, etc.)
    #    - Program configurations
    #
    # 4. ~/.config/home-manager/flake.nix - Modern Nix flakes
    #    - Reproducible dependencies
    #    - Pinned package versions
    #    - Lock file for consistency
    #
    # Validation approach:
    # - Generate configs
    # - Dry-run build (nixos-rebuild dry-build)
    # - Catch syntax errors and missing packages
    # - Fail fast before making system changes
    # ========================================================================

    local phase_name="generate_validate_configs"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 4 already completed (skipping)"
        return 0
    fi

    print_section "Phase 4/10: Configuration Generation & Validation"
    echo ""

    # ========================================================================
    # Step 4.1: Gather User Information
    # ========================================================================
    # Why: Need user preferences to customize configuration:
    #      - Username and description (for user account creation)
    #      - Shell preference (bash/zsh/fish)
    #      - Editor preference (vim/emacs/nano)
    #      - Desktop environment options
    # How: gather_user_info() prompts for user input
    # Sets: Global variables used by config generation
    #
    # Interactive prompts:
    # - User description: For account full name
    # - Default shell: Which shell to use (affects dotfiles)
    # - Text editor: Default EDITOR environment variable
    # - Optional features: Enable/disable specific components
    #
    # Why gather now: Prevents mid-deployment prompts
    # Validation: Ensures required info is present
    # Defaults: Sensible defaults if user skips prompts
    gather_user_info

    # ========================================================================
    # Step 4.2: Generate NixOS System Configuration
    # ========================================================================
    # Why: Create the main system configuration files from templates
    # How: generate_nixos_system_config() does:
    #      1. Read template files from templates/
    #      2. Substitute variables (GPU_TYPE, USER, etc.)
    #      3. Generate configuration.nix
    #      4. Generate hardware-configuration.nix
    #      5. Generate flake.nix (if using flakes)
    #      6. Write to /etc/nixos/ and ~/.config/home-manager/
    #
    # Template variable substitution:
    # - @GPU_TYPE@ → nvidia/amd/intel/software
    # - @GPU_DRIVER@ → nvidia-driver/amdgpu/etc
    # - @USER@ → Current username
    # - @HOSTNAME@ → System hostname
    # - @TIMEZONE@ → System timezone
    #
    # NixOS configuration structure:
    # configuration.nix:
    # - imports: Include other .nix files
    # - boot: Bootloader configuration
    # - networking: Hostname, firewall
    # - services: Systemd services (postgres, ollama, etc.)
    # - users: User account definitions
    # - environment.systemPackages: System-wide packages
    # - hardware: GPU drivers, kernel modules
    #
    # Nix language basics:
    # - Functional language (like Haskell)
    # - Attribute sets: { key = value; }
    # - Lists: [ item1 item2 ]
    # - Strings: "text" or ''multiline''
    # - Comments: # single-line
    #
    # File ownership:
    # - /etc/nixos/*: Owned by root (requires sudo)
    # - ~/.config/home-manager/*: Owned by user (no sudo)
    generate_nixos_system_config

    # ========================================================================
    # Step 4.3: Validate System Build (Dry Run)
    # ========================================================================
    # Why: Catch configuration errors BEFORE applying to live system
    # How: validate_system_build_stage() does:
    #      1. Run: nixos-rebuild dry-build --flake .#hostname
    #      2. Nix evaluates configuration (checks syntax)
    #      3. Nix resolves all dependencies
    #      4. Nix simulates build (doesn't actually build)
    #      5. Reports what would change
    # What: Detects errors like:
    #      - Syntax errors in .nix files
    #      - Missing packages
    #      - Conflicting options
    #      - Circular dependencies
    #      - Invalid attribute names
    #
    # NixOS build stages:
    # - dry-build: Evaluate + simulate (fastest, this step)
    # - build: Evaluate + download + build (slower)
    # - switch: build + activate (deployment, next phase)
    # - test: build + activate temporarily (testing)
    # - boot: build + set as next boot (safe testing)
    #
    # Common validation errors:
    # - "attribute 'X' missing": Typo in package name
    # - "infinite recursion": Circular dependency
    # - "package not found": Not in channel/flake
    # - "option conflict": Two configs set same option
    #
    # Exit behavior:
    # - Success: Continue to next phase
    # - Failure: Stop deployment, show error, exit
    #
    # Why validate here:
    # - Fast feedback (30 seconds vs 30 minutes)
    # - No system changes yet (safe to fail)
    # - Can fix config and retry
    # - Prevents wasted time on broken configs
    validate_system_build_stage

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # All configurations generated and validated successfully.
    # Ready to deploy in next phase.
    #
    # State: "generate_validate_configs" marked complete
    # Next: Phase 5 will clean up conflicts before deployment
    mark_step_complete "$phase_name"
    print_success "Phase 4: Configuration Generation & Validation - COMPLETE"
    echo ""
}

# Execute phase
phase_04_config_generation
