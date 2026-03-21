#!/usr/bin/env bash
#
# Deploy CLI - Performance Profiling Module
# Deployment timing instrumentation and performance metrics collection
#
# Usage:
#   source profiling.sh
#   profile_init
#   profile_phase_start "Pre-flight validation"
#   ... do work ...
#   profile_phase_end "Pre-flight validation"
#   profile_report

set -euo pipefail

# ============================================================================
# Global State
# ============================================================================

declare -gA _profile_timings
declare -gA _profile_phases
declare -g _profile_start_epoch
declare -g _profile_enabled="${DEPLOY_ENABLE_PROFILING:-true}"
declare -g _profile_logfile="${DEPLOY_PROFILE_LOG:-/tmp/deploy-profile-$$.log}"

# ============================================================================
# Initialization
# ============================================================================

profile_init() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  _profile_start_epoch="$(date +%s%N)"
  _profile_timings=()
  _profile_phases=()

  # Clear log file
  > "$_profile_logfile"

  log_debug "Profiling initialized (logfile: $_profile_logfile)"
}

# ============================================================================
# Phase Timing Functions
# ============================================================================

profile_phase_start() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  local phase="${1:-unknown}"
  _profile_phases["$phase"]="$(date +%s%N)"

  log_debug "Phase started: $phase"
}

profile_phase_end() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  local phase="${1:-unknown}"
  local end_time="$(date +%s%N)"
  local start_time="${_profile_phases[$phase]:-0}"

  if [[ "$start_time" -eq 0 ]]; then
    log_warn "Phase end called without start: $phase"
    return 1
  fi

  local duration_ns=$(( end_time - start_time ))
  local duration_ms=$(( duration_ns / 1000000 ))

  _profile_timings["$phase"]="$duration_ms"

  # Log to file
  printf '%s,%d\n' "$phase" "$duration_ms" >> "$_profile_logfile"

  log_debug "Phase ended: $phase (${duration_ms}ms)"
}

profile_mark() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  local label="${1:-mark}"
  local now="$(date +%s%N)"
  local elapsed_ns=$(( now - _profile_start_epoch ))
  local elapsed_ms=$(( elapsed_ns / 1000000 ))

  printf '[%8dms] %s\n' "$elapsed_ms" "$label" | tee -a "$_profile_logfile"
}

# ============================================================================
# Reporting Functions
# ============================================================================

profile_report() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  local total_ms=0
  local -a sorted_phases=()

  log ""
  log_info "╔════════════════════════════════════════════════════════╗"
  log_info "║        DEPLOYMENT PERFORMANCE PROFILE                 ║"
  log_info "╚════════════════════════════════════════════════════════╝"
  log ""

  # Calculate total and sort phases
  for phase in "${!_profile_timings[@]}"; do
    total_ms=$(( total_ms + ${_profile_timings[$phase]} ))
    sorted_phases+=("$phase")
  done

  # Sort phases by name
  IFS=$'\n' sorted_phases=($(sort <<<"${sorted_phases[*]}"))
  unset IFS

  # Print each phase
  for phase in "${sorted_phases[@]}"; do
    local ms="${_profile_timings[$phase]}"
    local sec=$(( ms / 1000 ))
    local dec=$(( (ms % 1000) / 10 ))

    # Format: phase name, duration in seconds, duration in ms
    printf '  %-45s %5d.%02ds (%7d ms)\n' \
      "$phase" "$sec" "$dec" "$ms" | tee -a "$_profile_logfile"
  done

  # Summary line
  log ""
  local total_sec=$(( total_ms / 1000 ))
  local total_dec=$(( (total_ms % 1000) / 10 ))

  log_info "─────────────────────────────────────────────────────────"
  log_success "TOTAL DEPLOYMENT TIME:  $total_sec.${total_dec}s"
  log_info "═════════════════════════════════════════════════════════"
  log ""

  # Write summary to log file
  printf '\nTOTAL_MS=%d\nTOTAL_SEC=%d.%02d\n' "$total_ms" "$total_sec" "$total_dec" >> "$_profile_logfile"

  return 0
}

profile_get_total_ms() {
  [[ "$_profile_enabled" == "true" ]] || { echo "0"; return 0; }

  local total_ms=0
  for ms in "${_profile_timings[@]}"; do
    total_ms=$(( total_ms + ms ))
  done

  echo "$total_ms"
}

profile_get_phase_ms() {
  [[ "$_profile_enabled" == "true" ]] || { echo "0"; return 0; }

  local phase="$1"
  echo "${_profile_timings[$phase]:-0}"
}

profile_print_summary() {
  [[ "$_profile_enabled" == "true" ]] || return 0

  local total_ms
  total_ms="$(profile_get_total_ms)"

  if [[ -z "$total_ms" ]] || [[ "$total_ms" -eq 0 ]]; then
    return 0
  fi

  local total_sec=$(( total_ms / 1000 ))
  local total_dec=$(( (total_ms % 1000) / 10 ))

  printf '\n=== DEPLOYMENT COMPLETE ===\nTotal time: %d.%02ds (%d ms)\n\n' \
    "$total_sec" "$total_dec" "$total_ms"
}

profile_is_enabled() {
  [[ "$_profile_enabled" == "true" ]]
}

profile_disable() {
  _profile_enabled="false"
}

profile_enable() {
  _profile_enabled="true"
}

# ============================================================================
# Export Functions
# ============================================================================

export -f profile_init
export -f profile_phase_start
export -f profile_phase_end
export -f profile_mark
export -f profile_report
export -f profile_get_total_ms
export -f profile_get_phase_ms
export -f profile_print_summary
export -f profile_is_enabled
export -f profile_disable
export -f profile_enable
