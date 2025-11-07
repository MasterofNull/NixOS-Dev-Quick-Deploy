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

# Bash strict mode - configure shell behavior for safer execution
set -o pipefail  # Catch errors in pipelines (e.g., "cmd1 | cmd2" fails if cmd1 fails)
    set -E           # ERR trap inherited by functions (error handling propagates to called functions)

# ============================================================================
# READONLY CONSTANTS
# ============================================================================

readonly SCRIPT_VERSION="4.0.0"  # Current version of deployment framework
    readonly BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # Get absolute path of script directory
readonly LIB_DIR="$BOOTSTRAP_SCRIPT_DIR/lib"  # Shared library functions location
    readonly CONFIG_DIR="$BOOTSTRAP_SCRIPT_DIR/config"  # Configuration files location
readonly PHASES_DIR="$BOOTSTRAP_SCRIPT_DIR/phases"  # Phase script implementations location

# Export SCRIPT_DIR for compatibility with libraries that expect it
readonly SCRIPT_DIR="$BOOTSTRAP_SCRIPT_DIR"  # Alias for backwards compatibility
    export SCRIPT_DIR  # Make available to all child processes and sourced files

# ============================================================================
# EARLY ENVIRONMENT SETUP
# ============================================================================
# Ensure critical environment variables are set before any library loading.
# USER might not be set in some environments (e.g., cron, systemd).
USER="${USER:-$(whoami 2>/dev/null || id -un 2>/dev/null || echo 'unknown')}"  # Try multiple methods to get username
    export USER  # Make USER available to all child processes

# EUID is a bash built-in, but export it for consistency
export EUID  # Export effective user ID (0 = root, >0 = regular user)

# ============================================================================
# EARLY LOGGING CONFIGURATION
# ============================================================================
# These variables must be defined BEFORE loading libraries (especially logging.sh)
# because logging.sh uses them immediately when init_logging() is called.

# Create log directory path in user cache
readonly LOG_DIR="${HOME}/.cache/nixos-quick-deploy/logs"  # Store logs in XDG cache directory
    # Create unique log file with timestamp
    readonly LOG_FILE="${LOG_DIR}/deploy-$(date +%Y%m%d_%H%M%S).log"  # Format: deploy-20250107_143022.log
# Set default log level (can be overridden by CLI args)
LOG_LEVEL="${LOG_LEVEL:-INFO}"  # Options: DEBUG, INFO, WARNING, ERROR
    # Debug flag (can be overridden by CLI args)
    ENABLE_DEBUG=false  # When true, enables bash -x tracing

# Export critical variables so they're available to all sourced files
export SCRIPT_VERSION  # Version info for logging
    export LOG_DIR  # Log directory path
export LOG_FILE  # Current log file path
    export LOG_LEVEL  # Logging verbosity level

# ============================================================================
# GLOBAL VARIABLES - CLI Flags
# ============================================================================
# These flags are set by command-line argument parsing and control deployment behavior.

DRY_RUN=false  # Preview changes without applying them
    FORCE_UPDATE=false  # Force recreation of configuration files even if they exist
# ENABLE_DEBUG defined above in EARLY LOGGING CONFIGURATION
ROLLBACK=false  # Rollback to previous NixOS generation
    RESET_STATE=false  # Clear state file for fresh deployment start
SKIP_HEALTH_CHECK=false  # Skip final system health validation
    SHOW_HELP=false  # Display usage help and exit
SHOW_VERSION=false  # Display version information and exit
    QUIET_MODE=false  # Show only warnings and errors
VERBOSE_MODE=false  # Show detailed debug output
    LIST_PHASES=false  # List all phases with status and exit
RESUME=true  # Resume from last completed phase (default behavior)
    RESTART_FAILED=false  # Restart the failed phase from beginning
RESTART_FROM_SAFE_POINT=false  # Restart from last safe entry point (phases 1, 3, or 8)
    ZSWAP_CONFIGURATION_OVERRIDE_REQUEST=""  # User request for zswap config: "enable", "disable", or "auto"

# Phase control - fine-grained execution control
declare -a SKIP_PHASES=()  # Array of phase numbers to skip during execution
    START_FROM_PHASE=""  # Start execution from this phase number
RESTART_PHASE=""  # Restart this specific phase (ignores completion status)
    TEST_PHASE=""  # Run only this phase in isolation
SHOW_PHASE_INFO_NUM=""  # Show detailed information about this phase number

# Safe restart phases (can safely restart from these without dependency issues)
readonly SAFE_RESTART_PHASES=(1 3 8)  # Phase 1=init, 3=config-gen, 8=finalization

# ============================================================================
# PHASE NAME MAPPING
# ============================================================================
# These functions provide metadata about each phase for display and validation.

get_phase_name() {
    # Return the canonical kebab-case name for a phase number
    case $1 in
        1) echo "system-initialization" ;;  # Initial validation and setup
        2) echo "system-backup" ;;  # Backup existing configs
        3) echo "configuration-generation" ;;  # Generate Nix configs from templates
        4) echo "pre-deployment-validation" ;;  # Validate generated configs
        5) echo "declarative-deployment" ;;  # Apply NixOS and Home Manager configs
        6) echo "additional-tooling" ;;  # Install npm/flatpak packages
        7) echo "post-deployment-validation" ;;  # Verify deployment success
        8) echo "finalization-and-report" ;;  # Cleanup and generate report
        *) echo "unknown" ;;  # Invalid phase number
    esac
}

get_phase_description() {
    # Return a human-readable description for a phase number
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
    # Return comma-separated list of phase numbers that must complete before this phase
    case $1 in
        1) echo "" ;;  # No dependencies - entry point
        2) echo "1" ;;  # Requires initialization
        3) echo "1,2" ;;  # Requires init and backup
        4) echo "1,2,3" ;;  # Requires config generation
        5) echo "1,2,3,4" ;;  # Requires validation before deployment
        6) echo "1,2,3,4,5" ;;  # Requires declarative deployment
        7) echo "1,2,3,4,5,6" ;;  # Requires all installations
        8) echo "1,2,3,4,5,6,7" ;;  # Requires everything before finalization
        *) echo "" ;;  # Unknown phase has no dependencies
    esac
}

# ============================================================================
# LIBRARY LOADING
# ============================================================================
# Load all shared libraries in dependency order. Libraries provide reusable functions
# for logging, error handling, GPU detection, package management, and more.

load_libraries() {
    # Array of library files to load (order matters for dependencies)
    local libs=(
        "colors.sh"  # Terminal color codes (must load first)
        "logging.sh"  # Logging functions (depends on colors)
        "error-handling.sh"  # Error trap and cleanup functions
        "state-management.sh"  # Phase completion tracking
        "user-interaction.sh"  # Prompts and confirmations
        "validation.sh"  # System validation checks
        "retry.sh"  # Retry logic for flaky operations
        "backup.sh"  # Backup and restore functions
        "gpu-detection.sh"  # Hardware detection (NVIDIA/AMD/Intel)
        "python.sh"  # Python package management
        "nixos.sh"  # NixOS-specific operations
        "packages.sh"  # Package installation helpers
        "home-manager.sh"  # Home Manager integration
        "user.sh"  # User account operations
        "config.sh"  # Configuration file generation
        "tools.sh"  # External tool installation
        "finalization.sh"  # Cleanup and finalization
        "reporting.sh"  # Deployment report generation
        "common.sh"  # Common utility functions
    )

    echo "Loading libraries..."

    for lib in "${libs[@]}"; do
        local lib_path="$LIB_DIR/$lib"  # Build full path to library

        if [[ ! -f "$lib_path" ]]; then  # Verify library file exists
            echo "FATAL: Library not found: $lib_path" >&2
                exit 1
        fi

        source "$lib_path" || {  # Source library into current shell
            echo "FATAL: Failed to load library: $lib" >&2
                exit 1
        }

        echo "  ✓ Loaded: $lib"  # Confirm successful load
    done
    echo ""
}

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================
# Load global configuration files that define deployment parameters and defaults.

load_configuration() {
    # Array of config files to load
    local configs=(
        "variables.sh"  # Global variables (paths, URLs, package lists)
        "defaults.sh"  # Default values for configuration generation
    )

    echo "Loading configuration..."

    for config in "${configs[@]}"; do
        local config_path="$CONFIG_DIR/$config"  # Build full path to config file
            if [[ ! -f "$config_path" ]]; then  # Verify config file exists
            echo "FATAL: Configuration not found: $config_path" >&2
                exit 1
        fi

        # Source config files
        # Note: set -u is not yet enabled at this point, so undefined variables
        # won't cause errors. Critical variables like LOG_DIR, LOG_FILE, and
        # SCRIPT_VERSION are already defined in main script before this runs.
        if source "$config_path" 2>/dev/null; then  # Source config into current shell
            echo "  ✓ Loaded: $config"  # Confirm successful load
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
        --enable-zswap          Force-enable zswap-backed hibernation setup (persists)
        --disable-zswap         Force-disable zswap-backed hibernation setup (persists)
        --zswap-auto            Return to automatic zswap detection (clears override)

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
    # Parse command-line arguments and set global flags
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)  # Display usage help
                SHOW_HELP=true
                    shift  # Consume this argument
                ;;
            -v|--version)  # Display version info
                SHOW_VERSION=true
                    shift
                ;;
            -q|--quiet)  # Enable quiet mode (warnings/errors only)
                QUIET_MODE=true
                    shift
                ;;
            --verbose)  # Enable verbose mode (detailed output)
                VERBOSE_MODE=true
                    shift
                ;;
            -d|--debug)  # Enable debug tracing (bash -x)
                ENABLE_DEBUG=true
                    shift
                ;;
            -f|--force-update)  # Force recreation of config files
                FORCE_UPDATE=true
                    shift
                ;;
            --dry-run)  # Preview changes without applying
                DRY_RUN=true
                    shift
                ;;
            --rollback)  # Rollback to previous generation
                ROLLBACK=true
                    shift
                ;;
            --reset-state)  # Clear state for fresh start
                RESET_STATE=true
                    shift
                ;;
            --skip-health-check)  # Skip final health validation
                SKIP_HEALTH_CHECK=true
                    shift
                ;;
            --enable-zswap)  # Force-enable zswap configuration
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="enable"
                    shift
                ;;
            --disable-zswap)  # Force-disable zswap configuration
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="disable"
                    shift
                ;;
            --zswap-auto)  # Return to automatic zswap detection
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="auto"
                    shift
                ;;
            --skip-phase)  # Skip specific phase number
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then  # Validate arg exists and isn't a flag
                    echo "ERROR: --skip-phase requires a phase number" >&2
                        exit 1
                fi
                SKIP_PHASES+=("$2")  # Add to skip list
                    shift 2  # Consume flag and value
                ;;
            --start-from-phase)  # Start from specific phase
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --start-from-phase requires a phase number" >&2
                        exit 1
                fi
                START_FROM_PHASE="$2"
                    shift 2
                ;;
            --restart-phase)  # Restart specific phase from beginning
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --restart-phase requires a phase number" >&2
                        exit 1
                fi
                RESTART_PHASE="$2"  # Phase to restart
                    START_FROM_PHASE="$2"  # Also set as starting point
                shift 2
                ;;
            --test-phase)  # Test specific phase in isolation
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --test-phase requires a phase number" >&2
                        exit 1
                fi
                TEST_PHASE="$2"
                    shift 2
                ;;
            --list-phases)  # List all phases with status
                LIST_PHASES=true
                    shift
                ;;
            --show-phase-info)  # Show detailed phase information
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --show-phase-info requires a phase number" >&2
                        exit 1
                fi
                SHOW_PHASE_INFO_NUM="$2"
                    shift 2
                ;;
            --resume)  # Resume from last completed phase
                RESUME=true
                    shift
                ;;
            --restart-failed)  # Restart failed phase from beginning
                RESTART_FAILED=true
                    shift
                ;;
            --restart-from-safe-point)  # Restart from last safe entry point
                RESTART_FROM_SAFE_POINT=true
                    shift
                ;;
            *)  # Unknown argument
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
    # Display a formatted list of all phases with their current status
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy - Phase Overview"
    echo "============================================"
    echo ""

    # Load libraries minimally to get state
    source "$LIB_DIR/colors.sh" 2>/dev/null || true  # Load colors for formatting
        source "$CONFIG_DIR/variables.sh" 2>/dev/null || true  # Load STATE_FILE location

    for phase_num in {1..8}; do  # Iterate through all 8 phases
        local phase_name=$(get_phase_name "$phase_num")  # Get phase name
            local phase_desc=$(get_phase_description "$phase_num")  # Get phase description
        local status="PENDING"  # Default status

        # Check if state file exists and get status
        if [[ -f "${STATE_FILE:-}" ]]; then  # If state file exists
            # Check if this phase is marked complete in state
            if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                status="COMPLETED"  # Phase has been completed
            fi
        fi

        printf "Phase %2d: %-30s [%s]\n" "$phase_num" "$phase_name" "$status"  # Print phase info
            printf "          %s\n\n" "$phase_desc"  # Print description indented
    done

    echo "============================================"
    echo ""
}

show_phase_info() {
    # Display detailed information about a specific phase
    local phase_num="$1"  # Phase number to display

    # Validate phase number is in range 1-8
    if [[ ! "$phase_num" =~ ^[0-9]+$ ]] || [[ "$phase_num" -lt 1 ]] || [[ "$phase_num" -gt 8 ]]; then
        echo "ERROR: Invalid phase number. Must be 1-8" >&2
            exit 1
    fi

    # Get phase metadata
    local phase_name=$(get_phase_name "$phase_num")  # Kebab-case name
        local phase_desc=$(get_phase_description "$phase_num")  # Human-readable description
    local phase_deps=$(get_phase_dependencies "$phase_num")  # Comma-separated dependency list
        local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"  # Full path to phase script

    # Print formatted phase information
    echo ""
    echo "============================================"
    echo "  Phase $phase_num: $phase_name"
    echo "============================================"
    echo ""
    echo "Description:"
        echo "  $phase_desc"  # Indented description
    echo ""
    echo "Script Location:"
        echo "  $phase_script"  # Indented path
    echo ""

    # Display dependencies (if any)
    if [[ -n "$phase_deps" ]]; then
        echo "Dependencies:"
            echo "  Requires phases: $phase_deps"  # List required phases
    else
        echo "Dependencies:"
            echo "  None (entry point phase)"  # No dependencies
    fi
    echo ""

    # Check if phase is safe restart point
    if [[ " ${SAFE_RESTART_PHASES[@]} " =~ " ${phase_num} " ]]; then  # Check if in safe restart list
        echo "Safe Restart Point: YES"  # Can safely restart from this phase
    else
        echo "Safe Restart Point: NO (requires dependency validation)"  # Must validate deps before restart
    fi
    echo ""

    # Check current status from state file
    source "$CONFIG_DIR/variables.sh" 2>/dev/null || true  # Load STATE_FILE path
    if [[ -f "${STATE_FILE:-}" ]]; then  # If state file exists
        # Check if phase is marked complete
        if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            echo "Current Status: COMPLETED"  # Phase has been completed
        else
            echo "Current Status: PENDING"  # Phase not yet completed
        fi
    else
        echo "Current Status: PENDING (no state file)"  # No state tracking yet
    fi
    echo ""
    echo "============================================"
    echo ""
}

# ============================================================================
# PHASE CONTROL
# ============================================================================
# Functions for managing phase execution: skipping, resuming, and dependency validation.

should_skip_phase() {
    # Check if a phase should be skipped based on user request
    local phase_num="$1"  # Phase number to check
    for skip_phase in "${SKIP_PHASES[@]}"; do  # Iterate through skip list
        if [[ "$skip_phase" == "$phase_num" ]]; then  # Match found
            return 0  # True - should skip
        fi
    done
    return 1  # False - don't skip
}

get_resume_phase() {
    # Determine which phase to start from based on state and user preferences

    # If restart-from-safe-point is set, find last safe point
    if [[ "$RESTART_FROM_SAFE_POINT" == true ]]; then
        local last_safe_phase=1  # Default to phase 1
            if [[ -f "$STATE_FILE" ]]; then  # If state file exists
            # Find the last completed safe restart phase
            for safe_phase in "${SAFE_RESTART_PHASES[@]}"; do  # Check phases 1, 3, 8
                # Check if this safe phase is completed
                if jq -e --arg step "phase-$(printf '%02d' $safe_phase)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                    last_safe_phase=$safe_phase  # Update to this safe phase
                fi
            done
        fi
        echo "$last_safe_phase"  # Return the safe phase number
            return
    fi

    # Otherwise, find the next incomplete phase
    if [[ ! -f "$STATE_FILE" ]]; then  # No state file exists
        echo "1"  # Start from beginning
            return
    fi

    # Find first incomplete phase
    for phase_num in {1..8}; do  # Check each phase in order
        # Check if phase is NOT marked complete
        if ! jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            echo "$phase_num"  # Return first incomplete phase
                return
        fi
    done

    # All phases complete
    echo "1"  # Return to phase 1 (no incomplete phases)
}

validate_phase_dependencies() {
    # Verify that all required dependency phases have been completed
    local phase_num="$1"  # Phase to validate
        local deps=$(get_phase_dependencies "$phase_num")  # Get comma-separated dependency list

    # No dependencies means this is an entry point phase
    if [[ -z "$deps" ]]; then
        return 0  # Always valid
    fi

    # State file must exist to validate dependencies
    if [[ ! -f "$STATE_FILE" ]]; then
        log ERROR "Cannot validate dependencies: state file not found"
            return 1  # Cannot validate without state
    fi

    # Check each dependency
    local missing_deps=()  # Track missing dependencies
        IFS=',' read -ra DEP_ARRAY <<< "$deps"  # Split comma-separated list into array
    for dep in "${DEP_ARRAY[@]}"; do  # Check each required dependency
        # Check if dependency phase is marked complete in state
        if ! jq -e --arg step "phase-$(printf '%02d' $dep)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            missing_deps+=("$dep")  # Add to missing list
        fi
    done

    # Report missing dependencies
    if [[ ${#missing_deps[@]} -gt 0 ]]; then  # If any dependencies are missing
        log ERROR "Phase $phase_num has missing dependencies: ${missing_deps[*]}"
            print_error "Cannot execute phase $phase_num: missing dependencies ${missing_deps[*]}"
        return 1  # Validation failed
    fi

    return 0  # All dependencies satisfied
}

execute_phase() {
    # Execute a single phase: validate, run script, mark complete
    local phase_num="$1"  # Phase number to execute
        local phase_name=$(get_phase_name "$phase_num")  # Get phase name
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"  # Build script path
        local phase_step="phase-$(printf '%02d' $phase_num)"  # Format for state tracking

    # Check if phase script exists
    if [[ ! -f "$phase_script" ]]; then  # Script file not found
        log ERROR "Phase script not found: $phase_script"
            print_error "Phase $phase_num script not found"
        return 1
    fi

    # Check if already completed (skip if not restart)
    if [[ -z "$RESTART_PHASE" ]] && is_step_complete "$phase_step"; then  # Phase complete and not restarting
        log INFO "Phase $phase_num already completed (skipping)"
            print_info "Phase $phase_num: $phase_name [ALREADY COMPLETED]"
        return 0
    fi

    # Validate dependencies
    if ! validate_phase_dependencies "$phase_num"; then  # Dependency check failed
        return 1  # Cannot proceed without dependencies
    fi

    # Execute phase
    print_section "Phase $phase_num: $phase_name"  # Print section header
        log INFO "Executing phase $phase_num: $phase_name"  # Log execution start

    # Handle dry-run mode
    if [[ "$DRY_RUN" == true ]]; then  # Preview mode enabled
        print_info "[DRY RUN] Would execute: $phase_script"  # Show what would run
            log INFO "[DRY RUN] Phase $phase_num skipped"
        return 0
    fi

    # Source and execute the phase script
    if source "$phase_script"; then  # Execute phase script by sourcing it
        mark_step_complete "$phase_step"  # Mark phase as complete in state
            log INFO "Phase $phase_num completed successfully"
        print_success "Phase $phase_num completed"  # Display success message
            return 0  # Success
    else
        local exit_code=$?  # Capture exit code
            log ERROR "Phase $phase_num failed with exit code $exit_code"
        return $exit_code  # Propagate failure code
    fi
}

handle_phase_failure() {
    # Interactive failure handling - let user decide how to proceed after phase failure
    local phase_num="$1"  # Failed phase number
        local phase_name=$(get_phase_name "$phase_num")  # Get phase name for display

    # Display failure message
    echo ""
    print_error "Phase $phase_num ($phase_name) failed!"
    echo ""

    # In dry-run mode, continue despite failures
    if [[ "$DRY_RUN" == true ]]; then
        log INFO "Dry run mode: continuing despite failure"
            return 0  # Don't stop in preview mode
    fi

    # Interactive failure handling - present options to user
    echo "What would you like to do?"
    echo "  1) Retry this phase"  # Try again immediately
        echo "  2) Skip and continue"  # Ignore failure and proceed
    echo "  3) Rollback"  # Revert to previous state
        echo "  4) Exit"  # Abort deployment
    echo ""
    read -p "Choice [1-4]: " choice  # Get user input

    case "$choice" in
        1)  # Retry the failed phase
            log INFO "User chose to retry phase $phase_num"
                execute_phase "$phase_num"  # Re-execute phase
            return $?  # Return result of retry
            ;;
        2)  # Skip this phase and continue
            log WARNING "User chose to skip phase $phase_num"
                print_warning "Skipping phase $phase_num"
            return 0  # Return success to continue workflow
            ;;
        3)  # Rollback to previous generation
            log INFO "User chose to rollback"
                ROLLBACK_IN_PROGRESS=true  # Set rollback flag
            export ROLLBACK_IN_PROGRESS  # Make flag available to cleanup handlers
                perform_rollback  # Execute rollback procedure
            exit $?  # Exit with rollback result
            ;;
        4|*)  # Exit deployment (default for invalid input)
            log INFO "User chose to exit"
                exit 1  # Terminate with failure code
            ;;
    esac
}

# ============================================================================
# ROLLBACK
# ============================================================================
# Restore system to the NixOS generation that existed before deployment started.

perform_rollback() {
    # Rollback to the previous NixOS generation using rollback info file
    log INFO "Performing rollback"
        print_section "Rolling back to previous state"

    # Verify rollback info file exists
    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then  # No rollback info saved
        print_error "No rollback information found"
            log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1
    fi

    # Read rollback generation from file
    local rollback_gen=$(cat "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "")  # Get generation number
        if [[ -z "$rollback_gen" ]]; then  # File empty or read failed
        print_error "Invalid rollback information"
            return 1
    fi

    # Display rollback target
    print_info "Rolling back to generation: $rollback_gen"
        log INFO "Rolling back to generation: $rollback_gen"

    # Handle dry-run mode
    if [[ "$DRY_RUN" == true ]]; then  # Preview mode
        print_info "[DRY RUN] Would execute: sudo nixos-rebuild switch --rollback"
            return 0  # Don't actually rollback in dry-run
    fi

    # Execute rollback
    if sudo nixos-rebuild switch --rollback; then  # Switch to previous generation
        print_success "Rollback completed successfully"
            log INFO "Rollback completed successfully"
        return 0  # Success
    else
        print_error "Rollback failed"
            log ERROR "Rollback failed"
        return 1  # Failure
    fi
}

# ============================================================================
# MAIN INITIALIZATION
# ============================================================================
# Functions called during main() initialization before phase execution.

print_header() {
    # Display deployment banner with version and mode information
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy v$SCRIPT_VERSION"  # Show current version
        echo "  8-Phase Modular Deployment"  # Architecture description
    echo "============================================"
    echo ""

    # Display special mode indicators
    if [[ "$DRY_RUN" == true ]]; then  # Preview mode active
        echo "  MODE: DRY RUN (no changes will be made)"
            echo ""
    fi

    if [[ "$ENABLE_DEBUG" == true ]]; then  # Debug tracing active
        echo "  DEBUG: Enabled"
            echo ""
    fi
}

ensure_nix_experimental_features_env() {
    # Enable Nix experimental features required for flakes and modern Nix commands
    export NIX_CONFIG="experimental-features = nix-command flakes"  # Enable flakes globally for this process
}

# ============================================================================
# MAIN FUNCTION
# ============================================================================
# Main entry point that orchestrates the entire deployment workflow.

main() {
    # Parse command-line arguments and set global flags
    parse_arguments "$@"  # Process CLI args into global variables

    # Enable debug mode if requested (bash -x tracing)
    if [[ "$ENABLE_DEBUG" == true ]]; then
        set -x  # Print each command before execution
    fi

    # Configure logging level based on verbosity flags
    if [[ "$QUIET_MODE" == true ]]; then  # Minimal output
        export LOG_LEVEL="WARNING"  # Only warnings and errors
            elif [[ "$VERBOSE_MODE" == true ]]; then  # Detailed output
        export LOG_LEVEL="DEBUG"  # All debug messages
    else  # Normal mode
        export LOG_LEVEL="INFO"  # Standard informational messages
    fi

    # Handle early-exit commands (info display, no deployment)
    if [[ "$SHOW_HELP" == true ]]; then  # User requested help
        print_usage  # Display usage information
            exit 0  # Exit successfully
    fi

    if [[ "$SHOW_VERSION" == true ]]; then  # User requested version
        print_version  # Display version and component info
            exit 0
    fi

    if [[ "$LIST_PHASES" == true ]]; then  # User requested phase list
        source "$LIB_DIR/colors.sh" 2>/dev/null || true  # Load colors for display
            source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true  # Load STATE_FILE path
        list_phases  # Display all phases with status
            exit 0
    fi

    if [[ -n "$SHOW_PHASE_INFO_NUM" ]]; then  # User requested specific phase info
        source "$LIB_DIR/colors.sh" 2>/dev/null || true  # Load colors
            source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true  # Load variables
        show_phase_info "$SHOW_PHASE_INFO_NUM"  # Display phase details
            exit 0
    fi

    # Load core components (libraries and configuration)
    load_libraries  # Source all library files
        load_configuration  # Source all config files

    # Handle zswap configuration override request (if provided via CLI)
    if [[ -n "$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST" ]]; then  # User provided zswap override
        case "$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST" in
            enable|disable|auto)  # Valid override values
                ZSWAP_CONFIGURATION_OVERRIDE="$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST"  # Set override
                    export ZSWAP_CONFIGURATION_OVERRIDE  # Make available to all phases
                # Persist override to file if function available
                if declare -F persist_zswap_configuration_override >/dev/null 2>&1; then  # Function exists
                    persist_zswap_configuration_override "$ZSWAP_CONFIGURATION_OVERRIDE" || true  # Save preference
                fi
                # Display confirmation message
                case "$ZSWAP_CONFIGURATION_OVERRIDE" in
                    enable)  # Force-enable zswap
                        print_info "Zswap override set to ENABLE; prompts will appear even if detection fails."
                            ;;
                    disable)  # Force-disable zswap
                        print_info "Zswap override set to DISABLE; swap-backed hibernation will be skipped."
                            ;;
                    auto)  # Return to automatic detection
                        print_info "Zswap override cleared; automatic detection restored."
                            ;;
                esac
                ;;
        esac
    fi

    # Enable strict undefined variable checking (after all variables are set)
    set -u  # Exit if undefined variable is referenced

    # Handle rollback mode (revert to previous generation)
    if [[ "$ROLLBACK" == true ]]; then  # User requested rollback
        ROLLBACK_IN_PROGRESS=true  # Set rollback flag
            export ROLLBACK_IN_PROGRESS  # Make available to cleanup handlers
        perform_rollback  # Execute rollback procedure
            exit $?  # Exit with rollback result
    fi

    # Handle state reset (clear for fresh start)
    if [[ "$RESET_STATE" == true ]]; then  # User requested state reset
        reset_state  # Clear state file
            print_success "State reset successfully"
        exit 0  # Exit after reset
    fi

    # Initialize core systems
    init_logging  # Set up logging to file and console
        ensure_nix_experimental_features_env  # Enable Nix flakes
    init_state  # Initialize or load state tracking

    # Print deployment header
    print_header  # Display banner with version and mode info

    # Handle test phase mode (run single phase in isolation)
    if [[ -n "$TEST_PHASE" ]]; then  # User requested single phase test
        log INFO "Testing phase $TEST_PHASE in isolation"
            print_section "Testing Phase $TEST_PHASE"
        execute_phase "$TEST_PHASE"  # Run only this phase
            exit $?  # Exit with phase result
    fi

    # Determine starting phase (user-specified, resume, or from beginning)
    local start_phase=1  # Default to phase 1

    if [[ -n "$START_FROM_PHASE" ]]; then  # User specified starting phase
        start_phase=$START_FROM_PHASE  # Use user's choice
            log INFO "Starting from phase $start_phase (user specified)"
    elif [[ "$RESUME" == true ]] || [[ -z "$START_FROM_PHASE" ]]; then  # Resume mode or no override
        start_phase=$(get_resume_phase)  # Find next incomplete phase from state
            if [[ $start_phase -gt 1 ]]; then  # Not starting from beginning
            log INFO "Resuming from phase $start_phase"
                print_info "Resuming from phase $start_phase"
        fi
    fi

    # Validate starting phase number is in valid range
    if [[ ! "$start_phase" =~ ^[0-9]+$ ]] || [[ "$start_phase" -lt 1 ]] || [[ "$start_phase" -gt 8 ]]; then
        print_error "Invalid starting phase: $start_phase"  # Invalid phase number
            exit 1
    fi

    # Create rollback point (save current generation for potential rollback)
    if [[ "$DRY_RUN" == false && $start_phase -eq 1 ]]; then  # Not dry-run and starting from beginning
        log INFO "Creating rollback point"
            create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"  # Save generation with timestamp
    fi

    # Execute phases sequentially from start_phase to phase 8
    echo ""
    print_section "Starting 8-Phase Deployment Workflow"  # Display workflow header
        log INFO "Starting deployment from phase $start_phase"
    echo ""

    for phase_num in $(seq $start_phase 8); do  # Loop through phases
        # Check if phase should be skipped
        if should_skip_phase "$phase_num"; then  # User requested skip via --skip-phase
            log INFO "Skipping phase $phase_num (user requested)"
                print_info "Skipping Phase $phase_num (--skip-phase)"
            continue  # Skip to next phase
        fi

        # Execute phase and handle failure
        if ! execute_phase "$phase_num"; then  # Phase execution failed
            handle_phase_failure "$phase_num" || exit 1  # Interactive failure handling or exit
        fi

        echo ""  # Blank line between phases
    done

    # Deployment success - all phases completed
    log INFO "All phases completed successfully"
        echo ""

    # Final system health check
    local health_exit=0  # Track health check result
        if [[ "$SKIP_HEALTH_CHECK" != true ]]; then  # Health check not skipped
        local health_script="$SCRIPT_DIR/scripts/system-health-check.sh"  # Path to health check script
            if [[ -x "$health_script" ]]; then  # Script exists and is executable
            print_section "Final System Health Check"
                log INFO "Running final system health check via $health_script"
            echo ""
                if "$health_script" --detailed; then  # Run health check with detailed output
                print_success "System health check passed"  # All checks passed
                    echo ""
            else
                health_exit=$?  # Capture failure code
                    print_warning "System health check reported issues. Review the output above and rerun with --fix if needed."
                echo ""
            fi
        else  # Health check script not found
            log WARNING "Health check script missing at $health_script"
                print_warning "Health check script not found at $health_script"
            print_info "Run git pull to restore scripts or download manually."
                echo ""
        fi
    else  # Health check explicitly skipped
        log INFO "Skipping final health check (flag)"
            print_info "Skipping final health check (--skip-health-check)"
    fi

    # Print final status summary
    echo "============================================"
    if [[ $health_exit -eq 0 ]]; then  # Health check passed or skipped
        print_success "Deployment completed successfully!"  # Everything succeeded
    else  # Health check reported issues
        print_warning "Deployment completed with follow-up actions required."
            print_info "Review the health check summary above. You can rerun fixes with: $health_script --fix"
    fi
    echo "============================================"
    echo ""
    echo "Log file: $LOG_FILE"  # Show where logs are stored
        echo ""

    return $health_exit  # Return health check result (0 = success, non-zero = issues)
}

# ============================================================================
# SCRIPT EXECUTION
# ============================================================================
# Entry point: call main() with all command-line arguments passed to script.

# Run main function with all CLI arguments
main "$@"  # Execute main deployment orchestration with user-provided arguments
