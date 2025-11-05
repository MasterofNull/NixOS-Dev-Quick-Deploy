#!/usr/bin/env bash
#
# Phase 06: Configuration Deployment
# Purpose: Apply NixOS and home-manager configurations
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/deployment.sh → prompt_installation_stage(), create_home_manager_config(), apply_home_manager_config()
#   - lib/ui.sh → confirm()
#
# Required Variables (from config/variables.sh):
#   - HM_CONFIG_DIR → Home-manager configuration directory
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - confirm() → Get user confirmation
#   - prompt_installation_stage() → Apply system config
#   - create_home_manager_config() → Create home-manager config
#   - apply_home_manager_config() → Apply home-manager config
#
# Requires Phases (must complete before this):
#   - Phase 4: CONFIGS_GENERATED must be true
#   - Phase 5: CLEANUP_COMPLETE must be true
#
# Produces (for later phases):
#   - DEPLOYMENT_COMPLETE → Flag indicating deployment done
#   - State: "deploy_configurations" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_06_deployment() {
    # ========================================================================
    # Phase 6: Configuration Deployment
    # ========================================================================
    # This is the "activation" phase - apply the validated configurations
    # to the live system. This is where actual system changes happen.
    #
    # CRITICAL PHASE: Point of no return for this deployment cycle
    # - Up to Phase 5: Planning, preparation, no lasting changes
    # - Phase 6: APPLIES changes to live system
    # - After Phase 6: System is running new configuration
    #
    # What gets deployed:
    # 1. NixOS System Configuration
    #    - Kernel and boot settings
    #    - System services (PostgreSQL, Ollama, Gitea, etc.)
    #    - GPU drivers and hardware support
    #    - Network configuration
    #    - System-wide packages
    #    Command: nixos-rebuild switch
    #
    # 2. Home-Manager User Configuration
    #    - User packages (git, python, etc.)
    #    - Dotfiles (.bashrc, .zshrc, .gitconfig)
    #    - User services (jupyter-lab, etc.)
    #    - Program configurations
    #    Command: home-manager switch
    #
    # NixOS deployment is atomic:
    # - Either entire config succeeds OR nothing changes
    # - New generation created with all changes
    # - Can rollback to previous generation if issues
    # - Old generations remain bootable
    #
    # Safety features:
    # - User confirmation before applying
    # - Automatic generation snapshot
    # - Rollback capability maintained
    # - Previous system remains in boot menu
    #
    # Time to complete: 5-30 minutes depending on:
    # - Number of packages to download
    # - Whether packages need compilation
    # - Network speed (binary cache downloads)
    # - Disk I/O speed
    # ========================================================================

    local phase_name="deploy_configurations"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 6 already completed (skipping)"
        return 0
    fi

    print_section "Phase 6/10: Configuration Deployment"
    echo ""

    # ========================================================================
    # Step 6.1: Final User Confirmation
    # ========================================================================
    # Why: Last chance to abort before making system changes
    # What: User can review generated configs before applying
    # How: Explicit yes/no confirmation
    #
    # This is the "commit point":
    # - Before: Can freely abort with no consequences
    # - After: System state will be modified
    #
    # What user should check before confirming:
    # - Review generated configs in /etc/nixos/ and ~/.config/home-manager/
    # - Check disk space is sufficient
    # - Ensure no urgent tasks running
    # - Consider timing (system will be busy for 5-30 min)
    #
    # If user declines:
    # - Configurations remain generated (can apply manually later)
    # - System unchanged
    # - State not marked complete (can resume later)
    # - Manual command provided for future deployment
    #
    # Variables explained:
    # - $HM_CONFIG_DIR: home-manager config directory (~/.config/home-manager)
    # - $(hostname): Current system hostname for flake selection
    # - --flake DIR#hostname: Nix flakes deployment syntax
    if ! confirm "Proceed with configuration deployment (this will apply system changes)?" "y"; then
        print_warning "Deployment skipped - configurations generated but not applied"
        print_info "To apply later, run: sudo nixos-rebuild switch --flake $HM_CONFIG_DIR#$(hostname)"
        echo ""
        return 0  # Exit successfully but skip deployment
    fi

    # ========================================================================
    # Step 6.2: Apply System Configuration
    # ========================================================================
    # Why: Deploy NixOS system-level configuration
    # How: prompt_installation_stage() executes:
    #      sudo nixos-rebuild switch --flake /path/to/flake#hostname
    # What happens:
    #      1. Nix evaluates configuration.nix and flake.nix
    #      2. Builds derivations (downloads from cache or compiles)
    #      3. Creates new system generation
    #      4. Switches to new generation (activates)
    #      5. Starts/restarts affected services
    #      6. Updates boot menu with new generation
    #
    # nixos-rebuild switch explained:
    # - "rebuild": Build new system configuration
    # - "switch": Activate immediately (vs "boot" = activate next boot)
    # - "--flake": Use flake.nix instead of configuration.nix directly
    # - "PATH#hostname": Path to flake, output for this hostname
    #
    # What gets installed/configured:
    # - Kernel modules and drivers
    # - System services (systemd units)
    # - Network configuration
    # - Boot loader updates
    # - System packages in /run/current-system
    # - Service configuration files
    #
    # Service behavior:
    # - New services: Started automatically
    # - Changed services: Restarted with new config
    # - Unchanged services: Keep running
    # - Removed services: Stopped
    #
    # Expected output:
    # - Building messages
    # - Download progress for packages
    # - Activation messages
    # - Service status changes
    # - Generation number (e.g., "activating generation 42")
    #
    # Time: 10-30 minutes for full system deployment
    # Network: Several GB downloaded from cache.nixos.org
    # Disk: New generation adds to /nix/store
    prompt_installation_stage

    # ========================================================================
    # Step 6.3: Create Home-Manager Configuration
    # ========================================================================
    # Why: Set up user environment declaratively
    # How: create_home_manager_config() does:
    #      1. Ensure ~/.config/home-manager/ exists
    #      2. Copy/generate home.nix
    #      3. Copy/generate flake.nix for home-manager
    #      4. Set proper file permissions (user-owned)
    #      5. Initialize git repo (if using flakes)
    #
    # Home-manager configuration structure:
    # home.nix:
    #   - home.username: User account name
    #   - home.homeDirectory: Home path
    #   - home.stateVersion: HM version (for compatibility)
    #   - home.packages: User packages list
    #   - programs.*: Program-specific configurations
    #   - services.*: User services (systemd --user)
    #   - home.file.*: Dotfiles to create/manage
    #
    # Why separate from system config:
    # - User manages own environment without sudo
    # - Multiple users can have different configs
    # - Easier to share/version control user config
    # - User changes don't require system rebuild
    #
    # Flake integration:
    # - flake.nix: Defines inputs (nixpkgs, home-manager)
    # - flake.lock: Pins exact versions for reproducibility
    # - Git required: Flakes need git repository
    #
    # File ownership: All files created with user permissions (no sudo)
    create_home_manager_config

    # ========================================================================
    # Step 6.4: Apply Home-Manager Configuration
    # ========================================================================
    # Why: Activate user environment changes
    # How: apply_home_manager_config() executes:
    #      home-manager switch --flake ~/.config/home-manager#username
    # What happens:
    #      1. Evaluates home.nix and flake.nix
    #      2. Builds user packages
    #      3. Creates new home-manager generation
    #      4. Activates dotfiles (symlinks to ~/.config/, etc.)
    #      5. Starts/restarts user services (systemd --user)
    #      6. Updates shell environment
    #
    # home-manager switch explained:
    # - Builds user environment
    # - Activates immediately (like nixos-rebuild switch)
    # - Creates generation snapshot for rollback
    # - No sudo needed (user-level changes)
    #
    # What gets installed/configured:
    # - User packages in ~/.nix-profile/
    # - Dotfiles in ~/.config/, ~/.bashrc, etc. (symlinks)
    # - User services in ~/.config/systemd/user/
    # - Program config files
    # - Shell completions and aliases
    #
    # Dotfile management:
    # - home-manager creates symlinks to /nix/store/
    # - Old dotfiles backed up with .bak extension
    # - Manual edits to dotfiles will be overwritten
    # - Edit home.nix instead, then re-run home-manager switch
    #
    # User services:
    # - Started automatically if enabled
    # - Managed by systemd --user
    # - Check with: systemctl --user status SERVICE
    # - Logs in: journalctl --user -u SERVICE
    #
    # Common user services:
    # - jupyter-lab: Interactive Python notebooks
    # - syncthing: File synchronization
    # - Custom scripts and daemons
    #
    # Expected output:
    # - Building messages
    # - Package downloads
    # - Activation messages
    # - Generation number
    #
    # Time: 2-10 minutes depending on number of user packages
    # Restart required: No, but "exec $SHELL" to reload environment
    apply_home_manager_config

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Deployment complete! System is now running new configuration.
    # Both NixOS system and home-manager user environment are active.
    #
    # What just happened:
    # - New NixOS generation created and activated
    # - New home-manager generation created and activated
    # - Services started/restarted with new configs
    # - Dotfiles linked to new versions
    # - System ready for next phase (tools installation)
    #
    # Rollback available:
    # - System: sudo nixos-rebuild --rollback
    # - User: home-manager --rollback
    # - Boot menu: Select previous generation
    #
    # State: "deploy_configurations" marked complete
    # Next: Phase 7 will install additional tools (Flatpak, Claude Code)
    mark_step_complete "$phase_name"
    print_success "Phase 6: Configuration Deployment - COMPLETE"
    echo ""
}

# Execute phase
phase_06_deployment
