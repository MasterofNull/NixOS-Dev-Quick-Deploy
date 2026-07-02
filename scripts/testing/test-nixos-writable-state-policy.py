#!/usr/bin/env python3
"""Compatibility wrapper for the Rust writable-state contract validator."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "harness-contracts",
            "--",
            "writable-state",
            "--root",
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
