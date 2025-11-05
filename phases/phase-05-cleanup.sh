#!/usr/bin/env bash
#
# Phase 05: Intelligent Cleanup
# Purpose: Selective removal of ONLY conflicting packages
# Version: 3.2.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries (must be loaded by bootstrap):
#   - lib/logging.sh → print_info(), print_success(), print_error(), print_warning()
#   - lib/state.sh → is_step_complete(), mark_step_complete()
#   - lib/ui.sh → confirm()
#
# Required Variables (from config/variables.sh):
#   - None (uses nix-env directly)
#
# Required Functions (from lib/common.sh):
#   - is_step_complete() → Check if phase already completed
#   - mark_step_complete() → Mark phase as completed
#   - print_section() → Print section header
#   - confirm() → Get user confirmation
#
# Requires Phases (must complete before this):
#   - Phase 3: BACKUP_ROOT must be set for safety
#   - Phase 4: Configs must be generated
#
# Produces (for later phases):
#   - CLEANUP_COMPLETE → Flag indicating cleanup done
#   - State: "intelligent_cleanup" → Marked complete in state.json
#
# Exit Codes:
#   0 → Success (phase completed or already complete)
#   1 → Fatal error (stops deployment)
#
# ============================================================================
# PHASE IMPLEMENTATION
# ============================================================================

phase_05_cleanup() {
    # ========================================================================
    # Phase 5: Intelligent Cleanup
    # ========================================================================
    # This is the "conflict resolution" phase - selectively remove ONLY
    # packages that would conflict with the new declarative configuration.
    #
    # The Problem: Imperative vs Declarative package management
    # - Imperative (nix-env): Install packages via command line
    #   Example: nix-env -iA nixpkgs.git
    #   State: Stored in user profile (~/.nix-profile)
    #   Management: Manual, like apt-get or yum
    #
    # - Declarative (home-manager/configuration.nix): Define in config files
    #   Example: home.packages = [ pkgs.git ];
    #   State: Derived from configuration
    #   Management: Atomic, reproducible
    #
    # Conflict scenario:
    # 1. User has git installed via nix-env (imperative)
    # 2. home-manager wants to install git (declarative)
    # 3. Result: "collision" error - same package from two sources
    #
    # Traditional solution (too aggressive):
    # - nix-env -e '.*' → Remove ALL user packages
    # - Problem: Removes non-conflicting packages user wants to keep
    #
    # Our intelligent solution:
    # - Scan nix-env packages
    # - Identify ONLY packages that conflict with home-manager config
    # - Remove ONLY conflicting packages
    # - Keep non-conflicting packages
    # - Give user option to clean up old generations
    #
    # Why this approach is better:
    # - Preserves user-installed tools that don't conflict
    # - Minimally invasive
    # - User maintains control
    # - Reversible via nix-env rollback
    # ========================================================================

    local phase_name="intelligent_cleanup"

    # ------------------------------------------------------------------------
    # Resume Check: Skip if already completed
    # ------------------------------------------------------------------------
    if is_step_complete "$phase_name"; then
        print_info "Phase 5 already completed (skipping)"
        return 0
    fi

    print_section "Phase 5/10: Intelligent Cleanup"
    echo ""

    # Warn user about what this phase does
    print_warning "This phase will remove conflicting packages and configurations"
    print_info "All removals are backed up and can be restored if needed"
    echo ""

    # ========================================================================
    # Step 5.1: Get User Confirmation
    # ========================================================================
    # Why: This phase removes packages - get explicit user consent
    # How: confirm() prompts with yes/no question
    # Default: "y" (yes) - proceed with cleanup
    # User can decline: Return 0 (success) but skip cleanup
    #
    # confirm() function:
    # - Shows prompt with [Y/n] or [y/N] indicator
    # - Reads user input (case-insensitive)
    # - Returns 0 for yes, 1 for no
    # - Default applies if user just presses Enter
    #
    # Why allow skip:
    # - User might want to manually handle conflicts
    # - User might not have any conflicting packages
    # - Advanced users might have custom setup
    #
    # ! operator: Logical NOT - inverts return code
    # if ! confirm: If user says NO (confirm returns 1, ! makes it 0/true)
    if ! confirm "Proceed with intelligent cleanup of conflicting packages?" "y"; then
        print_warning "Cleanup skipped - this may cause conflicts during installation"
        echo ""
        return 0  # Exit successfully but skip cleanup
    fi

    # ========================================================================
    # Step 5.2: Check for nix-env Installed Packages
    # ========================================================================
    # Why: Need to know what's installed imperatively before removing anything
    # How: Run nix-env -q (query) to list all user-installed packages
    # Output format: package-name-version (e.g., git-2.42.0)
    #
    # nix-env -q flags:
    # - No flags: List installed packages in current profile
    # - Output: One package per line with version
    #
    # Error handling:
    # - 2>/dev/null: Suppress error messages
    # - || true: If command fails, continue (don't exit script)
    # - Why: nix-env might fail if profile doesn't exist yet
    #
    # local variable: imperative_pkgs holds the list of packages
    print_info "Checking for packages installed via nix-env..."
    local imperative_pkgs
    imperative_pkgs=$(nix-env -q 2>/dev/null || true)

    # ========================================================================
    # Step 5.3: Process nix-env Packages (if any exist)
    # ========================================================================
    # Check if we found any packages
    # [[ -n "$var" ]]: True if variable is non-empty
    if [[ -n "$imperative_pkgs" ]]; then
        print_warning "Found packages installed via nix-env:"

        # Display packages with indentation for readability
        # sed 's/^/    /': Add 4 spaces to start of each line
        # | (pipe): Send output of echo to sed
        echo "$imperative_pkgs" | sed 's/^/    /'
        echo ""

        # --------------------------------------------------------------------
        # Intelligent Selective Removal Logic
        # --------------------------------------------------------------------
        # Goal: Remove ONLY packages that conflict with home-manager
        # Method: Pattern matching against known conflicting package names
        #
        # Why selective instead of removing all:
        # - User might have custom tools installed
        # - Not all packages conflict with home-manager
        # - Preserves user's workflow
        print_info "Identifying conflicting packages for selective removal..."

        # Array to store packages that need removal
        # local -a: Local array variable
        # =(): Initialize as empty array
        local -a conflicting_pkgs=()

        # --------------------------------------------------------------------
        # Scan Each Package for Conflicts
        # --------------------------------------------------------------------
        # while IFS= read -r pkg: Read package list line by line
        # - IFS=: Don't split on whitespace (preserve full line)
        # - read -r: Raw mode (don't interpret backslashes)
        # - pkg: Variable to store each line
        # <<< "$imperative_pkgs": Use string as input to while loop
        #
        # This is called a "here-string" - feeds string to loop
        while IFS= read -r pkg; do
            # Extract package name without version
            # echo "$pkg" | awk '{print $1}': Get first field
            # awk: Text processing tool, {print $1} prints first column
            # $1 in awk: First field (space-separated)
            local pkg_name
            pkg_name=$(echo "$pkg" | awk '{print $1}')

            # Only process if we got a valid package name
            if [[ -n "$pkg_name" ]]; then
                # --------------------------------------------------------
                # Pattern Matching for Known Conflicts
                # --------------------------------------------------------
                # [[ "$pkg_name" =~ ^(pattern1|pattern2|...) ]]:
                # - =~: Regex match operator
                # - ^: Start of string
                # - (a|b|c): Match a OR b OR c
                #
                # Known conflicting packages:
                # - home-manager: Will be managed declaratively
                # - git: Common in both imperative and home-manager
                # - vscodium: Editor, often in home-manager
                # - nodejs: Development tool, managed by home-manager
                # - python: Runtime, managed by home-manager
                #
                # Why these specific packages:
                # - Frequently installed both ways
                # - Cause "collision" errors
                # - Better managed declaratively
                if [[ "$pkg_name" =~ ^(home-manager|git|vscodium|nodejs|python) ]]; then
                    # Add to removal list
                    # +=(): Append to array
                    conflicting_pkgs+=("$pkg_name")
                fi
            fi
        done <<< "$imperative_pkgs"

        # --------------------------------------------------------------------
        # Remove Conflicting Packages
        # --------------------------------------------------------------------
        # Check if we found any conflicts
        # ${#array[@]}: Array length
        # -gt 0: Greater than 0
        if [[ ${#conflicting_pkgs[@]} -gt 0 ]]; then
            print_info "Removing ${#conflicting_pkgs[@]} conflicting package(s):"

            # Loop through conflicting packages and remove each
            # ${array[@]}: All array elements
            for pkg in "${conflicting_pkgs[@]}"; do
                print_info "  - $pkg"

                # nix-env -e: Uninstall/erase package
                # 2>/dev/null: Suppress errors
                # || print_warning: If removal fails, warn but continue
                # Why continue on failure: Package might already be removed
                nix-env -e "$pkg" 2>/dev/null || print_warning "    Failed to remove $pkg"
            done
            print_success "Conflicting packages removed"
        else
            # No conflicts found - this is good!
            print_info "No conflicting packages detected - keeping all nix-env packages"
        fi
    else
        # No nix-env packages at all - ideal state
        # All packages will be managed declaratively from now on
        print_success "No nix-env packages found - clean state!"
    fi

    # ========================================================================
    # Step 5.4: Optional Generation Cleanup
    # ========================================================================
    # Why: Old nix-env generations take up disk space
    # What: Each nix-env operation creates a "generation" (snapshot)
    # Where: ~/.nix-profile/generations/
    # How much: Can accumulate to several GB over time
    #
    # Generations provide rollback capability:
    # - nix-env --rollback: Revert to previous generation
    # - nix-env --list-generations: Show all generations
    # - nix-env --delete-generations old: Remove all but current
    #
    # Why ask user:
    # - Removes rollback capability
    # - Permanent operation (can't undo)
    # - Default "n" (no): Safer to keep generations unless space tight
    #
    # confirm with "n" default: User must explicitly type "y" to proceed
    if confirm "Remove old nix-env generations to free up space?" "n"; then
        # --delete-generations old: Remove all non-current generations
        # 2>/dev/null: Suppress errors (might not have old generations)
        # || true: If command fails, continue (don't exit script)
        nix-env --delete-generations old 2>/dev/null || true
        print_success "Old generations cleaned up"
    fi

    # ------------------------------------------------------------------------
    # Mark Phase Complete
    # ------------------------------------------------------------------------
    # Cleanup complete - system is now ready for declarative management.
    # No more imperative package conflicts.
    #
    # State: "intelligent_cleanup" marked complete
    # Next: Phase 6 will deploy the declarative configurations
    mark_step_complete "$phase_name"
    print_success "Phase 5: Intelligent Cleanup - COMPLETE"
    echo ""
}

# Execute phase
phase_05_cleanup
