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

check_sudo_command() {
  local label="$1"
  shift

  if sudo -n "$@" >/dev/null 2>&1; then
    echo "[sudo-readiness] PASS: ${label}"
    return 0
  fi

  echo "[sudo-readiness] FAIL: ${label}" >&2
  return 1
}

main() {
  local failed=0

  check_dir_owner "/run/sudo" "root" "root" || failed=1
  check_dir_owner "/run/sudo/ts" "root" "root" || failed=1

  check_sudo_command "sudo -n nixos-rebuild is usable" /run/current-system/sw/bin/nixos-rebuild --help || failed=1
  check_sudo_command "sudo -n systemctl is usable" /run/current-system/sw/bin/systemctl is-system-running || failed=1

  if [[ $failed -ne 0 ]]; then
    exit 1
  fi

  echo "[sudo-readiness] PASS: unattended sudo readiness checks passed"
}

main "$@"
