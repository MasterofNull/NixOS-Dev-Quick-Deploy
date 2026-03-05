#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
POLICY_FILE="${ROOT_DIR}/config/prsi/quarantine-workflow.json"

python3 - "$POLICY_FILE" "$ROOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(sys.argv[2])

for key in ["sla_hours", "states", "required_fields", "runbook", "template"]:
    if key not in policy:
        raise SystemExit(f"ERROR: quarantine workflow missing key: {key}")

if int(policy.get("sla_hours", 0)) <= 0:
    raise SystemExit("ERROR: quarantine sla_hours must be >0")

for rel in [policy["runbook"], policy["template"]]:
    p = root / rel
    if not p.exists():
        raise SystemExit(f"ERROR: quarantine workflow artifact missing: {p}")

print("PASS: PRSI quarantine workflow contract validated")
PY
