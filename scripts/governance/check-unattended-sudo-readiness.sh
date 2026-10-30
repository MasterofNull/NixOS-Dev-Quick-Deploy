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

forbidden_re='(nixos-rebuild|journalctl|flatpak|nixos-quick-deploy|aq-model-switch|/Documents/|/home/|\*)'

# DECLARED: evaluated sudoers, else static scan of the Nix sources.
check_declared() {
  local sudoers="" bad="" line
  if command -v nix >/dev/null 2>&1 && [[ -f "${REPO_ROOT}/flake.nix" ]]; then
    sudoers="$(cd "$REPO_ROOT" && nix eval --raw '.#nixosConfigurations.hyperd-ai-dev.config.security.sudo.configFile' 2>/dev/null || true)"
  fi
  if [[ -n "$sudoers" ]]; then
    while IFS= read -r line; do
      [[ "$line" == \#* || "$line" != *NOPASSWD* ]] && continue
      local cmds="${line#*NOPASSWD:}"
      cmds="${cmds//NOPASSWD:/}"
      IFS=',' read -ra parts <<<"$cmds"
      for c in "${parts[@]}"; do
        # bare systemctl (any args) is root-equivalent too
        if grep -Eq "$forbidden_re" <<<"$c" || grep -Eq '/bin/systemctl[[:space:]]*$' <<<"$c"; then
          bad+="${c# } ; "
        fi
      done
    done <<<"$sudoers"
    if ! grep -Eq '^[[:space:]]*Defaults[[:space:]]+timestamp_timeout=0[[:space:]]*$' <<<"$sudoers" \
      || grep -Eq '^[[:space:]]*Defaults[^#]*timestamp_timeout=[1-9-]' <<<"$sudoers"; then
      bad+="timestamp_timeout!=0 ; "
    fi
    if [[ -n "$bad" ]]; then
      echo "[sudo-readiness] FAIL: declared sudoers violates the owner boundary: ${bad}" >&2
      return 1
    fi
    echo "[sudo-readiness] PASS: declared (evaluated) sudoers has no passwordless root-equivalent rule; timestamp_timeout=0"
    return 0
  fi
  # Static fallback
  bad="$(grep -rnE 'command[[:space:]]*=[[:space:]]*"[^"]*(nixos-rebuild|journalctl|flatpak|nixos-quick-deploy|aq-model-switch|/Documents/|systemctl \*|\*")' "${REPO_ROOT}/nix" --include='*.nix' 2>/dev/null || true)"
  if [[ -n "$bad" ]]; then
    echo "[sudo-readiness] FAIL: Nix sources declare a forbidden NOPASSWD command pattern:" >&2
    echo "$bad" >&2
    return 1
  fi
  if ! grep -rqE 'timestamp_timeout=0' "${REPO_ROOT}/nix" --include='*.nix'; then
    echo "[sudo-readiness] FAIL: Nix sources do not set timestamp_timeout=0" >&2
    return 1
  fi
  echo "[sudo-readiness] PASS: declared check (static fallback; nix eval unavailable)"
}

# LIVE: collect problems instead of failing.
check_live() {
  local probe_out probe_rc cmd actual
  for path in /run/sudo /run/sudo/ts; do
    actual="$(stat -c '%U:%G' "$path" 2>/dev/null || echo missing)"
    [[ "$actual" == "root:root" ]] || live_problems+=("${path} owner is ${actual}, expected root:root")
  done
  for cmd in "/run/current-system/sw/bin/systemctl is-system-running" \
             "/run/current-system/sw/bin/nixos-rebuild switch"; do
    probe_rc=0
    # shellcheck disable=SC2086
    probe_out="$(sudo -n -l $cmd 2>&1)" || probe_rc=$?
    if [[ $probe_rc -eq 0 ]]; then
      live_problems+=("sudo -n permits '${cmd}' without a password")
    elif ! grep -qi "password is required" <<<"$probe_out"; then
      live_problems+=("cannot establish sudo authorization for '${cmd}': ${probe_out}")
    fi
  done
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
