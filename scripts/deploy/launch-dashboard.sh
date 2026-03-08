#!/usr/bin/env bash
set -euo pipefail

echo "launch-dashboard.sh is deprecated." >&2
echo "Use the declarative command center service instead." >&2
echo "Use: systemctl status command-center-dashboard-api.service" >&2
echo "Use: xdg-open http://127.0.0.1:8889/" >&2
exit 2
