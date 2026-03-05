#!/usr/bin/env python3
"""Compatibility shim for ai-stack-manager.py."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().with_name("ai-stack-manager.py")), run_name="__main__")
