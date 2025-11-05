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
    local phase_name="comprehensive_backup"

    if is_step_complete "$phase_name"; then
        print_info "Phase 3 already completed (skipping)"
        return 0
    fi

    print_section "Phase 3/10: System Backup"
    echo ""

    # Create rollback point
    if [[ "$DRY_RUN" == false ]]; then
        create_rollback_point "Before v3.1 deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # Backup existing configs
    if [[ -f "/etc/nixos/configuration.nix" ]]; then
        local backup_path="/etc/nixos/configuration.nix.backup.$(date +%Y%m%d_%H%M%S)"
        sudo cp "/etc/nixos/configuration.nix" "$backup_path"
        print_success "Backed up system configuration: $backup_path"
    fi

    # Backup home-manager configs if they exist
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then
        local hm_backup="$HOME/.config/home-manager/home.nix.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$HOME/.config/home-manager/home.nix" "$hm_backup"
        print_success "Backed up home-manager config: $hm_backup"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 3: System Backup - COMPLETE"
    echo ""
}

# Execute phase
phase_03_backup
