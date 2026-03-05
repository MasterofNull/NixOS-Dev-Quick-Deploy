#!/usr/bin/env python3
"""Compatibility shim for scripts/governance/skill-bundle-registry.py."""
import runpy
from pathlib import Path
runpy.run_path(str((Path(__file__).resolve().parent / "governance" / "skill-bundle-registry.py")), run_name="__main__")
