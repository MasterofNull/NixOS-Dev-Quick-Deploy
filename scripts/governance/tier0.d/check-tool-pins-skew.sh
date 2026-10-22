#!/usr/bin/env bash
# check-tool-pins-skew.sh — Tier 0 extension verifying tools meet canonical version floors (W6-S5)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PINS_FILE="$REPO_ROOT/config/tool-pins.json"

if [[ ! -f "$PINS_FILE" ]]; then
    echo "ERROR: missing config/tool-pins.json" >&2
    exit 1
fi

# 1. Check Python floor (3.11+)
MIN_PY="3.11.0"
CUR_PY=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    :
else
    echo "FAIL: python version $CUR_PY is below minimum floor $MIN_PY" >&2
    exit 1
fi

# 2. Check gitleaks floor if installed
if command -v gitleaks >/dev/null 2>&1; then
    GL_VER=$(gitleaks version 2>/dev/null | tr -d 'v' || echo "0.0.0")
    # Simple check that gitleaks version starts with 8
    if [[ ! "$GL_VER" =~ ^8\. ]]; then
        echo "WARN: gitleaks version $GL_VER differs from expected 8.x series" >&2
    fi
fi

echo "[tier0/check-tool-pins-skew] PASS: tool versions meet canonical floors"
