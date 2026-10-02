#!/usr/bin/env python3
"""Verify health-spider keeps queued/running OSI checks healthy while in progress."""
import sys, re
from pathlib import Path

SPIDER = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-health-spider"
src = SPIDER.read_text()

checks = [
    ("osi_layered_ready probe present", "osi_layered_ready" in src),
    # The producer represents queued and active work with pending:true.
    ("in-progress pending probe stays healthy",
     'if data.get("pending") is True:\n            return ""' in src),
    # In-progress work must not be reported as a pending failure.
    ("old vulnerable condition removed",
     'if data.get("pending") is True:\n            return "osi_layered_pending"' not in src),
    ("dashboard recovery resolver present", "def _resolve_recovered_dashboard_probe_alerts" in src),
    (
        "dashboard recovery uses attention queue",
        "get_pending(\"health-spider\")" in src
        and "resolve(alert.get(\"id\", \"\"), \"rejected\", resolved_by=\"health-spider-recovered\")" in src,
    ),
    ("dashboard probe OK resolves stale alert", "_resolve_recovered_dashboard_probe_alerts" in src and "resolved {recovered} recovered alert(s)" in src),
    (
        "apparmor scan bounded by service activation",
        "def _service_active_since_epoch" in src
        and "ActiveEnterTimestamp" in src
        and "since = max(since, active_since)" in src,
    ),
]

failed = [name for name, ok in checks if not ok]
if failed:
    print(f"FAIL: osi_layered_ready probe missing elements: {failed}")
    sys.exit(1)

# Extract just the osi_layered_ready block via regex and verify the pending contract.
block_match = re.search(
    r'if check == "osi_layered_ready":(.*?)(?=\n    if check ==|\Z)',
    src, re.DOTALL
)
if not block_match:
    print("FAIL: could not find osi_layered_ready block in source")
    sys.exit(1)

block = block_match.group(1)
# Queued or active work must return healthy until the next probe observes a result.
if 'if data.get("pending") is True:\n            return ""' not in block:
    print(f"FAIL: osi_layered_ready block does not treat pending work as healthy:\n{block[:300]}")
    sys.exit(1)

print("PASS: health-spider osi_layered_ready probe correctly tolerates in-progress pending state")
