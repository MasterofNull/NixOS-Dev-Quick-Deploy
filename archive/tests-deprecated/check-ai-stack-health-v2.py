#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
HEALTH_SHIM = ROOT_DIR / "scripts" / "testing" / "check-ai-stack-health.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compatibility shim over the current declarative AI stack health checks."
    )
    parser.add_argument(
        "-v",
        "--with-qa",
        action="store_true",
        dest="with_qa",
        help="Also run aq-qa phase 0 through the health shim.",
    )
    parser.add_argument(
        "qa_args",
        nargs=argparse.REMAINDER,
        help="Optional extra arguments forwarded after --with-qa to aq-qa.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cmd = [str(HEALTH_SHIM)]
    if args.with_qa:
        cmd.append("--with-qa")
        cmd.extend(args.qa_args)
    print(
        "scripts/testing/check-ai-stack-health-v2.py is a compatibility shim over "
        "check-ai-stack-health.sh.",
        flush=True,
    )
    proc = subprocess.run(cmd, cwd=ROOT_DIR, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
