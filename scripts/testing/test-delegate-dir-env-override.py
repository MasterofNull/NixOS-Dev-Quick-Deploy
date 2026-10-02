#!/usr/bin/env python3
"""Delegates must honor AQ_DELEGATION_DIR so sandboxed timers (ProtectHome=read-only) can write registry/outputs."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["delegate-to-codex", "delegate-to-claude", "delegate-to-local"]


def main() -> int:
    bad = []
    for name in REQUIRED:
        src = (ROOT / "scripts" / "ai" / name).read_text(encoding="utf-8")
        if not re.search(r'^DELEGATION_DIR="\$\{AQ_DELEGATION_DIR:-\$REPO_ROOT/\.agents/delegation\}"$', src, re.M):
            bad.append(name)
    if bad:
        print(f"FAIL: delegates ignore AQ_DELEGATION_DIR: {bad}")
        return 1
    print("PASS: delegates honor AQ_DELEGATION_DIR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
