#!/usr/bin/env bash
set -euo pipefail

# Fail if any .github/workflows/*.yml references a scripts/** path that does
# not exist on disk. Root cause this guards against: a script gets archived
# (scripts/foo.sh -> archive/tests-deprecated/foo.sh) but a workflow step
# still `chmod`s or invokes the old scripts/ path, which fails hard in CI
# the moment that job runs (see: archived scripts/testing/smoke-cross-client-compat.sh
# in commit 44d8da11 "refactor(runtime): archive deprecated tests", which sank
# the Syntax Validation job and dependency-skipped four downstream jobs).
#
# Usage: scripts/governance/check-workflow-script-refs.sh [workflow.yml ...]
#   No args: checks every .github/workflows/*.yml
#   Args: checks only the given workflow file(s) (paths repo-root-relative or absolute)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$#" -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=(.github/workflows/*.yml)
fi

python3 - "${ROOT_DIR}" "${TARGETS[@]}" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
targets = [pathlib.Path(p) for p in sys.argv[2:]]

# Matches scripts/<path>, with or without a file extension (some entrypoints,
# e.g. scripts/ai/aqd, are extensionless shims). Anchored to a path segment
# boundary so it doesn't match mid-word (e.g. "myscripts/foo").
ref_re = re.compile(r"(?<![A-Za-z0-9_./-])scripts/[A-Za-z0-9_./-]+")

def strip_trailing_punct(token: str) -> str:
    return token.rstrip(".,;:)")

violations = []
checked_files = 0
for wf in targets:
    path = wf if wf.is_absolute() else (root / wf)
    if not path.exists():
        print(f"[workflow-script-refs] FAIL: target workflow not found: {wf}", file=sys.stderr)
        sys.exit(2)
    checked_files += 1
    rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    seen_on_line = set()
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for m in ref_re.finditer(line):
            token = strip_trailing_punct(m.group(0))
            if not token or (idx, token) in seen_on_line:
                continue
            seen_on_line.add((idx, token))
            if not (root / token).exists():
                violations.append((rel, idx, token))

if violations:
    print("[workflow-script-refs] FAIL: workflow(s) reference scripts/** paths that do not exist on disk")
    for rel, idx, token in violations:
        print(f"{rel}:{idx}: {token}")
    print(f"[workflow-script-refs] Total dangling references: {len(violations)} across {checked_files} file(s) checked")
    sys.exit(1)

print(f"[workflow-script-refs] PASS: no dangling scripts/** references in {checked_files} workflow file(s)")
PY
