#!/usr/bin/env python3
import tempfile
"""
Unit tests for apparmor-fix-agent rule generalization:
- Volatile /tmp mknod files are skipped
- POSIX semaphores (/dev/shm/sem.<random>) are consolidated to /dev/shm/sem.* rwk,
- Root directory ('/') path extraction handles rstrip without producing empty string
- _path_already_covered recognizes glob-covered semaphore paths
"""
import sys
import unittest
from pathlib import Path

# Add scripts/automation to sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "automation"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "apparmor_fix_agent",
    _REPO_ROOT / "scripts" / "automation" / "apparmor-fix-agent.py"
)
_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_agent)


class TestAppArmorFixAgentGeneralization(unittest.TestCase):

    def test_posix_semaphore_generalization(self):
        rule = _agent._make_rule("mknod", "/dev/shm/sem.ZtjUCy", "rw")
        self.assertIsNotNone(rule)
        rule_line, comment = rule
        self.assertIn("/dev/shm/sem.* rwk,", rule_line)
        self.assertIn("POSIX semaphores", comment)

    def test_volatile_mktemp_skipped(self):
        rule = _agent._make_rule("mknod", "/tmp/tmp_a1b2c3", "rw")
        self.assertIsNone(rule)

    def test_root_path_extraction_non_empty(self):
        covered = _agent._path_already_covered(
            "profile test {\n  / r,\n  deny /home/** wx,\n}",
            "test",
            "            / r,"
        )
        self.assertTrue(covered)

    def test_glob_covers_semaphore(self):
        covers = _agent._apparmor_glob_covers("/dev/shm/sem.*", "/dev/shm/sem.Abc123")
        self.assertTrue(covers)



    def test_insert_rules_for_profile_inserts_before_deny_home(self):
        sample_nix = """
security.apparmor.policies."command-center-dashboard-api" = {
  profile = ''
    /bin/sh ix,
    deny /home/** wx,
  '';
};
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(sample_nix)
            tmp_path = Path(f.name)

        orig_nix = _agent.NIX_FILE
        try:
            _agent.NIX_FILE = tmp_path
            ok = _agent._insert_rules_for_profile("command-center-dashboard-api", [
                ("/proc/@{pids}/cmdline r,", "test comment"),
                ("/dev/shm/sem.* rwk,", "posix semaphores")
            ])
            self.assertTrue(ok)
            content = tmp_path.read_text()
            self.assertIn("/proc/@{pids}/cmdline r,  # test comment", content)
            self.assertIn("/dev/shm/sem.* rwk,  # posix semaphores", content)
            # verify insertion is before deny /home/**
            idx_rule = content.find("/dev/shm/sem.* rwk,")
            idx_deny = content.find("deny /home/**")
            self.assertLess(idx_rule, idx_deny)
        finally:
            _agent.NIX_FILE = orig_nix
            if tmp_path.exists():
                tmp_path.unlink()



    def test_git_commit_no_staged_changes_returns_head(self):
        from unittest.mock import patch, MagicMock
        with patch("subprocess.run") as mock_run:
            mock_diff = MagicMock()
            mock_diff.returncode = 0

            mock_rev = MagicMock()
            mock_rev.stdout = "abc1234\n"

            def side_effect(cmd, *args, **kwargs):
                if "diff" in cmd:
                    return mock_diff
                if "rev-parse" in cmd:
                    return mock_rev
                m = MagicMock()
                m.returncode = 0
                return m

            mock_run.side_effect = side_effect
            res = _agent._git_commit("test commit")
            self.assertEqual(res, "abc1234")


if __name__ == "__main__":
    unittest.main()
