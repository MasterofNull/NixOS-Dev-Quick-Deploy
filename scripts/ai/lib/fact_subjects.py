#!/usr/bin/env python3
"""List shared fact subjects (.agent/memory/facts/) for session hydration. Read-only, never fails hydration.

Usage: fact_subjects.py <repo-root> [limit=20]. Newest first by last commit touching the file, falling
back to mtime for uncommitted files. Persona P3 design: .agents/plans/persona-p3-collapse-20261113/DESIGN.md
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _fm(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if text.startswith("---\n") and (end := text.find("\n---", 4)) != -1:
        for ln in text[4:end].splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                out[k.strip()] = v.split(" #", 1)[0].strip().strip("'\"")
    return out


def _lane(instance: str) -> str:
    s = instance.removeprefix("Simurg@").split("#", 1)[0]
    return s.split("/", 1)[0] if "/" in s else "?"


def _order(repo: Path, files: list[Path]) -> list[Path]:
    stamp: dict[Path, int] = {}
    for f in files:
        r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%ct", "--", str(f.relative_to(repo))],
                           capture_output=True, text=True, check=False)
        stamp[f] = int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else int(f.stat().st_mtime)
    return sorted(files, key=lambda f: (stamp[f], f.name), reverse=True)


def main(argv: list[str]) -> int:
    repo = Path(argv[1] if len(argv) > 1 else ".")
    limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 20
    d = repo / ".agent/memory/facts"
    files = sorted(d.glob("*.md")) if d.is_dir() else []
    if not files:
        print("(no fact files yet: .agent/memory/facts/)")
        return 0
    print(f"{len(files)} total; showing {min(limit, len(files))} newest (recall: rg <prefix> .agent/memory/facts/)")
    for f in _order(repo, files)[:limit]:
        fm = _fm(f.read_text(encoding="utf-8", errors="replace"))
        print(f"- {f.stem} ({_lane(fm.get('instance', ''))}): {fm.get('claim', '')[:100]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as e:  # hydration must never break
        print(f"(fact listing unavailable: {e})")
