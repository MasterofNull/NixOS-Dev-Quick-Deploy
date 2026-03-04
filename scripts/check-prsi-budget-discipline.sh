#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
POLICY_FILE="${PRSI_POLICY_FILE:-${ROOT_DIR}/config/runtime-prsi-policy.json}"
STATE_FILE="${PRSI_STATE_PATH:-/var/lib/nixos-ai-stack/prsi/runtime-state.json}"

python3 - "$POLICY_FILE" "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
state_path = Path(sys.argv[2])
state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

cycle = policy.get("cycle", {}) if isinstance(policy, dict) else {}
if int(cycle.get("max_mutating_actions", 0)) != 1:
    raise SystemExit("ERROR: budget discipline requires max_mutating_actions=1")

budget = policy.get("budget", {}) if isinstance(policy, dict) else {}
cap = int(budget.get("remote_token_cap_daily", 0) or 0)
used = int(state.get("remote_tokens_used", 0) or 0)
if cap > 0 and used > cap:
    raise SystemExit(f"ERROR: remote token cap exceeded ({used}>{cap})")

print(f"PASS: PRSI budget discipline validated (used={used}, cap={cap})")
PY
