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


if __name__ == "__main__":
    unittest.main()
