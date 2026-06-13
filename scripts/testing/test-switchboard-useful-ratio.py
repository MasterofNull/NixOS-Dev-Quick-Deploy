#!/usr/bin/env python3
"""Verify switchboard.py emits useful_ratio=1.0 in both token_usage emission sites (Phase 166)."""
import sys
from pathlib import Path

SWITCHBOARD = Path(__file__).resolve().parents[2] / "ai-stack" / "switchboard" / "switchboard.py"
src = SWITCHBOARD.read_text()

# Find both token_usage emission blocks
site1_ok = 'usage["useful_ratio"] = 1.0' in src or "usage['useful_ratio'] = 1.0" in src
site2_ok = '"useful_ratio": 1.0' in src

checks = [
    ("switchboard.py exists and readable", src != ""),
    ("site 1 (llama.cpp usage block) has useful_ratio injection", site1_ok),
    ("site 2 (estimated fallback block) has useful_ratio key", site2_ok),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: switchboard useful_ratio emission missing: {failed}")
    sys.exit(1)

# Verify site 1 precedes first token_usage_emitted = True
idx1 = src.find('usage["useful_ratio"] = 1.0')
if idx1 < 0:
    idx1 = src.find("usage['useful_ratio'] = 1.0")
idx_emit1 = src.find("token_usage_emitted = True", idx1) if idx1 >= 0 else -1
if idx1 < 0 or idx_emit1 < 0 or idx1 > idx_emit1:
    print("FAIL: site 1 useful_ratio injection must precede token_usage_emitted = True")
    sys.exit(1)

print("PASS: switchboard.py emits useful_ratio=1.0 at both token_usage emission sites")
