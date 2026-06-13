#!/usr/bin/env python3
"""Verify exploration stagnation guard (reads-without-edit) is in agent_executor.py (Phase 165)."""
import sys
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "agent_executor.py"
src = EXECUTOR.read_text()

checks = [
    ("reads_without_edit counter", "_reads_without_edit" in src),
    ("soft nudge threshold", "_MAX_READS_WITHOUT_EDIT" in src),
    ("hard abort threshold", "_READS_HARD_LIMIT" in src),
    ("reset on edit/write", '"edit_file"' in src and '"write_file"' in src and "_reads_without_edit = 0" in src),
    ("exploration stagnation abort", "Exploration stagnation" in src),
    ("nudge injection into messages", "_exploration_nudge_sent" in src),
    ("nudge text references edit_file", "EXPLORATION WARNING" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: exploration stagnation guard missing: {failed}")
    sys.exit(1)

# Verify threshold values are reasonable
import re
hard = re.search(r"_READS_HARD_LIMIT\s*=\s*(\d+)", src)
soft = re.search(r"_MAX_READS_WITHOUT_EDIT\s*=\s*(\d+)", src)
if hard and soft:
    h, s = int(hard.group(1)), int(soft.group(1))
    if not (s < h):
        print(f"FAIL: soft ({s}) must be < hard ({h})")
        sys.exit(1)
    if h > 20:
        print(f"FAIL: hard limit too large ({h}), should be <= 20 to prevent runaway loops")
        sys.exit(1)

print("PASS: exploration stagnation guard present and thresholds reasonable")
