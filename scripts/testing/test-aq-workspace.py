#!/usr/bin/env python3
"""
test-aq-workspace.py — Validation test suite for the SOTA Agentic Workspace.

Verifies:
  1. aq-workspace CLI options (--help, status, --tui --once)
  2. aq-cockpit-monitor snapshot and health probes
  3. aq-fleet-monitor snapshot and fleet parsing
  4. aq-coordinator-repl CLI interface
  5. Zellij KDL layout syntax and file structure
  6. File permissions (executable bits)
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_AI = REPO_ROOT / "scripts" / "ai"
ZELLIJ_LAYOUT = REPO_ROOT / "config" / "zellij" / "aq-agentic-workspace.kdl"


class TestAgenticWorkspace(unittest.TestCase):
    """Test suite for aq-workspace and associated components."""

    def test_script_permissions(self):
        """Verify executable bits are set on all workspace tools."""
        tools = [
            SCRIPTS_AI / "aq-workspace",
            SCRIPTS_AI / "aq-coordinator-repl",
            SCRIPTS_AI / "aq-fleet-monitor",
            SCRIPTS_AI / "aq-cockpit-monitor",
            SCRIPTS_AI / "aq-agent-window",
        ]
        for tool in tools:
            self.assertTrue(tool.is_file(), f"Tool missing: {tool}")
            mode = tool.stat().st_mode
            self.assertTrue(bool(mode & 0o111), f"Tool not executable: {tool}")

    def test_workspace_help(self):
        """Verify aq-workspace --help outputs valid usage."""
        cmd = [str(SCRIPTS_AI / "aq-workspace"), "--help"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-workspace --help failed: {res.stderr}")
        self.assertIn("AQ-OS SOTA Agentic Workspace", res.stdout)
        self.assertIn("Navigation in Tiled Workspace", res.stdout)

    def test_cockpit_monitor_once(self):
        """Verify aq-cockpit-monitor --once renders telemetry."""
        cmd = [str(SCRIPTS_AI / "aq-cockpit-monitor"), "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-cockpit-monitor --once failed: {res.stderr}")
        self.assertIn("AQ-OS Telemetry Cockpit", res.stdout)
        self.assertIn("AI Services", res.stdout)
        self.assertIn("Local Inference Engine", res.stdout)

    def test_fleet_monitor_once(self):
        """Verify aq-fleet-monitor --once renders fleet matrix."""
        cmd = [str(SCRIPTS_AI / "aq-fleet-monitor"), "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-fleet-monitor --once failed: {res.stderr}")
        self.assertIn("Sub-Agent Fleet Matrix", res.stdout)
        self.assertIn("Delegated Fleet Status", res.stdout)

    def test_coordinator_repl_help(self):
        """Verify aq-coordinator-repl --help returns 0 and lists routing."""
        cmd = [str(SCRIPTS_AI / "aq-coordinator-repl"), "--help"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-coordinator-repl --help failed: {res.stderr}")
        self.assertIn("Coordinator Console", res.stdout)

    def test_workspace_tui_once(self):
        """Verify aq-workspace --tui --once renders the 3-tile fallback layout."""
        cmd = [str(SCRIPTS_AI / "aq-workspace"), "--tui", "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-workspace --tui --once failed: {res.stderr}")
        self.assertIn("Coordinator Console", res.stdout)
        self.assertIn("Sub-Agent Fleet Matrix", res.stdout)
        self.assertIn("Telemetry Cockpit", res.stdout)

    def test_zellij_layout_file(self):
        """Verify Zellij KDL layout file exists and contains expected tab definitions."""
        self.assertTrue(ZELLIJ_LAYOUT.is_file(), f"Missing layout file: {ZELLIJ_LAYOUT}")
        content = ZELLIJ_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("Agentic Workspace", content)
        self.assertIn("Multi-Agent Studio", content)
        self.assertIn("Local Qwen", content)
        self.assertIn("Claude", content)
        self.assertIn("Codex", content)
        self.assertIn("Gemini", content)
        self.assertIn("Fleet Matrix", content)
        self.assertIn("Operations & Mesh", content)
        self.assertIn("Scratch Shell", content)
        self.assertIn("aq-coordinator-repl", content)
        self.assertIn("aq-agent-window", content)
        self.assertIn("aq-fleet-monitor", content)
        self.assertIn("aq-cockpit-monitor", content)


if __name__ == "__main__":
    unittest.main()
