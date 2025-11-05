#!/usr/bin/env bash
#
# NixOS Quick Deploy - Modular Bootstrap Loader
# Version: 3.2.0
# Purpose: Orchestrate modular deployment phases with advanced execution control
#
# ============================================================================
# ARCHITECTURE OVERVIEW
# ============================================================================
# This is the bootstrap loader - the main entry point that orchestrates
# the entire 10-phase deployment workflow. It's called "bootstrap" because
# it loads and executes all the modular components.
#
# Why modular architecture:
# - Separation of concerns: Each phase has single responsibility
# - Maintainability: Easier to update individual phases
# - Testability: Can test phases in isolation
# - Debuggability: Clear phase boundaries for troubleshooting
# - Flexibility: Can skip, restart, or test individual phases
#
# Directory structure:
# nixos-quick-deploy-modular.sh (this file) - Orchestrator
# ├── config/                                - Configuration files
# │   ├── variables.sh                       - Global variables
# │   └── defaults.sh                        - Default values
# ├── lib/                                   - Shared libraries
# │   ├── colors.sh                          - Terminal colors
# │   ├── logging.sh                         - Logging functions
# │   ├── error-handling.sh                  - Error management
# │   ├── state-management.sh                - State tracking
# │   └── ... (30+ library files)
# └── phases/                                - Phase implementations
#     ├── phase-01-preparation.sh            - System validation
#     ├── phase-02-prerequisites.sh          - Package installation
#     ├── ... (phases 03-09)
#     └── phase-10-reporting.sh              - Final report
#
# Execution flow:
# 1. Parse command-line arguments
# 2. Load libraries (order matters - dependencies)
# 3. Load configuration files
# 4. Initialize logging and state management
# 5. Execute phases in sequence (1-10)
# 6. Handle errors with rollback capability
# 7. Generate final report
#
# Advanced features:
# - Resume from failure: Automatically continue from last failed phase
# - Phase control: Skip, restart, or test individual phases
# - Dry-run mode: Preview changes without applying
# - Rollback: Revert to previous system state
# - State tracking: Remember what's been completed
#
# ============================================================================
# SCRIPT CONFIGURATION
# ============================================================================

# Bash strict mode configuration:
# -o pipefail: If any command in a pipeline fails, the whole pipeline fails
#              Example: false | true returns 1 (not 0)
#              Why: Catch errors in middle of pipelines
set -o pipefail

# -E: ERR trap is inherited by shell functions
#     Why: Error handler catches failures in all functions
#     Without: ERR trap only catches errors in main script
set -E

# Note about set -u (undefined variable checking):
# We enable it AFTER loading configuration to avoid issues with
# optional variables that might be unset. This allows config files
# to use ${VAR:-default} syntax safely.

# ============================================================================
# READONLY CONSTANTS
# ============================================================================
# These values never change during execution - defined once at script start
# readonly: Prevents accidental modification (immutable)

# Script version - semantic versioning (MAJOR.MINOR.PATCH)
# Used in: Reports, logs, error messages
readonly SCRIPT_VERSION="3.2.0"

# Script directory detection:
# ${BASH_SOURCE[0]}: Path to this script file
# dirname: Get directory containing the script
# cd + pwd: Convert to absolute path (resolve symlinks)
# $(cmd): Command substitution - run cmd and capture output
# Why absolute path: Ensures we can find lib/config/phases regardless of cwd
readonly BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Component directories:
# $BOOTSTRAP_SCRIPT_DIR/lib: Shared library functions
# $BOOTSTRAP_SCRIPT_DIR/config: Configuration files
# $BOOTSTRAP_SCRIPT_DIR/phases: Phase implementations
readonly LIB_DIR="$BOOTSTRAP_SCRIPT_DIR/lib"
readonly CONFIG_DIR="$BOOTSTRAP_SCRIPT_DIR/config"
readonly PHASES_DIR="$BOOTSTRAP_SCRIPT_DIR/phases"

# ============================================================================
# GLOBAL VARIABLES - CLI Flags
# ============================================================================
# These variables are set by command-line arguments parsed in parse_arguments()
# Default values assume normal deployment mode
# Can be overridden via CLI flags (--dry-run, --debug, etc.)

# DRY_RUN: Preview mode - show what would happen without making changes
# Default: false (make real changes)
# Set by: --dry-run flag
DRY_RUN=false

# FORCE_UPDATE: Force recreation of configurations even if they exist
# Default: false (use existing configs if present)
# Set by: --force-update flag
FORCE_UPDATE=false

# ENABLE_DEBUG: Verbose debug output (set -x)
# Default: false (normal output)
# Set by: --debug flag
# Effect: Shows every command before execution
ENABLE_DEBUG=false

# ROLLBACK: Rollback to previous system state
# Default: false (normal deployment)
# Set by: --rollback flag
# Effect: Reverts to last working generation
ROLLBACK=false

# RESET_STATE: Clear state file for fresh deployment
# Default: false (resume from last state)
# Set by: --reset-state flag
# Effect: Deletes state.json, starts from phase 1
RESET_STATE=false

# SKIP_HEALTH_CHECK: Skip comprehensive health validation
# Default: false (run health check)
# Set by: --skip-health-check flag
# Saves: 2-5 minutes of validation time
SKIP_HEALTH_CHECK=false

# SHOW_HELP: Display help message and exit
# Default: false
# Set by: -h or --help flags
SHOW_HELP=false

# LIST_PHASES: Show all phases with current status
# Default: false
# Set by: --list-phases flag
LIST_PHASES=false

# RESUME: Resume from last incomplete phase
# Default: true (auto-resume on script restart)
# Set by: --resume flag (explicit)
# Note: This is the default behavior
RESUME=true

# RESTART_FAILED: Restart the last failed phase from beginning
# Default: false
# Set by: --restart-failed flag
RESTART_FAILED=false

# RESTART_FROM_SAFE_POINT: Restart from last safe checkpoint
# Default: false
# Set by: --restart-from-safe-point flag
# Safe points: Phases 1, 3, 8 (no mid-operation state)
RESTART_FROM_SAFE_POINT=false

# ============================================================================
# GLOBAL VARIABLES - Phase Control
# ============================================================================
# These variables control which phases execute and in what order

# SKIP_PHASES: Array of phase numbers to skip
# Type: Bash array
# Set by: --skip-phase N (can be used multiple times)
# Example: --skip-phase 5 --skip-phase 7 → SKIP_PHASES=(5 7)
# declare -a: Declare as array variable
declare -a SKIP_PHASES=()

# START_FROM_PHASE: Phase number to start execution from
# Default: Empty (start from phase 1 or resume point)
# Set by: --start-from-phase N
# Example: --start-from-phase 4 → Skip phases 1-3, start at 4
START_FROM_PHASE=""

# RESTART_PHASE: Phase to restart execution from
# Default: Empty (normal execution)
# Set by: --restart-phase N
# Effect: Marks phase N as incomplete, starts from there
RESTART_PHASE=""

# TEST_PHASE: Run single phase in isolation
# Default: Empty (run all phases)
# Set by: --test-phase N
# Effect: Only run phase N, exit after completion
TEST_PHASE=""

# SHOW_PHASE_INFO_NUM: Phase number to show detailed info about
# Default: Empty (don't show phase info)
# Set by: --show-phase-info N
# Effect: Display phase details and exit
SHOW_PHASE_INFO_NUM=""

# ============================================================================
# READONLY CONSTANTS - Safe Restart Points
# ============================================================================
# Safe restart phases are entry points where deployment can safely restart
# without leaving the system in an inconsistent state
#
# Why these phases are safe:
# - Phase 1: No system changes yet, just validation
# - Phase 3: Backups created, but no modifications applied
# - Phase 8: Deployment complete, just validation phase
#
# Unsafe restart points (not in this list):
# - Phase 6: Mid-deployment (system partially modified)
# - Phase 7: Tools partially installed
# - Phase 9: Finalization in progress
#
# Usage: --restart-from-safe-point finds last completed safe phase
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
# Libraries must be loaded in specific order due to dependencies.
# Think of this like a dependency graph:
# colors.sh → logging.sh → error-handling.sh → everything else
#
# Why order matters:
# - logging.sh uses colors.sh functions (print in color)
# - error-handling.sh uses logging.sh functions (log errors)
# - state-management.sh uses logging.sh functions (log state changes)
# - All other libs may use any of the above
#
# Loading process:
# 1. Check library file exists
# 2. Source (execute) the library file
# 3. Verify loading succeeded
# 4. Continue to next library
#
# Why fail on missing library:
# - Can't continue without core functions
# - Better to fail early with clear message
# - Prevents cryptic "command not found" errors later
#
# ============================================================================

load_libraries() {
    # ========================================================================
    # Library Load Order (CRITICAL - Do not reorder without testing!)
    # ========================================================================
    # This array defines the exact order libraries are loaded.
    # Dependencies must be loaded before dependents.
    #
    # Dependency chain:
    # 1. colors.sh → FIRST (no dependencies, provides color codes)
    # 2. logging.sh → Uses colors.sh for colored output
    # 3. error-handling.sh → Uses logging.sh to log errors
    # 4. state-management.sh → Uses logging.sh to log state changes
    # 5. user-interaction.sh → Uses logging.sh and colors.sh
    # 6. validation.sh → Uses logging.sh for validation messages
    # 7. retry.sh → Uses logging.sh for retry messages
    # 8. backup.sh → Uses logging.sh for backup messages
    # 9. gpu-detection.sh → Uses logging.sh for detection messages
    # 10. common.sh → LAST (aggregates functions from all above)
    #
    # local: Function-scoped variable (not global)
    # array syntax: libs=("item1" "item2" ...)
    local libs=(
        "colors.sh"              # Terminal color codes (MUST be first)
        "logging.sh"             # Logging functions (depends on colors)
        "error-handling.sh"      # Error management (depends on logging)
        "state-management.sh"    # State tracking (depends on logging)
        "user-interaction.sh"    # User prompts (depends on logging/colors)
        "validation.sh"          # Validation functions (depends on logging)
        "retry.sh"               # Retry logic (depends on logging)
        "backup.sh"              # Backup functions (depends on logging)
        "gpu-detection.sh"       # GPU detection (depends on logging)
        "common.sh"              # Common utilities (depends on all above)
    )

    echo "Loading libraries..."

    # ========================================================================
    # Load Each Library in Sequence
    # ========================================================================
    # for lib in "${libs[@]}": Iterate through library array
    # "${libs[@]}": Expand to all array elements (quoted preserves spaces)
    for lib in "${libs[@]}"; do
        # Construct full path to library file
        # $LIB_DIR/filename.sh
        local lib_path="$LIB_DIR/$lib"

        # --------------------------------------------------------------------
        # Check Library Exists
        # --------------------------------------------------------------------
        # [[ ! -f ... ]]: Check if file does NOT exist
        # -f: Test for regular file (not directory or symlink)
        # Why check: Better error message than "command not found"
        if [[ ! -f "$lib_path" ]]; then
            # Print to stderr (>&2): Error messages go to stderr
            # Why stderr: Separates errors from normal output
            # exit 1: Fatal error - can't continue without libraries
            echo "FATAL: Library not found: $lib_path" >&2
            exit 1
        fi

        # --------------------------------------------------------------------
        # Source (Load) Library
        # --------------------------------------------------------------------
        # source: Execute script in current shell context
        # Effect: Functions/variables from library become available
        # Alternative: . (dot) does same thing
        #
        # || { ... }: If source fails, execute error block
        # Why might it fail:
        # - Syntax error in library
        # - Permission denied
        # - Circular dependency
        source "$lib_path" || {
            echo "FATAL: Failed to load library: $lib" >&2
            exit 1
        }

        # Success feedback for user
        # ✓ (checkmark): Unicode U+2713 for visual confirmation
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
# This is the orchestrator - the central control function that manages
# the entire deployment lifecycle from start to finish.
#
# Execution order (critical):
# 1. Parse CLI arguments (before loading anything)
# 2. Handle early-exit commands (help, list phases, etc.)
# 3. Load libraries and configuration
# 4. Initialize logging and state management
# 5. Handle special modes (rollback, reset, test)
# 6. Determine starting phase (resume or fresh)
# 7. Execute phases sequentially
# 8. Handle errors and generate report
#
# Why this order:
# - Parse args first: Need to know what mode we're in
# - Early-exit commands: Don't load everything if just showing help
# - Load libs/config: Need functions before using them
# - Initialize systems: Logging and state tracking required
# - Determine start: Resume from failure or start fresh
# - Execute phases: Main deployment workflow
#
# Error handling:
# - set -E ensures error trap catches all failures
# - Each phase can fail independently
# - Failures offer retry/skip/rollback options
# - State tracking enables resume from failure
#
# ============================================================================

main() {
    # ========================================================================
    # Step 1: Parse Command-Line Arguments
    # ========================================================================
    # Why first: Need to know user's intent before loading anything
    # "$@": All arguments passed to script
    # Must happen before loading libraries (--help shouldn't load everything)
    #
    # What parse_arguments() does:
    # - Processes all flags (--dry-run, --debug, etc.)
    # - Sets global variables (DRY_RUN, ENABLE_DEBUG, etc.)
    # - Validates argument values
    # - Handles unknown arguments with error message
    parse_arguments "$@"

    # ========================================================================
    # Step 2: Enable Debug Mode (if requested)
    # ========================================================================
    # set -x: Print each command before executing
    # Effect: Shows detailed trace of script execution
    # Use: Troubleshooting, understanding script flow
    # Performance: Slightly slower due to extra output
    #
    # When to use: --debug flag for verbose troubleshooting
    # Output format: + command arguments (plus sign prefix)
    if [[ "$ENABLE_DEBUG" == true ]]; then
        set -x
    fi

    # ========================================================================
    # Step 3: Handle Help (early exit)
    # ========================================================================
    # Why early: Don't load libraries just to show help
    # print_usage: Displays help message (defined later in script)
    # exit 0: Success exit (help was shown successfully)
    if [[ "$SHOW_HELP" == true ]]; then
        print_usage
        exit 0
    fi

    # ========================================================================
    # Step 4: Handle List Phases (early exit with minimal loading)
    # ========================================================================
    # Why minimal loading: Only need colors and variables for phase list
    # Don't need: Full library suite, just basic display functions
    #
    # Minimal library loading:
    # - colors.sh: For colored output
    # - variables.sh: For STATE_FILE location
    # 2>/dev/null: Suppress errors if files missing
    # || true: Don't exit if source fails
    # grep -v "readonly variable": Filter out readonly warnings
    #
    # Why filter readonly warnings:
    # - variables.sh might be loaded multiple times in different contexts
    # - Bash warns when trying to re-declare readonly variables
    # - These warnings are harmless and just clutter output
    if [[ "$LIST_PHASES" == true ]]; then
        # Load minimal libraries for list_phases
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        list_phases
        exit 0
    fi

    # ========================================================================
    # Step 5: Handle Show Phase Info (early exit)
    # ========================================================================
    # Same minimal loading approach as list_phases
    # [[ -n "$VAR" ]]: Check if variable is non-empty
    # Why check: SHOW_PHASE_INFO_NUM is empty string by default
    if [[ -n "$SHOW_PHASE_INFO_NUM" ]]; then
        # Load minimal libraries for show_phase_info
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        show_phase_info "$SHOW_PHASE_INFO_NUM"
        exit 0
    fi

    # ========================================================================
    # Step 6: Load Core Components (full loading)
    # ========================================================================
    # Now that early-exit commands are handled, load everything
    # load_libraries: Source all library files in dependency order
    # load_configuration: Source config files (variables, defaults)
    #
    # Why now: All subsequent steps need full library suite
    # Order: Libraries before config (config might use library functions)
    load_libraries
    load_configuration

    # ========================================================================
    # Step 7: Enable Strict Undefined Variable Checking
    # ========================================================================
    # set -u: Error on undefined variable reference
    # Why now: Config loaded, all variables should be defined
    # Why not earlier: Config files might have optional variables
    #
    # Effect: ${UNDEFINED_VAR} will cause script to exit
    # Safety: Catches typos in variable names
    # Example: $PHAE instead of $PHASE would exit with error
    set -u

    # ========================================================================
    # Step 8: Handle Rollback Mode
    # ========================================================================
    # Rollback: Revert to previous NixOS generation
    # perform_rollback: Function that executes nixos-rebuild --rollback
    # exit $?: Exit with rollback function's exit code
    #
    # Why separate mode: Rollback is destructive, shouldn't mix with deployment
    # When to use: Deployment failed and broke system, need to undo
    if [[ "$ROLLBACK" == true ]]; then
        perform_rollback
        exit $?
    fi

    # ========================================================================
    # Step 9: Handle State Reset
    # ========================================================================
    # Reset state: Delete state.json and start fresh
    # reset_state: Function that removes state file
    # Use case: Want to re-run entire deployment from scratch
    #
    # Difference from --restart-phase 1:
    # - --restart-phase: Keeps state, marks phase incomplete
    # - --reset-state: Deletes state entirely, fresh start
    if [[ "$RESET_STATE" == true ]]; then
        reset_state
        print_success "State reset successfully"
        exit 0
    fi

    # ========================================================================
    # Step 10: Initialize Core Systems
    # ========================================================================
    # Three initializations required before deployment:
    # 1. Logging: File logging for audit trail
    # 2. Nix experimental features: Enable flakes and nix-command
    # 3. State management: Load or create state.json
    #
    # init_logging: Creates log file, redirects output
    # ensure_nix_experimental_features_env: Sets NIX_CONFIG env var
    # init_state: Loads existing state or creates new state file
    init_logging
    ensure_nix_experimental_features_env
    init_state

    # ========================================================================
    # Step 11: Print Deployment Header
    # ========================================================================
    # Visual header showing:
    # - Script version
    # - Mode (dry-run, debug, normal)
    # - Start time
    print_header

    # ========================================================================
    # Step 12: Handle Test Phase Mode (isolated testing)
    # ========================================================================
    # Test phase: Run single phase in isolation
    # Use case: Debugging specific phase, testing changes
    # [[ -n "$VAR" ]]: Check if variable non-empty
    #
    # Isolation means:
    # - Only run specified phase
    # - Don't run other phases
    # - Don't check dependencies
    # - Exit after completion
    if [[ -n "$TEST_PHASE" ]]; then
        log INFO "Testing phase $TEST_PHASE in isolation"
        print_section "Testing Phase $TEST_PHASE"
        execute_phase "$TEST_PHASE"
        exit $?  # Exit with phase's exit code
    fi

    # ========================================================================
    # Step 13: Determine Starting Phase
    # ========================================================================
    # Three scenarios:
    # 1. User specified: --start-from-phase N
    # 2. Resume mode: Auto-detect last incomplete phase
    # 3. Fresh start: Begin at phase 1
    #
    # local: Function-scoped variable
    # Default: 1 (first phase)
    local start_phase=1

    # Scenario 1: User explicitly specified starting phase
    if [[ -n "$START_FROM_PHASE" ]]; then
        start_phase=$START_FROM_PHASE
        log INFO "Starting from phase $start_phase (user specified)"

    # Scenario 2: Resume mode (default) or no explicit start phase
    # get_resume_phase: Checks state.json for last incomplete phase
    elif [[ "$RESUME" == true ]] || [[ -z "$START_FROM_PHASE" ]]; then
        start_phase=$(get_resume_phase)

        # If resuming from middle (not phase 1), inform user
        # -gt: Greater than
        if [[ $start_phase -gt 1 ]]; then
            log INFO "Resuming from phase $start_phase"
            print_info "Resuming from phase $start_phase"
        fi
    fi

    # ========================================================================
    # Step 14: Validate Starting Phase Number
    # ========================================================================
    # Validation checks:
    # 1. Is numeric: =~ ^[0-9]+$ (regex match)
    # 2. In range: 1-10 (we have exactly 10 phases)
    #
    # [[ ! ... ]]: NOT operator (invert condition)
    # =~ regex: Regex match operator
    # ^[0-9]+$: Start (^) one-or-more digits ([0-9]+) end ($)
    # -lt: Less than, -gt: Greater than
    #
    # Why validate: Invalid phase number would cause cryptic errors later
    if [[ ! "$start_phase" =~ ^[0-9]+$ ]] || [[ "$start_phase" -lt 1 ]] || [[ "$start_phase" -gt 10 ]]; then
        print_error "Invalid starting phase: $start_phase"
        exit 1
    fi

    # ========================================================================
    # Step 15: Create Rollback Point (if fresh start)
    # ========================================================================
    # Only create rollback point when:
    # - NOT in dry-run mode (can't rollback dry-run)
    # - Starting from phase 1 (fresh deployment)
    #
    # Why check phase 1: If resuming from phase 5, rollback point already exists
    # create_rollback_point: Records current NixOS generation
    # Timestamp: Labeled with current date/time for identification
    if [[ "$DRY_RUN" == false && $start_phase -eq 1 ]]; then
        log INFO "Creating rollback point"
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # ========================================================================
    # Step 16: Execute Phases Sequentially
    # ========================================================================
    # Main deployment loop - this is where the actual work happens
    #
    # Phase execution workflow:
    # for each phase from start_phase to 10:
    #   1. Check if should skip (--skip-phase)
    #   2. Execute phase script
    #   3. Handle failure (retry/skip/rollback)
    #   4. Continue to next phase
    #
    # seq: Generate sequence of numbers
    # Example: seq 3 10 → 3 4 5 6 7 8 9 10
    echo ""
    print_section "Starting 10-Phase Deployment Workflow"
    log INFO "Starting deployment from phase $start_phase"
    echo ""

    # Loop through phases from start_phase to 10
    for phase_num in $(seq $start_phase 10); do
        # --------------------------------------------------------------------
        # Check if Phase Should Be Skipped
        # --------------------------------------------------------------------
        # should_skip_phase: Checks SKIP_PHASES array
        # User can skip with: --skip-phase N
        # Use case: Skip non-critical phase (like health check)
        if should_skip_phase "$phase_num"; then
            log INFO "Skipping phase $phase_num (user requested)"
            print_info "Skipping Phase $phase_num (--skip-phase)"
            continue  # Skip to next iteration of loop
        fi

        # --------------------------------------------------------------------
        # Execute Phase
        # --------------------------------------------------------------------
        # execute_phase: Runs phase script from phases/ directory
        # Returns: 0 on success, non-zero on failure
        # ! operator: Invert return code (true if phase failed)
        #
        # Error handling:
        # - If phase succeeds: Continue to next phase
        # - If phase fails: handle_phase_failure offers options
        #   - Retry: Re-run failed phase
        #   - Skip: Continue to next phase (risky)
        #   - Rollback: Revert system to pre-deployment state
        #   - Exit: Abort deployment
        if ! execute_phase "$phase_num"; then
            # Phase failed - let user decide what to do
            # || exit 1: If user chooses exit, abort deployment
            handle_phase_failure "$phase_num" || exit 1
        fi

        # Blank line between phases for readability
        echo ""
    done

    # ========================================================================
    # Step 17: Deployment Success!
    # ========================================================================
    # All phases completed successfully if we reach here
    # Log success and display final message
    log INFO "All phases completed successfully"
    echo ""
    echo "============================================"
    print_success "Deployment completed successfully!"
    echo "============================================"
    echo ""
    echo "Log file: $LOG_FILE"
    echo ""

    # Return success
    # 0: Success exit code
    # Bash convention: 0 = success, non-zero = failure
    return 0
}

# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

# Run main function
main "$@"
