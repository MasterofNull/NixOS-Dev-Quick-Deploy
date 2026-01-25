#!/usr/bin/env bash
# AI Stack Secrets Manager - Bash wrapper
# Simple wrapper for the Python secrets manager

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MANAGER="$SCRIPT_DIR/manage-secrets.py"

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Check for rich library
if ! python3 -c "import rich" 2>/dev/null; then
    echo "Warning: 'rich' library not found for fancy UI"
    echo "Install with: pip install rich"
    echo "Running in basic mode...\n"
fi

# Run Python manager
python3 "$PYTHON_MANAGER" "$@"
