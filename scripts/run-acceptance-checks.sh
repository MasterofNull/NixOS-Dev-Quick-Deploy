#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

"${SCRIPT_DIR}/system-health-check.sh" --detailed

if command -v curl >/dev/null 2>&1; then
  curl -fsS --max-time 5 "${AIDB_URL%/}/health" >/dev/null || {
    echo "AIDB health endpoint failed (${AIDB_URL%/}/health)" >&2
    exit 1
  }
  curl -fsS --max-time 5 "${HYBRID_URL%/}/health" >/dev/null || {
    echo "Hybrid coordinator health endpoint failed (${HYBRID_URL%/}/health)" >&2
    exit 1
  }
fi

echo "Acceptance checks passed (declarative mode)."
