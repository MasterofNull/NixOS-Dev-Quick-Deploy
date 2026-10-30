#!/usr/bin/env python3
"""
test-radar-ingest.py — Verification suite for aq-radar-ingest (list + discover).

Runs against a temp copy of the registry so the tracked config is never touched.
`scan` is excluded: it needs the network and writes under .agent/research/.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / "scripts/ai/aq-radar-ingest"
REGISTRY = ROOT / "config/frontier-radar-registry.json"


def test_radar_lifecycle():
    assert CLI.is_file() and os.access(CLI, os.X_OK), "CLI missing or non-executable"

    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.json"
        shutil.copyfile(REGISTRY, reg)
        env = {**os.environ, "AQ_RADAR_REGISTRY_PATH": str(reg),
               "AQ_RADAR_STATE_PATH": str(Path(tmp) / "state.json")}

        res_list = subprocess.run([sys.executable, str(CLI), "list"], capture_output=True, text=True, env=env)
        assert res_list.returncode == 0
        assert "Frontier Radar Registry" in res_list.stdout
        assert "cisa-kev" in res_list.stdout

        res_disc = subprocess.run([
            sys.executable, str(CLI), "discover",
            "--id", "test-discovered-lab",
            "--name", "Test Frontier Lab",
            "--category", "discovered_targets",
            "--url", "https://example.org/feed.xml",
            "--type", "rss",
            "--trust-tier", "tier2_peer_reviewed",
            "--context", "Automated test discovery",
        ], capture_output=True, text=True, env=env)
        assert res_disc.returncode == 0
        assert "Dynamically registered new radar source" in res_disc.stdout

        data = json.loads(reg.read_text(encoding="utf-8"))
        assert "test-discovered-lab" in [s["id"] for s in data["sources"]]
    print("PASS: aq-radar-ingest lifecycle (list, discover, persistence) verified")


def main():
    test_radar_lifecycle()
    print("ALL RADAR INGEST TESTS PASSED")


if __name__ == "__main__":
    main()
