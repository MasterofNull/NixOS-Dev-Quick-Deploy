#!/usr/bin/env bash
#
# Phase 03: Comprehensive System Backup
# Purpose: ONE complete backup of all system and user state before ANY changes
# Version: 3.3.0
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
#   - STATE_DIR → State directory for tracking
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
    # Phase 3: Comprehensive System Backup
    # ========================================================================
    # This is the ONE AND ONLY backup phase. Everything gets backed up here
    # BEFORE making ANY changes to the system.
    #
    # Following NixOS Best Practices:
    # - NixOS generations provide system-level rollback
    # - We backup configs for manual inspection/restoration
    # - We document current state for comparison
    # - This enables informed rollback decisions
    # ========================================================================

    local phase_name="comprehensive_backup"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 3 already completed (skipping)"
        return 0
    fi

    print_section "Phase 3/10: Comprehensive System Backup"
    echo ""

    # Create backup root directory with timestamp
    local BACKUP_ROOT="$HOME/.config-backups/pre-deployment-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_ROOT"
    print_info "Backup directory: $BACKUP_ROOT"
    echo ""

    # ========================================================================
    # Step 3.1: Record Current System State
    # ========================================================================
    print_info "Recording current system state..."

    # Record current NixOS generation
    local current_gen
    current_gen=$(readlink /run/current-system | grep -oP 'system-\K[0-9]+-link' | grep -oP '[0-9]+' || echo "unknown")
    echo "NixOS Generation: $current_gen" > "$BACKUP_ROOT/system-state.txt"
    print_success "Current NixOS generation: $current_gen"

    # Record current home-manager generation (if exists)
    if [[ -d "$HOME/.local/state/nix/profiles" ]]; then
        local hm_gen
        hm_gen=$(readlink "$HOME/.local/state/nix/profiles/home-manager" | grep -oP 'home-manager-\K[0-9]+-link' | grep -oP '[0-9]+' 2>/dev/null || echo "none")
        echo "Home-Manager Generation: $hm_gen" >> "$BACKUP_ROOT/system-state.txt"
        print_success "Current home-manager generation: $hm_gen"
    fi

    # List nix-env packages (for reference - we'll only remove script-generated ones)
    if command -v nix-env &>/dev/null; then
        print_info "Listing current nix-env packages..."
        nix-env -q > "$BACKUP_ROOT/nix-env-packages.txt" 2>/dev/null || true
        local pkg_count=$(wc -l < "$BACKUP_ROOT/nix-env-packages.txt" 2>/dev/null || echo "0")
        if [[ "$pkg_count" -gt 0 ]]; then
            print_info "Found $pkg_count nix-env packages (saved for reference)"
        else
            print_success "No nix-env packages installed"
        fi
    fi

    echo ""

    # ========================================================================
    # Step 3.2: Create NixOS Rollback Point
    # ========================================================================
    print_info "Creating NixOS generation rollback point..."
    if [[ "$DRY_RUN" == false ]]; then
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
        print_success "NixOS rollback point created"
    else
        print_info "[DRY RUN] Would create NixOS rollback point"
    fi
    echo ""

    # ========================================================================
    # Step 3.3: Backup System Configurations
    # ========================================================================
    print_info "Backing up system configuration files..."

    # Backup /etc/nixos/configuration.nix
    if [[ -f "/etc/nixos/configuration.nix" ]]; then
        sudo cp "/etc/nixos/configuration.nix" "$BACKUP_ROOT/configuration.nix" 2>/dev/null
        print_success "✓ Backed up: /etc/nixos/configuration.nix"
    fi

    # Backup /etc/nixos/flake.nix (if exists)
    if [[ -f "/etc/nixos/flake.nix" ]]; then
        sudo cp "/etc/nixos/flake.nix" "$BACKUP_ROOT/nixos-flake.nix" 2>/dev/null
        print_success "✓ Backed up: /etc/nixos/flake.nix"
    fi

    echo ""

    # ========================================================================
    # Step 3.4: Backup User Configurations
    # ========================================================================
    print_info "Backing up user configuration files..."

    # Backup home-manager configs
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then
        mkdir -p "$BACKUP_ROOT/home-manager"
        cp "$HOME/.config/home-manager/home.nix" "$BACKUP_ROOT/home-manager/" 2>/dev/null
        print_success "✓ Backed up: ~/.config/home-manager/home.nix"
    fi

    if [[ -f "$HOME/.config/home-manager/flake.nix" ]]; then
        cp "$HOME/.config/home-manager/flake.nix" "$BACKUP_ROOT/home-manager/" 2>/dev/null
        print_success "✓ Backed up: ~/.config/home-manager/flake.nix"
    fi

    # Backup important user configs (non-destructive - just copy for reference)
    local user_configs=(
        ".config/flatpak"
        ".config/aider"
        ".config/tea"
        ".config/huggingface"
        ".config/gitea"
        ".config/obsidian"
    )

    for config_dir in "${user_configs[@]}"; do
        local full_path="$HOME/$config_dir"
        if [[ -d "$full_path" ]] && [[ $(du -s "$full_path" 2>/dev/null | cut -f1) -lt 102400 ]]; then
            # Only backup if < 100MB (avoid huge caches)
            local dir_name=$(basename "$config_dir")
            local parent=$(dirname "$config_dir")
            mkdir -p "$BACKUP_ROOT/$parent"
            cp -a "$full_path" "$BACKUP_ROOT/$parent/" 2>/dev/null && \
                print_success "✓ Backed up: ~/$config_dir"
        fi
    done

    echo ""

    # ========================================================================
    # Step 3.5: Save Recovery Instructions
    # ========================================================================
    print_info "Creating recovery instructions..."

    cat > "$BACKUP_ROOT/RECOVERY-README.txt" << EOF
NixOS Quick Deploy - Backup Recovery Instructions
Created: $(date)
Backup Location: $BACKUP_ROOT

=================================================================
AUTOMATIC ROLLBACK (Recommended)
=================================================================

1. Rollback NixOS system (if deployment failed):
   sudo nixos-rebuild --rollback

2. Rollback home-manager (if user environment broken):
   home-manager --rollback

=================================================================
MANUAL RECOVERY (If needed)
=================================================================

1. Restore system configuration:
   sudo cp $BACKUP_ROOT/configuration.nix /etc/nixos/configuration.nix
   sudo nixos-rebuild switch

2. Restore home-manager configuration:
   cp $BACKUP_ROOT/home-manager/home.nix ~/.config/home-manager/home.nix
   home-manager switch

3. Restore user configs:
   cp -a $BACKUP_ROOT/.config/. ~/.config/

=================================================================
SYSTEM STATE AT BACKUP
=================================================================

EOF
    cat "$BACKUP_ROOT/system-state.txt" >> "$BACKUP_ROOT/RECOVERY-README.txt"

    print_success "Recovery instructions saved to: $BACKUP_ROOT/RECOVERY-README.txt"
    echo ""

    # ========================================================================
    # Summary
    # ========================================================================
    print_section "Backup Summary"
    echo "✓ NixOS generation rollback point created"
    echo "✓ System configurations backed up"
    echo "✓ User configurations backed up"
    echo "✓ Current state documented"
    echo "✓ Recovery instructions created"
    echo ""
    echo "Backup location: $BACKUP_ROOT"
    echo "Recovery guide: $BACKUP_ROOT/RECOVERY-README.txt"
    echo ""

    # Save backup location for other phases to reference
    echo "$BACKUP_ROOT" > "$STATE_DIR/last-backup-location.txt"

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 3: Comprehensive System Backup - COMPLETE"
    echo ""
}

# Execute phase
phase_03_backup
