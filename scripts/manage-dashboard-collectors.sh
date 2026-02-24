#!/usr/bin/env bash
set -euo pipefail

echo "scripts/manage-dashboard-collectors.sh is deprecated." >&2
echo "Collector management is declarative via systemd/NixOS modules." >&2
echo "Use: systemctl list-units 'command-center*'" >&2
exit 2
