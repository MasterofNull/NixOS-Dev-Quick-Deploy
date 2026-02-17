#!/usr/bin/env bash
set -euo pipefail

info() {
  printf '[fs-integrity-check] %s\n' "$*"
}

pattern='Failed to start File System Check on|Dependency failed for /sysroot|You are in emergency mode|systemd-fsck.*failed|status=1/FAILURE|status=4|has unrepaired errors, please fix them manually|mounting fs with errors, running e2fsck is recommended|error count since last fsck'
pattern="${FS_INTEGRITY_PATTERN:-$pattern}"

combined_logs=""
if [[ -n "${FS_INTEGRITY_LOG_TEXT:-}" ]]; then
  combined_logs="${FS_INTEGRITY_LOG_TEXT}"
elif [[ -n "${FS_INTEGRITY_LOG_FILE:-}" && -f "${FS_INTEGRITY_LOG_FILE}" ]]; then
  combined_logs="$(cat "${FS_INTEGRITY_LOG_FILE}")"
else
  current_boot="$(journalctl -b --no-pager 2>/dev/null || true)"
  current_kernel="$(journalctl -k -b --no-pager 2>/dev/null || true)"
  previous_boot="$(journalctl -b -1 --no-pager 2>/dev/null || true)"
  previous_kernel="$(journalctl -k -b -1 --no-pager 2>/dev/null || true)"

  combined_logs="$current_boot"$'\n'"$current_kernel"$'\n'"$previous_boot"$'\n'"$previous_kernel"
fi

if echo "$combined_logs" | grep -Eiq "$pattern"; then
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
