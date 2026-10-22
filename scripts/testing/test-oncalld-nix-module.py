#!/usr/bin/env python3
"""
Unit test verifying declarative Nix module and AppArmor profile for oncalld (Slice W2-S3).
"""

import os
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

if __name__ == "__main__":
    unittest.main()
