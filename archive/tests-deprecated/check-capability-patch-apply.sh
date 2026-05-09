#!/usr/bin/env bash
# Purpose: Test capability patch application and conflict resolution
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STUB_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-stub"
APPEND_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-catalog-append"
PREP_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-patch-prep"
APPLY_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-patch-apply"
CATALOG="${ROOT_DIR}/config/capability-gap-catalog.json"

tmp_catalog="$(mktemp)"
tmp_stub="$(mktemp)"
tmp_updated="$(mktemp)"
tmp_patch="$(mktemp)"
tmp_backup="$(mktemp)"
tmp_dry="$(mktemp)"
tmp_apply="$(mktemp)"
trap 'rm -f "${tmp_catalog}" "${tmp_stub}" "${tmp_updated}" "${tmp_patch}" "${tmp_backup}" "${tmp_dry}" "${tmp_apply}"' EXIT

cp "${CATALOG}" "${tmp_catalog}"
python3 "${STUB_TOOL}" --tool mm --save-artifact "${tmp_stub}" --format json > /dev/null
python3 "${APPEND_TOOL}" --stub-file "${tmp_stub}" --catalog "${tmp_catalog}" --output "${tmp_updated}" --format json > /dev/null
python3 "${PREP_TOOL}" --catalog "${tmp_catalog}" --updated-catalog-file "${tmp_updated}" --output "${tmp_patch}" --format json > /dev/null
python3 "${APPLY_TOOL}" --catalog "${tmp_catalog}" --patch-file "${tmp_patch}" --format json > "${tmp_dry}"
python3 "${APPLY_TOOL}" --catalog "${tmp_catalog}" --patch-file "${tmp_patch}" --backup-output "${tmp_backup}" --execute --format json > "${tmp_apply}"

python3 - "${tmp_catalog}" "${tmp_backup}" "${tmp_dry}" "${tmp_apply}" <<'PY'
import json
import sys
from pathlib import Path

catalog = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
backup = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
dry = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
applied = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))

if dry.get("ok") is not True or dry.get("mode") != "dry-run":
    print("ERROR: patch apply dry-run did not validate successfully", file=sys.stderr)
    raise SystemExit(1)
if applied.get("ok") is not True or applied.get("mode") != "execute":
    print("ERROR: patch apply execute did not report success", file=sys.stderr)
    raise SystemExit(1)
if not applied.get("backup_output"):
    print("ERROR: patch apply did not report backup output", file=sys.stderr)
    raise SystemExit(1)
if "mm" not in {item.get("id") for item in catalog.get("capabilities", [])}:
    print("ERROR: patch apply did not update the target catalog copy", file=sys.stderr)
    raise SystemExit(1)
if "capabilities" not in backup:
    print("ERROR: patch apply backup is not a valid catalog copy", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability patch apply validated")
PY
