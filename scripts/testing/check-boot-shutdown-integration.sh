#!/usr/bin/env bash
set -euo pipefail

# check-boot-shutdown-integration.sh
# Validate boot/shutdown integration signals and static AI stack service wiring.

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

have_rg() {
  command -v rg >/dev/null 2>&1
}

search_files() {
  local pattern="$1"
  shift
  if have_rg; then
    rg -n "$pattern" "$@"
  else
    grep -En "$pattern" "$@"
  fi
}

search_text_ci() {
  local pattern="$1"
  if have_rg; then
    rg -qi "$pattern"
  else
    grep -Eqi "$pattern"
  fi
}

# Static guard: ensure ai-stack service definitions include restart policy
if search_files 'systemd\.services\.(llama-cpp|llama-cpp-embed|ai-switchboard)' nix/modules/roles/ai-stack.nix nix/modules/services/switchboard.nix >/dev/null; then
  pass "service definitions present in nix modules"
else
  fail "expected ai stack service definitions not found"
fi

if command -v systemctl >/dev/null 2>&1; then
  failed_units="$(systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${failed_units}" != "0" ]]; then
    warn "system has ${failed_units} failed units; inspect with: systemctl --failed"
  else
    pass "no failed systemd units"
  fi

  if command -v journalctl >/dev/null 2>&1; then
    if journalctl -b --no-pager 2>/dev/null | search_text_ci 'A stop job is running|timed out waiting for|Dependency failed for /sysroot'; then
      warn "boot/shutdown warning patterns detected in current boot journal"
    else
      pass "no critical boot/shutdown warning patterns detected"
    fi
  fi
fi
