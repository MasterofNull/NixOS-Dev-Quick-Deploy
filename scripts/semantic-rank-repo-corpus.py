#!/usr/bin/env python3
"""Compatibility shim for scripts/data/semantic-rank-repo-corpus.py."""
import runpy
from pathlib import Path
runpy.run_path(str((Path(__file__).resolve().parent / "data" / "semantic-rank-repo-corpus.py")), run_name="__main__")
