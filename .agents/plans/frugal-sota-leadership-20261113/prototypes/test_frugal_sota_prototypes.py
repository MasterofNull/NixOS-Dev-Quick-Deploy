#!/usr/bin/env python3
"""Unit test suite for Frugal SOTA Leadership Prototypes (Slices F1, F2, F3)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, str(PROTO_DIR / filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestContextPacketPrototype(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("aq_context_packet_proto", "aq-context-packet-prototype.py")

    def test_within_2500_token_ceiling_including_exemplar(self):
        pkt = self.mod.build_packet(
            "Verify attention_queue generation fence",
            ["scripts/ai/lib/attention_queue.py:push"],
            max_tokens=2500,
            include_exemplar=True,
        )
        self.assertLessEqual(pkt["estimated_tokens"], 2500)
        self.assertIn("Surgical Context Packet", pkt["markdown"])

    def test_degrades_to_signatures_when_budget_tight(self):
        pkt = self.mod.build_packet(
            "Audit full attention_queue module",
            ["scripts/ai/lib/attention_queue.py"],
            max_tokens=450,
            include_exemplar=False,
        )
        self.assertTrue(pkt["degraded_to_signatures"])
        self.assertLessEqual(pkt["estimated_tokens"], 550)


class TestSystem1RouterPrototype(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("system1_router_proto", "system1_router_prototype.py")

    def test_hysteresis_load5_guard(self):
        # Not previously paused: 0.65 is allowed, 0.75 enters pause
        ok1, _ = self.mod.is_neural_system1_eligible(
            {"ac_online": True, "battery_pct": 90, "load5_ratio": 0.65, "max_temp_c": 65.0},
            previously_paused=False,
        )
        self.assertTrue(ok1)

        ok2, reason2 = self.mod.is_neural_system1_eligible(
            {"ac_online": True, "battery_pct": 90, "load5_ratio": 0.75, "max_temp_c": 65.0},
            previously_paused=False,
        )
        self.assertFalse(ok2)
        self.assertIn("load5_hysteresis_guard", reason2)

        # Previously paused: 0.60 stays paused (must drop <= 0.55 to exit)
        ok3, _ = self.mod.is_neural_system1_eligible(
            {"ac_online": True, "battery_pct": 90, "load5_ratio": 0.60, "max_temp_c": 65.0},
            previously_paused=True,
        )
        self.assertFalse(ok3)

        ok4, _ = self.mod.is_neural_system1_eligible(
            {"ac_online": True, "battery_pct": 90, "load5_ratio": 0.50, "max_temp_c": 65.0},
            previously_paused=True,
        )
        self.assertTrue(ok4)

    def test_never_drops_gated_tasks_silently(self):
        hot_vitals = {"ac_online": False, "battery_pct": 30, "load5_ratio": 0.4, "max_temp_c": 70.0}
        bg = self.mod.route_slice(
            task="distill trajectories",
            files_touched=1,
            available_lanes=["local", "claude", "gemini"],
            is_background_job=True,
            vitals=hot_vitals,
        )
        self.assertEqual(bg["disposition"], "defer_cooldown")
        self.assertEqual(bg["selected_lane"], "defer")

        fg = self.mod.route_slice(
            task="fix unit test",
            files_touched=1,
            available_lanes=["local", "claude", "gemini"],
            is_background_job=False,
            vitals=hot_vitals,
        )
        self.assertEqual(fg["disposition"], "substitute_remote")
        self.assertEqual(fg["selected_lane"], "claude")


class TestTrajectoryCollectorQuarantine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("collect_trajectories_proto", "collect_verified_trajectories_prototype.py")

    def test_clean_and_known_pattern_redacted_accepted(self):
        res = self.mod.sanitize_trajectory_tuple(
            {
                "context_packet": "File in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/foo.py",
                "rejected_attempts": ["api_key = 'sk-1234567890abcdef12345678'"],
                "verified_diff": "+x = 1",
                "review_receipt": "Reviewed-head-sha: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\nReview-Disposition: PASS",
            }
        )
        self.assertEqual(res["status"], "accepted")
        self.assertIn("[REDACTED_SECRET]", res["record"]["rejected_attempts"])
        self.assertIn("/home/$USER", res["record"]["context_packet"])

    def test_novel_high_entropy_secret_quarantines_tuple(self):
        res = self.mod.sanitize_trajectory_tuple(
            {
                "context_packet": "clean",
                "rejected_attempts": [],
                "verified_diff": "+CUSTOM_CRED = 'Zx9_Qp7Lm2Vw8Kr4Tn6Yb1Cf3Hj5Ds0Ga9'",
                "review_receipt": "PASS",
            }
        )
        self.assertEqual(res["status"], "quarantined")
        self.assertTrue(any("verified_diff:" in r for r in res["quarantine_reasons"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
