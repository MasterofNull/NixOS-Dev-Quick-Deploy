#!/usr/bin/env bash
# Compatibility helper.
# Production dashboard runtime is managed by NixOS/systemd, not by this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../config/service-endpoints.sh
source "$PROJECT_ROOT/config/service-endpoints.sh"

echo "scripts/deploy/start-unified-dashboard.sh is not the production launcher." >&2
echo "Authoritative runtime: command-center-dashboard-api.service" >&2
echo >&2
echo "Use one of the following instead:" >&2
echo "  sudo systemctl restart command-center-dashboard-api.service" >&2
echo "  systemctl status command-center-dashboard-api.service" >&2
echo "  open ${DASHBOARD_URL}" >&2
echo >&2
echo "For frontend development only, use:" >&2
echo "  cd dashboard && ./start-dashboard.sh" >&2
exit 2
