#!/usr/bin/env bash
# Purpose: enforce uv-first Python tooling for scripts and CI while allowing explicit exceptions.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOWLIST_FILE="${1:-${ROOT_DIR}/config/python-tooling-policy-allowlist.txt}"

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "[python-tooling-policy] FAIL: missing allowlist: ${ALLOWLIST_FILE}" >&2
  exit 2
fi

python3 - "${ROOT_DIR}" "${ALLOWLIST_FILE}" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
allowlist_path = Path(sys.argv[2])

allowlist = {
    line.strip()
    for line in allowlist_path.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.strip().startswith("#")
}

targets = []
for path in (root / "scripts").rglob("*"):
    if not path.is_file():
        continue
    if "__pycache__" in path.parts:
        continue
    if path.suffix not in {"", ".sh", ".py"}:
        continue
    targets.append(path)

for path in (root / ".github" / "workflows").glob("*.yml"):
    if path.is_file():
        targets.append(path)

pattern = re.compile(r"\b(?:python(?:3)?\s+-m\s+pip|pip3?\s+install)\b")
violations = []

for path in sorted(set(targets)):
    rel = path.relative_to(root).as_posix()
    if rel in allowlist or rel == "scripts/governance/check-python-tooling-policy.sh":
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "uv pip install" in line:
            continue
        if pattern.search(line):
            violations.append((rel, line_no, line.strip()))

if violations:
    print("[python-tooling-policy] FAIL: bare pip install usage found outside allowlist")
    for rel, line_no, line in violations[:120]:
        print(f"{rel}:{line_no}: {line}")
    print(f"[python-tooling-policy] Total violations: {len(violations)}")
    sys.exit(1)

print("[python-tooling-policy] PASS: uv-first Python tooling policy enforced.")
PY
