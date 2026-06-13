#!/usr/bin/env python3
"""Verify health-spider osi_layered_ready probe tolerates running:True (Phase 166)."""
import sys, re
from pathlib import Path

SPIDER = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-health-spider"
src = SPIDER.read_text()

checks = [
    ("osi_layered_ready probe present", "osi_layered_ready" in src),
    # Condition must include 'and not data.get("running")' or single-quote variant
    ("probe tolerates running:True",
     'and not data.get("running")' in src or "and not data.get('running')" in src),
    # The original vulnerable condition (no running check) must NOT be present
    ("old vulnerable condition removed",
     'if data.get("pending") is True:\n            return "osi_layered_pending"' not in src),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: osi_layered_ready probe missing elements: {failed}")
    sys.exit(1)

# Extract just the osi_layered_ready block via regex and verify the condition text
block_match = re.search(
    r'if check == "osi_layered_ready":(.*?)(?=\n    if check ==|\Z)',
    src, re.DOTALL
)
if not block_match:
    print("FAIL: could not find osi_layered_ready block in source")
    sys.exit(1)

block = block_match.group(1)
# Running warm-up line must contain 'and not data.get("running")'
if 'and not data.get("running")' not in block and "and not data.get('running')" not in block:
    print(f"FAIL: osi_layered_ready block does not have running guard:\n{block[:300]}")
    sys.exit(1)

print("PASS: health-spider osi_layered_ready probe correctly tolerates running:True transient state")
