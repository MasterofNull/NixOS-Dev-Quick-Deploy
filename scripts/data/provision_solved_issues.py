#!/usr/bin/env python3
"""Compatibility shim for scripts/data/provision-solved-issues.py."""

from __future__ import annotations

from pathlib import Path
import runpy


TARGET = Path(__file__).with_name("provision-solved-issues.py")


if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
