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

    def test_cross_lane_triggers_hold(self):
        # api.anthropic.com is allowed for claude, but not for codex
        res = self.engine.evaluate({"lane": "codex", "dest_host": "api.anthropic.com", "dest_port": 443})
        self.assertEqual(res["action"], "hold")
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

    def test_rate_budget_collapse_never_relaxes_hold(self):
        for i in range(12):
            res = self.engine.evaluate({"lane": "claude", "dest_host": f"novel-host-{i}.example.org", "dest_port": 443})
            self.assertEqual(res["outcome"], "hold")
        self.assertTrue(res["collapsed"])
        res_raw = self.engine.evaluate({"lane": "claude", "dest_host": "203.0.113.1", "dest_port": 443, "raw_ip": True})
        self.assertEqual(res_raw["action"], "hold")
        self.assertFalse(res_raw["collapsed"])

    def test_no_flag_outcomes(self):
        for lane in LANES:
            for h in ("evil.example.org", "api.openai.com", "xn--example.com", ""):
                res = self.engine.evaluate({"lane": lane, "dest_host": h, "dest_port": 443})
                self.assertNotEqual(res["outcome"], "flag", (lane, h))

    def test_obfuscated_ip_forms_hold(self):
        for h in ("2130706433", "0177.0.0.1", "0x7f.0.0.1", "0x7f000001", "127.1",
                  "::ffff:127.0.0.1", "[::ffff:7f00:1]", "::ffff:198.51.100.1"):
            for lane in ("gemini", "codex", "claude"):
                res = self.engine.evaluate({"lane": lane, "dest_host": h, "dest_port": 443})
                self.assertEqual(res["outcome"], "hold", (lane, h))
                self.assertEqual(res["reason_code"], "EGR_RAW_IP", (lane, h))

    def test_unknown_lane_punycode_holds(self):
        res = self.engine.evaluate({"lane": "nonesuch", "dest_host": "xn--example.com", "dest_port": 443})
        self.assertEqual(res["outcome"], "hold")
        self.assertEqual(res["reason_code"], "EGR_UNATTRIBUTED")

    def test_punycode_known_lane_holds(self):
        res = self.engine.evaluate({"lane": "gemini", "dest_host": "xn--example.com", "dest_port": 443})
        self.assertEqual(res["outcome"], "hold")

    def test_allowlisted_hosts_still_allowed(self):
        for lane, hosts in (("codex", ("api.openai.com", "chatgpt.com")),
                            ("claude", ("api.anthropic.com", "claude.ai")),
                            ("gemini", ("cloudcode-pa.googleapis.com", "generativelanguage.googleapis.com"))):
            for h in hosts:
                res = self.engine.evaluate({"lane": lane, "dest_host": h, "dest_port": 443})
                self.assertEqual(res["outcome"], "none", (lane, h))

    def test_gemini_lane_real_hosts_allowed(self):
        for h in ("cloudcode-pa.googleapis.com", "generativelanguage.googleapis.com"):
            res = self.engine.evaluate({"lane": "gemini", "dest_host": h, "dest_port": 443})
            self.assertEqual(res["outcome"], "none", h)
            self.assertEqual(res["reason_code"], "RULE_ALLOWLISTED")

    def test_gemini_unknown_host_not_allowed(self):
        res = self.engine.evaluate({"lane": "gemini", "dest_host": "evil.example.org", "dest_port": 443})
        self.assertEqual(res["outcome"], "hold")
        self.assertEqual(res["reason_code"], "EGR_NOVEL_DOMAIN")

    def test_unknown_lane_still_held(self):
        res = self.engine.evaluate({"lane": "nonesuch", "dest_host": "api.openai.com", "dest_port": 443})
        self.assertEqual(res["outcome"], "hold")
        self.assertEqual(res["reason_code"], "EGR_UNATTRIBUTED")

    def test_raw_ip_literals_hold(self):
        for h in ("198.51.100.1", "::1", "[2001:db8::1]", "2001:db8::1", "fe80::1%eth0"):
            res = self.engine.evaluate({"lane": "gemini", "dest_host": h, "dest_port": 443})
            self.assertEqual(res["outcome"], "hold", h)
            self.assertEqual(res["reason_code"], "EGR_RAW_IP", h)

    def test_codex_claude_unchanged(self):
        for lane, h in (("codex", "api.openai.com"), ("claude", "api.anthropic.com")):
            res = self.engine.evaluate({"lane": lane, "dest_host": h, "dest_port": 443})
            self.assertEqual(res["outcome"], "none")

    def test_default_host_from_config(self):
        import remote_lane_egress as m
        self.assertEqual(m.check_egress_cli("gemini", ""), 0)
        self.assertEqual(m.check_egress_cli("codex", ""), 0)
        self.assertEqual(m.check_egress_cli("claude", ""), 0)

    def test_free_text_payload_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.evaluate({"lane": "claude", "dest_host": "example.org", "dest_port": 443, "prompt": "malicious input"})


if __name__ == "__main__":
    unittest.main()
