#!/usr/bin/env bash
# Deprecated automation helper retained for compatibility guidance.
set -euo pipefail

echo "scripts/automation/cron-templates.sh is deprecated." >&2
echo "Dashboard and telemetry collectors run as declarative systemd services/timers." >&2
echo "Use: systemctl list-timers --all | rg 'prometheus|node-exporter|command-center'" >&2
exit 2
