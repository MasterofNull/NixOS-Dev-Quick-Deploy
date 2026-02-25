#!/usr/bin/env bash
#
# Manually trigger an immediate AIDB catalog refresh.
# Default mode uses systemd user service when available.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYNC_SCRIPT="${REPO_ROOT}/scripts/sync-aidb-library-catalog.sh"

MODE="systemd"
if [[ "${1:-}" == "--direct" ]]; then
  MODE="direct"
  shift
fi

if [[ "${MODE}" == "systemd" ]]; then
  if systemctl --user cat aidb-library-catalog-sync.service >/dev/null 2>&1; then
    echo "Triggering immediate catalog sync via systemd user unit..."
    systemctl --user start aidb-library-catalog-sync.service
    echo "Done. Inspect logs with:"
    echo "  journalctl --user -u aidb-library-catalog-sync.service -n 200 --no-pager"
    exit 0
  fi
  echo "systemd user unit not installed; falling back to direct script run."
fi

echo "Running direct catalog sync..."
"${SYNC_SCRIPT}" "$@"
