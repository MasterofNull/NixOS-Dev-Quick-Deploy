#!/usr/bin/env bash
set -euo pipefail

# Validate local markdown link targets.
# Modes:
#   --active : operator-facing docs surface
#   --all    : full repo markdown set

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:---active}"

usage() {
  cat <<'EOF'
Usage: scripts/governance/check-doc-links.sh [--active|--all]

Checks markdown links for missing local targets.
- --active: checks README.md, AGENTS.md, CLAUDE.md, and docs/ excluding docs/archive/
- --all: checks all markdown files in repo
EOF
}

case "${MODE}" in
  --active|--all) ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "[check-doc-links] Unknown mode: ${MODE}" >&2
    usage
    exit 1
    ;;
esac

python3 - "${ROOT_DIR}" "${MODE}" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
mode = sys.argv[2]

link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

def should_skip_target(target: str) -> bool:
    t = target.strip()
    if not t:
        return True
    if t.startswith("#"):
        return True
    if "://" in t:
        return True
    if t.startswith("mailto:"):
        return True
    if t.startswith("file://"):
        return True
    return False

def is_markdown_target(target: str) -> bool:
    t = target.strip().split("#", 1)[0].strip()
    if not t:
        return False
    # Only validate documentation links in this checker.
    return t.endswith(".md")

def collect_files():
    if mode == "--all":
        return [p for p in root.rglob("*.md") if p.is_file()]
    files = []
    for top in ["README.md", "AGENTS.md", "CLAUDE.md"]:
        p = root / top
        if p.exists():
            files.append(p)
    for p in (root / "docs").rglob("*.md"):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("docs/archive/"):
            continue
        if rel.startswith("docs/development/"):
            continue
        files.append(p)
    return sorted(set(files))

def resolve_target(src: pathlib.Path, target: str):
    # Strip optional title content: path "title"
    t = target.strip()
    if " " in t and not t.startswith("/"):
        t = t.split(" ", 1)[0]
    t = t.split("#", 1)[0]
    if not t:
        return None
    if t.startswith("/"):
        return (root / t.lstrip("/")).resolve()
    return (src.parent / t).resolve()

errors = []
for md in collect_files():
    text = md.read_text(encoding="utf-8", errors="ignore")
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in link_re.finditer(line):
            target = m.group(1).strip()
            if should_skip_target(target):
                continue
            if not is_markdown_target(target):
                continue
            resolved = resolve_target(md, target)
            if resolved is None:
                continue
            if not resolved.exists():
                errors.append((md.relative_to(root).as_posix(), idx, target))

if errors:
    print("[check-doc-links] FAIL: broken local links found")
    for path, line, target in errors[:400]:
        print(f"{path}:{line}: {target}")
    print(f"[check-doc-links] Total broken links: {len(errors)}")
    sys.exit(1)

print("[check-doc-links] PASS: no broken local links")
PY
