#!/usr/bin/env python3
"""Unit tests for Claude Code / Harness lifecycle hooks (W3-S3)."""
import json
import os
import subprocess
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_SESSION_START = REPO_ROOT / "scripts" / "ai" / "aq-hook-session-start"
HOOK_STOP = REPO_ROOT / "scripts" / "ai" / "aq-hook-stop"
HOOK_POST_TOOL = REPO_ROOT / "scripts" / "ai" / "aq-hook-post-tool"


class TestHarnessHooks(unittest.TestCase):
    def test_session_start_hook_latency_and_output(self):
        t0 = time.perf_counter()
        res = subprocess.run([str(HOOK_SESSION_START)], capture_output=True, text=True, check=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(elapsed_ms, 100.0, f"SessionStart hook latency exceeded 100ms: {elapsed_ms:.2f}ms")
        self.assertEqual(res.returncode, 0)

    def test_stop_hook_latency_and_output(self):
        t0 = time.perf_counter()
        res = subprocess.run([str(HOOK_STOP)], capture_output=True, text=True, check=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(elapsed_ms, 100.0, f"Stop hook latency exceeded 100ms: {elapsed_ms:.2f}ms")
        self.assertIn("Harness Stop Gate", res.stdout)

    def test_post_tool_hook_latency(self):
        t0 = time.perf_counter()
        env = dict(os.environ, CLAUDE_TOOL_NAME="Read")
        res = subprocess.run([str(HOOK_POST_TOOL)], capture_output=True, text=True, check=True, env=env)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(elapsed_ms, 100.0, f"PostToolUse hook latency exceeded 100ms: {elapsed_ms:.2f}ms")
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
