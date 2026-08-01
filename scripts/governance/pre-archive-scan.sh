#!/usr/bin/env bash
set -euo pipefail

# Find repo files that link to a path before it is moved to an archive.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/governance/pre-archive-scan.sh <file>

Exits 1 when any tracked repo file links to <file>; exits 0 when no inbound
links are found. The scan checks Markdown link/image targets plus plain path
mentions for the repo-relative file path.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

target_arg="$1"

python3 - "$ROOT_DIR" "$target_arg" <<'PY'
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

root = Path(sys.argv[1]).resolve()
target_arg = sys.argv[2]

# Resolve only the parent; keep the leaf un-followed for symlink detection.
abs_target = Path(target_arg) if Path(target_arg).is_absolute() else (root / target_arg)
lexical = abs_target.parent.resolve() / abs_target.name

try:
    target_rel = lexical.relative_to(root).as_posix()
except ValueError:
    print(f"[pre-archive-scan] ERROR: target is outside repo: {lexical}", file=sys.stderr)
    sys.exit(2)

# Use lexical-existence check (symlink counts as existing even if target is broken).
if not os.path.lexists(lexical):
    print(f"[pre-archive-scan] ERROR: target does not exist: {target_rel}", file=sys.stderr)
    sys.exit(2)

# Detect and report symlinks.
is_link = os.path.islink(lexical)
link_target = os.readlink(lexical) if is_link else None

if is_link:
    print(f"[pre-archive-scan] NOTE: {target_rel} is a symlink -> {link_target} (scanning inbound refs to the lexical link path, not following it)", file=sys.stderr)

tracked = subprocess.run(
    ["git", "-C", str(root), "ls-files"],
    check=True,
    text=True,
    capture_output=True,
).stdout.splitlines()

link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
plain_tokens = {target_rel, f"./{target_rel}"}
findings: list[tuple[str, int, str]] = []


def normalize_link(source_rel: str, raw_target: str) -> str | None:
    value = raw_target.strip().split()[0].strip("<>")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    source_dir = (root / source_rel).parent
    return (source_dir / path).resolve().relative_to(root).as_posix()


for rel in tracked:
    if rel == target_rel:
        continue
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    except OSError:
        continue

    for line_no, line in enumerate(text.splitlines(), start=1):
        matched = False
        for match in link_re.finditer(line):
            try:
                normalized = normalize_link(rel, match.group(1))
            except ValueError:
                normalized = None
            if normalized == target_rel:
                findings.append((rel, line_no, line.strip()))
                matched = True
                break
        if matched:
            continue
        if any(token in line for token in plain_tokens):
            findings.append((rel, line_no, line.strip()))

if findings:
    print(f"[pre-archive-scan] FAIL: inbound references to {target_rel}")
    for rel, line_no, line in findings:
        print(f"{rel}:{line_no}: {line}")
    sys.exit(1)

print(f"[pre-archive-scan] PASS: no inbound references to {target_rel}")
PY
