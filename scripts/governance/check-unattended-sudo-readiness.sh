#!/usr/bin/env bash
# Check unattended sudo readiness for deploy-time automation.
# Validates root ownership of sudo timestamp directories and sudo -n viability.

set -euo pipefail

check_dir_owner() {
  local path="$1"
  local expected_user="$2"
  local expected_group="$3"
  local actual

  if [[ ! -e "$path" ]]; then
    echo "[sudo-readiness] FAIL: missing path ${path}" >&2
    return 1
  fi

  actual="$(stat -c '%U:%G' "$path")"
  if [[ "$actual" != "${expected_user}:${expected_group}" ]]; then
    echo "[sudo-readiness] FAIL: ${path} owner is ${actual}, expected ${expected_user}:${expected_group}" >&2
    return 1
  fi

  echo "[sudo-readiness] PASS: ${path} owner ${actual}"
}

main() {
  local failed=0

  check_dir_owner "/run/sudo" "root" "root" || failed=1
  check_dir_owner "/run/sudo/ts" "root" "root" || failed=1

  # Owner boundary (2026-10-29): the primary user must NOT have passwordless
  # root via nixos-rebuild/systemctl, so these now FAIL the check if usable.
  if sudo -n /run/current-system/sw/bin/systemctl is-system-running >/dev/null 2>&1; then
    echo "[sudo-readiness] FAIL: sudo -n systemctl is passwordless (owner boundary violated)" >&2
    failed=1
  else
    echo "[sudo-readiness] PASS: sudo -n systemctl requires the owner password"
  fi

  if [[ $failed -ne 0 ]]; then
    exit 1
  fi

  echo "[sudo-readiness] PASS: unattended sudo readiness checks passed"
}

main "$@"
