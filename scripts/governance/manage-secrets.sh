#!/usr/bin/env bash
# Declarative SOPS secrets manager wrapper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MANAGER="$SCRIPT_DIR/manage-secrets.py"

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Run Python manager
python3 "$PYTHON_MANAGER" "$@"
