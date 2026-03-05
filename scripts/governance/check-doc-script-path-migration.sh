#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ALIASES_FILE="${1:-config/legacy-root-script-aliases.txt}"

if [[ ! -f "${ALIASES_FILE}" ]]; then
  echo "[doc-script-migration] FAIL: missing aliases file: ${ALIASES_FILE}" >&2
  exit 2
fi

python3 - "${ROOT_DIR}" "${ALIASES_FILE}" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
aliases_file = Path(sys.argv[2])

aliases = {
    ln.strip()
    for ln in aliases_file.read_text(encoding="utf-8").splitlines()
    if ln.strip() and not ln.strip().startswith("#")
}

link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
legacy_cmd_re = re.compile(r"(?:^|[\s`])(?:\./)?([A-Za-z0-9._-]+\.(?:sh|py))(?=$|[\s`])")

def collect_docs():
    files = []
    for top in ["README.md", "AGENTS.md", "CLAUDE.md"]:
        p = root / top
        if p.exists():
            files.append(p)
    docs_dir = root / "docs"
    for p in docs_dir.rglob("*.md"):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("docs/archive/"):
            continue
        if rel.startswith("docs/development/"):
            continue
        files.append(p)
    return sorted(set(files))

violations = []
for md in collect_docs():
    rel = md.relative_to(root).as_posix()
    text = md.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    for idx, line in enumerate(lines, start=1):
        # 1) Legacy root script command mentions in active docs.
        for m in legacy_cmd_re.finditer(line):
            name = m.group(1)
            if name in aliases:
                violations.append((rel, idx, f"legacy_root_script_reference:{name}"))

        # 2) Markdown links that point to underscore scripts when kebab exists.
        for m in link_re.finditer(line):
            raw_target = m.group(1).strip()
            if not raw_target or "://" in raw_target or raw_target.startswith("#"):
                continue
            target = raw_target.split(" ", 1)[0].split("#", 1)[0]
            if not target:
                continue
            if not (target.endswith(".sh") or target.endswith(".py")):
                continue

            # If link target is a legacy root alias, fail.
            target_name = Path(target).name
            if "/" not in target and target_name in aliases:
                violations.append((rel, idx, f"legacy_link_target:{target_name}"))
                continue

            # If link points to scripts/... underscore path and kebab peer exists, fail.
            normalized = target.lstrip("/")
            if normalized.startswith("scripts/"):
                p = Path(normalized)
                stem = p.stem
                if "_" in stem:
                    kebab = p.with_name(stem.replace("_", "-") + p.suffix)
                    if (root / kebab).exists():
                        violations.append((rel, idx, f"underscore_script_link:{normalized} -> {kebab.as_posix()}"))

if violations:
    print("[doc-script-migration] FAIL: active docs contain pre-migration script references")
    for rel, line, msg in violations[:120]:
        print(f"{rel}:{line}: {msg}")
    print(f"[doc-script-migration] Total violations: {len(violations)}")
    sys.exit(1)

print("[doc-script-migration] PASS: active docs use migrated script paths.")
PY
