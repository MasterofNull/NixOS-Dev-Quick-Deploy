#!/usr/bin/env bash
set -euo pipefail
# Normalize and de-duplicate repo structure allowlist entries.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOWLIST_FILE="${1:-${ROOT_DIR}/config/repo-structure-allowlist.txt}"

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "Missing allowlist file: ${ALLOWLIST_FILE}" >&2
  exit 2
fi

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

python3 - "${ALLOWLIST_FILE}" > "${tmp_file}" <<'PY'
from pathlib import Path
import sys

allowlist = Path(sys.argv[1])
root = Path.cwd()

seen = set()
kept = 0
dropped_missing = 0
dropped_duplicate = 0

out_lines = []
for raw in allowlist.read_text(encoding="utf-8").splitlines():
    line = raw.rstrip("\n")
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        out_lines.append(line)
        continue

    if stripped in seen:
        dropped_duplicate += 1
        continue

    path = root / stripped
    if not path.exists():
        dropped_missing += 1
        continue

    seen.add(stripped)
    kept += 1
    out_lines.append(stripped)

if out_lines and out_lines[-1] != "":
    out_lines.append("")

sys.stdout.write("\n".join(out_lines))
sys.stderr.write(
    f"[normalize-repo-allowlist] kept={kept} "
    f"dropped_missing={dropped_missing} dropped_duplicate={dropped_duplicate}\n"
)
PY

mv "${tmp_file}" "${ALLOWLIST_FILE}"
echo "[normalize-repo-allowlist] Updated ${ALLOWLIST_FILE}"
