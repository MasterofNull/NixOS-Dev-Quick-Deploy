#!/usr/bin/env python3
"""Compatibility shim for scripts/data/rag-system-complete.py."""
import runpy
from pathlib import Path
runpy.run_path(str((Path(__file__).resolve().parent / "data" / "rag-system-complete.py")), run_name="__main__")
