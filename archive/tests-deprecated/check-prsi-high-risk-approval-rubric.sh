#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUBRIC_FILE="${ROOT_DIR}/config/prsi/high-risk-approval-rubric.json"

python3 - "$RUBRIC_FILE" "$ROOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

rubric = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(sys.argv[2])

required = rubric.get("required_checklist")
if not isinstance(required, list) or len(required) < 4:
    raise SystemExit("ERROR: high-risk rubric required_checklist invalid")

for key in ["approval_record_template", "runbook"]:
    rel = rubric.get(key)
    if not isinstance(rel, str) or not rel:
        raise SystemExit(f"ERROR: high-risk rubric missing {key}")
    p = root / rel
    if not p.exists():
        raise SystemExit(f"ERROR: high-risk rubric artifact missing: {p}")

print("PASS: PRSI high-risk approval rubric validated")
PY
