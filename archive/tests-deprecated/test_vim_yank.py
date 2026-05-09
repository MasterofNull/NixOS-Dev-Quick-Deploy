#!/usr/bin/env python3
"""Compatibility shim for test-vim-yank.py."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().with_name("test-vim-yank.py")), run_name="__main__")
