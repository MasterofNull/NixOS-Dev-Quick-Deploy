#!/usr/bin/env python3
"""Verify JSON embedded-newline sanitizer is in tool_registry.py (Phase 165 iter 20)."""
import sys
from pathlib import Path

TOOL_REGISTRY = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "tool_registry.py"
src = TOOL_REGISTRY.read_text()

checks = [
    ("_sanitize_json function defined", "_sanitize_json" in src),
    ("sanitizer handles embedded newlines", '\\\\n' in src or '"\\\\n"' in src or "\\\\n" in src or "escape bare control" in src.lower()),
    ("sanitizer called in parse fallback", "json.JSONDecodeError" in src and "_sanitize_json" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: JSON sanitizer missing elements: {failed}")
    sys.exit(1)

# Functional test: parse JSON with embedded literal newline
import json
sys.path.insert(0, str(TOOL_REGISTRY.parent))
try:
    from tool_registry import ToolRegistry
    r = ToolRegistry.__new__(ToolRegistry)
    r._tools = {}
    bad_json = '{"function": "edit_file", "arguments": {"old_string": "line 1\nline 2", "new_string": "x"}}'
    tc = r.parse_tool_call_from_llama(bad_json)
    if tc is None or tc.tool_name != "edit_file":
        print("FAIL: parse_tool_call_from_llama returned None for embedded-newline JSON")
        sys.exit(1)
except Exception as e:
    print(f"FAIL: functional test error: {e}")
    sys.exit(1)

print("PASS: JSON embedded-newline sanitizer verified in tool_registry.py")
