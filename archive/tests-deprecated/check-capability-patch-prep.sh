#!/usr/bin/env bash
# Purpose: Test capability patch preparation and diff generation
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STUB_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-stub"
APPEND_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-catalog-append"
PATCH_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-patch-prep"
CATALOG="${ROOT_DIR}/config/capability-gap-catalog.json"

tmp_stub="$(mktemp)"
tmp_catalog="$(mktemp)"
tmp_patch="$(mktemp)"
trap 'rm -f "${tmp_stub}" "${tmp_catalog}" "${tmp_patch}"' EXIT

python3 "${STUB_TOOL}" --tool mm --save-artifact "${tmp_stub}" --format json > /dev/null
python3 "${APPEND_TOOL}" --stub-file "${tmp_stub}" --output "${tmp_catalog}" --format json > /dev/null
python3 "${PATCH_TOOL}" --updated-catalog-file "${tmp_catalog}" --output "${tmp_patch}" --format json > /dev/null

python3 - "${CATALOG}" "${tmp_patch}" <<'PY'
import sys
from pathlib import Path

catalog = Path(sys.argv[1])
patch = Path(sys.argv[2]).read_text(encoding="utf-8")

if str(catalog) not in patch:
    print("ERROR: capability patch prep did not include the base catalog path in the diff header", file=sys.stderr)
    raise SystemExit(1)
if '"id": "mm"' not in patch:
    print("ERROR: capability patch prep did not include the promoted capability in the diff", file=sys.stderr)
    raise SystemExit(1)
if not patch.startswith("--- "):
    print("ERROR: capability patch prep did not emit a unified diff artifact", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability patch prep validated")
PY
