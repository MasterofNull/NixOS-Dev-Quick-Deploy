#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MATRIX_FILE="${ROOT_DIR}/config/prsi/validation-matrix.json"

python3 - "$MATRIX_FILE" "$ROOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

matrix_path = Path(sys.argv[1])
root = Path(sys.argv[2])

if not matrix_path.exists():
    raise SystemExit(f"ERROR: missing {matrix_path}")

matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
required = matrix.get("required_verification")
if not isinstance(required, list) or not required:
    raise SystemExit("ERROR: required_verification missing or empty")

required_ids = {
    "syntax_or_lint",
    "runtime_contract",
    "report_schema",
    "security_checks",
    "focused_smoke_or_eval",
    "critical_regression_scan",
    "chaos_fallback",
}

ids = set()
for row in required:
    if not isinstance(row, dict):
        raise SystemExit("ERROR: required_verification rows must be objects")
    for key in ["id", "owner", "command"]:
        if key not in row or not isinstance(row[key], str) or not row[key].strip():
            raise SystemExit(f"ERROR: invalid verification row key '{key}'")
    ids.add(row["id"])
    owner_path = root / row["owner"]
    if not owner_path.exists():
        raise SystemExit(f"ERROR: verification owner script missing: {owner_path}")

missing = sorted(required_ids - ids)
if missing:
    raise SystemExit(f"ERROR: missing required validation ids: {missing}")

print("PASS: PRSI validation matrix contract validated")
PY
