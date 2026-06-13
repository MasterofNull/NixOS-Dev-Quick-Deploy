#!/usr/bin/env python3
"""Verify BEHAVIORAL CONTRACT READ LIMIT rule is in agent_executor.py (Phase 165 iter 18)."""
import sys
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "agent_executor.py"
src = EXECUTOR.read_text()

checks = [
    ("READ LIMIT rule present", "READ LIMIT:" in src),
    ("4-read cap in rule", "4 read_file" in src or "At most 4" in src),
    ("edit_file fallback instruction in rule", "old_string not found" in src and "THEN read more" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: BEHAVIORAL CONTRACT READ LIMIT rule missing elements: {failed}")
    sys.exit(1)

print("PASS: BEHAVIORAL CONTRACT READ LIMIT rule verified in agent_executor.py")
