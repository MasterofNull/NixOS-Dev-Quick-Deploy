#!/usr/bin/env bash
set -euo pipefail

echo "scripts/cron-templates.sh is deprecated." >&2
echo "Dashboard and telemetry collectors run as declarative systemd services/timers." >&2
echo "Use: systemctl list-timers --all | rg 'prometheus|node-exporter|command-center'" >&2
exit 2
