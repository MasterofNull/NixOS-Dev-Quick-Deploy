#!/usr/bin/env python3
"""Tests for brief_caps: parser, validator (WARN->FAIL schedule), cap tiers, measurement record."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import brief_caps as bc  # noqa: E402

GOOD = """slice_objective: x
checks:
  command: python3 scripts/testing/test-x.py
  end_state: exit 0
caps:
  tier: small
  stop_condition: halt
"""
BEFORE = dt.date(2026, 11, 18)
AFTER = dt.date(2026, 12, 2)


class Parse(unittest.TestCase):
    def test_blocks(self):
        b = bc.parse_brief(GOOD)
        self.assertEqual(b["checks"]["command"], "python3 scripts/testing/test-x.py")
        self.assertEqual(b["caps"]["tier"], "small")

    def test_legacy_aliases(self):
        b = bc.parse_brief("check_command: pytest\ntoken_budget: 9000\nturn_cap: 3\n")
        self.assertEqual(b["checks"]["command"], "pytest")
        r = bc.resolve_caps(b["caps"])
        self.assertEqual((r["input_tokens"], r["max_turns"]), (9000, 3))


class Validate(unittest.TestCase):
    def test_valid(self):
        r = bc.validate(GOOD, BEFORE)
        self.assertEqual((r["errors"], r["warnings"]), ([], []))

    def test_missing_checks_warns_before_checkpoint(self):
        r = bc.validate("caps:\n  tier: small\n", BEFORE)
        self.assertEqual(r["errors"], [])
        self.assertTrue(any("checks.command" in w and "2026-12-02" in w for w in r["warnings"]))

    def test_missing_checks_fails_from_checkpoint(self):
        r = bc.validate("caps:\n  tier: small\n", AFTER)
        self.assertTrue(any("checks.command" in e for e in r["errors"]))

    def test_bad_tier_and_numbers_fail(self):
        self.assertTrue(bc.validate(GOOD.replace("small", "huge"), BEFORE)["errors"])
        self.assertTrue(bc.validate(GOOD + "  output_tokens: abc\n", BEFORE)["errors"])
        self.assertTrue(bc.validate(GOOD + "  max_turns: 0\n", BEFORE)["errors"])

    def test_missing_caps_warns_and_defaults(self):
        r = bc.validate("checks:\n  command: x\n  end_state: y\n", BEFORE)
        self.assertTrue(any("caps" in w for w in r["warnings"]))
        self.assertEqual(r["caps"]["tier"], "medium")


class Tiers(unittest.TestCase):
    def test_tier_values(self):
        for tier, i, o in (("small", 2000, 500), ("medium", 12000, 4000), ("large", 24000, 8000)):
            r = bc.resolve_caps({"tier": tier})
            self.assertEqual((r["input_tokens"], r["output_tokens"]), (i, o))

    def test_default_and_override(self):
        self.assertEqual(bc.resolve_caps({})["tier"], "medium")
        self.assertEqual(bc.resolve_caps({"tier": "small", "output_tokens": "900"})["output_tokens"], 900)
        self.assertEqual(bc.resolve_caps({})["stop_condition"], bc.DEFAULT_STOP)


class Configurable(unittest.TestCase):
    ENV = ("AQ_BRIEF_TIERS_FILE", "AQ_BRIEF_LANE_CTX", "AQ_BRIEF_LANE_MODEL", "AQ_BRIEF_CHECKS_FAIL_FROM")

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in self.ENV}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_tiers_file_override(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            f = Path(td) / "tiers.json"
            f.write_text(json.dumps({"default_tier": "tiny", "tiers": {
                "tiny": {"input_tokens": 300, "output_tokens": 100, "max_turns": 2}}}))
            os.environ["AQ_BRIEF_TIERS_FILE"] = str(f)
            r = bc.resolve_caps({})
            self.assertEqual((r["tier"], r["input_tokens"], r["output_tokens"], r["max_turns"]),
                             ("tiny", 300, 100, 2))
            self.assertTrue(bc.validate("caps:\n  tier: small\n", BEFORE)["errors"])  # not in this file

    def test_unreadable_tiers_file_falls_back_to_builtin(self):
        os.environ["AQ_BRIEF_TIERS_FILE"] = "/nonexistent/tiers.json"
        self.assertEqual(bc.resolve_caps({"tier": "large"})["input_tokens"], 24000)

    def test_lane_ctx_clamps_tier_caps_not_explicit_values(self):
        os.environ["AQ_BRIEF_LANE_CTX"] = "8192"
        r = bc.resolve_caps({"tier": "large"})
        self.assertEqual((r["input_tokens"], r["output_tokens"]), (4096, 2048))
        self.assertEqual(r["over_lane_budget"], [])
        r = bc.resolve_caps({"tier": "large", "output_tokens": "6000"})
        self.assertEqual(r["output_tokens"], 6000)
        self.assertEqual(r["over_lane_budget"], ["output_tokens"])

    def test_lane_model_from_coordinator_config(self):
        os.environ["AQ_BRIEF_LANE_MODEL"] = "llama-cpp-local"
        n = bc.lane_context()
        self.assertIsInstance(n, int)
        self.assertLessEqual(bc.resolve_caps({"tier": "large"})["input_tokens"], n // 2)
        os.environ["AQ_BRIEF_LANE_MODEL"] = "no-such-model"
        self.assertIsNone(bc.lane_context())

    def test_checks_fail_from_env(self):
        os.environ["AQ_BRIEF_CHECKS_FAIL_FROM"] = "2027-06-01"
        self.assertEqual(bc.validate("caps:\n  tier: small\n", AFTER)["errors"], [])
        self.assertTrue(bc.validate("caps:\n  tier: small\n", dt.date(2027, 6, 1))["errors"])
        os.environ["AQ_BRIEF_CHECKS_FAIL_FROM"] = "never"
        r = bc.validate("caps:\n  tier: small\n", dt.date(2099, 1, 1))
        self.assertEqual(r["errors"], [])
        self.assertTrue(r["warnings"])


class Measure(unittest.TestCase):
    def test_record_from_registry_and_timing(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            d = Path(td)
            out = d / "outputs" / "t1.log"
            out.parent.mkdir()
            (d / "registry.jsonl").write_text(json.dumps(
                {"id": "t1", "output_file": str(out), "tokens_in": 1500, "tokens_out": 900}) + "\n")
            Path(str(out) + ".timing.json").write_text(json.dumps({"request_elapsed_seconds": 12.5}))
            rec = bc.measure(d, "t1", GOOD, lane="local-direct", turns=2, now="2026-11-18T00:00:00Z")
            self.assertEqual(rec["caps"], {"input_tokens": 2000, "output_tokens": 500, "max_turns": 4})
            self.assertEqual(rec["within_caps"], {"input_tokens": True, "output_tokens": False, "turns": True})
            self.assertEqual(rec["elapsed_seconds"], 12.5)
            line = json.loads((d / bc.LOG).read_text().splitlines()[0])
            self.assertEqual(line, rec)
            s = bc.summarize([line])
            self.assertEqual((s["runs"], s["over_cap"]["output_tokens"]), (1, 1))

    def test_unknown_actuals_are_null_not_zero(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            rec = bc.measure(Path(td), "nope", "caps:\n  tier: large\n")
            self.assertEqual(rec["actual"], {"input_tokens": None, "output_tokens": None, "turns": None})
            self.assertEqual(rec["within_caps"]["input_tokens"], None)
            self.assertFalse(rec["checks_declared"])
            self.assertEqual(bc.summarize([rec])["unknown"]["input_tokens"], 1)


if __name__ == "__main__":
    unittest.main()
