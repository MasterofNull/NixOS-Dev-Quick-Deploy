#!/usr/bin/env bash
set -euo pipefail

# test-aqos-vm-dogfood.sh — unit-level checks for the VM dogfood harness.
#
# Deliberately does NOT run nixos-rebuild build-vm or boot a VM (too slow for
# a unit test). It only asserts: the harness script is syntactically valid,
# the aqos-vm host files exist and reference the golden profile, the flake
# wires .#aqos-vm as a nixosConfiguration, and Step A's eval-check commands
# are present in the harness source.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

HARNESS="scripts/testing/aqos-vm-dogfood.sh"
HOST_DIR="nix/hosts/aqos-vm"

pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

failures=0
check() {
  local desc="$1"
  shift
  if "$@"; then
    pass "$desc"
  else
    echo "[FAIL] $desc" >&2
    failures=$((failures + 1))
  fi
}

# 1. Harness script exists, is executable, and is syntactically valid bash.
check "harness script exists: ${HARNESS}" test -f "${HARNESS}"
check "harness script is executable" test -x "${HARNESS}"
check "harness script passes bash -n" bash -n "${HARNESS}"

# 2. Test script itself is syntactically valid (self-check).
check "test script passes bash -n" bash -n "scripts/testing/test-aqos-vm-dogfood.sh"

# 3. aqos-vm host files exist and reference the golden profile.
check "host default.nix exists" test -f "${HOST_DIR}/default.nix"
check "host facts.nix exists" test -f "${HOST_DIR}/facts.nix"
check "host hardware-configuration.nix exists" test -f "${HOST_DIR}/hardware-configuration.nix"
check "facts.nix references the aqos-workstation profile" \
  grep -q '"aqos-workstation"' "${HOST_DIR}/facts.nix"
check "facts.nix declares hostName aqos-vm" \
  grep -q 'hostName = "aqos-vm"' "${HOST_DIR}/facts.nix"

# 4. flake.nix wires .#aqos-vm as an explicit nixosConfiguration on the
#    golden profile (not just discovered via the hostDirs x profiles matrix).
check "flake.nix defines an aqos-vm nixosConfiguration entry" \
  grep -q 'aqos-vm = mkHost {' flake.nix
check "flake.nix's aqos-vm entry targets the aqos-workstation profile" \
  bash -c "grep -A3 'aqos-vm = mkHost {' flake.nix | grep -q '\"aqos-workstation\"'"

# 5. Step A's eval-check commands are present in the harness (the fast gate
#    this whole file exists to protect: a host that doesn't even eval).
check "harness evaluates system.build.toplevel.drvPath" \
  grep -q 'config.system.build.toplevel.drvPath' "${HARNESS}"
check "harness checks environment.systemPackages for golden markers" \
  grep -q 'environment.systemPackages' "${HARNESS}"
check "harness guards the heavy build behind --full" \
  grep -q -- '--full' "${HARNESS}"
# Looks for an actual sudo COMMAND invocation (sudo as the first token of a
# line or right after a command separator), not the word "sudo" appearing in
# comments/strings documenting that sudo is never required.
check "harness never invokes sudo as a command" \
  bash -c "! grep -qE '(^|[;&|]{1,2})[[:space:]]*sudo[[:space:]]' '${HARNESS}'"
check "harness prints an ACTIVATION-AUDIT summary line" \
  grep -q 'ACTIVATION-AUDIT' "${HARNESS}"

if [ "${failures}" -ne 0 ]; then
  fail "${failures} check(s) failed"
fi

pass "all aqos-vm-dogfood unit checks passed"
