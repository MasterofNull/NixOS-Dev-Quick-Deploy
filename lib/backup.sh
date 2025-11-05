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

# ============================================================================
# Centralized Backup Function
# ============================================================================
# Purpose: Back up a file or directory with manifest tracking
# Parameters:
#   $1 - Source path to backup
#   $2 - Human-readable description of what's being backed up
# Returns:
#   0 - Backup succeeded (or source doesn't exist - not an error)
#   1 - Backup failed
#
# How it works:
# 1. Checks if source exists (skip if not - not all files exist on all systems)
# 2. Calculates backup path preserving directory structure
# 3. Creates parent directories as needed
# 4. Copies with archive mode (preserves permissions, timestamps, etc.)
# 5. Records backup in manifest file for tracking
#
# Why centralized backup?
# - Single point of control for all backups
# - Consistent manifest tracking
# - Uniform error handling
# - Easy to add features (compression, encryption, etc.)
# - Audit trail of what was backed up when
#
# Backup structure:
#   BACKUP_ROOT/
#     .config/
#       nixos/
#         configuration.nix  (backed up from $HOME/.config/nixos/configuration.nix)
#     .bashrc                (backed up from $HOME/.bashrc)
#     .backup-manifest.txt   (list of all backups)
#
# The directory structure under BACKUP_ROOT mirrors the original
# ============================================================================
centralized_backup() {
    # Capture function parameters
    local source="$1"         # Path to file/directory to backup
    local description="$2"    # Human-readable description

    # ========================================================================
    # Check if source exists
    # ========================================================================
    # -e tests for existence (file, directory, symlink, etc.)
    # If source doesn't exist, skip backup (not an error condition)
    # This allows backup calls for optional files without failing
    if [[ ! -e "$source" ]]; then
        # Log at DEBUG level - this is normal, not a warning
        # Not all systems have all files
        log DEBUG "Backup skipped - source does not exist: $source"
        return 0  # Return success - skipping non-existent file is OK
    fi

    # ========================================================================
    # Calculate backup path preserving directory structure
    # ========================================================================
    # Remove $HOME prefix from source path to get relative path
    # ${parameter#pattern} removes shortest match of pattern from beginning
    # Example: If source="/home/user/.config/file.txt" and HOME="/home/user"
    # Then relative_path=".config/file.txt"
    #
    # This preserves directory structure in backup:
    # $HOME/.config/file.txt → $BACKUP_ROOT/.config/file.txt
    local relative_path="${source#$HOME/}"

    # Construct full backup path
    # Combines backup root with relative path
    local backup_path="$BACKUP_ROOT/$relative_path"

    # ========================================================================
    # Create parent directories for backup destination
    # ========================================================================
    # $(dirname "$backup_path") gets parent directory of backup path
    # Example: dirname "/backup/.config/file.txt" → "/backup/.config"
    # mkdir -p creates parent directories as needed
    # This ensures the backup destination directory exists
    mkdir -p "$(dirname "$backup_path")"

    # ========================================================================
    # Copy source to backup location with archive mode
    # ========================================================================
    # cp -a = archive mode, preserves:
    # - Permissions (chmod)
    # - Ownership (chown) - when possible
    # - Timestamps (modification time, access time)
    # - Symbolic links (copies as links, not dereferencing)
    # - Directory structure (recursive)
    #
    # 2>/dev/null suppresses error messages
    # We check exit code instead of displaying cp errors
    if cp -a "$source" "$backup_path" 2>/dev/null; then
        # ====================================================================
        # Backup succeeded - record in manifest
        # ====================================================================
        # Manifest format: timestamp | source -> destination | description
        # This creates an audit trail of all backups
        #
        # $(date -Iseconds) produces ISO 8601 timestamp
        # >> appends to manifest file (doesn't overwrite)
        # Using pipe (|) as field separator (easier to parse than spaces)
        echo "$(date -Iseconds) | $source -> $backup_path | $description" >> "$BACKUP_MANIFEST"

        # Display success message to user
        print_success "Backed up: $description"

        # Log detailed info for debugging
        log INFO "Backed up: $source -> $backup_path"

        return 0  # Return success
    else
        # ====================================================================
        # Backup failed
        # ====================================================================
        # Could fail due to:
        # - Permission denied
        # - Disk full
        # - Source locked/in use
        # - Filesystem errors

        # Display warning to user (not error - deployment can continue)
        print_warning "Failed to backup: $description"

        # Log for debugging
        log WARNING "Backup failed: $source"

        return 1  # Return failure
    fi
}

# ============================================================================
# Why use cp -a instead of rsync or tar?
# ============================================================================
# cp -a is chosen for simplicity and availability:
# - Available on all Unix systems (no dependencies)
# - Simple syntax
# - Fast for small backups
# - Preserves all important attributes
#
# When to consider alternatives:
# - rsync: For incremental backups, network transfer, or large directories
# - tar: For compression, archiving, or efficient storage
# - borgbackup/restic: For deduplicated, encrypted backups
#
# Current approach is sufficient for small config file backups
# ============================================================================

# ============================================================================
# Create Rollback Point Function
# ============================================================================
# Purpose: Record current system state for potential rollback
# Parameters:
#   $1 - Description of rollback point (e.g., "Before major upgrade")
# Returns: 0 (always succeeds)
#
# What is a rollback point?
# A snapshot of the current NixOS system state including:
# - Nix environment generation number
# - Home Manager generation number (if using Home Manager)
# - Backup directory location
# - Timestamp and description
#
# Why NixOS generations?
# NixOS uses a generational approach:
# - Each nix-env -i, nixos-rebuild, etc. creates a new "generation"
# - Generations are numbered sequentially (1, 2, 3, ...)
# - Previous generations remain available
# - Can rollback to any previous generation
# - Old generations can be garbage collected
#
# This is like git commits for your system configuration!
#
# How rollback works in NixOS:
# 1. System builds new generation from configuration
# 2. New generation is activated (symlinks updated)
# 3. Previous generation remains in /nix/store
# 4. Can switch back to any previous generation instantly
# 5. No reinstallation needed - just change symlinks!
#
# This function records generation numbers for later rollback
# ============================================================================
create_rollback_point() {
    # Capture description parameter
    local description="$1"

    # Log rollback point creation
    log INFO "Creating rollback point: $description"

    # ========================================================================
    # Query current Nix environment generation
    # ========================================================================
    # nix-env --list-generations shows all generations:
    #   1   2024-01-01 10:00:00
    #   2   2024-01-02 11:30:00
    #   3   2024-01-03 14:15:00   (current)
    #
    # Pipeline breakdown:
    # 1. nix-env --list-generations → lists all generations
    # 2. tail -1 → gets last line (most recent generation)
    # 3. awk '{print $1}' → extracts first column (generation number)
    # 4. || echo "unknown" → fallback if command fails
    #
    # 2>/dev/null suppresses errors if nix-env not available
    #
    # Why tail -1?
    # Last line is the current (most recent) generation
    # That's the one we want to record for rollback
    local nix_generation=$(nix-env --list-generations 2>/dev/null | tail -1 | awk '{print $1}' || echo "unknown")

    # ========================================================================
    # Query current Home Manager generation
    # ========================================================================
    # home-manager generations shows generation history:
    #   2024-01-03 14:15:00 : id 123 -> /nix/store/...-home-manager-generation
    #   2024-01-02 11:30:00 : id 122 -> /nix/store/...-home-manager-generation
    #
    # Pipeline breakdown:
    # 1. home-manager generations → lists generations (newest first)
    # 2. head -1 → gets first line (most recent generation)
    # 3. awk '{print $NF}' → extracts last field (generation path)
    # 4. || echo "unknown" → fallback if command fails
    #
    # $NF in awk = last field in line
    # We store the path so we can activate it during rollback
    #
    # Why head -1?
    # home-manager shows newest first, so first line is current
    local hm_generation=$(home-manager generations 2>/dev/null | head -1 | awk '{print $NF}' || echo "unknown")

    # ========================================================================
    # Write rollback info to JSON file
    # ========================================================================
    # Using JSON for structured storage
    # Easy to parse with jq during rollback
    #
    # Heredoc (<<EOF) writes multi-line content
    # Variables expand inside heredoc (unless <<'EOF')
    cat > "$ROLLBACK_INFO_FILE" <<EOF
{
  "description": "$description",
  "created_at": "$(date -Iseconds)",
  "nix_generation": "$nix_generation",
  "home_manager_generation": "$hm_generation",
  "backup_root": "$BACKUP_ROOT"
}
EOF

    # Inform user that rollback point was created
    print_info "Rollback point created: $description"

    # Log file location for reference
    log INFO "Rollback info saved to: $ROLLBACK_INFO_FILE"
}

# ============================================================================
# What are NixOS generations?
# ============================================================================
# NixOS generations are like snapshots of your system configuration:
#
# Generation 1: Initial install
#   /nix/store/abc123-nixos-system-1
#
# Generation 2: After adding package X
#   /nix/store/def456-nixos-system-2
#
# Generation 3: After configuring service Y
#   /nix/store/ghi789-nixos-system-3  (current)
#
# Each generation is a complete, standalone system configuration.
# Switching between generations is instant (just update symlinks).
# No reinstallation, no package downloads (already in /nix/store).
#
# Benefits:
# - Atomic upgrades: New generation is built before activation
# - Safe experimentation: Can always rollback
# - System history: See what changed when
# - Boot menu: Can boot into any previous generation
# ============================================================================

# ============================================================================
# Perform Rollback Function
# ============================================================================
# Purpose: Rollback system to previously recorded state
# Parameters: None (reads from ROLLBACK_INFO_FILE)
# Returns:
#   0 - Rollback completed (or cancelled by user)
#   1 - No rollback point available
#
# What this does:
# 1. Reads rollback point information from file
# 2. Asks user for confirmation (rollback is destructive!)
# 3. Rolls back Nix environment to previous generation
# 4. Rolls back Home Manager to previous generation
# 5. Optionally rolls back NixOS system configuration
#
# Rollback is multi-layered because NixOS has separate generations for:
# - User environment (nix-env): Per-user packages
# - Home Manager: Per-user dotfiles and configuration
# - System: System-wide configuration (requires sudo)
#
# Why separate confirmations?
# - User environment and Home Manager are per-user (safe to rollback)
# - System rollback affects all users (requires explicit confirmation)
# - System rollback requires sudo (permission boundary)
#
# What happens during rollback?
# - Symlinks are updated to point to previous generation
# - No data loss (old generation still in /nix/store)
# - Can roll forward again if needed
# - Nearly instant (just symlink updates)
# ============================================================================
perform_rollback() {
    # ========================================================================
    # Check if rollback point exists
    # ========================================================================
    # -f tests for regular file existence
    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        # No rollback point available
        # This happens if script hasn't been run before
        # or if rollback file was deleted
        print_error "No rollback point available"
        log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1  # Return failure
    fi

    # Display section header
    print_section "Rolling Back to Previous State"

    # ========================================================================
    # Read rollback point information
    # ========================================================================
    # Use jq to extract description from JSON
    # jq -r = raw output (no JSON quotes)
    # '.description' = extract description field
    # || echo "unknown" = fallback if jq fails
    local description=$(jq -r '.description' "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "unknown")

    # Show user what rollback point they're reverting to
    print_info "Rollback point: $description"

    # ========================================================================
    # Get user confirmation before proceeding
    # ========================================================================
    # Rollback is destructive (reverts changes)
    # Always confirm with user before rolling back
    # Default to "n" (safe default - don't accidentally rollback)
    if ! confirm "Are you sure you want to rollback?" "n"; then
        # User cancelled rollback
        print_info "Rollback cancelled"
        return 0  # Return success (user chose to cancel, not an error)
    fi

    # ========================================================================
    # Rollback Nix environment (user packages)
    # ========================================================================
    # nix-env --rollback switches to previous generation
    # This affects packages installed with nix-env -i
    #
    # What it does:
    # 1. Updates ~/.nix-profile symlink to previous generation
    # 2. Previous generation becomes active
    # 3. Package availability changes to match previous generation
    #
    # || print_warning allows rollback to continue even if this fails
    # Some systems might not have a previous nix-env generation
    print_info "Rolling back Nix environment..."
    nix-env --rollback || print_warning "Nix rollback had issues"

    # ========================================================================
    # Rollback Home Manager (user dotfiles and config)
    # ========================================================================
    print_info "Rolling back Home Manager..."

    # Extract Home Manager generation path from rollback info
    # This is a path like: /nix/store/...-home-manager-generation
    local hm_gen=$(jq -r '.home_manager_generation' "$ROLLBACK_INFO_FILE" 2>/dev/null)

    # Check if we have a valid Home Manager generation to rollback to
    # Multiple conditions checked with &&:
    # 1. -n "$hm_gen" → generation path is not empty
    # 2. "$hm_gen" != "unknown" → we successfully queried the generation
    # 3. -x "$hm_gen/activate" → activation script exists and is executable
    if [[ -n "$hm_gen" && "$hm_gen" != "unknown" && -x "$hm_gen/activate" ]]; then
        # Activate the previous Home Manager generation
        # The activate script updates symlinks and applies configuration
        # This changes dotfiles, shell config, etc. to previous state
        #
        # || print_warning allows continuing even if activation fails
        "$hm_gen/activate" || print_warning "Home Manager rollback had issues"
    fi

    # ========================================================================
    # Rollback NixOS system configuration (system-wide)
    # ========================================================================
    # System rollback affects ALL users and requires sudo
    # Ask for separate confirmation because this is more impactful
    print_info "Rolling back NixOS system..."

    # Confirm system rollback separately
    # Default to "n" (safe default)
    if confirm "Rollback NixOS system configuration?" "n"; then
        # Perform system rollback using nixos-rebuild
        # nixos-rebuild switch --rollback:
        # 1. Finds previous system generation
        # 2. Builds system (or uses cached build)
        # 3. Activates previous generation
        # 4. Updates bootloader to boot previous generation
        #
        # This changes:
        # - System services
        # - Kernel and boot config
        # - System packages
        # - Network configuration
        # - All system-wide settings
        #
        # || print_warning allows script to continue even if rollback fails
        # Rollback failure is logged but doesn't stop the script
        sudo nixos-rebuild switch --rollback || print_warning "NixOS rollback had issues"
    fi

    # ========================================================================
    # Rollback complete
    # ========================================================================
    print_success "Rollback completed"
    log INFO "Rollback completed"

    # Note: We don't delete the rollback info file
    # User might want to know what they rolled back from
    # They can manually delete it or create a new rollback point
}

# ============================================================================
# Rollback Best Practices and Patterns
# ============================================================================
# 1. Always confirm: Rollback is destructive, get user consent
# 2. Multiple layers: Rollback user and system separately
# 3. Safe defaults: Default to "n" for confirmation prompts
# 4. Graceful degradation: Continue even if part of rollback fails
# 5. Preserve info: Keep rollback info file for reference
# 6. Log everything: Record rollback attempts for audit trail
# 7. Check prerequisites: Verify rollback info exists before attempting
# 8. Structured data: Use JSON for rollback info (easy to parse)
# 9. Permission boundaries: Separate user vs system rollback
# 10. User feedback: Show progress for multi-step operation
#
# Why NixOS rollback is so powerful:
# - Instant: Just symlink updates, no reinstallation
# - Complete: Entire system state is rolled back
# - Safe: Previous generation remains available
# - Atomic: Generation switch is all-or-nothing
# - Reversible: Can roll forward again
#
# This is fundamentally different from traditional Linux:
# - Traditional: Reinstall packages, restore configs from backup
# - NixOS: Change one symlink, previous system instantly active
#
# The generational model makes experimentation safe and rollback trivial
# ============================================================================
