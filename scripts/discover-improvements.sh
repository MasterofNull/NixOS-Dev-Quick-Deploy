#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/discover-improvements.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$PY_SCRIPT" "$@"
fi

if command -v nix >/dev/null 2>&1; then
  exec nix shell nixpkgs#python3 --command python3 "$PY_SCRIPT" "$@"
fi

echo "ERROR: python3 not found and nix fallback unavailable" >&2
exit 1
