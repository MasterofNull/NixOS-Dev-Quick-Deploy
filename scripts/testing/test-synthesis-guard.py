#!/usr/bin/env python3
"""Verify synthesis guard for tool-call-as-final-result is in agent_executor.py (Phase 165)."""
import sys
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "agent_executor.py"
src = EXECUTOR.read_text()

checks = [
    ("tool-call JSON detection", "startswith('{\"function\"')" in src or 'startswith(\'{"function"\')' in src),
    ("COMPLETED: prefix request in synthesis", "COMPLETED:" in src),
    ("256-token prose synthesis budget", "256" in src and ("prose" in src or "synthesis" in src or "syn_tokens" in src)),
    ("final-response-is-tool-call warning", "final-response-is-tool-call" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: synthesis guard missing elements: {failed}")
    sys.exit(1)

print("PASS: synthesis guard present in agent_executor.py")
