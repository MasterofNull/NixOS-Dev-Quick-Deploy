#!/usr/bin/env bash
set -euo pipefail

# Local troubleshooting helper only.
# Production dashboard serving is handled by command-center-dashboard-api.service,
# which serves both the operator UI and the API from one port.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
PORT="${DASHBOARD_PORT}"
WEB_ROOT="${SCRIPT_DIR}"

echo "scripts/deploy/serve-dashboard.sh is a local static-file helper only." >&2
echo "Do not use it as the production dashboard runtime." >&2
echo "Production authority: command-center-dashboard-api.service" >&2
echo >&2

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for static dashboard serving" >&2
  exit 1
fi

cd "$WEB_ROOT"
exec python3 -m http.server "$PORT" --bind "$BIND_ADDRESS" --directory "$WEB_ROOT"
