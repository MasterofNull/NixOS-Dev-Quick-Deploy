#!/usr/bin/env python3
"""Regression: fs-integrity-check must stream journal text, not hold it in bash memory.

Root cause (2026-11-28): the check expanded four whole-boot journals into one bash
string; on a ~2 GB journal bash SEGV'd at ~6 GB RSS. Here a fake journalctl emits
~480 MB total under a 256 MB address-space cap; an accumulating script cannot pass.

FS_INTEGRITY_SCRIPT overrides the script under test (used to prove the test fails
against the pre-fix script).
"""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = Path(os.environ.get("FS_INTEGRITY_SCRIPT", REPO_ROOT / "scripts" / "health" / "fs-integrity-check.sh"))
MODULE = REPO_ROOT / "nix" / "modules" / "core" / "fs-integrity-monitor.nix"

FAKE_JOURNALCTL = """#!/usr/bin/env bash
yes 'Nov 28 kernel: ordinary log line with padding to look like a real journal entry' | head -c 120000000
%s
"""


def run_check(inject: str):
    with tempfile.TemporaryDirectory() as d:
        fake = Path(d) / "journalctl"
        fake.write_text(FAKE_JOURNALCTL % inject)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        env = {"PATH": f"{d}:{os.environ['PATH']}", "ROOT_UUID_OVERRIDE": "1111-2222"}
        # ulimit -v is in KiB: 256 MiB address space.
        return subprocess.run(
            ["bash", "-c", f'ulimit -v 262144; exec bash "{SCRIPT}"'],
            env=env, capture_output=True, text=True, timeout=300,
        )


class TestFsIntegrityBounded(unittest.TestCase):
    def test_large_clean_journal_under_memory_cap(self):
        r = run_check("")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("No filesystem integrity failure", r.stdout)

    def test_signature_in_large_journal_detected_under_memory_cap(self):
        r = run_check("echo 'systemd-fsck[1]: failed on /dev/sda1'")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("/dev/disk/by-uuid/1111-2222", r.stdout)

    def test_module_declares_resource_contract_and_single_source(self):
        text = MODULE.read_text()
        for needle in ("MemoryMax", "TimeoutSec", "IOSchedulingClass", "Nice"):
            self.assertIn(needle, text)
        self.assertIn("scripts/health/fs-integrity-check.sh", text)


if __name__ == "__main__":
    unittest.main()
