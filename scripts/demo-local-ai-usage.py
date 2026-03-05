#!/usr/bin/env python3
"""Compatibility shim for scripts/testing/demo-local-ai-usage.py."""
import runpy
from pathlib import Path
runpy.run_path(str((Path(__file__).resolve().parent / "testing" / "demo-local-ai-usage.py")), run_name="__main__")
