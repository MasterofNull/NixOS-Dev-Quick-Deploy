#!/usr/bin/env python3
"""Test suite for remote lane egress friction rules table (DEC-S4 / W2-S7)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

from remote_lane_egress import EgressRulesEngine, LANES


class TestRemoteLaneEgress(unittest.TestCase):
    def setUp(self):
        self.engine = EgressRulesEngine()

    def test_all_lanes_exercised(self):
        for lane in LANES:
            res = self.engine.evaluate({"lane": lane, "dest_host": "api.anthropic.com", "dest_port": 443})
            self.assertIn(res["action"], {"none", "flag", "hold"})
            self.assertIn("reason_code", res)

    def test_allowlist_match(self):
        res = self.engine.evaluate({"lane": "claude", "dest_host": "api.anthropic.com", "dest_port": 443})
        self.assertEqual(res["action"], "none")
        self.assertEqual(res["reason_code"], "RULE_ALLOWLISTED")

    def test_cross_lane_triggers_flag(self):
        # api.anthropic.com is allowed for claude, but novel for codex
        res = self.engine.evaluate({"lane": "codex", "dest_host": "api.anthropic.com", "dest_port": 443})
        self.assertEqual(res["action"], "flag")
        self.assertEqual(res["reason_code"], "EGR_CROSS_LANE")

    def test_high_signal_unbudgeted_raw_ip(self):
        for i in range(15):
            res = self.engine.evaluate({"lane": "claude", "dest_host": "198.51.100.1", "dest_port": 443, "raw_ip": True})
            self.assertEqual(res["action"], "hold")
            self.assertEqual(res["reason_code"], "EGR_RAW_IP")
            self.assertFalse(res["collapsed"])

    def test_high_signal_unbudgeted_sni_mismatch(self):
        for i in range(15):
            res = self.engine.evaluate({"lane": "antigravity", "dest_host": "example.org", "dest_port": 443, "sni_mismatch": True})
            self.assertEqual(res["action"], "hold")
            self.assertEqual(res["reason_code"], "EGR_SNI_MISMATCH")
            self.assertFalse(res["collapsed"])

    def test_rate_budget_collapse_on_novel_domains(self):
        # Exceed 20 flags in an hour on novel domain
        for i in range(20):
            res = self.engine.evaluate({"lane": "claude", "dest_host": f"novel-host-{i}.example.org", "dest_port": 443})
            self.assertEqual(res["action"], "flag")
            self.assertFalse(res["collapsed"])

        # 21st novel domain collapses to avoid alert fatigue
        res = self.engine.evaluate({"lane": "claude", "dest_host": "novel-host-21.example.org", "dest_port": 443})
        self.assertTrue(res["collapsed"])

        # Even with novel domain budget exhausted, high-signal alerts still fire
        res_raw = self.engine.evaluate({"lane": "claude", "dest_host": "203.0.113.1", "dest_port": 443, "raw_ip": True})
        self.assertEqual(res_raw["action"], "hold")
        self.assertEqual(res_raw["reason_code"], "EGR_RAW_IP")
        self.assertFalse(res_raw["collapsed"])

    def test_free_text_payload_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.evaluate({"lane": "claude", "dest_host": "example.org", "dest_port": 443, "prompt": "malicious input"})


if __name__ == "__main__":
    unittest.main()
