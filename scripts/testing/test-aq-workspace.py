#!/usr/bin/env python3
"""
test-aq-workspace.py — Validation test suite for the SOTA Agentic Workspace.

Verifies:
  1. aq-workspace CLI options (--help, status, --tui --once, tree)
  2. aq-cockpit-monitor snapshot and health probes
  3. aq-fleet-monitor snapshot, tree hierarchy, and agent filter
  4. aq-agent-window custom model support and subagent tracking
  5. aq-coordinator-repl CLI interface
  6. Zellij KDL layout syntax and dual-board floating panes structure
  7. File permissions (executable bits)
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
            SCRIPTS_AI / "aq-agent-launcher",
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
        self.assertIn("Floating Panes Navigation", res.stdout)
        self.assertIn("Supported Models in Windows", res.stdout)

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
        self.assertIn("Delegated Sub-Agent Fleet", res.stdout)

    def test_fleet_monitor_tree(self):
        """Verify aq-fleet-monitor --tree renders delegation hierarchy."""
        cmd = [str(SCRIPTS_AI / "aq-fleet-monitor"), "--tree", "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-fleet-monitor --tree failed: {res.stderr}")
        self.assertIn("Sub-Agent Delegation Hierarchy Tree", res.stdout)
        self.assertIn("Sovereign Swarm Orchestrator", res.stdout)

    def test_fleet_monitor_agent_filter(self):
        """Verify aq-fleet-monitor --agent claude filters by parent agent."""
        cmd = [str(SCRIPTS_AI / "aq-fleet-monitor"), "--agent", "claude", "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-fleet-monitor --agent claude failed: {res.stderr}")
        self.assertIn("claude", res.stdout.lower())

    def test_agent_window_subagents(self):
        """Verify aq-agent-window --subagents outputs subagents and operations."""
        cmd = [str(SCRIPTS_AI / "aq-agent-window"), "--subagents"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-agent-window --subagents failed: {res.stderr}")
        self.assertIn("Active Sub-Agent Delegations", res.stdout)

    def test_agent_window_custom_model(self):
        """Verify aq-agent-window accepts any model string."""
        cmd = [str(SCRIPTS_AI / "aq-agent-window"), "--lane", "deepseek-r1", "--subagents"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-agent-window custom model failed: {res.stderr}")
        self.assertIn("deepseek", res.stdout.lower())

    def test_coordinator_repl_help(self):
        """Verify aq-coordinator-repl --help returns 0 and lists routing."""
        cmd = [str(SCRIPTS_AI / "aq-coordinator-repl"), "--help"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-coordinator-repl --help failed: {res.stderr}")
        self.assertIn("Coordinator Console", res.stdout)

    def test_workspace_tui_once(self):
        """Verify aq-workspace --tui --once renders dual-board layout."""
        cmd = [str(SCRIPTS_AI / "aq-workspace"), "--tui", "--once"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-workspace --tui --once failed: {res.stderr}")
        self.assertIn("Left Board: Main Agents", res.stdout)
        self.assertIn("Sub-Agent Delegation Hierarchy", res.stdout)

    def test_zellij_floating_layout(self):
        """Verify Zellij KDL layout file exists and defines floating panes with left/right alignment."""
        self.assertTrue(ZELLIJ_LAYOUT.is_file(), f"Missing layout file: {ZELLIJ_LAYOUT}")
        content = ZELLIJ_LAYOUT.read_text(encoding="utf-8")
        self.assertIn("floating_panes", content)
        self.assertIn("Left Board", content)
        self.assertIn("Swarm & Sub-Agents", content)
        self.assertIn("Floating Swarm Board", content)
        self.assertIn("Claude & Sub-Agents", content)
        self.assertIn("Codex & Sub-Agents", content)
        self.assertIn("Gemini & Sub-Agents", content)
        self.assertIn("Local Qwen & Sub-Agents", content)

    def test_agent_launcher_syntax_and_lanes(self):
        """Verify aq-agent-launcher syntax and lane resolution."""
        cmd = ["bash", "-n", str(SCRIPTS_AI / "aq-agent-launcher")]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"aq-agent-launcher syntax error: {res.stderr}")
        content = (SCRIPTS_AI / "aq-agent-launcher").read_text(encoding="utf-8")
        self.assertIn("claude", content)
        self.assertIn("codex", content)
        self.assertIn("local", content)
        self.assertIn("gemini", content)
        self.assertIn("get_auth_status", content)


if __name__ == "__main__":
    unittest.main()
