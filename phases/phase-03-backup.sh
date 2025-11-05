#!/usr/bin/env bash
#
# Phase 03: System Backup
# Purpose: Create comprehensive backup of system state before changes
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/backup.sh → create_rollback_point()
#
# Required Variables (from config/variables.sh):
#   - DRY_RUN → Whether running in dry-run mode
#   - HOME → User home directory
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - create_rollback_point() → Create system rollback point
#
# Requires Phases (must complete before this):
#   - Phase 2: Prerequisites must be installed
#
# Produces (for later phases):
#   - BACKUP_ROOT → Root directory for backups
#   - NIX_GEN_BEFORE → NixOS generation before deployment
#   - HM_GEN_BEFORE → Home-manager generation before deployment
#   - State: "comprehensive_backup" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_03_backup() {
    # ========================================================================
    # Phase 3: System Backup
    # ========================================================================
    # This is the "safety net" phase - create comprehensive backups BEFORE
    # making ANY system changes. This enables rollback if deployment fails.
    #
    # NixOS philosophy: "Declarative + Atomic + Rollback"
    # - Every system change creates a new "generation"
    # - Each generation is a complete system snapshot
    # - Can rollback to any previous generation at boot
    # - Generations stored in /nix/var/nix/profiles/
    #
    # This phase creates THREE types of backups:
    # 1. NixOS generation snapshot (rollback point)
    # 2. Configuration file backup (manual restore)
    # 3. Home-manager config backup (user environment)
    #
    # Why backup even with NixOS generations:
    # - Generations track installed packages, not config files
    # - Manual config edits might not be in version control
    # - Provides extra safety layer for troubleshooting
    # - Enables comparing old vs new configs
    # ========================================================================

    local phase_name="comprehensive_backup"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 3 already completed (skipping)"
        return 0
    fi

    print_section "Phase 3/10: System Backup"
    echo ""

    # ========================================================================
    # Step 3.1: Create NixOS Rollback Point
    # ========================================================================
    # Why: Create a labeled generation snapshot for easy identification
    # How: create_rollback_point() does:
    #      1. Records current generation number
    #      2. Creates labeled snapshot in NixOS boot menu
    #      3. Saves generation info to rollback.json
    # Result: Can rollback via: sudo nixos-rebuild --rollback
    #
    # NixOS generation management:
    # - Each nixos-rebuild creates a new generation
    # - Generations numbered sequentially: 1, 2, 3, ...
    # - Current generation: /run/current-system
    # - All generations: /nix/var/nix/profiles/system-*-link
    # - Boot menu shows last 5 generations by default
    #
    # Rollback methods:
    # - At boot: Select previous generation in GRUB/systemd-boot
    # - Live system: sudo nixos-rebuild --rollback
    # - Specific gen: sudo nixos-rebuild switch --rollback-to N
    #
    # DRY_RUN check: Skip actual backup in dry-run mode
    if [[ "$DRY_RUN" == false ]]; then
        # $(date +%Y-%m-%d_%H:%M:%S): Current timestamp in ISO-like format
        # Example label: "Before v3.1 deployment 2025-11-05_14:30:45"
        create_rollback_point "Before v3.1 deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # ========================================================================
    # Step 3.2: Backup System Configuration File
    # ========================================================================
    # Why: Preserve existing /etc/nixos/configuration.nix before overwriting
    # How: Copy to timestamped backup in same directory
    # When: Only if file exists (fresh install might not have it)
    #
    # File location: /etc/nixos/configuration.nix
    # - Main NixOS system configuration
    # - Root-owned, requires sudo to modify
    # - Defines: boot, networking, services, packages, users
    # - Generated during NixOS installation
    #
    # Backup naming: configuration.nix.backup.YYYYMMDD_HHMMSS
    # - Timestamp: Unique identifier for this backup
    # - Format: YYYYMMDD_HHMMSS (e.g., 20251105_143045)
    # - Kept in same dir for easy discovery
    #
    # Why sudo cp: /etc/nixos owned by root, need elevation
    # Why check existence: Fresh installs might not have this file yet
    if [[ -f "/etc/nixos/configuration.nix" ]]; then
        # local: Function-scoped variable (not global)
        # $(date +%Y%m%d_%H%M%S): Timestamp without hyphens/colons
        local backup_path="/etc/nixos/configuration.nix.backup.$(date +%Y%m%d_%H%M%S)"

        # sudo: Need root to read/write /etc/nixos
        # cp: Copy preserving permissions and timestamps
        sudo cp "/etc/nixos/configuration.nix" "$backup_path"
        print_success "Backed up system configuration: $backup_path"
    fi

    # ========================================================================
    # Step 3.3: Backup Home-Manager Configuration File
    # ========================================================================
    # Why: Preserve user environment config before home-manager changes
    # How: Copy to timestamped backup in same directory
    # When: Only if file exists (might be first-time setup)
    #
    # File location: ~/.config/home-manager/home.nix
    # - Main home-manager user configuration
    # - User-owned, no sudo needed
    # - Defines: packages, dotfiles, services, programs
    # - Created by home-manager init or manually
    #
    # Home-manager concept:
    # - NixOS manages system: kernel, drivers, system services
    # - Home-manager manages user: dotfiles, user packages, user services
    # - Separation of concerns: system admin vs user preferences
    # - User can manage their own environment without sudo
    #
    # Backup naming: home.nix.backup.YYYYMMDD_HHMMSS
    # - Same timestamp format as system config
    # - Keeps versioned history of user config
    # - Easy to compare changes: diff home.nix home.nix.backup.XXX
    #
    # Why no sudo: ~/.config/home-manager owned by user, not root
    # $HOME variable: User home directory (e.g., /home/alice)
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then
        # User files don't need sudo
        local hm_backup="$HOME/.config/home-manager/home.nix.backup.$(date +%Y%m%d_%H%M%S)"

        # cp: Regular copy (user has permission to source and destination)
        cp "$HOME/.config/home-manager/home.nix" "$hm_backup"
        print_success "Backed up home-manager config: $hm_backup"
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # All backups created successfully.
    # System is now safe to modify - we have rollback points.
    #
    # Recovery methods available after this phase:
    # 1. NixOS generation rollback (system-level)
    # 2. Manual config restore from backup files
    # 3. Home-manager generation rollback (user-level)
    #
    # State tracking: "comprehensive_backup" marked complete
    mark_step_complete "$phase_name"
    print_success "Phase 3: System Backup - COMPLETE"
    echo ""
}

# Execute phase
phase_03_backup
