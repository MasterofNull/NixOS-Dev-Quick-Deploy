#!/usr/bin/env python3
"""Fail when a workflow masks a failure without saying why.

A workflow line containing `|| true` or `continue-on-error: true` must carry a
`# KNOWN-FAILING:` or `# NON-GATING:` comment on the same line or the line above,
so a gate cannot be silently made always-pass.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MASK = re.compile(r"\|\|\s*true\b|continue-on-error:\s*true\b")
ANNOTATION = re.compile(r"#\s*(KNOWN-FAILING|NON-GATING):\s*\S")


def scan_text(text: str) -> list[int]:
    """Return 1-based line numbers of unannotated masks."""
    lines = text.splitlines()
    bad = []
    for i, line in enumerate(lines):
        code = line.lstrip()
        if code.startswith("#") or not MASK.search(line):
            continue
        prev = lines[i - 1] if i else ""
        if ANNOTATION.search(line) or ANNOTATION.search(prev):
            continue
        bad.append(i + 1)
    return bad


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    failures = 0
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        for n in scan_text(path.read_text()):
            print(f"{path.relative_to(root)}:{n}: failure mask without '# KNOWN-FAILING:' or '# NON-GATING:' annotation", file=sys.stderr)
            failures += 1
    if failures:
        print(f"check-workflow-masks: FAIL ({failures} unannotated mask(s))", file=sys.stderr)
        return 1
    print("check-workflow-masks: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
