#!/usr/bin/env python3
"""Tests must locate the repo from __file__, never from this host's checkout path.

Regression (2026-10-01): test-candidate-lifecycle.py imported from
/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/..., so QA check 0.150.1 could only
pass on the owner's machine and failed on CI runners.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = re.compile(r"""["']/home/[^/"']+/[^"']*NixOS-Dev-Quick-Deploy""")


def main() -> int:
    offenders = []
    for path in sorted((ROOT / "scripts" / "testing").rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if HOST_REPO.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    if offenders:
        print("FAIL: host-specific repo paths in tests (derive from __file__):\n  " + "\n  ".join(offenders))
        return 1
    print("PASS: no host-specific repo paths in scripts/testing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
