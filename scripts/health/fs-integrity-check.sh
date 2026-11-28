#!/usr/bin/env bash
# Detect filesystem integrity failure signatures from journal logs.
set -euo pipefail

info() {
  printf '[fs-integrity-check] %s\n' "$*"
}

pattern='Failed to start File System Check on|Dependency failed for /sysroot|You are in emergency mode|systemd-fsck.*failed|status=1/FAILURE|status=4|has unrepaired errors, please fix them manually|mounting fs with errors, running e2fsck is recommended|error count since last fsck'
pattern="${FS_INTEGRITY_PATTERN:-$pattern}"

# Stream every log source through grep; never hold journal text in a shell
# variable. Four whole-boot journals expanded into one bash string made bash
# SEGV (remove_quoted_nulls) at ~6 GB RSS on a ~2 GB journal.
# grep -c (not -q) drains its input so journalctl never gets SIGPIPE under pipefail.
count_matches() {
  grep -Eic -- "$pattern" || true
}

matches=0
if [[ -n "${FS_INTEGRITY_LOG_TEXT:-}" ]]; then
  matches="$(count_matches <<<"${FS_INTEGRITY_LOG_TEXT}")"
elif [[ -n "${FS_INTEGRITY_LOG_FILE:-}" && -f "${FS_INTEGRITY_LOG_FILE}" ]]; then
  matches="$(count_matches <"${FS_INTEGRITY_LOG_FILE}")"
else
  for jargs in "-b" "-k -b" "-b -1" "-k -b -1"; do
    # shellcheck disable=SC2086 # intentional word splitting of fixed flag sets
    n="$({ journalctl $jargs --no-pager 2>/dev/null || true; } | count_matches)"
    matches=$((matches + n))
  done
fi

if ((matches > 0)); then
  root_src="${ROOT_SOURCE_OVERRIDE:-$(findmnt -no SOURCE / 2>/dev/null || true)}"
  root_real="${ROOT_REAL_OVERRIDE:-$(readlink -f "$root_src" 2>/dev/null || true)}"
  root_uuid="${ROOT_UUID_OVERRIDE:-}"
  if [[ -z "$root_real" ]]; then
    root_real="$root_src"
  fi
  if [[ -z "$root_uuid" && -n "$root_real" && -b "$root_real" ]]; then
    root_uuid="$(blkid -s UUID -o value "$root_real" 2>/dev/null || true)"
    if [[ -z "$root_uuid" ]]; then
      root_uuid="$(lsblk -no UUID "$root_real" 2>/dev/null | head -n1 || true)"
    fi
  fi

  info "CRITICAL: filesystem integrity signatures detected."
  if [[ -n "$root_uuid" ]]; then
    info "Recommended offline repair: e2fsck -f /dev/disk/by-uuid/$root_uuid"
  else
    info "Recommended offline repair: e2fsck -f <root-device>"
  fi
  exit 2
fi

info "No filesystem integrity failure signatures detected in current/previous boot logs."
