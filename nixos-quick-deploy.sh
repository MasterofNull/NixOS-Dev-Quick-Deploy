#!/usr/bin/env bash
#
# NixOS Quick Deploy - Bootstrap Loader
# Version: 4.0.0
# Purpose: Orchestrate modular 8-phase deployment workflow
#
# ============================================================================
# ARCHITECTURE OVERVIEW
# ============================================================================
# This is the main entry point that orchestrates the 8-phase deployment
# workflow using a modular architecture.
#
# Workflow Phases (v4.0.0):
# - Phase 1: System Initialization - Validate requirements, install temp tools
# - Phase 2: System Backup - Comprehensive backup of system and user state
# - Phase 3: Configuration Generation - Generate declarative NixOS configs
# - Phase 4: Pre-deployment Validation - Validate configs, check conflicts
# - Phase 5: Declarative Deployment - Remove nix-env packages, apply configs
# - Phase 6: Additional Tooling - Install non-declarative tools (Claude Code)
# - Phase 7: Post-deployment Validation - Verify packages and services
# - Phase 8: Finalization and Report - Complete setup, generate report
#
# Directory structure:
# nixos-quick-deploy.sh (this file) - Main entry point
# ├── config/                        - Configuration files
# │   ├── variables.sh               - Global variables
# │   └── defaults.sh                - Default values
# ├── lib/                           - Shared libraries
# │   ├── colors.sh                  - Terminal colors
# │   ├── logging.sh                 - Logging functions
# │   ├── error-handling.sh          - Error management
# │   ├── state-management.sh        - State tracking
# │   └── ... (additional libraries)
# └── phases/                        - Phase implementations
#     ├── phase-01-system-initialization.sh
#     ├── phase-02-system-backup.sh
#     ├── phase-03-configuration-generation.sh
#     ├── phase-04-pre-deployment-validation.sh
#     ├── phase-05-declarative-deployment.sh
#     ├── phase-06-additional-tooling.sh
#     ├── phase-07-post-deployment-validation.sh
#     └── phase-08-finalization-and-report.sh
#
# ============================================================================
# SCRIPT CONFIGURATION
# ============================================================================

# Bash strict mode
set -o pipefail  # Catch errors in pipelines
set -E           # ERR trap inherited by functions

# ============================================================================
# READONLY CONSTANTS
# ============================================================================

readonly SCRIPT_VERSION="4.0.0"
readonly BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LIB_DIR="$BOOTSTRAP_SCRIPT_DIR/lib"
readonly CONFIG_DIR="$BOOTSTRAP_SCRIPT_DIR/config"
readonly PHASES_DIR="$BOOTSTRAP_SCRIPT_DIR/phases"

# Export SCRIPT_DIR for compatibility with libraries that expect it
readonly SCRIPT_DIR="$BOOTSTRAP_SCRIPT_DIR"
export SCRIPT_DIR

# ============================================================================
# EARLY ENVIRONMENT SETUP
# ============================================================================
# Ensure critical environment variables are set before any library loading
# USER might not be set in some environments (e.g., cron, systemd)
USER="${USER:-$(whoami 2>/dev/null || id -un 2>/dev/null || echo 'unknown')}"
export USER

# EUID is a bash built-in, but export it for consistency
export EUID

# ============================================================================
# EARLY LOGGING CONFIGURATION
# ============================================================================
# These variables must be defined BEFORE loading libraries (especially logging.sh)
# because logging.sh uses them immediately when init_logging() is called

# Create log directory path in user cache
readonly LOG_DIR="${HOME}/.cache/nixos-quick-deploy/logs"
# Create unique log file with timestamp
readonly LOG_FILE="${LOG_DIR}/deploy-$(date +%Y%m%d_%H%M%S).log"
# Set default log level (can be overridden by CLI args)
LOG_LEVEL="${LOG_LEVEL:-INFO}"
# Debug flag (can be overridden by CLI args)
ENABLE_DEBUG=false

# Export critical variables so they're available to all sourced files
export SCRIPT_VERSION
export LOG_DIR
export LOG_FILE
export LOG_LEVEL

# ============================================================================
# GLOBAL VARIABLES - CLI Flags
# ============================================================================

DRY_RUN=false
FORCE_UPDATE=false
# ENABLE_DEBUG defined above in EARLY LOGGING CONFIGURATION
ROLLBACK=false
RESET_STATE=false
SKIP_HEALTH_CHECK=false
SHOW_HELP=false
SHOW_VERSION=false
QUIET_MODE=false
VERBOSE_MODE=false
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

# Safe restart phases (can safely restart from these)
readonly SAFE_RESTART_PHASES=(1 3 8)

# ============================================================================
# PHASE NAME MAPPING
# ============================================================================

get_phase_name() {
    case $1 in
        1) echo "system-initialization" ;;
        2) echo "system-backup" ;;
        3) echo "configuration-generation" ;;
        4) echo "pre-deployment-validation" ;;
        5) echo "declarative-deployment" ;;
        6) echo "additional-tooling" ;;
        7) echo "post-deployment-validation" ;;
        8) echo "finalization-and-report" ;;
        *) echo "unknown" ;;
    esac
}

get_phase_description() {
    case $1 in
        1) echo "System initialization - validate requirements and install temporary tools" ;;
        2) echo "System backup - comprehensive backup of all system and user state" ;;
        3) echo "Configuration generation - generate all declarative NixOS configs" ;;
        4) echo "Pre-deployment validation - validate configs and check for conflicts" ;;
        5) echo "Declarative deployment - remove nix-env packages and apply configs" ;;
        6) echo "Additional tooling - install non-declarative tools (Claude Code, etc.)" ;;
        7) echo "Post-deployment validation - verify packages and services running" ;;
        8) echo "Finalization and report - complete setup and generate deployment report" ;;
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
        "python.sh"
        "nixos.sh"
        "packages.sh"
        "home-manager.sh"
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

        # Source config files
        # Note: set -u is not yet enabled at this point, so undefined variables
        # won't cause errors. Critical variables like LOG_DIR, LOG_FILE, and
        # SCRIPT_VERSION are already defined in main script before this runs.
        if source "$config_path" 2>/dev/null; then
            echo "  ✓ Loaded: $config"
        else
            echo "FATAL: Failed to load configuration: $config" >&2
            exit 1
        fi
    done

    echo ""
}

# ============================================================================
# HELP AND USAGE
# ============================================================================

print_version() {
    cat << EOF
NixOS Quick Deploy - Modular Bootstrap Loader
Version: $SCRIPT_VERSION
Architecture: 8-phase modular deployment system

Components:
  - 10 library files (colors, logging, error-handling, state, etc.)
  - 2 config files (variables, defaults)
  - 8 phase modules (system-initialization through finalization-and-report)
  - 1 bootstrap orchestrator (this script)

Copyright (c) 2025
License: MIT
Repository: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy

For help: $(basename "$0") --help
EOF
}

print_usage() {
    cat << 'EOF'
NixOS Quick Deploy - Bootstrap Loader v4.0.0

USAGE:
    ./nixos-quick-deploy.sh [OPTIONS]

BASIC OPTIONS:
    -h, --help                  Show this help message
    -v, --version               Show version information
    -q, --quiet                 Quiet mode (only warnings and errors)
        --verbose               Verbose mode (detailed output)
    -d, --debug                 Enable debug mode (trace execution)
    -f, --force-update          Force recreation of configurations
        --dry-run               Preview changes without applying
        --rollback              Rollback to previous state
        --reset-state           Clear state for fresh start
        --skip-health-check     Skip health check validation

PHASE CONTROL OPTIONS:
        --skip-phase N          Skip specific phase number (1-8)
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
    Phase 1:  System Initialization       - Validate requirements, install temp tools
    Phase 2:  System Backup               - Comprehensive system and user backup
    Phase 3:  Configuration Generation    - Generate declarative NixOS configs
    Phase 4:  Pre-deployment Validation   - Validate configs, check conflicts
    Phase 5:  Declarative Deployment      - Remove nix-env packages, apply configs
    Phase 6:  Additional Tooling          - Install non-declarative tools
    Phase 7:  Post-deployment Validation  - Verify packages and services
    Phase 8:  Finalization and Report     - Complete setup, generate report

EXAMPLES:
    # Normal deployment (resumes from last failure if any)
    ./nixos-quick-deploy.sh

    # Start fresh deployment
    ./nixos-quick-deploy.sh --reset-state

    # Skip health check and start from phase 3
    ./nixos-quick-deploy.sh --skip-health-check --start-from-phase 3

    # Skip specific phases
    ./nixos-quick-deploy.sh --skip-phase 5 --skip-phase 7

    # Test a specific phase
    ./nixos-quick-deploy.sh --test-phase 4

    # List all phases with current status
    ./nixos-quick-deploy.sh --list-phases

    # Show detailed info about a phase
    ./nixos-quick-deploy.sh --show-phase-info 6

    # Rollback to previous state
    ./nixos-quick-deploy.sh --rollback

    # Dry run to preview changes
    ./nixos-quick-deploy.sh --dry-run

SAFE RESTART POINTS:
    Phases 1, 3, and 8 are safe restart points. Other phases may require
    dependency validation before restarting.

FOR MORE INFORMATION:
    Visit: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy
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
            -v|--version)
                SHOW_VERSION=true
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            --verbose)
                VERBOSE_MODE=true
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

    for phase_num in {1..8}; do
        local phase_name=$(get_phase_name "$phase_num")
        local phase_desc=$(get_phase_description "$phase_num")
        local status="PENDING"

        # Check if state file exists and get status
        if [[ -f "${STATE_FILE:-}" ]]; then
            if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                status="COMPLETED"
            fi
        fi

        printf "Phase %2d: %-30s [%s]\n" "$phase_num" "$phase_name" "$status"
        printf "          %s\n\n" "$phase_desc"
    done

    echo "============================================"
    echo ""
}

show_phase_info() {
    local phase_num="$1"

    if [[ ! "$phase_num" =~ ^[0-9]+$ ]] || [[ "$phase_num" -lt 1 ]] || [[ "$phase_num" -gt 8 ]]; then
        echo "ERROR: Invalid phase number. Must be 1-8" >&2
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
        if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
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
                if jq -e --arg step "phase-$(printf '%02d' $safe_phase)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
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

    for phase_num in {1..8}; do
        if ! jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
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
        if ! jq -e --arg step "phase-$(printf '%02d' $dep)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
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
    echo "  8-Phase Modular Deployment"
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
    # Parse arguments
    parse_arguments "$@"

    # Enable debug mode if requested
    if [[ "$ENABLE_DEBUG" == true ]]; then
        set -x
    fi

    # Configure logging level
    if [[ "$QUIET_MODE" == true ]]; then
        export LOG_LEVEL="WARNING"
    elif [[ "$VERBOSE_MODE" == true ]]; then
        export LOG_LEVEL="DEBUG"
    else
        export LOG_LEVEL="INFO"
    fi

    # Handle early-exit commands
    if [[ "$SHOW_HELP" == true ]]; then
        print_usage
        exit 0
    fi

    if [[ "$SHOW_VERSION" == true ]]; then
        print_version
        exit 0
    fi

    if [[ "$LIST_PHASES" == true ]]; then
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        list_phases
        exit 0
    fi

    if [[ -n "$SHOW_PHASE_INFO_NUM" ]]; then
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        show_phase_info "$SHOW_PHASE_INFO_NUM"
        exit 0
    fi

    # Load core components
    load_libraries
    load_configuration

    # Enable strict undefined variable checking
    set -u

    # Handle rollback mode
    if [[ "$ROLLBACK" == true ]]; then
        perform_rollback
        exit $?
    fi

    # Handle state reset
    if [[ "$RESET_STATE" == true ]]; then
        reset_state
        print_success "State reset successfully"
        exit 0
    fi

    # Initialize core systems
    init_logging
    ensure_nix_experimental_features_env
    init_state

    # Print deployment header
    print_header

    # Handle test phase mode
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

    # Validate starting phase number
    if [[ ! "$start_phase" =~ ^[0-9]+$ ]] || [[ "$start_phase" -lt 1 ]] || [[ "$start_phase" -gt 8 ]]; then
        print_error "Invalid starting phase: $start_phase"
        exit 1
    fi

    # Create rollback point
    if [[ "$DRY_RUN" == false && $start_phase -eq 1 ]]; then
        log INFO "Creating rollback point"
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # Execute phases sequentially
    echo ""
    print_section "Starting 8-Phase Deployment Workflow"
    log INFO "Starting deployment from phase $start_phase"
    echo ""

    for phase_num in $(seq $start_phase 8); do
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

    # Deployment success
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
