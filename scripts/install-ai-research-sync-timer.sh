#!/usr/bin/env bash
# Install weekly AI research sync timer (user systemd units).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

RUN_NOW=false
if [[ "${1:-}" == "--run-now" ]]; then
  RUN_NOW=true
fi

mkdir -p "$SYSTEMD_USER_DIR"
sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
  "$PROJECT_ROOT/systemd/ai-research-sync.service" \
  > "$SYSTEMD_USER_DIR/ai-research-sync.service"
cp "$PROJECT_ROOT/systemd/ai-research-sync.timer" "$SYSTEMD_USER_DIR/"
chmod +x "$PROJECT_ROOT/scripts/sync-ai-research-knowledge.sh"

systemctl --user daemon-reload
systemctl --user enable ai-research-sync.timer
systemctl --user start ai-research-sync.timer

if [[ "$RUN_NOW" == true ]]; then
  systemctl --user start ai-research-sync.service
fi

echo "Weekly AI research sync timer installed."
systemctl --user list-timers ai-research-sync.timer --all
