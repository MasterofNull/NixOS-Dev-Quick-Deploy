#!/usr/bin/env bash
#
# Dry-Run Validation Functions
# Purpose: Comprehensive dry-run validation for deployment operations
# Version: 1.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#   - lib/validation.sh → Validation functions
#
# Exports:
#   - dry_run_phase_validation() → Validate what a phase would do
#   - dry_run_check_permissions() → Check required permissions
#   - dry_run_check_dependencies() → Check required dependencies
#   - dry_run_check_conflicts() → Check for conflicts
# ============================================================================

# ============================================================================
# Dry-Run Phase Validation
# ============================================================================
# Purpose: Validate what a phase would do without executing it
# Parameters:
#   $1 - Phase number
#   $2 - Phase name
#   $3 - Phase script path
# Returns: 0 if validation passes, 1 if issues found
# ============================================================================
dry_run_phase_validation() {
    local phase_num="${1:-}"
    local phase_name="${2:-}"
    local phase_script="${3:-}"
    
    if [[ -z "$phase_num" || -z "$phase_name" || -z "$phase_script" ]]; then
        log WARNING "dry_run_phase_validation: missing required parameters"
        return 1
    fi
    
    log INFO "[DRY RUN] Validating phase $phase_num: $phase_name"
    
    local issues_found=0
    
    # Check script exists and is readable
    if [[ ! -f "$phase_script" ]]; then
        print_warning "[DRY RUN] Phase script not found: $phase_script"
        log WARNING "[DRY RUN] Phase $phase_num script missing"
        ((issues_found++))
    elif [[ ! -r "$phase_script" ]]; then
        print_warning "[DRY RUN] Phase script not readable: $phase_script"
        log WARNING "[DRY RUN] Phase $phase_num script not readable"
        ((issues_found++))
    else
        print_info "[DRY RUN] Phase script exists and is readable"
        log DEBUG "[DRY RUN] Phase $phase_num script validated"
    fi
    
    # Check permissions based on phase requirements
    if ! dry_run_check_permissions "$phase_num"; then
        ((issues_found++))
    fi
    
    # Check dependencies
    if ! dry_run_check_dependencies "$phase_num"; then
        ((issues_found++))
    fi
    
    # Check for conflicts
    if ! dry_run_check_conflicts "$phase_num"; then
        ((issues_found++))
    fi
    
    # Phase-specific validations
    case "$phase_num" in
        3)
            # Phase 3: Configuration Generation
            if ! dry_run_validate_config_generation; then
                ((issues_found++))
            fi
            ;;
        5)
            # Phase 5: Declarative Deployment
            if ! dry_run_validate_deployment; then
                ((issues_found++))
            fi
            ;;
        6)
            # Phase 6: Additional Tooling
            if ! dry_run_validate_tooling; then
                ((issues_found++))
            fi
            ;;
    esac
    
    if [[ $issues_found -eq 0 ]]; then
        print_success "[DRY RUN] Phase $phase_num validation passed"
        log INFO "[DRY RUN] Phase $phase_num validation complete - no issues"
        return 0
    else
        print_warning "[DRY RUN] Phase $phase_num validation found $issues_found issue(s)"
        log WARNING "[DRY RUN] Phase $phase_num validation found issues"
        return 1
    fi
}

# ============================================================================
# Check Required Permissions
# ============================================================================
# Purpose: Validate that required permissions are available
# Parameters:
#   $1 - Phase number
# Returns: 0 if permissions OK, 1 if missing
# ============================================================================
dry_run_check_permissions() {
    local phase_num="${1:-}"
    local missing_perms=0
    
    case "$phase_num" in
        5|6|7)
            # Phases that need sudo for system changes
            if [[ $EUID -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
                print_warning "[DRY RUN] sudo not available but may be required for phase $phase_num"
                log WARNING "[DRY RUN] Missing sudo for phase $phase_num"
                ((missing_perms++))
            fi
            ;;
    esac
    
    # Check write permissions for common directories
    local -a check_dirs=(
        "${HOME}/.cache"
        "${HOME}/.local"
        "${LOG_DIR:-}"
    )
    
    for dir in "${check_dirs[@]}"; do
        if [[ -n "$dir" && -d "$dir" && ! -w "$dir" ]]; then
            print_warning "[DRY RUN] Directory not writable: $dir"
            log WARNING "[DRY RUN] Missing write permission: $dir"
            ((missing_perms++))
        fi
    done
    
    return $missing_perms
}

# ============================================================================
# Check Dependencies
# ============================================================================
# Purpose: Validate that required commands/tools are available
# Parameters:
#   $1 - Phase number
# Returns: 0 if dependencies OK, 1 if missing
# ============================================================================
dry_run_check_dependencies() {
    local phase_num="${1:-}"
    local missing_deps=0
    
    # Common dependencies for all phases
    local -a common_deps=("bash" "jq")
    
    # Phase-specific dependencies
    case "$phase_num" in
        1)
            local -a phase_deps=("nix" "git")
            ;;
        3)
            local -a phase_deps=("nix" "jq")
            ;;
        5)
            local -a phase_deps=("nix" "sudo" "systemctl")
            ;;
        6)
            local -a phase_deps=("npm" "flatpak")
            ;;
        *)
            local -a phase_deps=()
            ;;
    esac
    
    # Check all dependencies
    local -a all_deps=("${common_deps[@]}" "${phase_deps[@]}")
    for dep in "${all_deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            print_warning "[DRY RUN] Required command not found: $dep"
            log WARNING "[DRY RUN] Missing dependency: $dep"
            ((missing_deps++))
        fi
    done
    
    return $missing_deps
}

# ============================================================================
# Check for Conflicts
# ============================================================================
# Purpose: Check for potential conflicts before deployment
# Parameters:
#   $1 - Phase number
# Returns: 0 if no conflicts, 1 if conflicts found
# ============================================================================
dry_run_check_conflicts() {
    local phase_num="${1:-}"
    local conflicts_found=0
    
    case "$phase_num" in
        5)
            # Phase 5: Check for running nixos-rebuild
            if systemctl >/dev/null 2>&1; then
                if systemctl is-active --quiet nixos-rebuild-switch-to-configuration.service 2>/dev/null; then
                    print_warning "[DRY RUN] nixos-rebuild service already running - may conflict"
                    log WARNING "[DRY RUN] Conflicting service running: nixos-rebuild"
                    ((conflicts_found++))
                fi
            fi
            ;;
        6)
            # Phase 6: Check for existing Flatpak installations
            if command -v flatpak >/dev/null 2>&1; then
                local flatpak_count
                flatpak_count=$(flatpak list --user --app 2>/dev/null | wc -l || echo "0")
                if [[ $flatpak_count -gt 0 ]]; then
                    print_info "[DRY RUN] Found $flatpak_count existing Flatpak applications"
                    log INFO "[DRY RUN] Existing Flatpak apps detected: $flatpak_count"
                fi
            fi
            ;;
    esac
    
    return $conflicts_found
}

# ============================================================================
# Phase-Specific Validations
# ============================================================================

dry_run_validate_config_generation() {
    local issues=0
    
    if [[ ! -d "${HM_CONFIG_DIR:-}" ]]; then
        print_info "[DRY RUN] Configuration directory will be created: ${HM_CONFIG_DIR:-<undefined>}"
    else
        print_info "[DRY RUN] Configuration directory exists: ${HM_CONFIG_DIR:-}"
    fi
    
    return $issues
}

dry_run_validate_deployment() {
    local issues=0
    
    if [[ ! -d "${HM_CONFIG_DIR:-}" ]]; then
        print_warning "[DRY RUN] Configuration directory missing - Phase 3 must complete first"
        log WARNING "[DRY RUN] Missing HM_CONFIG_DIR for deployment"
        ((issues++))
    elif [[ ! -f "${HM_CONFIG_DIR:-}/flake.nix" ]]; then
        print_warning "[DRY RUN] flake.nix missing - Phase 3 must complete first"
        log WARNING "[DRY RUN] Missing flake.nix for deployment"
        ((issues++))
    else
        print_info "[DRY RUN] Configuration files validated"
    fi
    
    return $issues
}

dry_run_validate_tooling() {
    local issues=0
    
    if ! command -v npm >/dev/null 2>&1; then
        print_warning "[DRY RUN] npm not available - Phase 6 tooling may be limited"
        log WARNING "[DRY RUN] npm missing for tooling installation"
        ((issues++))
    fi
    
    if ! command -v flatpak >/dev/null 2>&1; then
        print_warning "[DRY RUN] flatpak not available - Flatpak apps won't be installed"
        log WARNING "[DRY RUN] flatpak missing"
        ((issues++))
    fi
    
    return $issues
}

