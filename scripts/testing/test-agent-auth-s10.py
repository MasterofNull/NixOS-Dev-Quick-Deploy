#!/usr/bin/env python3
"""Unit tests for AUTH-S10: sandbox class profile and issuer contract."""

import json
import unittest
from pathlib import Path


class TestAgentAuthS10(unittest.TestCase):
    def setUp(self):
        self.policy_path = Path("config/agent-auth-policy.json")
        self.assertTrue(self.policy_path.exists())
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))

    def test_sandbox_class_profile_exists(self):
        classes = self.policy.get("classes", {})
        self.assertIn("sandbox", classes)
        sandbox_scopes = set(classes["sandbox"])

        # Must have read-only inspection & tighten rights per DESIGN.md section 10
        self.assertIn("read.hints", sandbox_scopes)
        self.assertIn("read.status", sandbox_scopes)
        self.assertIn("safety.tighten", sandbox_scopes)
        self.assertIn("prsi.read", sandbox_scopes)

        # Must NOT have administrative or mutating capabilities
        self.assertNotIn("admin", sandbox_scopes)
        self.assertNotIn("orchestrate", sandbox_scopes)
        self.assertNotIn("memory.write", sandbox_scopes)

    def test_sandbox_self_service_profile(self):
        self_service = self.policy.get("self_service", {})
        self.assertIn("sandbox-readonly", self_service)
        profile_scopes = set(self_service["sandbox-readonly"])
        self.assertEqual(profile_scopes, {"read.hints", "read.status"})

        # Must be a strict subset of owner-agent
        owner_scopes = set(self.policy.get("classes", {}).get("owner-agent", []))
        self.assertTrue(profile_scopes.issubset(owner_scopes))


if __name__ == "__main__":
    unittest.main()
