#!/usr/bin/env python3
"""
test-radar-ingest.py — Verification suite for aq-radar-ingest.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "scripts/ai/aq-radar-ingest"
REGISTRY = ROOT / "config/frontier-radar-registry.json"


def test_radar_lifecycle():
    assert CLI.is_file() and os.access(CLI, os.X_OK), "CLI missing or non-executable"

    # 1. Test list
    res_list = subprocess.run([sys.executable, str(CLI), "list"], capture_output=True, text=True)
    assert res_list.returncode == 0
    assert "Frontier Radar Registry" in res_list.stdout
    assert "cisa-kev" in res_list.stdout

    # 2. Test discover
    res_disc = subprocess.run([
        sys.executable, str(CLI), "discover",
        "--id", "test-discovered-lab",
        "--name", "Test Frontier Lab",
        "--category", "discovered_targets",
        "--url", "https://example.org/feed.xml",
        "--type", "rss",
        "--trust-tier", "tier2_peer_reviewed",
        "--context", "Automated test discovery"
    ], capture_output=True, text=True)
    assert res_disc.returncode == 0
    assert "Dynamically registered new radar source" in res_disc.stdout

    # Verify written
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["sources"]]
    assert "test-discovered-lab" in ids

    # 3. Test scan
    res_scan = subprocess.run([sys.executable, str(CLI), "scan"], capture_output=True, text=True)
    assert res_scan.returncode == 0
    assert "Scan complete" in res_scan.stdout

    # Clean up test entry
    data["sources"] = [s for s in data["sources"] if s["id"] != "test-discovered-lab"]
    REGISTRY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("PASS: aq-radar-ingest lifecycle (list, discover, scan, persistence) verified")


def main():
    import os
    test_radar_lifecycle()
    print("ALL RADAR INGEST TESTS PASSED")


if __name__ == "__main__":
    main()
