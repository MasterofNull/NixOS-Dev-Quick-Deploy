#!/usr/bin/env python3
"""Validate the docs/dashboard visibility contract for staged slices.

The rule is intentionally path based. If a slice changes runtime surfaces that an
operator depends on, it must also stage at least one explanatory/visibility
surface: docs, plans, handoff evidence, or Command Center/dashboard code.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable


RUNTIME_PREFIXES = (
    "ai-stack/",
    "nix/modules/",
    "nix/roles/",
    "dashboard/backend/",
    "scripts/ai/",
    "scripts/automation/",
    "config/systemd/",
)

RUNTIME_SUFFIXES = (
    ".service",
    ".timer",
)

DOC_PREFIXES = (
    "docs/",
    ".agent/",
    ".agents/plans/",
    ".agents/scratchpad/",
)

DOC_FILENAMES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
)

DASHBOARD_PREFIXES = (
    "assets/dashboard",
    "dashboard.html",
    "dashboard/",
    "dashboard-v2.html",
)

GOVERNANCE_SELF_PREFIXES = (
    "scripts/governance/check-cross-surface-contract.py",
    "scripts/governance/tier0-validation-gate.sh",
)


def changed_files_from_git(mode: str) -> list[str]:
    if mode == "--pre-commit":
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    else:
        cmd = ["bash", "-lc", "{ git diff --name-only --diff-filter=ACM origin/main...HEAD 2>/dev/null || true; git diff --name-only --diff-filter=ACM 2>/dev/null || true; } | awk 'NF && !seen[$0]++'"]
    out = subprocess.check_output(cmd, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def is_runtime(path: str) -> bool:
    if path in GOVERNANCE_SELF_PREFIXES:
        return False
    if path.startswith(DOC_PREFIXES):
        return False
    if is_dashboard(path):
        return False
    if path.endswith("README.md") or path.endswith(".md"):
        return False
    return path.startswith(RUNTIME_PREFIXES) or path.endswith(RUNTIME_SUFFIXES)


def is_doc(path: str) -> bool:
    name = Path(path).name
    return path.startswith(DOC_PREFIXES) or name in DOC_FILENAMES or path.endswith("/README.md")


def is_dashboard(path: str) -> bool:
    return path.startswith(DASHBOARD_PREFIXES) or path in {"dashboard.html", "dashboard-v2.html"}


def summarize(paths: Iterable[str]) -> str:
    return "\n".join(f"  - {p}" for p in paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="--pre-commit", choices=("--pre-commit", "--pre-deploy"))
    parser.add_argument("files", nargs="*", help="Optional explicit file list for tests/dry-runs")
    args = parser.parse_args()

    changed = args.files or changed_files_from_git(args.mode)
    runtime = [p for p in changed if is_runtime(p)]
    if not runtime:
        print("PASS: no runtime/module/service changes detected")
        return 0

    docs = [p for p in changed if is_doc(p)]
    dashboard = [p for p in changed if is_dashboard(p)]
    if docs or dashboard:
        surfaces = []
        if docs:
            surfaces.append(f"docs/handoff surfaces: {len(docs)}")
        if dashboard:
            surfaces.append(f"dashboard surfaces: {len(dashboard)}")
        print("PASS: runtime changes include connected visibility surface (" + ", ".join(surfaces) + ")")
        return 0

    print("FAIL: runtime/module/service changes need connected documentation, dashboard visibility, or handoff evidence.", file=sys.stderr)
    print("Runtime changes:", file=sys.stderr)
    print(summarize(runtime), file=sys.stderr)
    print("\nStage at least one relevant docs/plan/handoff file or Command Center/dashboard surface.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
