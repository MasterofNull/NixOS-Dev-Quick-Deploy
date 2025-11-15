#!/usr/bin/env bash
#
# Phase 02: System Backup
# Purpose: ONE complete backup of all system and user state before ANY changes
# Version: 4.0.0
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

phase_02_backup() {
    # ========================================================================
    # Phase 2: System Backup
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
        print_info "Phase 2 already completed (skipping)"
        return 0
    fi

    print_section "Phase 2/8: System Backup"
    echo ""

    # Create backup root directory with timestamp
    # Stored under ~/.config-backups so it respects PRIMARY_HOME overrides
    local backup_root_path="$HOME/.config-backups/pre-deployment-$(date +%Y%m%d_%H%M%S)"
    if ! safe_mkdir "$backup_root_path"; then
        print_error "Failed to create backup directory: $backup_root_path"
        return 1
    fi
    safe_chown_user_dir "$backup_root_path" || true
    print_info "Backup directory: $backup_root_path"
    echo ""

    # ========================================================================
    # Step 3.1: Record Current System State
    # ========================================================================
    print_info "Recording current system state..."

    # Record current NixOS generation
    local current_gen
    current_gen=$(readlink /run/current-system | grep -oP 'system-\K[0-9]+-link' | grep -oP '[0-9]+' || echo "unknown")
    echo "NixOS Generation: $current_gen" > "$backup_root_path/system-state.txt"
    print_success "Current NixOS generation: $current_gen"

    # Record current home-manager generation (if exists)
    if [[ -d "$HOME/.local/state/nix/profiles" ]]; then
        local hm_gen
        hm_gen=$(readlink "$HOME/.local/state/nix/profiles/home-manager" | grep -oP 'home-manager-\K[0-9]+-link' | grep -oP '[0-9]+' 2>/dev/null || echo "none")
        echo "Home-Manager Generation: $hm_gen" >> "$backup_root_path/system-state.txt"
        print_success "Current home-manager generation: $hm_gen"
    fi

    # List nix-env packages (for reference - we'll only remove script-generated ones)
    if command -v nix-env &>/dev/null; then
        print_info "Listing current nix-env packages..."
        nix-env -q > "$backup_root_path/nix-env-packages.txt" 2>/dev/null || true
        local pkg_count=$(wc -l < "$backup_root_path/nix-env-packages.txt" 2>/dev/null || echo "0")
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
        sudo cp "/etc/nixos/configuration.nix" "$backup_root_path/configuration.nix" 2>/dev/null
        print_success "✓ Backed up: /etc/nixos/configuration.nix"
    fi

    # Backup /etc/nixos/flake.nix (if exists)
    if [[ -f "/etc/nixos/flake.nix" ]]; then
        sudo cp "/etc/nixos/flake.nix" "$backup_root_path/nixos-flake.nix" 2>/dev/null
        print_success "✓ Backed up: /etc/nixos/flake.nix"
    fi

    echo ""

    # ========================================================================
    # Step 3.4: Backup User Configurations
    # ========================================================================
    print_info "Backing up user configuration files..."

    # Backup home-manager configs
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then
        safe_mkdir "$backup_root_path/home-manager" || print_warning "Could not create home-manager backup dir"
        safe_copy_file_silent "$HOME/.config/home-manager/home.nix" "$backup_root_path/home-manager/home.nix" && \
            print_success "✓ Backed up: ~/.config/home-manager/home.nix"
    fi

    if [[ -f "$HOME/.config/home-manager/flake.nix" ]]; then
        safe_copy_file_silent "$HOME/.config/home-manager/flake.nix" "$backup_root_path/home-manager/flake.nix" && \
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
            if safe_mkdir "$backup_root_path/$parent"; then
                cp -a "$full_path" "$backup_root_path/$parent/" 2>/dev/null && \
                    print_success "✓ Backed up: ~/$config_dir"
            fi
        fi
    done

    echo ""

    # ========================================================================
    # Step 3.5: Save Recovery Instructions
    # ========================================================================
    print_info "Creating recovery instructions..."

    cat > "$backup_root_path/RECOVERY-README.txt" << EOF
NixOS Quick Deploy - Backup Recovery Instructions
Created: $(date)
Backup Location: $backup_root_path

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
   sudo cp $backup_root_path/configuration.nix /etc/nixos/configuration.nix
   sudo nixos-rebuild switch

2. Restore home-manager configuration:
   cp $backup_root_path/home-manager/home.nix ~/.config/home-manager/home.nix
   home-manager switch

3. Restore user configs:
   cp -a $backup_root_path/.config/. ~/.config/

=================================================================
SYSTEM STATE AT BACKUP
=================================================================

EOF
    cat "$backup_root_path/system-state.txt" >> "$backup_root_path/RECOVERY-README.txt"

    print_success "Recovery instructions saved to: $backup_root_path/RECOVERY-README.txt"
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
    echo "Backup location: $backup_root_path"
    echo "Recovery guide: $backup_root_path/RECOVERY-README.txt"
    echo ""

    # Save backup location for other phases to reference
    echo "$backup_root_path" > "$STATE_DIR/last-backup-location.txt"

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"
    print_success "Phase 2: System Backup - COMPLETE"
    echo ""
}

# Execute phase
phase_02_backup
