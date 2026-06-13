#!/usr/bin/env python3
"""Verify context_sanitizer is imported and called in agent_executor.py (Phase 165)."""
import sys
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "agent_executor.py"
src = EXECUTOR.read_text()

checks = [
    ("import context_sanitizer", "from context_sanitizer import sanitize_tool_result" in src or "_sanitize_tool_result" in src),
    ("_CONTEXT_SANITIZER_AVAILABLE flag", "_CONTEXT_SANITIZER_AVAILABLE" in src),
    ("sanitize_tool_result called on formatted_result", "_sanitize_tool_result(" in src and "formatted_result" in src),
    ("violation logging", "_violations" in src and "context_sanitizer:" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: context_sanitizer wiring missing: {failed}")
    sys.exit(1)

print("PASS: context_sanitizer wired into agent_executor tool result path")
