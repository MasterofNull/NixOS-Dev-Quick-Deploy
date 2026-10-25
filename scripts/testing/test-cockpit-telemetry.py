#!/usr/bin/env python3
"""scripts/testing/test-cockpit-telemetry.py

Unit tests for cockpit telemetry bridge, stream card assets, and operator guidance guide.
"""

from __future__ import annotations
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MONITOR_SCRIPT = REPO_ROOT / "scripts" / "ai" / "aq-cockpit-monitor"
INTERACTIVE_SCRIPT = REPO_ROOT / "scripts" / "ai" / "aq-subagent-interactive"
STREAM_CARD = REPO_ROOT / "assets" / "cockpit" / "stream-card.html"
GUIDE_DOC = REPO_ROOT / "docs" / "operations" / "AQ-COCKPIT-STREAM-GUIDE.md"


class TestCockpitTelemetry(unittest.TestCase):
    def test_scripts_executable_and_present(self):
        self.assertTrue(MONITOR_SCRIPT.is_file(), f"Missing {MONITOR_SCRIPT}")
        self.assertTrue(INTERACTIVE_SCRIPT.is_file(), f"Missing {INTERACTIVE_SCRIPT}")

    def test_stream_card_asset_valid(self):
        self.assertTrue(STREAM_CARD.is_file(), f"Missing {STREAM_CARD}")
        content = STREAM_CARD.read_text(encoding="utf-8")
        self.assertIn("cockpit-stream-card", content)
        self.assertIn("intervention-dock", content)
        self.assertIn("[p] Pause", content)

    def test_operator_guide_present(self):
        self.assertTrue(GUIDE_DOC.is_file(), f"Missing {GUIDE_DOC}")
        content = GUIDE_DOC.read_text(encoding="utf-8")
        self.assertIn("AQ-Cockpit", content)
        self.assertIn("Operator Steering & Intervention", content)


if __name__ == "__main__":
    unittest.main()
