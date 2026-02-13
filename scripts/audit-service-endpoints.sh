#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/audit-service-endpoints.sh [path...]

Scans for hardcoded localhost endpoints in active code paths.
Defaults: scripts/ dashboard/backend/

Exit codes:
  0 - no hardcoded endpoints found
  2 - hardcoded endpoints found
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

paths=("scripts" "dashboard/backend")
if [[ $# -gt 0 ]]; then
  paths=("$@")
fi

patterns=(
  "http://localhost"
  "http://127.0.0.1"
  "ws://localhost"
  "ws://127.0.0.1"
)

rg_args=(
  --no-heading
  --line-number
  --color=never
  --glob '!**/*.md'
  --glob '!**/*.html'
  --glob '!**/node_modules/**'
  --glob '!**/__pycache__/**'
  --glob '!**/dist/**'
  --glob '!**/build/**'
  --glob '!**/audit-service-endpoints.sh'
)

found=0
for pattern in "${patterns[@]}"; do
  if rg "${rg_args[@]}" -e "$pattern" "${paths[@]/#/${ROOT_DIR}/}"; then
    found=1
  fi
done

if [[ $found -ne 0 ]]; then
  echo "[WARN] Hardcoded localhost endpoints detected. Prefer config/service-endpoints.sh or service_endpoints.py." >&2
  exit 2
fi

echo "[OK] No hardcoded localhost endpoints detected in ${paths[*]}"
