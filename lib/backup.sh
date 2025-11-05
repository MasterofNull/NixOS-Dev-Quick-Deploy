#!/usr/bin/env bash
#
# Backup & Rollback Functions
# Purpose: Centralized backup and rollback mechanism
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/user-interaction.sh → print_* and confirm() functions
#   - lib/logging.sh → log() function
#
# Required Variables:
#   - BACKUP_ROOT → Root directory for backups
#   - BACKUP_MANIFEST → Path to backup manifest file
#   - ROLLBACK_INFO_FILE → Path to rollback info file
#   - HOME → User home directory
#
# Exports:
#   - centralized_backup() → Backup a file or directory
#   - create_rollback_point() → Create rollback point
#   - perform_rollback() → Perform rollback to previous state
#
# ============================================================================

# Centralized backup function
centralized_backup() {
    local source="$1"
    local description="$2"

    if [[ ! -e "$source" ]]; then
        log DEBUG "Backup skipped - source does not exist: $source"
        return 0
    fi

    local relative_path="${source#$HOME/}"
    local backup_path="$BACKUP_ROOT/$relative_path"

    mkdir -p "$(dirname "$backup_path")"

    if cp -a "$source" "$backup_path" 2>/dev/null; then
        echo "$(date -Iseconds) | $source -> $backup_path | $description" >> "$BACKUP_MANIFEST"
        print_success "Backed up: $description"
        log INFO "Backed up: $source -> $backup_path"
        return 0
    else
        print_warning "Failed to backup: $description"
        log WARNING "Backup failed: $source"
        return 1
    fi
}

# Create rollback point
create_rollback_point() {
    local description="$1"

    log INFO "Creating rollback point: $description"

    # Get current generation
    local nix_generation=$(nix-env --list-generations 2>/dev/null | tail -1 | awk '{print $1}' || echo "unknown")
    local hm_generation=$(home-manager generations 2>/dev/null | head -1 | awk '{print $NF}' || echo "unknown")

    cat > "$ROLLBACK_INFO_FILE" <<EOF
{
  "description": "$description",
  "created_at": "$(date -Iseconds)",
  "nix_generation": "$nix_generation",
  "home_manager_generation": "$hm_generation",
  "backup_root": "$BACKUP_ROOT"
}
EOF

    print_info "Rollback point created: $description"
    log INFO "Rollback info saved to: $ROLLBACK_INFO_FILE"
}

# Perform rollback
perform_rollback() {
    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        print_error "No rollback point available"
        log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1
    fi

    print_section "Rolling Back to Previous State"

    local description=$(jq -r '.description' "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "unknown")
    print_info "Rollback point: $description"

    if ! confirm "Are you sure you want to rollback?" "n"; then
        print_info "Rollback cancelled"
        return 0
    fi

    print_info "Rolling back Nix environment..."
    nix-env --rollback || print_warning "Nix rollback had issues"

    print_info "Rolling back Home Manager..."
    local hm_gen=$(jq -r '.home_manager_generation' "$ROLLBACK_INFO_FILE" 2>/dev/null)
    if [[ -n "$hm_gen" && "$hm_gen" != "unknown" && -x "$hm_gen/activate" ]]; then
        "$hm_gen/activate" || print_warning "Home Manager rollback had issues"
    fi

    print_info "Rolling back NixOS system..."
    if confirm "Rollback NixOS system configuration?" "n"; then
        sudo nixos-rebuild switch --rollback || print_warning "NixOS rollback had issues"
    fi

    print_success "Rollback completed"
    log INFO "Rollback completed"
}
