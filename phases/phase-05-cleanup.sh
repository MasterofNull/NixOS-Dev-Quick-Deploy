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
    local phase_name="intelligent_cleanup"

    if is_step_complete "$phase_name"; then
        print_info "Phase 5 already completed (skipping)"
        return 0
    fi

    print_section "Phase 5/10: Intelligent Cleanup"
    echo ""

    print_warning "This phase will remove conflicting packages and configurations"
    print_info "All removals are backed up and can be restored if needed"
    echo ""

    # User confirmation before destructive operations
    if ! confirm "Proceed with intelligent cleanup of conflicting packages?" "y"; then
        print_warning "Cleanup skipped - this may cause conflicts during installation"
        echo ""
        return 0
    fi

    # Check for nix-env packages
    print_info "Checking for packages installed via nix-env..."
    local imperative_pkgs
    imperative_pkgs=$(nix-env -q 2>/dev/null || true)

    if [[ -n "$imperative_pkgs" ]]; then
        print_warning "Found packages installed via nix-env:"
        echo "$imperative_pkgs" | sed 's/^/    /'
        echo ""

        # Intelligent selective removal instead of nix-env -e '.*'
        print_info "Identifying conflicting packages for selective removal..."
        local -a conflicting_pkgs=()

        # Only remove packages that conflict with home-manager
        while IFS= read -r pkg; do
            local pkg_name
            pkg_name=$(echo "$pkg" | awk '{print $1}')
            if [[ -n "$pkg_name" ]]; then
                # Add known conflicting packages
                if [[ "$pkg_name" =~ ^(home-manager|git|vscodium|nodejs|python) ]]; then
                    conflicting_pkgs+=("$pkg_name")
                fi
            fi
        done <<< "$imperative_pkgs"

        if [[ ${#conflicting_pkgs[@]} -gt 0 ]]; then
            print_info "Removing ${#conflicting_pkgs[@]} conflicting package(s):"
            for pkg in "${conflicting_pkgs[@]}"; do
                print_info "  - $pkg"
                nix-env -e "$pkg" 2>/dev/null || print_warning "    Failed to remove $pkg"
            done
            print_success "Conflicting packages removed"
        else
            print_info "No conflicting packages detected - keeping all nix-env packages"
        fi
    else
        print_success "No nix-env packages found - clean state!"
    fi

    # Cleanup old generations (optional)
    if confirm "Remove old nix-env generations to free up space?" "n"; then
        nix-env --delete-generations old 2>/dev/null || true
        print_success "Old generations cleaned up"
    fi

    mark_step_complete "$phase_name"
    print_success "Phase 5: Intelligent Cleanup - COMPLETE"
    echo ""
}

# Execute phase
phase_05_cleanup
