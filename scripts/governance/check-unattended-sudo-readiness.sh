#!/usr/bin/env bash
# Owner-boundary sudo check.
#   DECLARED (HARD, exit 1): the checked-out config's evaluated sudoers has no
#     passwordless root-equivalent rule and sets timestamp_timeout=0. This is
#     what a commit can regress, so tier0 gates on it.
#   LIVE (WARN, exit 0): /run/sudo ownership and `sudo -n -l` probes against the
#     running host. Drift until the owner rebuilds is maintenance, not a commit
#     blocker (Rule 19 gate corollary). `--strict-live` makes LIVE fail; use it
#     after the owner's rebuild to validate activation.

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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STRICT_LIVE=0
live_problems=()

# DECLARED: allowlist of the evaluated sudoers (fails if nix eval fails; no
# static fallback, a HARD gate must not pass on an unevaluated config).
check_declared() {
  python3 "${REPO_ROOT}/scripts/governance/lib/sudoers_boundary.py" declared
}

# LIVE: collect problems instead of failing.
check_live() {
  local cmd actual
  for path in /run/sudo /run/sudo/ts; do
    actual="$(stat -c '%U:%G' "$path" 2>/dev/null || echo missing)"
    [[ "$actual" == "root:root" ]] || live_problems+=("${path} owner is ${actual}, expected root:root")
  done
  # `sudo -n -l <cmd>` succeeds for password-required commands too (listpw), so
  # read the full listing and require a NOPASSWD tag on the matching rule.
  local listing listing_rc=0
  listing="$(sudo -n -l 2>&1)" || listing_rc=$?
  if [[ $listing_rc -eq 0 ]]; then
    for cmd in "/run/current-system/sw/bin/systemctl is-system-running" \
               "/run/current-system/sw/bin/nixos-rebuild switch"; do
      # shellcheck disable=SC2086
      if python3 "${REPO_ROOT}/scripts/governance/lib/sudoers_boundary.py" passwordless $cmd <<<"$listing"; then
        live_problems+=("sudo -n permits '${cmd}' without a password")
      fi
    done
  elif ! grep -qi "password is required" <<<"$listing"; then
    live_problems+=("cannot read the sudo listing: ${listing}")
  fi
  if [[ -r /etc/sudoers ]]; then
    grep -Eq '^[[:space:]]*Defaults[[:space:]]+timestamp_timeout=0[[:space:]]*$' /etc/sudoers \
      || live_problems+=("/etc/sudoers lacks Defaults timestamp_timeout=0")
  fi
  if [[ ${#live_problems[@]} -eq 0 ]]; then
    echo "[sudo-readiness] PASS: live sudo matches the owner boundary"
    return 0
  fi
  local p
  for p in "${live_problems[@]}"; do
    if [[ $STRICT_LIVE -eq 1 ]]; then
      echo "[sudo-readiness] FAIL: live: ${p}" >&2
    else
      echo "[sudo-readiness] WARN: live sudoers not yet deployed (pending rebuild): ${p}"
    fi
  done
  [[ $STRICT_LIVE -eq 0 ]]
}

main() {
  local failed=0
  [[ "${1:-}" == "--strict-live" ]] && STRICT_LIVE=1
  check_declared || failed=1
  check_live || failed=1
  if [[ $failed -ne 0 ]]; then
    exit 1
  fi
  echo "[sudo-readiness] PASS: unattended sudo readiness checks passed"
}

main "$@"
