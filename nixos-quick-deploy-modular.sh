#!/usr/bin/env bash
#
# NixOS Quick Deploy - Modular Bootstrap Loader
# Version: 3.2.0
# Purpose: Orchestrate modular deployment phases with advanced execution control
#
# Architecture: Modular design with separate phase modules
# - lib/: Shared libraries
# - config/: Configuration files
# - phases/: Phase execution modules (10 phases)
#
# ============================================================================
# SCRIPT CONFIGURATION
# ============================================================================

set -o pipefail     # Exit on pipe failures
set -E              # Inherit ERR trap

# Note: set -u is enabled after configuration loading to avoid conflicts

readonly SCRIPT_VERSION="3.2.0"
readonly BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LIB_DIR="$BOOTSTRAP_SCRIPT_DIR/lib"
readonly CONFIG_DIR="$BOOTSTRAP_SCRIPT_DIR/config"
readonly PHASES_DIR="$BOOTSTRAP_SCRIPT_DIR/phases"

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

# CLI flags
DRY_RUN=false
FORCE_UPDATE=false
ENABLE_DEBUG=false
ROLLBACK=false
RESET_STATE=false
SKIP_HEALTH_CHECK=false
SHOW_HELP=false
LIST_PHASES=false
RESUME=true
RESTART_FAILED=false
RESTART_FROM_SAFE_POINT=false

# Phase control
declare -a SKIP_PHASES=()
START_FROM_PHASE=""
RESTART_PHASE=""
TEST_PHASE=""
SHOW_PHASE_INFO_NUM=""

# Safe restart points (phases that can be safely restarted)
readonly SAFE_RESTART_PHASES=(1 3 8)

# ============================================================================
# PHASE NAME MAPPING
# ============================================================================

get_phase_name() {
    case $1 in
        1) echo "preparation" ;;
        2) echo "prerequisites" ;;
        3) echo "backup" ;;
        4) echo "config-generation" ;;
        5) echo "cleanup" ;;
        6) echo "deployment" ;;
        7) echo "tools-installation" ;;
        8) echo "validation" ;;
        9) echo "finalization" ;;
        10) echo "reporting" ;;
        *) echo "unknown" ;;
    esac
}

get_phase_description() {
    case $1 in
        1) echo "System preparation and environment setup" ;;
        2) echo "Install prerequisites and validate system" ;;
        3) echo "Backup current configuration" ;;
        4) echo "Generate NixOS configurations" ;;
        5) echo "Cleanup temporary files and caches" ;;
        6) echo "Deploy configuration to system" ;;
        7) echo "Install additional tools" ;;
        8) echo "Validate deployment success" ;;
        9) echo "Finalize and apply system changes" ;;
        10) echo "Generate deployment report" ;;
        *) echo "Unknown phase" ;;
    esac
}

get_phase_dependencies() {
    case $1 in
        1) echo "" ;;
        2) echo "1" ;;
        3) echo "1,2" ;;
        4) echo "1,2,3" ;;
        5) echo "1,2,3,4" ;;
        6) echo "1,2,3,4,5" ;;
        7) echo "1,2,3,4,5,6" ;;
        8) echo "1,2,3,4,5,6,7" ;;
        9) echo "1,2,3,4,5,6,7,8" ;;
        10) echo "1,2,3,4,5,6,7,8,9" ;;
        *) echo "" ;;
    esac
}

# ============================================================================
# LIBRARY LOADING
# ============================================================================

load_libraries() {
    local libs=(
        "colors.sh"
        "logging.sh"
        "error-handling.sh"
        "state-management.sh"
        "user-interaction.sh"
        "validation.sh"
        "retry.sh"
        "backup.sh"
        "gpu-detection.sh"
        "common.sh"
    )

    echo "Loading libraries..."
    for lib in "${libs[@]}"; do
        local lib_path="$LIB_DIR/$lib"
        if [[ ! -f "$lib_path" ]]; then
            echo "FATAL: Library not found: $lib_path" >&2
            exit 1
        fi

        source "$lib_path" || {
            echo "FATAL: Failed to load library: $lib" >&2
            exit 1
        }
        echo "  ✓ Loaded: $lib"
    done
    echo ""
}

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

load_configuration() {
    local configs=(
        "variables.sh"
        "defaults.sh"
    )

    echo "Loading configuration..."

    for config in "${configs[@]}"; do
        local config_path="$CONFIG_DIR/$config"
        if [[ ! -f "$config_path" ]]; then
            echo "FATAL: Configuration not found: $config_path" >&2
            exit 1
        fi

        # Source config files with relaxed error handling
        # (readonly variable warnings are expected and non-fatal)
        {
            set +e +u
            source "$config_path"
            set -e -u
        } 2>&1 | grep -v "readonly variable" >&2 || true

        echo "  ✓ Loaded: $config"
    done

    echo ""
}

# ============================================================================
# HELP AND USAGE
# ============================================================================

print_usage() {
    cat << 'EOF'
NixOS Quick Deploy - Modular Bootstrap Loader v3.2.0

USAGE:
    ./nixos-quick-deploy-modular.sh [OPTIONS]

BASIC OPTIONS:
    -h, --help                  Show this help message
    -d, --debug                 Enable debug mode (verbose output)
    -f, --force-update          Force recreation of configurations
        --dry-run               Preview changes without applying
        --rollback              Rollback to previous state
        --reset-state           Clear state for fresh start
        --skip-health-check     Skip health check validation

PHASE CONTROL OPTIONS:
        --skip-phase N          Skip specific phase number (1-10)
                                Can be used multiple times
        --start-from-phase N    Start execution from phase N onwards
        --restart-phase N       Restart from specific phase number
        --test-phase N          Test specific phase in isolation
        --resume                Resume from last failed phase (default)
        --restart-failed        Restart the failed phase from beginning
        --restart-from-safe-point   Restart from last safe entry point

INFORMATION OPTIONS:
        --list-phases           List all phases with status
        --show-phase-info N     Show detailed info about phase N

PHASE OVERVIEW:
    Phase 1:  Preparation          - System preparation and environment setup
    Phase 2:  Prerequisites        - Install prerequisites and validate system
    Phase 3:  Backup              - Backup current configuration
    Phase 4:  Config Generation   - Generate NixOS configurations
    Phase 5:  Cleanup             - Cleanup temporary files and caches
    Phase 6:  Deployment          - Deploy configuration to system
    Phase 7:  Tools Installation  - Install additional tools
    Phase 8:  Validation          - Validate deployment success
    Phase 9:  Finalization        - Finalize and apply system changes
    Phase 10: Reporting           - Generate deployment report

EXAMPLES:
    # Normal deployment (resumes from last failure if any)
    ./nixos-quick-deploy-modular.sh

    # Start fresh deployment
    ./nixos-quick-deploy-modular.sh --reset-state

    # Skip health check and start from phase 3
    ./nixos-quick-deploy-modular.sh --skip-health-check --start-from-phase 3

    # Skip specific phases
    ./nixos-quick-deploy-modular.sh --skip-phase 5 --skip-phase 7

    # Test a specific phase
    ./nixos-quick-deploy-modular.sh --test-phase 4

    # List all phases with current status
    ./nixos-quick-deploy-modular.sh --list-phases

    # Show detailed info about a phase
    ./nixos-quick-deploy-modular.sh --show-phase-info 6

    # Rollback to previous state
    ./nixos-quick-deploy-modular.sh --rollback

    # Dry run to preview changes
    ./nixos-quick-deploy-modular.sh --dry-run

SAFE RESTART POINTS:
    Phases 1, 3, and 8 are safe restart points. Other phases may require
    dependency validation before restarting.

FOR MORE INFORMATION:
    Visit: https://github.com/yourusername/NixOS-Dev-Quick-Deploy
    Logs: ~/.config/nixos-quick-deploy/logs/

EOF
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                SHOW_HELP=true
                shift
                ;;
            -d|--debug)
                ENABLE_DEBUG=true
                shift
                ;;
            -f|--force-update)
                FORCE_UPDATE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --reset-state)
                RESET_STATE=true
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            --skip-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --skip-phase requires a phase number" >&2
                    exit 1
                fi
                SKIP_PHASES+=("$2")
                shift 2
                ;;
            --start-from-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --start-from-phase requires a phase number" >&2
                    exit 1
                fi
                START_FROM_PHASE="$2"
                shift 2
                ;;
            --restart-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --restart-phase requires a phase number" >&2
                    exit 1
                fi
                RESTART_PHASE="$2"
                START_FROM_PHASE="$2"
                shift 2
                ;;
            --test-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --test-phase requires a phase number" >&2
                    exit 1
                fi
                TEST_PHASE="$2"
                shift 2
                ;;
            --list-phases)
                LIST_PHASES=true
                shift
                ;;
            --show-phase-info)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --show-phase-info requires a phase number" >&2
                    exit 1
                fi
                SHOW_PHASE_INFO_NUM="$2"
                shift 2
                ;;
            --resume)
                RESUME=true
                shift
                ;;
            --restart-failed)
                RESTART_FAILED=true
                shift
                ;;
            --restart-from-safe-point)
                RESTART_FROM_SAFE_POINT=true
                shift
                ;;
            *)
                echo "ERROR: Unknown option: $1" >&2
                echo "Run with --help for usage information" >&2
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# PHASE INFORMATION
# ============================================================================

list_phases() {
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy - Phase Overview"
    echo "============================================"
    echo ""

    # Load libraries minimally to get state
    source "$LIB_DIR/colors.sh" 2>/dev/null || true
    source "$CONFIG_DIR/variables.sh" 2>/dev/null || true

    for phase_num in {1..10}; do
        local phase_name=$(get_phase_name "$phase_num")
        local phase_desc=$(get_phase_description "$phase_num")
        local status="PENDING"

        # Check if state file exists and get status
        if [[ -f "${STATE_FILE:-}" ]]; then
            if jq -e ".completed_steps[] | select(. == \"phase-$(printf '%02d' $phase_num)\")" "$STATE_FILE" &>/dev/null; then
                status="COMPLETED"
            fi
        fi

        printf "Phase %2d: %-20s [%s]\n" "$phase_num" "$phase_name" "$status"
        printf "          %s\n\n" "$phase_desc"
    done

    echo "============================================"
    echo ""
}

show_phase_info() {
    local phase_num="$1"

    if [[ ! "$phase_num" =~ ^[0-9]+$ ]] || [[ "$phase_num" -lt 1 ]] || [[ "$phase_num" -gt 10 ]]; then
        echo "ERROR: Invalid phase number. Must be 1-10" >&2
        exit 1
    fi

    local phase_name=$(get_phase_name "$phase_num")
    local phase_desc=$(get_phase_description "$phase_num")
    local phase_deps=$(get_phase_dependencies "$phase_num")
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"

    echo ""
    echo "============================================"
    echo "  Phase $phase_num: $phase_name"
    echo "============================================"
    echo ""
    echo "Description:"
    echo "  $phase_desc"
    echo ""
    echo "Script Location:"
    echo "  $phase_script"
    echo ""

    if [[ -n "$phase_deps" ]]; then
        echo "Dependencies:"
        echo "  Requires phases: $phase_deps"
    else
        echo "Dependencies:"
        echo "  None (entry point phase)"
    fi
    echo ""

    # Check if phase is safe restart point
    if [[ " ${SAFE_RESTART_PHASES[@]} " =~ " ${phase_num} " ]]; then
        echo "Safe Restart Point: YES"
    else
        echo "Safe Restart Point: NO (requires dependency validation)"
    fi
    echo ""

    # Check current status
    source "$CONFIG_DIR/variables.sh" 2>/dev/null || true
    if [[ -f "${STATE_FILE:-}" ]]; then
        if jq -e ".completed_steps[] | select(. == \"phase-$(printf '%02d' $phase_num)\")" "$STATE_FILE" &>/dev/null; then
            echo "Current Status: COMPLETED"
        else
            echo "Current Status: PENDING"
        fi
    else
        echo "Current Status: PENDING (no state file)"
    fi
    echo ""
    echo "============================================"
    echo ""
}

# ============================================================================
# PHASE CONTROL
# ============================================================================

should_skip_phase() {
    local phase_num="$1"
    for skip_phase in "${SKIP_PHASES[@]}"; do
        if [[ "$skip_phase" == "$phase_num" ]]; then
            return 0
        fi
    done
    return 1
}

get_resume_phase() {
    # If restart-from-safe-point is set, find last safe point
    if [[ "$RESTART_FROM_SAFE_POINT" == true ]]; then
        local last_safe_phase=1
        if [[ -f "$STATE_FILE" ]]; then
            for safe_phase in "${SAFE_RESTART_PHASES[@]}"; do
                if jq -e ".completed_steps[] | select(. == \"phase-$(printf '%02d' $safe_phase)\")" "$STATE_FILE" &>/dev/null; then
                    last_safe_phase=$safe_phase
                fi
            done
        fi
        echo "$last_safe_phase"
        return
    fi

    # Otherwise, find the next incomplete phase
    if [[ ! -f "$STATE_FILE" ]]; then
        echo "1"
        return
    fi

    for phase_num in {1..10}; do
        if ! jq -e ".completed_steps[] | select(. == \"phase-$(printf '%02d' $phase_num)\")" "$STATE_FILE" &>/dev/null; then
            echo "$phase_num"
            return
        fi
    done

    # All phases complete
    echo "1"
}

validate_phase_dependencies() {
    local phase_num="$1"
    local deps=$(get_phase_dependencies "$phase_num")

    if [[ -z "$deps" ]]; then
        return 0
    fi

    if [[ ! -f "$STATE_FILE" ]]; then
        log ERROR "Cannot validate dependencies: state file not found"
        return 1
    fi

    local missing_deps=()
    IFS=',' read -ra DEP_ARRAY <<< "$deps"
    for dep in "${DEP_ARRAY[@]}"; do
        if ! jq -e ".completed_steps[] | select(. == \"phase-$(printf '%02d' $dep)\")" "$STATE_FILE" &>/dev/null; then
            missing_deps+=("$dep")
        fi
    done

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log ERROR "Phase $phase_num has missing dependencies: ${missing_deps[*]}"
        print_error "Cannot execute phase $phase_num: missing dependencies ${missing_deps[*]}"
        return 1
    fi

    return 0
}

execute_phase() {
    local phase_num="$1"
    local phase_name=$(get_phase_name "$phase_num")
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"
    local phase_step="phase-$(printf '%02d' $phase_num)"

    # Check if phase script exists
    if [[ ! -f "$phase_script" ]]; then
        log ERROR "Phase script not found: $phase_script"
        print_error "Phase $phase_num script not found"
        return 1
    fi

    # Check if already completed (skip if not restart)
    if [[ -z "$RESTART_PHASE" ]] && is_step_complete "$phase_step"; then
        log INFO "Phase $phase_num already completed (skipping)"
        print_info "Phase $phase_num: $phase_name [ALREADY COMPLETED]"
        return 0
    fi

    # Validate dependencies
    if ! validate_phase_dependencies "$phase_num"; then
        return 1
    fi

    # Execute phase
    print_section "Phase $phase_num: $phase_name"
    log INFO "Executing phase $phase_num: $phase_name"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Would execute: $phase_script"
        log INFO "[DRY RUN] Phase $phase_num skipped"
        return 0
    fi

    # Source and execute the phase script
    if source "$phase_script"; then
        mark_step_complete "$phase_step"
        log INFO "Phase $phase_num completed successfully"
        print_success "Phase $phase_num completed"
        return 0
    else
        local exit_code=$?
        log ERROR "Phase $phase_num failed with exit code $exit_code"
        return $exit_code
    fi
}

handle_phase_failure() {
    local phase_num="$1"
    local phase_name=$(get_phase_name "$phase_num")

    echo ""
    print_error "Phase $phase_num ($phase_name) failed!"
    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        log INFO "Dry run mode: continuing despite failure"
        return 0
    fi

    # Interactive failure handling
    echo "What would you like to do?"
    echo "  1) Retry this phase"
    echo "  2) Skip and continue"
    echo "  3) Rollback"
    echo "  4) Exit"
    echo ""
    read -p "Choice [1-4]: " choice

    case "$choice" in
        1)
            log INFO "User chose to retry phase $phase_num"
            execute_phase "$phase_num"
            return $?
            ;;
        2)
            log WARNING "User chose to skip phase $phase_num"
            print_warning "Skipping phase $phase_num"
            return 0
            ;;
        3)
            log INFO "User chose to rollback"
            perform_rollback
            exit $?
            ;;
        4|*)
            log INFO "User chose to exit"
            exit 1
            ;;
    esac
}

# ============================================================================
# ROLLBACK
# ============================================================================

perform_rollback() {
    log INFO "Performing rollback"
    print_section "Rolling back to previous state"

    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        print_error "No rollback information found"
        log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1
    fi

    # Read rollback generation
    local rollback_gen=$(cat "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "")
    if [[ -z "$rollback_gen" ]]; then
        print_error "Invalid rollback information"
        return 1
    fi

    print_info "Rolling back to generation: $rollback_gen"
    log INFO "Rolling back to generation: $rollback_gen"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Would execute: sudo nixos-rebuild switch --rollback"
        return 0
    fi

    if sudo nixos-rebuild switch --rollback; then
        print_success "Rollback completed successfully"
        log INFO "Rollback completed successfully"
        return 0
    else
        print_error "Rollback failed"
        log ERROR "Rollback failed"
        return 1
    fi
}

# ============================================================================
# MAIN INITIALIZATION
# ============================================================================

print_header() {
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy v$SCRIPT_VERSION"
    echo "  Modular Bootstrap Loader"
    echo "============================================"
    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        echo "  MODE: DRY RUN (no changes will be made)"
        echo ""
    fi

    if [[ "$ENABLE_DEBUG" == true ]]; then
        echo "  DEBUG: Enabled"
        echo ""
    fi
}

ensure_nix_experimental_features_env() {
    # Ensure flakes and nix-command are enabled
    export NIX_CONFIG="experimental-features = nix-command flakes"
}

# ============================================================================
# MAIN FUNCTION
# ============================================================================

main() {
    # Parse arguments first (before loading libraries)
    parse_arguments "$@"

    # Enable debug mode if requested
    if [[ "$ENABLE_DEBUG" == true ]]; then
        set -x
    fi

    # Handle help
    if [[ "$SHOW_HELP" == true ]]; then
        print_usage
        exit 0
    fi

    # Handle informational commands (before loading libraries to avoid initialization)
    if [[ "$LIST_PHASES" == true ]]; then
        # Load minimal libraries for list_phases
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        list_phases
        exit 0
    fi

    if [[ -n "$SHOW_PHASE_INFO_NUM" ]]; then
        # Load minimal libraries for show_phase_info
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        show_phase_info "$SHOW_PHASE_INFO_NUM"
        exit 0
    fi

    # Load core components
    load_libraries
    load_configuration

    # Enable strict undefined variable checking now that config is loaded
    set -u

    # Handle rollback
    if [[ "$ROLLBACK" == true ]]; then
        perform_rollback
        exit $?
    fi

    # Handle reset state
    if [[ "$RESET_STATE" == true ]]; then
        reset_state
        print_success "State reset successfully"
        exit 0
    fi

    # Initialize core systems
    init_logging
    ensure_nix_experimental_features_env
    init_state

    # Print header
    print_header

    # Handle test phase (isolated testing)
    if [[ -n "$TEST_PHASE" ]]; then
        log INFO "Testing phase $TEST_PHASE in isolation"
        print_section "Testing Phase $TEST_PHASE"
        execute_phase "$TEST_PHASE"
        exit $?
    fi

    # Determine starting phase
    local start_phase=1
    if [[ -n "$START_FROM_PHASE" ]]; then
        start_phase=$START_FROM_PHASE
        log INFO "Starting from phase $start_phase (user specified)"
    elif [[ "$RESUME" == true ]] || [[ -z "$START_FROM_PHASE" ]]; then
        start_phase=$(get_resume_phase)
        if [[ $start_phase -gt 1 ]]; then
            log INFO "Resuming from phase $start_phase"
            print_info "Resuming from phase $start_phase"
        fi
    fi

    # Validate starting phase
    if [[ ! "$start_phase" =~ ^[0-9]+$ ]] || [[ "$start_phase" -lt 1 ]] || [[ "$start_phase" -gt 10 ]]; then
        print_error "Invalid starting phase: $start_phase"
        exit 1
    fi

    # Create rollback point if starting from beginning
    if [[ "$DRY_RUN" == false && $start_phase -eq 1 ]]; then
        log INFO "Creating rollback point"
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # Execute phases
    echo ""
    print_section "Starting 10-Phase Deployment Workflow"
    log INFO "Starting deployment from phase $start_phase"
    echo ""

    for phase_num in $(seq $start_phase 10); do
        # Check if phase should be skipped
        if should_skip_phase "$phase_num"; then
            log INFO "Skipping phase $phase_num (user requested)"
            print_info "Skipping Phase $phase_num (--skip-phase)"
            continue
        fi

        # Execute phase
        if ! execute_phase "$phase_num"; then
            handle_phase_failure "$phase_num" || exit 1
        fi

        echo ""
    done

    # Success!
    log INFO "All phases completed successfully"
    echo ""
    echo "============================================"
    print_success "Deployment completed successfully!"
    echo "============================================"
    echo ""
    echo "Log file: $LOG_FILE"
    echo ""

    return 0
}

# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

# Run main function
main "$@"
