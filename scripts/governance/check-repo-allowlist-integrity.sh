#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOWLIST_FILE="${1:-${ROOT_DIR}/config/repo-structure-allowlist.txt}"

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "[allowlist-integrity] FAIL: missing allowlist file: ${ALLOWLIST_FILE}" >&2
  exit 2
fi

python3 - "${ALLOWLIST_FILE}" <<'PY'
from pathlib import Path
import sys

allowlist = Path(sys.argv[1])
entries = []
line_map = {}
for i, raw in enumerate(allowlist.read_text(encoding="utf-8").splitlines(), start=1):
    s = raw.strip()
    if not s or s.startswith("#"):
        continue
    entries.append(s)
    line_map.setdefault(s, []).append(i)

duplicates = [(e, line_map[e]) for e in line_map if len(line_map[e]) > 1]
missing = [e for e in entries if not Path(e).exists()]

if duplicates or missing:
    print("[allowlist-integrity] FAIL: repo-structure allowlist drift detected")
    if duplicates:
        print(f"  duplicate entries: {len(duplicates)}")
        for entry, lines in duplicates[:20]:
            print(f"    lines {','.join(map(str, lines))}: {entry}")
    if missing:
        print(f"  missing paths: {len(missing)}")
        for entry in missing[:40]:
            print(f"    {entry}")
    sys.exit(1)

print(f"[allowlist-integrity] PASS: entries={len(entries)} duplicates=0 missing=0")
PY
