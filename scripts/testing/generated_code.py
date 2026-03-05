#!/usr/bin/env python3
"""Compatibility shim for generated-code.py."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().with_name("generated-code.py")), run_name="__main__")
