#!/usr/bin/env python3
"""Tests for scripts/ai/aq-worktree-write-guard (incident 30f7979b)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "ai" / "aq-worktree-write-guard"


def run(payload, home=None, raw=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = home
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True, text=True, env=env)


def denied(r):
    if not r.stdout.strip():
        return False
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(os.path.realpath(self.tmp.name))
        self.main = base / "repo"
        self.wt = self.main / ".claude" / "worktrees" / "agent-x"
        self.wt.mkdir(parents=True)
        (self.main / ".agent").mkdir()
        self.home = base / "home"
        (self.home / ".claude" / "projects" / "p" / "memory").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, target, tool="Write", cwd=None, key="file_path"):
        return run({"tool_name": tool, "cwd": str(cwd or self.wt), "tool_input": {key: str(target)}},
                   home=str(self.home))

    def test_in_worktree_allowed(self):
        self.assertFalse(denied(self.call(self.wt / "a" / "b.txt")))
        self.assertFalse(denied(self.call("rel/file.txt")))

    def test_main_checkout_denied(self):
        for tool, key in [("Write", "file_path"), ("Edit", "file_path"), ("MultiEdit", "file_path"),
                          ("NotebookEdit", "notebook_path"), ("mcp__lean-ctx__ctx_edit", "path")]:
            self.assertTrue(denied(self.call(self.main / ".agent" / "x.md", tool, key=key)), tool)

    def test_traversal_denied(self):
        self.assertTrue(denied(self.call(self.wt / ".." / ".." / ".." / ".agent" / "x.md")))
        self.assertTrue(denied(self.call("../../../.agent/x.md")))

    def test_symlink_escape_denied(self):
        (self.wt / "link").symlink_to(self.main / ".agent")
        self.assertTrue(denied(self.call(self.wt / "link" / "x.md")))

    def test_scratchpad_and_memory_allowed(self):
        self.assertFalse(denied(self.call("/tmp/claude-1000/proj/sess/scratchpad/n.txt")))
        self.assertFalse(denied(self.call(self.home / ".claude" / "projects" / "p" / "memory" / "m.md")))

    def test_non_worktree_cwd_allowed(self):
        self.assertFalse(denied(self.call(self.main / ".agent" / "x.md", cwd=self.main)))

    def test_unguarded_tool_allowed(self):
        self.assertFalse(denied(self.call(self.main / "x", tool="Read")))

    def test_malformed_input_no_crash(self):
        for raw in ["", "not json", "[]", "null", '{"tool_name": "Write"}',
                    '{"tool_name":"Write","cwd":5,"tool_input":"x"}']:
            r = run(None, raw=raw)
            self.assertEqual(r.returncode, 0, raw)
            self.assertFalse(denied(r), raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
