#!/usr/bin/env python3
"""
# Skill: aidb-knowledge

Deterministic helper that lets local agents query the repository knowledge base
without depending on the private AI-Optimizer stack. The script scans `docs/`
inside the repo and surfaces matching files, line numbers, and snippets.

Usage examples:

```bash
python .agent/skills/aidb-knowledge/SKILL.md --search "Phase 9" --limit 5
python .agent/skills/aidb-knowledge/SKILL.md --list --project Hyper-NixOS
python .agent/skills/aidb-knowledge/SKILL.md --show docs/AGENTS.md
```
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = REPO_ROOT / "docs"


def iter_docs(docs_root: Path):
    for path in sorted(docs_root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        yield path


def list_documents(docs_root: Path, project: str) -> None:
    print(f"📚 Documents for project '{project}' under {docs_root}")
    for path in iter_docs(docs_root):
        rel = path.relative_to(REPO_ROOT)
        print(f"- {rel}")


def show_document(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")
    print(dedent(
        f"""
        ──────────────────────────────────────────────────────────────
        {path.relative_to(REPO_ROOT)}
        ──────────────────────────────────────────────────────────────
        """
    ))
    print(path.read_text())


def search_documents(docs_root: Path, query: str, limit: int) -> None:
    matches = 0
    q = query.lower()
    for doc in iter_docs(docs_root):
        text = doc.read_text(errors="ignore")
        lowered = text.lower()
        if q not in lowered:
            continue
        rel = doc.relative_to(REPO_ROOT)
        lines = text.splitlines()
        found_line = next(
            (
                f"{idx + 1}: {line.strip()}"
                for idx, line in enumerate(lines)
                if q in line.lower()
            ),
            None,
        )
        print(f"✅ {rel}")
        if found_line:
            print(f"    {found_line}")
        matches += 1
        if matches >= limit:
            break
    if matches == 0:
        print(f"No matches for '{query}' in {docs_root}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local documentation lookup helper")
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS_DIR, help="Docs directory (default: %(default)s)")
    parser.add_argument("--project", default="NixOS-Dev-Quick-Deploy", help="Logical project label for display only")
    parser.add_argument("--search", help="Keyword to search for inside docs")
    parser.add_argument("--limit", type=int, default=10, help="Max search matches to show")
    parser.add_argument("--list", action="store_true", help="List every markdown file under --docs")
    parser.add_argument("--show", type=Path, help="Print the contents of the specified document")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    docs_dir = args.docs

    if not docs_dir.exists():
        parser.error(f"Docs directory not found: {docs_dir}")

    if args.list:
        list_documents(docs_dir, args.project)
        return 0

    if args.show:
        target = args.show if args.show.is_absolute() else docs_dir / args.show
        show_document(target)
        return 0

    if args.search:
        search_documents(docs_dir, args.search, args.limit)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
