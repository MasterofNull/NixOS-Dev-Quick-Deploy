#!/usr/bin/env python3
"""
Unit test verifying declarative Nix module and AppArmor profile for oncalld (Slice W2-S3).
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ONCALLD_NIX = REPO_ROOT / "nix" / "modules" / "services" / "oncalld.nix"
SERVICES_DEFAULT = REPO_ROOT / "nix" / "modules" / "services" / "default.nix"

class TestOncalldNixModule(unittest.TestCase):
    def test_oncalld_module_exists(self):
        self.assertTrue(ONCALLD_NIX.is_file(), f"{ONCALLD_NIX} does not exist")

    def test_oncalld_imported_in_services_default(self):
        content = SERVICES_DEFAULT.read_text()
        self.assertIn("./oncalld.nix", content)

    def test_oncalld_declares_apparmor_and_systemd(self):
        content = ONCALLD_NIX.read_text()
        self.assertIn('security.apparmor.policies."aq-oncalld"', content)
        self.assertIn('systemd.services.ai-oncalld', content)
        self.assertIn('ProtectHome = "read-only"', content)
        self.assertIn('deny /run/secrets/**', content)
        self.assertIn('deny @{HOME}/.ssh/**', content)

    def test_unit_path_has_git(self):
        """Regression: unit PATH lacked git (ENOENT on every claim)."""
        content = ONCALLD_NIX.read_text()
        self.assertRegex(content, r"path\s*=\s*\[[^\]]*pkgs\.git\b")
        self.assertIn("pkgs.bubblewrap", content)

    def test_no_write_path_into_owner_repo(self):
        """Owner checkout is read-only to the unit: no repoDir write grant, clone is separate."""
        content = ONCALLD_NIX.read_text()
        rw_match = re.search(r"ReadWritePaths\s*=\s*\[(.*?)\]", content, re.S)
        self.assertIsNotNone(rw_match)
        assert rw_match is not None
        rw = rw_match.group(1)
        self.assertNotIn("repoDir", rw)
        self.assertNotIn(".git", rw)
        self.assertIn("cfg.cloneDir", rw)
        self.assertIn('ProtectHome = "read-only"', content)
        for line in content.splitlines():
            if "repoDir" in line and line.rstrip().endswith(("rwk,", "rw,", "w,")):
                self.fail(f"AppArmor write rule on owner repo: {line.strip()}")
        self.assertNotRegex(content, r"repoDir\}/\.git")

    def test_clone_must_differ_and_apparmor_reads_configured_repo(self):
        content = ONCALLD_NIX.read_text()
        self.assertIn("cfg.cloneDir != cfg.repoDir", content)
        self.assertIn("${cfg.repoDir}/** r,", content)
        self.assertNotIn("/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/**", content)

    def test_repairs_default_off_and_wired(self):
        content = ONCALLD_NIX.read_text()
        self.assertRegex(content, r"repairs\.enable\s*=\s*mkOption\s*\{[^}]*default = false")
        self.assertIn("AQ_ONCALL_REPAIRS", content)
        self.assertIn("AQ_ONCALL_CLONE_DIR", content)

if __name__ == "__main__":
    unittest.main()
