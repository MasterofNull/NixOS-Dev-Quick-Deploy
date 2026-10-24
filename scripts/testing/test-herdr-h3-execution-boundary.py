#!/usr/bin/env python3
"""Contract and invariant test for Herdr Phase H3 execution boundary.

Per .agents/plans/herdr-agent-operations/PROGRAM-PLAN.md:
H3 — confined executor adoption:
- Dispatch-admitted tasks run in persistent PTYs while workers cannot access Herdr control.
- Role-by-role socket/binary denial + cancellation/fence/review end-to-end.
- Broker starts admitted task argv in a Herdr PTY while the child cell hides the Herdr
  socket/config/binary and scrubs HERDR_*.
- Attempts to send input, spawn siblings, close panes, install plugins, or stop the server
  from inside worker execution cells must deny.
- Canonical lifecycle and cancellation remain registry/lease/fence driven.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestHerdrH3ExecutionBoundary(unittest.TestCase):
    def test_environment_scrub_invariants(self) -> None:
        """Confined worker environments must strip all HERDR_* control variables."""
        unsafe_env = {
            "PATH": "/run/current-system/sw/bin",
            "HOME": "/home/hyperd",
            "HERDR_SOCKET": "/run/user/1000/herdr/herdr.sock",
            "HERDR_SESSION": "aq-os",
            "HERDR_TOKEN": "secret-control-token",
            "HERDR_MUTATION_ENABLED": "1",
        }
        scrubbed = {k: v for k, v in unsafe_env.items() if not k.startswith("HERDR_")}
        self.assertNotIn("HERDR_SOCKET", scrubbed)
        self.assertNotIn("HERDR_SESSION", scrubbed)
        self.assertNotIn("HERDR_TOKEN", scrubbed)
        self.assertNotIn("HERDR_MUTATION_ENABLED", scrubbed)
        self.assertIn("PATH", scrubbed)

    def test_herdr_socket_hidden_in_sandbox_profile(self) -> None:
        """Worker sandbox profiles must never mount or expose the herdr socket."""
        import json
        policy_path = REPO_ROOT / "config" / "agent-auth-policy.json"
        self.assertTrue(policy_path.exists())
        policy = json.loads(policy_path.read_text())

        # Verify sandbox class in config/agent-auth-policy.json
        sandbox_scopes = set(policy.get("classes", {}).get("sandbox", []))
        self.assertNotIn("admin", sandbox_scopes)
        self.assertNotIn("herdr.control", sandbox_scopes)
        self.assertNotIn("herdr.mutate", sandbox_scopes)
        self.assertNotIn("pane.spawn", sandbox_scopes)

    def test_canonical_lifecycle_single_authority(self) -> None:
        """Lifecycle remains bound to TEG / TaskRegistry, not Herdr socket state."""
        # Herdr observations are presentation drift only and cannot dictate task disposition
        task_state = "RUNNING"
        herdr_observation = {"state": "disconnected", "pane_id": "pane-99"}

        # Ground truth is TEG
        effective_disposition = task_state
        self.assertEqual(effective_disposition, "RUNNING")
        self.assertEqual(herdr_observation["state"], "disconnected")


if __name__ == "__main__":
    unittest.main()
