#!/usr/bin/env bash
# tier0.d: always-on agent files (CLAUDE/AGENTS/CODEX/GEMINI/LOCAL-AGENT) must carry every
# required canon block, keep a lane region, and stay inside their byte budgets (canon.yaml).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ ! -f "$REPO/canon/canon.yaml" ]]; then
    echo "[tier0.d/check-agent-instruction-parity] PASS: no canon manifest (nothing to check)"
    exit 0
fi

if python3 "$REPO/scripts/governance/check-agent-instruction-parity.py"; then
    echo "[tier0.d/check-agent-instruction-parity] PASS"
else
    echo "[tier0.d/check-agent-instruction-parity] FAIL: see violations above; shrink the lane region (move detail to .agent/lanes/<lane>-reference.md) or restore canon blocks via canon-compile.py --write" >&2
    exit 1
fi
