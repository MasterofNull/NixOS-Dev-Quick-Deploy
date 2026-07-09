#!/usr/bin/env bash
# tier0.d: canon blocks in agent instruction files must match canon/blocks/ (WS1.4).
# Rule 16 parity as a gate: drifted or missing canon regions block the commit.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ ! -f "$REPO/canon/canon.yaml" ]]; then
    echo "[tier0.d/check-canon-drift] PASS: no canon manifest (nothing to check)"
    exit 0
fi

if python3 "$REPO/scripts/governance/canon-compile.py" --check; then
    echo "[tier0.d/check-canon-drift] PASS: canon blocks in sync"
else
    echo "[tier0.d/check-canon-drift] FAIL: canon drift — run: python3 scripts/governance/canon-compile.py --write" >&2
    exit 1
fi
