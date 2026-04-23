#!/usr/bin/env python3
"""
Verify that every check_pattern call in verify-flake-first-roadmap-completion.sh
references a pattern that actually exists in the target file.

This prevents the "pattern removed from code but verifier still checks it" class
of drift — e.g., the X-AI-Profile incident (2026-04-20) where a test was
restructured but the verifier kept checking a deleted string.

Usage:
    python3 scripts/testing/verify-self-consistency.py
    # Exit 0 = all clean.  Exit 1 = stale/broken patterns found.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "testing" / "verify-flake-first-roadmap-completion.sh"

# Matches both single-quoted and double-quoted pattern args
CHECK_RE = re.compile(
    r"""check_pattern\s+"([^"]+)"\s+['"]([^'"]+)['"]\s+['"]([^'"]+)['"]"""
)


def _grep_ok(pattern: str, file_path: Path) -> bool:
    """Return True if pattern matches at least one line in file_path."""
    result = subprocess.run(
        ["grep", "-qE", pattern, str(file_path)],
        capture_output=True,
    )
    return result.returncode == 0


def main() -> int:
    if not VERIFIER.exists():
        print(f"[ERROR] verifier script not found: {VERIFIER}", file=sys.stderr)
        return 2

    text = VERIFIER.read_text(encoding="utf-8")
    checks = CHECK_RE.findall(text)

    missing_files: list[str] = []
    stale_patterns: list[str] = []

    for file_rel, pattern, label in checks:
        target = ROOT / file_rel
        if not target.exists():
            missing_files.append(f"  FILE_MISSING  {file_rel!r}  ({label})")
            continue
        if not _grep_ok(pattern, target):
            stale_patterns.append(
                f"  PATTERN_MISS  {file_rel!r}\n"
                f"    pattern : {pattern!r}\n"
                f"    label   : {label}"
            )

    total = len(checks)
    failures = len(missing_files) + len(stale_patterns)

    if failures:
        print(f"[FAIL] {failures} stale/broken verifier check(s) out of {total} total:")
        for entry in missing_files + stale_patterns:
            print(entry)
        return 1

    print(f"[PASS] all {total} verifier check_pattern references confirmed in their target files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
