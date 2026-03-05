#!/usr/bin/env bash
set -euo pipefail

# Classify failed systemd units after deploy into critical/non-critical buckets.
# Default non-critical allowlist includes libvirtd legacy monolithic daemon.

NON_CRITICAL_UNITS="${NON_CRITICAL_UNITS:-libvirtd.service}"

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

command -v systemctl >/dev/null 2>&1 || fail "missing systemctl"

mapfile -t failed_units < <(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}')

if [[ "${#failed_units[@]}" -eq 0 ]]; then
  pass "no failed units"
  exit 0
fi

declare -a critical=()
declare -a non_critical=()

is_non_critical() {
  local unit="$1"
  for allowed in ${NON_CRITICAL_UNITS}; do
    [[ "$unit" == "$allowed" ]] && return 0
  done
  return 1
}

is_critical_pattern() {
  local unit="$1"
  [[ "$unit" =~ ^ai- ]] && return 0
  [[ "$unit" =~ ^llama- ]] && return 0
  [[ "$unit" =~ ^qdrant ]] && return 0
  [[ "$unit" =~ ^postgresql ]] && return 0
  [[ "$unit" =~ ^redis-mcp ]] && return 0
  [[ "$unit" =~ ^command-center-dashboard ]] && return 0
  [[ "$unit" =~ ^prometheus ]] && return 0
  [[ "$unit" =~ ^ai-stack\.target$ ]] && return 0
  return 1
}

for unit in "${failed_units[@]}"; do
  if is_non_critical "$unit"; then
    non_critical+=("$unit")
  elif is_critical_pattern "$unit"; then
    critical+=("$unit")
  else
    non_critical+=("$unit")
  fi
done

if [[ "${#non_critical[@]}" -gt 0 ]]; then
  warn "non-critical failed units: ${non_critical[*]}"
fi

if [[ "${#critical[@]}" -gt 0 ]]; then
  fail "critical failed units: ${critical[*]}"
fi

pass "no critical failed units"
