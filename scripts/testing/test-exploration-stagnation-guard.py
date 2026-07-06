#!/usr/bin/env python3
"""Verify exploration stagnation guard (reads-without-edit) is in agent_executor.py (Phase 165)."""
import sys
from pathlib import Path

EXECUTOR = Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents" / "agent_executor.py"
src = EXECUTOR.read_text()

checks = [
    ("reads_without_edit counter", "_reads_without_edit" in src),
    ("analysis-only task type set", "_ANALYSIS_ONLY_TASK_TYPES" in src),
    ("soft nudge threshold", "_MAX_READS_WITHOUT_EDIT" in src),
    ("hard abort threshold", "_READS_HARD_LIMIT" in src),
    ("implementation hard limit", "_IMPLEMENTATION_READS_HARD_LIMIT" in src and "AI_AGENT_IMPL_READS_HARD_LIMIT" in src),
    ("analysis hard limit", "_ANALYSIS_READS_HARD_LIMIT" in src and "AI_AGENT_ANALYSIS_READS_HARD_LIMIT" in src),
    ("repeated read path guard", "_read_path_counts" in src and "_REPEATED_READ_PATH_LIMIT" in src),
    ("analysis checkpoint reset", '"store_memory"' in src and "Analysis checkpoint stagnation" in src),
    ("reset on edit/write", '"edit_file"' in src and '"write_file"' in src and "_reads_without_edit = 0" in src),
    ("exploration stagnation abort", "Exploration stagnation" in src),
    ("nudge injection into messages", "_exploration_nudge_sent" in src),
    ("single-edit-first nudge text references edit_file", "STOP READING" in src and "exactly ONE edit" in src and "edit_file" in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: exploration stagnation guard missing: {failed}")
    sys.exit(1)

# Verify threshold values are reasonable
import re
impl_hard = re.search(r"_IMPLEMENTATION_READS_HARD_LIMIT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
impl_soft = re.search(r"_IMPLEMENTATION_MAX_READS_WITHOUT_EDIT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
analysis_hard = re.search(r"_ANALYSIS_READS_HARD_LIMIT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
analysis_soft = re.search(r"_ANALYSIS_MAX_READS_WITHOUT_CHECKPOINT\s*=\s*_env_int\([^,]+,\s*(\d+)\)", src)
if impl_hard and impl_soft and analysis_hard and analysis_soft:
    ih, isoft = int(impl_hard.group(1)), int(impl_soft.group(1))
    ah, asoft = int(analysis_hard.group(1)), int(analysis_soft.group(1))
    if not (isoft < ih <= 12):
        print(f"FAIL: implementation soft/hard limits invalid ({isoft}/{ih})")
        sys.exit(1)
    if not (12 < asoft < ah):
        print(f"FAIL: analysis soft/hard limits invalid ({asoft}/{ah})")
        sys.exit(1)
    if ah > 120:
        print(f"FAIL: analysis hard limit too large ({ah}), checkpoint guard should still bound runaway reads")
        sys.exit(1)

print("PASS: exploration stagnation guard present and thresholds reasonable")
