#!/usr/bin/env bash

# =============================================================================
# Main Script Decomposition Helper
# Purpose: Demonstrate how the main function in nixos-quick-deploy.sh can be decomposed
# Version: 1.0.0
#
# This script demonstrates the refactoring approach for Phase 17.1:
# Decomposing the main() function in nixos-quick-deploy.sh to be under 50 lines
# =============================================================================

# Function to handle early exit commands (help, version, list phases, etc.)
handle_early_exit_commands() {
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
}

# Function to setup environment and logging
setup_environment() {
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

    # Initialize logging
    init_logging

    # Load required libraries
    load_libraries

    # Validate runtime paths
    if ! validate_runtime_paths; then
        print_error "Runtime path validation failed"
        exit "${ERR_PATH_VALIDATION:-20}"
    fi
}

# Function to handle special modes (rollback, reset state, etc.)
handle_special_modes() {
    # Handle rollback mode
    if [[ "$ROLLBACK" == true ]]; then
        ROLLBACK_IN_PROGRESS=true
        export ROLLBACK_IN_PROGRESS
        perform_rollback
        exit $?
    fi

    # Handle state reset
    if [[ "$RESET_STATE" == true ]]; then
        reset_state
        print_success "State reset successfully"
        exit 0
    fi

    # Handle resume validation
    if [[ "$RESUME" == true ]]; then
        print_info "Validating resume state..."
        if ! validate_resume_state "$VALIDATE_STATE"; then
            exit "${ERR_STATE_INVALID:-31}"
        fi
    fi
}

# Function to acquire deployment lock
acquire_deployment_lock() {
    local lock_file="${CACHE_DIR}/deploy.lock"
    local lock_fd=200
    mkdir -p "$CACHE_DIR" >/dev/null 2>&1 || true

    if command -v flock >/dev/null 2>&1; then
        local lock_acquired=false
        local lock_start_time
        local lock_warned=false
        local lock_timeout_sec="${DEPLOY_LOCK_TIMEOUT_SEC:-60}"
        lock_start_time=$(date +%s)
        
        while true; do
            exec 200>"${lock_file}"
            if flock -n "$lock_fd"; then
                printf '%s\n' "$$" > "$lock_file"
                lock_acquired=true
                break
            fi
            
            local lock_pid
            lock_pid=$(cat "$lock_file" 2>/dev/null || true)
            if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
                print_warning "Stale deploy lock detected (PID $lock_pid not running); clearing lock."
                rm -f "$lock_file" 2>/dev/null || true
                continue
            fi
            
            local now elapsed
            now=$(date +%s)
            elapsed=$((now - lock_start_time))
            if (( lock_timeout_sec > 0 && elapsed >= lock_timeout_sec )); then
                print_error "Another nixos-quick-deploy instance is running (lock: $lock_file, waited ${elapsed}s)"
                exit 1
            fi
            if [[ "$lock_warned" != true ]]; then
                print_warning "Another nixos-quick-deploy instance is running; waiting for lock release..."
                lock_warned=true
            fi
            sleep 2
        done
        if [[ "$lock_acquired" != true ]]; then
            print_error "Unable to acquire deploy lock (lock: $lock_file)"
            exit 1
        fi
        _DEPLOY_LOCK_FD="$lock_fd"
        _DEPLOY_LOCK_FILE="$lock_file"
        trap _deploy_exit_cleanup EXIT
    else
        if [[ -f "$lock_file" ]]; then
            local lock_pid
            lock_pid=$(cat "$lock_file" 2>/dev/null || true)
            if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
                print_error "Another nixos-quick-deploy instance is running (PID: $lock_pid)"
                exit 1
            fi
            if [[ -n "$lock_pid" ]]; then
                print_warning "Stale deploy lock detected (PID $lock_pid not running); clearing lock."
            fi
            rm -f "$lock_file" 2>/dev/null || true
        fi
        echo "$$" > "$lock_file"
    fi
}

# Function to handle preflight checks
handle_preflight_checks() {
    # Preflight: avoid overlapping AI stack setup/stack runs
    local allow_running_stack_setup="${ALLOW_RUNNING_STACK_SETUP:-false}"
    local auto_stop_stack="${AUTO_STOP_STACK_ON_CONFLICT:-false}"
    if [[ "$allow_running_stack_setup" != "true" ]]; then
        local stack_conflict=false
        if pgrep -f "setup-hybrid-learning-auto\\.sh" >/dev/null 2>&1; then
            print_warning "Hybrid learning setup is already running (setup-hybrid-learning-auto.sh)."
            stack_conflict=true
        fi
        if [[ "$stack_conflict" == "true" ]]; then
            if [[ "$auto_stop_stack" == "true" && -x "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" ]]; then
                print_warning "AUTO_STOP_STACK_ON_CONFLICT=true; stopping AI stack to continue."
                "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" || print_warning "AI stack stop reported issues."
            else
                print_error "AI stack setup is already running. Aborting to avoid conflicts."
                print_info "Wait for it to finish or re-run with ALLOW_RUNNING_STACK_SETUP=true"
                exit 1
            fi
        fi
    fi
}

# Function to run the deployment phases
run_deployment_workflow() {
    # Run the deployment phases
    if ! run_deployment_phases; then
        print_error "Deployment phases failed"
        exit "${ERR_DEPLOYMENT:-50}"
    fi

    # Run post-deployment tasks
    if ! run_post_deployment; then
        print_warning "Post-deployment tasks reported issues"
        # Don't exit on post-deployment failures, just warn
    fi
}

# Refactored main function (now under 50 lines)
main() {
    # Parse arguments
    parse_arguments "$@"

    # Handle flatpak reinstall request
    if [[ "$FLATPAK_REINSTALL_REQUEST" == true ]]; then
        export RESET_FLATPAK_STATE_BEFORE_SWITCH="true"
    fi

    # Handle early exit commands
    handle_early_exit_commands

    # Setup environment and logging
    setup_environment

    # Handle special modes
    handle_special_modes

    # Ensure Nix experimental features
    ensure_nix_experimental_features_env

    # Initialize state management
    init_state

    # Check for template changes that require config regeneration
    maybe_reset_config_phases_on_template_change

    # Acquire deployment lock to prevent concurrent runs
    acquire_deployment_lock

    # Handle preflight checks
    handle_preflight_checks

    # Run the main deployment workflow
    run_deployment_workflow

    # Log successful completion
    log INFO "Deployment completed successfully"
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi