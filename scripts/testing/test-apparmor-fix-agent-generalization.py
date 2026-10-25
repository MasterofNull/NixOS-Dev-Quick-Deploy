#!/usr/bin/env python3
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


if __name__ == "__main__":
    unittest.main()
