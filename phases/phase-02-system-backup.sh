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

    local phase_name="comprehensive_backup"  # State tracking identifier

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then  # Check state file
        print_info "Phase 2 already completed (skipping)"
            return 0  # Skip to next phase
    fi

    print_section "Phase 2/8: System Backup"  # Display phase header
        echo ""

    # Create backup root directory with timestamp for unique identification
    local BACKUP_ROOT="$HOME/.config-backups/pre-deployment-$(date +%Y%m%d_%H%M%S)"  # Format: pre-deployment-20250107_152030
        if ! safe_mkdir "$BACKUP_ROOT"; then  # Create directory with safe permissions
        print_error "Failed to create backup directory: $BACKUP_ROOT"
            return 1  # Fatal - can't proceed without backup
    fi
    safe_chown_user_dir "$BACKUP_ROOT" || true  # Ensure user ownership (not root)
        print_info "Backup directory: $BACKUP_ROOT"
    echo ""

    # ========================================================================
    # Step 3.1: Record Current System State
    # ========================================================================
    # Document current generation numbers for rollback reference
    print_info "Recording current system state..."

    # Record current NixOS generation number
    local current_gen  # System generation number
        current_gen=$(readlink /run/current-system | grep -oP 'system-\K[0-9]+-link' | grep -oP '[0-9]+' || echo "unknown")  # Extract generation from symlink
    echo "NixOS Generation: $current_gen" > "$BACKUP_ROOT/system-state.txt"  # Save to file
        print_success "Current NixOS generation: $current_gen"

    # Record current home-manager generation (if home-manager is installed)
    if [[ -d "$HOME/.local/state/nix/profiles" ]]; then  # Profile directory exists
        local hm_gen  # Home-manager generation number
            hm_gen=$(readlink "$HOME/.local/state/nix/profiles/home-manager" | grep -oP 'home-manager-\K[0-9]+-link' | grep -oP '[0-9]+' 2>/dev/null || echo "none")  # Extract from symlink
        echo "Home-Manager Generation: $hm_gen" >> "$BACKUP_ROOT/system-state.txt"  # Append to file
            print_success "Current home-manager generation: $hm_gen"
    fi

    # List nix-env packages (for reference - we'll only remove script-generated ones in Phase 5)
    if command -v nix-env &>/dev/null; then  # nix-env command available
        print_info "Listing current nix-env packages..."
            nix-env -q > "$BACKUP_ROOT/nix-env-packages.txt" 2>/dev/null || true  # Query installed packages
        local pkg_count=$(wc -l < "$BACKUP_ROOT/nix-env-packages.txt" 2>/dev/null || echo "0")  # Count lines
            if [[ "$pkg_count" -gt 0 ]]; then  # Packages found
            print_info "Found $pkg_count nix-env packages (saved for reference)"
        else  # No packages installed
            print_success "No nix-env packages installed"
        fi
    fi

    echo ""

    # ========================================================================
    # Step 3.2: Create NixOS Rollback Point
    # ========================================================================
    # Save current NixOS generation as a named rollback point
    print_info "Creating NixOS generation rollback point..."
    if [[ "$DRY_RUN" == false ]]; then  # Not in preview mode
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"  # Create named generation
            print_success "NixOS rollback point created"
    else  # Dry-run mode
        print_info "[DRY RUN] Would create NixOS rollback point"
    fi
    echo ""

    # ========================================================================
    # Step 3.3: Backup System Configurations
    # ========================================================================
    # Copy system-level config files from /etc/nixos to backup directory
    print_info "Backing up system configuration files..."

    # Backup /etc/nixos/configuration.nix (main system config)
    if [[ -f "/etc/nixos/configuration.nix" ]]; then  # Config file exists
        sudo cp "/etc/nixos/configuration.nix" "$BACKUP_ROOT/configuration.nix" 2>/dev/null  # Copy with sudo (owned by root)
            print_success "✓ Backed up: /etc/nixos/configuration.nix"
    fi

    # Backup /etc/nixos/flake.nix (if using flakes)
    if [[ -f "/etc/nixos/flake.nix" ]]; then  # Flake file exists
        sudo cp "/etc/nixos/flake.nix" "$BACKUP_ROOT/nixos-flake.nix" 2>/dev/null  # Copy with sudo
            print_success "✓ Backed up: /etc/nixos/flake.nix"
    fi

    echo ""

    # ========================================================================
    # Step 3.4: Backup User Configurations
    # ========================================================================
    # Copy user-level config files from home directory to backup
    print_info "Backing up user configuration files..."

    # Backup home-manager configs (user environment management)
    if [[ -f "$HOME/.config/home-manager/home.nix" ]]; then  # home.nix exists
        safe_mkdir "$BACKUP_ROOT/home-manager" || print_warning "Could not create home-manager backup dir"  # Create subdirectory
            safe_copy_file_silent "$HOME/.config/home-manager/home.nix" "$BACKUP_ROOT/home-manager/home.nix" && \  # Copy file
            print_success "✓ Backed up: ~/.config/home-manager/home.nix"
    fi

    if [[ -f "$HOME/.config/home-manager/flake.nix" ]]; then  # home-manager flake exists
        safe_copy_file_silent "$HOME/.config/home-manager/flake.nix" "$BACKUP_ROOT/home-manager/flake.nix" && \  # Copy file
                print_success "✓ Backed up: ~/.config/home-manager/flake.nix"
    fi

    # Backup important user configs (non-destructive - just copy for reference)
    local user_configs=(  # Array of config directories to backup
        ".config/flatpak"  # Flatpak app configs
            ".config/aider"  # Aider AI coding assistant settings
        ".config/tea"  # Gitea CLI config
            ".config/huggingface"  # Hugging Face credentials
        ".config/gitea"  # Gitea config
            ".config/obsidian"  # Obsidian notes app settings
    )

    # Iterate through config directories and backup if reasonable size
    for config_dir in "${user_configs[@]}"; do  # Check each config directory
        local full_path="$HOME/$config_dir"  # Build full path
            if [[ -d "$full_path" ]] && [[ $(du -s "$full_path" 2>/dev/null | cut -f1) -lt 102400 ]]; then  # Directory exists and < 100MB
            # Only backup if < 100MB (avoid huge caches)
            local dir_name=$(basename "$config_dir")  # Get directory name
                local parent=$(dirname "$config_dir")  # Get parent path (.config)
            if safe_mkdir "$BACKUP_ROOT/$parent"; then  # Create parent directory in backup
                cp -a "$full_path" "$BACKUP_ROOT/$parent/" 2>/dev/null && \  # Copy directory recursively (preserve attributes)
                        print_success "✓ Backed up: ~/$config_dir"
            fi
        fi
    done

    echo ""

    # ========================================================================
    # Step 3.5: Save Recovery Instructions
    # ========================================================================
    # Create a README file with step-by-step recovery instructions
    print_info "Creating recovery instructions..."

    # Write recovery README with heredoc
    cat > "$BACKUP_ROOT/RECOVERY-README.txt" << EOF  # Create file with instructions
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
    cat "$BACKUP_ROOT/system-state.txt" >> "$BACKUP_ROOT/RECOVERY-README.txt"  # Append system state info

    print_success "Recovery instructions saved to: $BACKUP_ROOT/RECOVERY-README.txt"
    echo ""

    # ========================================================================
    # Summary
    # ========================================================================
    # Display backup completion summary
    print_section "Backup Summary"
    echo "✓ NixOS generation rollback point created"
        echo "✓ System configurations backed up"
    echo "✓ User configurations backed up"
        echo "✓ Current state documented"
    echo "✓ Recovery instructions created"
    echo ""
    echo "Backup location: $BACKUP_ROOT"  # Show where backups are stored
        echo "Recovery guide: $BACKUP_ROOT/RECOVERY-README.txt"
    echo ""

    # Save backup location for other phases to reference
    echo "$BACKUP_ROOT" > "$STATE_DIR/last-backup-location.txt"  # Store path in state directory

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    mark_step_complete "$phase_name"  # Update state.json with completion
        print_success "Phase 2: System Backup - COMPLETE"
    echo ""
}

# Execute phase function (called when this script is sourced by main orchestrator)
phase_02_backup  # Run all backup operations
