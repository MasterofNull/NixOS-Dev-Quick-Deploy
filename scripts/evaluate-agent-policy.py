#!/usr/bin/env python3
"""Compatibility shim for scripts/governance/evaluate-agent-policy.py."""
import runpy
from pathlib import Path
runpy.run_path(str((Path(__file__).resolve().parent / "governance" / "evaluate-agent-policy.py")), run_name="__main__")
