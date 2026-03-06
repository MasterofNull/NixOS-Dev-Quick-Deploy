#!/usr/bin/env bash
set -euo pipefail
# Enforce required metadata blocks on active docs categories.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "${ROOT_DIR}" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
targets = [root / "docs" / "operations", root / "docs" / "development"]
violations = []

for base in targets:
    if not base.exists():
        continue
    for md in sorted(base.rglob("*.md")):
        rel = md.relative_to(root).as_posix()
        if rel.startswith("docs/archive/"):
            continue
        lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
        if not lines:
            continue
        head = "\n".join(lines[:40])
        has_status = "Status:" in head
        has_owner = "Owner:" in head
        has_updated = ("Last Updated:" in head) or ("Updated:" in head)
        if not (has_status and has_owner and has_updated):
            missing = []
            if not has_status:
                missing.append("Status")
            if not has_owner:
                missing.append("Owner")
            if not has_updated:
                missing.append("Last Updated/Updated")
            violations.append((rel, ", ".join(missing)))

if violations:
    print("[doc-metadata] FAIL: missing required metadata in active docs/operations or docs/development")
    for rel, missing in violations[:120]:
        print(f"{rel}: missing {missing}")
    print(f"[doc-metadata] Total violations: {len(violations)}")
    sys.exit(1)

print("[doc-metadata] PASS: required metadata present for active docs/operations and docs/development.")
PY
