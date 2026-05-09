#!/usr/bin/env python3
"""Compatibility shim over the current declarative AI stack health checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "scripts" / "testing" / "check-ai-stack-health.sh"
    cmd = [str(target), *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
