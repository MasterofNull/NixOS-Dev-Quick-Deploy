#!/usr/bin/env bash
# Phase 12.4.1 — MCP server process tree watchdog.
#
# Scans each MCP server's cgroup process tree for unexpected executables.
# Legitimate processes run from /nix/store/ (content-addressed Nix binaries).
# Any process whose exe path does NOT start with /nix/store/ triggers an alert.
#
# Environment variables (all optional):
#   MCP_SERVICES   — space-separated systemd service names to check
#   ALERT_DIR      — directory for alert JSONL output
#   ALLOWLIST_FILE — file with extra allowed exe prefixes (one per line)
#
# Exit: always 0 (alerts written to ALERT_DIR; do not fail the timer unit).
set -euo pipefail

: "${MCP_SERVICES:=ai-aidb ai-hybrid-coordinator ai-ralph-wiggum ai-embeddings ai-audit-sidecar}"
: "${ALERT_DIR:=/var/log/ai-mcp-process-watch/alerts}"
: "${ALLOWLIST_FILE:=/etc/ai-mcp-process-allowlist}"

mkdir -p "$ALERT_DIR"

ts=$(date +%Y-%m-%dT%H:%M:%SZ)
alert_file="$ALERT_DIR/$(date +%Y-%m-%d-%H%M%S).jsonl"

services_checked=0
pids_scanned=0
alerts_emitted=0

# Read optional extra allowlist entries (one path prefix per line).
extra_allowed=()
if [[ -f "$ALLOWLIST_FILE" ]]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    extra_allowed+=("$line")
  done < "$ALLOWLIST_FILE"
fi

is_allowed() {
  local exe="$1"
  # Nix store: all legitimate binaries live here (content-addressed, immutable).
  [[ "$exe" == /nix/store/* ]] && return 0
  # Extra allowlist entries.
  for prefix in "${extra_allowed[@]}"; do
    [[ "$exe" == "$prefix"* ]] && return 0
  done
  return 1
}

for svc in $MCP_SERVICES; do
  # Get the cgroup path for this service (empty if service is not running).
  cgroup_path=$(systemctl show "$svc" --property=ControlGroup --value 2>/dev/null || true)
  if [[ -z "$cgroup_path" ]]; then
    continue
  fi

  # Kernel exposes cgroup task list at /sys/fs/cgroup/<path>/cgroup.procs.
  procs_file="/sys/fs/cgroup${cgroup_path}/cgroup.procs"
  if [[ ! -f "$procs_file" ]]; then
    continue
  fi

  services_checked=$(( services_checked + 1 ))

  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    pids_scanned=$(( pids_scanned + 1 ))

    # Resolve the executable path (fails if PID has already exited — skip).
    exe=$(readlink -f "/proc/${pid}/exe" 2>/dev/null) || continue

    if ! is_allowed "$exe"; then
      alerts_emitted=$(( alerts_emitted + 1 ))
      # Emit JSON alert line.
      printf '{"timestamp":"%s","service":"%s","pid":%s,"exe":"%s","alert":"unexpected_executable"}\n' \
        "$ts" "$svc" "$pid" "$exe" >> "$alert_file"
      # Also log to the system journal so it surfaces in `journalctl`.
      logger -t ai-mcp-process-watch -p local0.warning \
        "ALERT: unexpected exe in $svc (pid=$pid): $exe"
    fi
  done < "$procs_file"
done

printf 'Checked %d services, %d PIDs, %d alerts\n' \
  "$services_checked" "$pids_scanned" "$alerts_emitted" >&2

# Remove empty alert file if no alerts were found.
if [[ -f "$alert_file" ]] && [[ ! -s "$alert_file" ]]; then
  rm -f "$alert_file"
fi

exit 0
