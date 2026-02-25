#!/usr/bin/env bash
#
# Install weekly AIDB library catalog sync timer (systemd user units).
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

RUN_NOW=false
if [[ "${1:-}" == "--run-now" ]]; then
  RUN_NOW=true
fi

echo "=== AIDB Library Catalog Timer Installation ==="
echo

mkdir -p "$SYSTEMD_USER_DIR"
echo "✓ Systemd user directory: $SYSTEMD_USER_DIR"

echo
echo "Installing service/timer units..."
sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
  "$PROJECT_ROOT/systemd/aidb-library-catalog-sync.service" \
  > "$SYSTEMD_USER_DIR/aidb-library-catalog-sync.service"
cp "$PROJECT_ROOT/systemd/aidb-library-catalog-sync.timer" "$SYSTEMD_USER_DIR/"
echo "✓ Unit files installed"

echo
echo "Ensuring sync script is executable..."
chmod +x "$PROJECT_ROOT/scripts/sync-aidb-library-catalog.sh"
echo "✓ Sync script executable"

echo
echo "Reloading systemd user daemon..."
systemctl --user daemon-reload
echo "✓ Daemon reloaded"

echo
echo "Enabling and starting weekly timer..."
systemctl --user enable aidb-library-catalog-sync.timer
systemctl --user start aidb-library-catalog-sync.timer
echo "✓ Timer enabled and started"

if [[ "$RUN_NOW" == true ]]; then
  echo
  echo "Running one immediate sync..."
  if systemctl --user start aidb-library-catalog-sync.service; then
    echo "✓ Immediate sync run completed"
  else
    echo "⚠ Immediate sync run failed; timer is still installed and active." >&2
  fi
fi

echo
echo "=== Timer Status ==="
systemctl --user list-timers aidb-library-catalog-sync.timer --all

echo
echo "Weekly schedule: Sunday 03:30 local time"
echo "Manual run: systemctl --user start aidb-library-catalog-sync.service"
echo "Logs: journalctl --user -u aidb-library-catalog-sync.service -n 200 --no-pager"
