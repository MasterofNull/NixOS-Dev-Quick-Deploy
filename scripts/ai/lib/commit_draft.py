"""Deterministic commit-message draft from the staged diff (no LLM)."""
from __future__ import annotations

import os
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

MAX_FILES = 15


def staged(repo: Path) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "diff", "--cached", "--name-status", "--no-renames"], cwd=repo,
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if path:
            rows.append((status[:1], path))
    return rows


def _scope(paths: list[str]) -> str:
    parts = Counter()
    for p in paths:
        segs = Path(p).parts
        # Prefer the meaningful component: scripts/ai/lib/x.py -> ai, nix/modules/... -> nix.
        if len(segs) >= 3 and segs[0] in ("scripts", "ai-stack"):
            parts[segs[1]] += 1
        elif len(segs) >= 2:
            parts[segs[0].lstrip(".")] += 1
        else:
            parts["repo"] += 1
    return parts.most_common(1)[0][0]


def _type(rows: list[tuple[str, str]]) -> str:
    paths = [p for _, p in rows]
    if all(p.startswith(("scripts/testing/", "tests/")) for p in paths):
        return "test"
    if all(p.endswith(".md") for p in paths):
        return "docs"
    added = any(s == "A" for s, p in rows if not p.startswith(("scripts/testing/", "tests/", "docs/")))
    if added:
        return "feat"
    if any(p.startswith("nix/") or p.endswith((".py", ".sh")) for p in paths):
        return "fix"
    return "chore"


def draft(repo: Path) -> str | None:
    rows = staged(repo)
    if not rows:
        return None
    paths = [p for _, p in rows]
    groups: dict[str, list[str]] = defaultdict(list)
    for status, path in rows:
        groups[str(Path(path).parent)].append(f"{status} {Path(path).name}")
    lines, shown = [], 0
    for directory in sorted(groups):
        for entry in groups[directory]:
            if shown == MAX_FILES:
                break
            lines.append(f"- {directory}/: {entry}")
            shown += 1
    if len(rows) > MAX_FILES:
        lines.append(f"- +{len(rows) - MAX_FILES} more")
    agent = os.environ.get("AQ_AGENT_NAME") or "<agent>"
    header = f"{_type(rows)}({_scope(paths)}): <summary>"
    return "\n".join([header, "", *lines, "", "Root cause: <required for fixes>", "",
                      f"Co-Authored-By: {agent} <noreply@anthropic.com>"]) + "\n"
