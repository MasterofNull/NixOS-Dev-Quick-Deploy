#!/usr/bin/env bash
#
# Progress Tracking Utilities
# Purpose: Track and display deployment progress
# Version: 1.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/colors.sh → Color codes
#
# Exports:
#   - track_phase_start() → Record phase start time
#   - track_phase_complete() → Record phase completion
#   - show_progress() → Display current progress
#   - estimate_time_remaining() → Calculate ETA
# ============================================================================

# ============================================================================
# Progress Tracking State
# ============================================================================

declare -A PHASE_START_TIMES=()
declare -A PHASE_DURATIONS=()
TOTAL_START_TIME=0
TOTAL_PHASES=8

# ============================================================================
# Track Phase Start
# ============================================================================
# Purpose: Record when a phase starts for duration tracking
# Parameters:
#   $1 - Phase number
# Returns: 0 on success
# ============================================================================
track_phase_start() {
    local phase_num="${1:-}"
    if [[ -z "$phase_num" ]]; then
        return 1
    fi
    
    PHASE_START_TIMES["$phase_num"]=$(date +%s)
    
    # Track total start time on first phase
    if [[ $TOTAL_START_TIME -eq 0 ]]; then
        TOTAL_START_TIME=$(date +%s)
    fi
    
    log DEBUG "Phase $phase_num started"
    return 0
}

# ============================================================================
# Track Phase Complete
# ============================================================================
# Purpose: Record phase completion and calculate duration
# Parameters:
#   $1 - Phase number
# Returns: Duration in seconds, 0 if not tracked
# ============================================================================
track_phase_complete() {
    local phase_num="${1:-}"
    if [[ -z "$phase_num" ]]; then
        return 1
    fi
    
    local start_time="${PHASE_START_TIMES[$phase_num]:-}"
    if [[ -z "$start_time" ]]; then
        return 0
    fi
    
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # shellcheck disable=SC2034
    PHASE_DURATIONS["$phase_num"]=$duration
    log DEBUG "Phase $phase_num completed in ${duration}s"
    
    return 0
}

# ============================================================================
# Show Progress Bar
# ============================================================================
# Purpose: Display a visual progress bar
# Parameters:
#   $1 - Current value
#   $2 - Maximum value
#   $3 - Width in characters (default: 50)
# Returns: Prints progress bar to stdout
# ============================================================================
show_progress_bar() {
    local current="${1:-0}"
    local maximum="${2:-100}"
    local width="${3:-50}"
    
    if [[ $maximum -eq 0 ]]; then
        maximum=100
    fi
    
    local percentage=$(( (current * 100) / maximum ))
    local filled=$(( (current * width) / maximum ))
    local empty=$((width - filled))
    
    printf "["
    printf "%*s" $filled "" | tr ' ' '='
    printf "%*s" $empty "" | tr ' ' '-'
    printf "] %3d%%" "$percentage"
}

# ============================================================================
# Show Overall Progress
# ============================================================================
# Purpose: Display deployment progress with ETA
# Parameters:
#   $1 - Current phase number
# Returns: Prints progress info to stdout
# ============================================================================
show_progress() {
    local current_phase="${1:-0}"
    
    if [[ $current_phase -eq 0 ]]; then
        return 0
    fi
    
    local completed=$current_phase
    local percentage=$(( (completed * 100) / TOTAL_PHASES ))
    
    printf "\n"
    print_info "Deployment Progress:"
    print_info "  Completed: $completed/$TOTAL_PHASES phases"
    print_info "  Progress: $(show_progress_bar $completed $TOTAL_PHASES)"
    
    # Calculate ETA if we have timing data
    if [[ $TOTAL_START_TIME -gt 0 ]]; then
        local elapsed
        elapsed=$(date +%s)
        elapsed=$((elapsed - TOTAL_START_TIME))
        
        if [[ $completed -gt 0 && $elapsed -gt 0 ]]; then
            local avg_time_per_phase=$((elapsed / completed))
            local remaining_phases=$((TOTAL_PHASES - completed))
            local eta_seconds=$((avg_time_per_phase * remaining_phases))
            
            local eta_minutes=$((eta_seconds / 60))
            local eta_hours=$((eta_minutes / 60))
            
            if [[ $eta_hours -gt 0 ]]; then
                print_info "  Estimated time remaining: ${eta_hours}h ${eta_minutes}m"
            else
                print_info "  Estimated time remaining: ${eta_minutes}m"
            fi
        fi
        
        local elapsed_minutes=$((elapsed / 60))
        print_info "  Elapsed time: ${elapsed_minutes}m"
    fi
    
    printf "\n"
}

# ============================================================================
# Estimate Time Remaining
# ============================================================================
# Purpose: Calculate estimated time to completion based on current progress
# Parameters:
#   $1 - Current phase number
# Returns: Estimated seconds remaining, or 0 if cannot calculate
# ============================================================================
estimate_time_remaining() {
    local current_phase="${1:-0}"
    
    if [[ $current_phase -eq 0 || $TOTAL_START_TIME -eq 0 ]]; then
        return 0
    fi
    
    local elapsed
    elapsed=$(date +%s)
    elapsed=$((elapsed - TOTAL_START_TIME))
    
    if [[ $current_phase -gt 0 && $elapsed -gt 0 ]]; then
        local avg_time_per_phase=$((elapsed / current_phase))
        local remaining_phases=$((TOTAL_PHASES - current_phase))
        local eta=$((avg_time_per_phase * remaining_phases))
        return $eta
    fi
    
    return 0
}
