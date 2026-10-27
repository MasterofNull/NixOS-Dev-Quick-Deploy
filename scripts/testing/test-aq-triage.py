#!/usr/bin/env python3
"""Comprehensive test suite for System 1 High-Frequency Triage Engine (`aq-triage`).

Exercises:
1. Classification accuracy across failure modes and benign noise.
2. Persistent cursor tracking and state recovery across restarts.
3. Token bucket flood-rate limiter behavior under burst load.
4. Actionable filtering and confidence calibration.
5. P95 latency benchmark (< 200ms target).
6. Health summary schema contract for QA and dashboard visibility.
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add scripts/ai/lib to path
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ai" / "lib"))

from triage_engine import FastClassifier, JournalStreamTriage, TokenBucketLimiter, health_summary


class TestAqTriage(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp_dir.name)
        self.engine = JournalStreamTriage(state_dir=self.state_dir)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_fixture_1_classification_accuracy(self) -> None:
        """Fixture 1: Verify correct severity, class, and actionable tags across categories."""
        cases = [
            ("kernel: oom-killer: killed process llama-server", "CRITICAL", "RESOURCE_EXHAUSTION", True),
            ("segmentation fault in worker process 1402", "CRITICAL", "CRASH", True),
            ("Traceback (most recent call last):\n  File 'test.py', line 1: ZeroDivisionError", "HIGH", "CRASH", True),
            ("service loaded failed failed", "HIGH", "HEALTH_CHECK_FAILURE", True),
            ("syntaxerror: unexpected EOF while parsing config.py", "HIGH", "CONFIGURATION", True),
            ("request timed out after 30000ms", "HIGH", "TIMEOUT", True),
            ("update_slots: all slots are idle", "NOISE", "BENIGN_INFO", False),
            ("systemd: started session completed successfully", "NOISE", "BENIGN_INFO", False),
        ]
        for msg, exp_sev, exp_cls, exp_actionable in cases:
            res = FastClassifier.classify(source="test.service", message=msg)
            self.assertEqual(res.severity, exp_sev, f"Mismatch for '{msg}': expected sev {exp_sev}, got {res.severity}")
            self.assertEqual(res.incident_class, exp_cls, f"Mismatch for '{msg}': expected cls {exp_cls}, got {res.incident_class}")
            self.assertEqual(res.actionable, exp_actionable, f"Mismatch for '{msg}': expected actionable {exp_actionable}")
            self.assertGreater(res.confidence, 0.0)
            self.assertLessEqual(res.confidence, 1.0)
            self.assertTrue(bool(res.correlation_key))

    def test_wave12_patterns_systemd_apparmor_exit_code(self) -> None:
        """Wave 12 patterns: systemd crash, AppArmor denial, exit-code failure."""
        cases = [
            ("llama.service: Main process exited, code=dumped, status=11/SEGV", "CRITICAL", "CRASH", "local"),
            ("systemd[1]: foo.service: Failed with result 'exit-code'.", "HIGH", "HEALTH_CHECK_FAILURE", "local"),
            ('audit: type=1400 apparmor="DENIED" operation="open" profile="x"', "CRITICAL", "SECURITY_VIOLATION", "antigravity"),
        ]
        for msg, exp_sev, exp_cls, exp_lane in cases:
            res = FastClassifier.classify(source="test.service", message=msg)
            self.assertEqual(res.incident_class, exp_cls, f"class mismatch for '{msg}': {res.incident_class}")
            self.assertEqual(res.severity, exp_sev, f"severity mismatch for '{msg}': {res.severity}")
            self.assertEqual(res.suggested_lane, exp_lane, f"lane mismatch for '{msg}': {res.suggested_lane}")
            self.assertTrue(res.actionable)

    def test_fixture_2_persistent_cursor(self) -> None:
        """Fixture 2: Verify cursor persistence and recovery across engine instances."""
        batch1 = [
            {"MESSAGE": "Log entry 1", "__CURSOR": "s=abc;i=1", "__REALTIME_TIMESTAMP": "1700000001000000"},
            {"MESSAGE": "Log entry 2", "__CURSOR": "s=abc;i=2", "__REALTIME_TIMESTAMP": "1700000002000000"},
        ]
        res1 = self.engine.ingest_entries(batch1, subsystem="journald")
        self.assertEqual(len(res1), 2)

        cur, ts = self.engine.get_cursor("journald")
        self.assertEqual(cur, "s=abc;i=2")
        self.assertEqual(ts, "1700000002000000")

        # New engine instance on same state dir
        engine2 = JournalStreamTriage(state_dir=self.state_dir)
        cur2, ts2 = engine2.get_cursor("journald")
        self.assertEqual(cur2, "s=abc;i=2")
        self.assertEqual(ts2, "1700000002000000")

        batch2 = [
            {"MESSAGE": "Log entry 3", "__CURSOR": "s=abc;i=3", "__REALTIME_TIMESTAMP": "1700000003000000"},
        ]
        res2 = engine2.ingest_entries(batch2, subsystem="journald")
        self.assertEqual(len(res2), 1)
        cur3, _ = engine2.get_cursor("journald")
        self.assertEqual(cur3, "s=abc;i=3")

    def test_fixture_3_token_bucket_limiter(self) -> None:
        """Fixture 3: Verify token bucket rate limiter throttles high-frequency floods."""
        limiter = TokenBucketLimiter(capacity=3, refill_rate_per_sec=1.0)
        now = 1000.0

        # Initial burst of 3 should succeed
        self.assertTrue(limiter.allow("svc_flood", now=now))
        self.assertTrue(limiter.allow("svc_flood", now=now))
        self.assertTrue(limiter.allow("svc_flood", now=now))

        # 4th in same instant should be rate-limited
        self.assertFalse(limiter.allow("svc_flood", now=now))

        # Distinct source should still have its own capacity
        self.assertTrue(limiter.allow("svc_other", now=now))

        # After 1.5 seconds, 1 token refilled
        now += 1.5
        self.assertTrue(limiter.allow("svc_flood", now=now))
        self.assertFalse(limiter.allow("svc_flood", now=now))

    def test_rate_limited_entry_does_not_advance_cursor_past_it(self) -> None:
        """A throttled entry remains at the head of the next ingestion batch."""
        self.engine.limiter = TokenBucketLimiter(capacity=1, refill_rate_per_sec=0.0)
        entries = [
            {"MESSAGE": f"failure {index}", "source": "svc", "__CURSOR": f"cursor-{index}", "__REALTIME_TIMESTAMP": str(index)}
            for index in range(1, 4)
        ]

        results = self.engine.ingest_entries(entries, subsystem="journald")

        self.assertEqual(len(results), 1)
        self.assertEqual(self.engine.get_cursor("journald"), ("cursor-1", "1"))

    def test_fixture_4_actionable_filtering(self) -> None:
        """Fixture 4: Verify strict gating for actionable flag."""
        high_critical_entries = [
            {"MESSAGE": "kernel panic - not syncing", "source": "kernel"},
            {"MESSAGE": "cannot allocate memory (oom)", "source": "ai-stack"},
            {"MESSAGE": "Traceback (most recent call last):\n  ValueError: boom", "source": "worker"},
        ]
        results = self.engine.ingest_entries(high_critical_entries)
        for r in results:
            self.assertTrue(r.actionable, f"Entry {r.summary} should be actionable")
            self.assertIn(r.severity, ("CRITICAL", "HIGH"))
            self.assertGreaterEqual(r.confidence, 0.85)

        noise_entries = [
            {"MESSAGE": "update_slots: all slots are idle", "source": "llama-server"},
            {"MESSAGE": "health check passed successfully", "source": "health-check"},
        ]
        noise_results = self.engine.ingest_entries(noise_entries)
        for r in noise_results:
            self.assertFalse(r.actionable, f"Entry {r.summary} should NOT be actionable")
            self.assertEqual(r.severity, "NOISE")

    def test_fixture_5_p95_latency_benchmark(self) -> None:
        """Fixture 5: Verify sub-second P95 classification latency (< 200ms target)."""
        bench = self.engine.benchmark(sample_count=200)
        self.assertTrue(bench["passed"], f"Benchmark failed: P95 is {bench['p95_ms']}ms (target < {bench['target_p95_ms']}ms)")
        self.assertLess(bench["p95_ms"], 200.0)
        # In pure Python on modern CPU, it should be well under 10ms
        self.assertLess(bench["p95_ms"], 50.0)

    def test_fixture_6_health_summary_contract(self) -> None:
        """Fixture 6: Verify health_summary contract schema and fields."""
        summary = self.engine.health_summary()
        self.assertTrue(summary.get("available"))
        self.assertEqual(summary.get("status"), "ready")
        self.assertIn("p95_ms", summary)
        self.assertIn("cursor_tracked", summary)
        self.assertIn("total_classified", summary)
        self.assertIn("actionable_count", summary)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAqTriage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\nALL 6 FIXTURES PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
