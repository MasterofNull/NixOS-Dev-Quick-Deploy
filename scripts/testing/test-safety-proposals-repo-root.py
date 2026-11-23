#!/usr/bin/env python3
"""Verify SafetyControlLayer resolves PROPOSALS_DIR from REPO_ROOT or ancestor CLAUDE.md, not arbitrary cwd."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack/mcp-servers/hybrid-coordinator"
sys.path.insert(0, str(HC))

from workflow import safety_control_layer as scl  # noqa: E402


class SafetyProposalsRepoRootTest(unittest.TestCase):
    def test_repo_root_env_overrides_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo_env = base / "explicit_repo"
            other_cwd = base / "arbitrary_cwd"
            repo_env.mkdir()
            other_cwd.mkdir()
            prev = Path.cwd()
            try:
                os.chdir(other_cwd)
                with mock.patch.dict(os.environ, {"REPO_ROOT": str(repo_env)}):
                    layer = scl.SafetyControlLayer(mode="review")
                    self.assertEqual(layer.proposals_dir, repo_env.resolve() / ".agent/proposals")
                    self.assertFalse((repo_env / ".agent").exists())  # lazy: not at registration
                    layer.intercept_action("run_command", {"command": "rm -rf /"}, "t")
                    self.assertTrue((repo_env / ".agent/proposals/proposals.json").is_file())
                    self.assertFalse((other_cwd / ".agent").exists())
            finally:
                os.chdir(prev)

    def test_walk_up_finds_repo_root_when_env_unset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            other_cwd = Path(td) / "sub_cwd"
            other_cwd.mkdir()
            prev = Path.cwd()
            try:
                os.chdir(other_cwd)
                with mock.patch.dict(os.environ, {"REPO_ROOT": ""}):
                    resolved = scl._resolve_repo_root()
                    self.assertEqual(resolved, ROOT.resolve())
                    self.assertFalse((other_cwd / ".agent").exists())
            finally:
                os.chdir(prev)

    def test_unwritable_proposals_dir_registration_succeeds_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ro = Path(td) / "ro"
            ro.mkdir()
            ro.chmod(0o555)
            try:
                with mock.patch.dict(os.environ, {"REPO_ROOT": str(ro)}):
                    layer = scl.SafetyControlLayer(mode="review")
                    self.assertFalse((ro / ".agent").exists())
                    if os.geteuid() != 0:
                        res = layer.intercept_action("run_command", {"command": "rm -rf /"}, "t")
                        self.assertEqual((res or {}).get("status"), "blocked")
            finally:
                ro.chmod(0o755)

    def test_delegate_isolated_child_gets_worktree_repo_root(self) -> None:
        src = (ROOT / "scripts/ai/delegate-to-local").read_text()
        self.assertIn('cd "$WT_PATH" && REPO_ROOT="$WT_PATH" "${_DISPATCH_ARGS[@]}"', src)
        self.assertIn("&& REPO_ROOT=$(printf '%q' \"$WT_PATH\") $(printf '%q ' \"${_DISPATCH_ARGS[@]}\")", src)


if __name__ == "__main__":
    unittest.main()
