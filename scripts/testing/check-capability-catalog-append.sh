#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STUB_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-stub"
APPEND_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-catalog-append"
CATALOG="${ROOT_DIR}/config/capability-gap-catalog.json"

tmp_stub="$(mktemp)"
tmp_catalog="$(mktemp)"
tmp_dup="$(mktemp)"
trap 'rm -f "${tmp_stub}" "${tmp_catalog}" "${tmp_dup}"' EXIT

python3 "${STUB_TOOL}" --tool mm --save-artifact "${tmp_stub}" --format json > /dev/null
python3 "${APPEND_TOOL}" --stub-file "${tmp_stub}" --output "${tmp_catalog}" --format json > /dev/null

python3 - "${CATALOG}" "${tmp_catalog}" <<'PY'
import json
import sys
from pathlib import Path

base = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
updated = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

base_ids = {item["id"] for item in base.get("capabilities", [])}
updated_ids = [item["id"] for item in updated.get("capabilities", [])]
if "mm" not in updated_ids:
    print("ERROR: appended catalog artifact did not contain mm", file=sys.stderr)
    raise SystemExit(1)
if base_ids & {"mm"}:
    print("ERROR: base catalog unexpectedly already contains mm", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability catalog append artifact validated")
PY

if python3 "${APPEND_TOOL}" --fragment-file <(python3 "${STUB_TOOL}" --tool rg --fragment-only --format json) --output "${tmp_dup}" --format json >/dev/null 2>&1; then
  echo "ERROR: duplicate capability append unexpectedly succeeded" >&2
  exit 1
fi
