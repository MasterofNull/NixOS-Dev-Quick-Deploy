#!/usr/bin/env python3
"""Unit tests for Foundation C slice C4: network egress confinement invariants."""

import unittest
from pathlib import Path


class TestC4NetworkConfinement(unittest.TestCase):
    def setUp(self):
        self.design_path = Path(".agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md")
        self.assertTrue(self.design_path.exists())
        self.content = self.design_path.read_text(encoding="utf-8")

    def test_c4_af_unix_only_confinement(self):
        # Section 5 requires broker & gateways confined to AF_UNIX only (no AF_INET/AF_INET6)
        self.assertIn("AF_UNIX", self.content)
        self.assertIn("must not allow AF_INET/AF_INET6", self.content)
        self.assertIn("bwrap --unshare-net", self.content)

    def test_c4_audit_and_privacy_schema(self):
        # Section 6 specifies closed audit schema and privacy redaction
        self.assertIn("aq.egress-broker-audit.v1", self.content)
        self.assertIn("NoNewPrivileges", self.content)

    def test_c4_freeze_prerequisites_explicitly_stated(self):
        # Must require operational epoch-bump path and runner hardening
        self.assertIn("AMEND-C4", self.content)
        self.assertIn("C6d", self.content)
        self.assertIn("C6c", self.content)
        self.assertIn("C6-S", self.content)


if __name__ == "__main__":
    unittest.main()
