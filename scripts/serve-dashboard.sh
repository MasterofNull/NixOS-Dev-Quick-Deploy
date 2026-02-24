#!/usr/bin/env bash
set -euo pipefail

# Declarative frontend-only dashboard server.
# API/control actions are served by command-center-dashboard-api.service.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIND_ADDRESS="${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
PORT="${DASHBOARD_PORT}"
WEB_ROOT="${SCRIPT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for static dashboard serving" >&2
  exit 1
fi

cd "$WEB_ROOT"
exec python3 -m http.server "$PORT" --bind "$BIND_ADDRESS" --directory "$WEB_ROOT"
