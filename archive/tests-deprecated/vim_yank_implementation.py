#!/usr/bin/env python3
"""Compatibility shim for vim-yank-implementation.py."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().with_name("vim-yank-implementation.py")), run_name="__main__")
