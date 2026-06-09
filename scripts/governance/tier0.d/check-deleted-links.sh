#!/usr/bin/env bash
# Tier0 extension: block commits that delete agent docs still referenced elsewhere.
# Phase 92.2 — pre-archive safety net.

set -euo pipefail

MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

# Doc directories where deletions are guarded.
DOC_PREFIXES=(".agent/" ".agents/plans/" "docs/")
LOCAL_RUNTIME_DOCS=(".agent/collaboration/HANDOFF.md")

collect_deleted_files() {
  if [[ "${MODE}" == "--pre-commit" ]]; then
    git diff --cached --name-status --diff-filter=D 2>/dev/null | awk '{print $2}' || true
    return 0
  fi
  git diff --name-status --diff-filter=D origin/main...HEAD 2>/dev/null | awk '{print $2}' || true
}

deleted=()
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ "$f" != *.md ]] && continue
  skip_runtime=false
  for runtime_doc in "${LOCAL_RUNTIME_DOCS[@]}"; do
    if [[ "$f" == "$runtime_doc" ]]; then
      skip_runtime=true
      break
    fi
  done
  $skip_runtime && continue
  for prefix in "${DOC_PREFIXES[@]}"; do
    if [[ "$f" == "${prefix}"* ]]; then
      deleted+=("$f")
      break
    fi
  done
done < <(collect_deleted_files)

if [[ ${#deleted[@]} -eq 0 ]]; then
  echo "[tier0.d/check-deleted-links] PASS: no doc deletions staged"
  exit 0
fi

python3 - "${REPO_ROOT}" "${deleted[@]}" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
deleted_set = set(sys.argv[2:])

link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

tracked = subprocess.run(
    ["git", "-C", str(root), "ls-files"],
    check=True, text=True, capture_output=True,
).stdout.splitlines()

def normalize_link(source_rel, raw_target):
    value = raw_target.strip().split()[0].strip("<>")
    if "://" in value or value.startswith("#"):
        return None
    from urllib.parse import unquote, urlparse
    path = unquote(urlparse(value).path)
    if not path:
        return None
    source_dir = (root / source_rel).parent
    try:
        return (source_dir / path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None

violations = []
for rel in tracked:
    if rel in deleted_set:
        continue
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in link_re.finditer(line):
            norm = normalize_link(rel, match.group(1))
            if norm in deleted_set:
                violations.append(f"  {rel}:{line_no}: {line.strip()[:100]}")
                break
        else:
            for d in deleted_set:
                if d in line or f"./{d}" in line:
                    violations.append(f"  {rel}:{line_no}: {line.strip()[:100]}")
                    break

if violations:
    print(f"[tier0.d/check-deleted-links] FAIL: {len(sys.argv[2:])} deleted doc(s) still referenced:")
    for v in violations[:20]:
        print(v)
    if len(violations) > 20:
        print(f"  ... and {len(violations) - 20} more")
    print("Run scripts/governance/pre-archive-scan.sh <file> before archiving, or update references first.")
    sys.exit(1)

print(f"[tier0.d/check-deleted-links] PASS: {len(sys.argv[2:])} deleted doc(s) have no inbound references")
PY
