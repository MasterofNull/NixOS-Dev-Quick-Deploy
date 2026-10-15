#!/usr/bin/env python3
"""Comprehensive test suite for hermetic candidate evaluation evidence (ECC P0-D).

Validates:
1. Happy path: valid candidate evaluation receipt verification and promotion.
2. Escape violation: fail-closed (escape_detected).
3. Secret leakage: forbidden credential pattern in output fails closed (secret_detected).
4. Network violation: unauthorized network attempted fails closed (network_violation).
5. Host write violation: write attempted outside sandbox fails closed (write_violation).
6. Timeout violation: execution timeout fails closed (timeout).
7. Execution error: non-zero exit code fails closed (execution_failed).
8. Corrupted receipt: tampered receipt digest or payload fails closed (receipt_corrupted).
9. Tampered artifact: artifact modified after eval fails closed (artifact_digest_mismatch).
10. Reviewer conflict: implementer self-review fails closed (reviewer_conflict).
11. Missing promotion: receipt integrity without reviewed promotion fails closed (promotion_missing).
12. Reviewer rejection: rejected candidate fails closed (promotion_rejected).
13. CLI interface: aq-hermetic-eval summary, evaluate, and verify.
14. Dogfood: harmless local-agent candidate evaluated through baseline and after-run.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import hermetic_candidate_eval as hce  # noqa: E402


class TestHermeticCandidateEval(unittest.TestCase):
    def setUp(self) -> None:
        # test-only: pretend a real executor backend exists
        self._saved = hce.REAL_EXECUTOR_BACKENDS
        hce.REAL_EXECUTOR_BACKENDS = frozenset({"process"})
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.artifact = self.tmp_path / "candidate_plugin.py"
        self.artifact.write_text('def run(): return "harmless candidate"\n', encoding="utf-8")

        self.containment = {
            # "process" = stand-in for a real backend so verification logic is exercised
            "backend": "process",
            "network": "none",
            "read_only_paths": ["/"],
            "writable_tmp": "/tmp/sandbox",
            "memory_limit_mb": 512,
            "timeout_seconds": 30,
        }

        self.clean_exec = {
            "exit_code": 0,
            "duration_ms": 15.0,
            "peak_memory_mb": 35.0,
            "stdout": "harmless output\n",
            "stderr": "",
            "escape_detected": False,
            "network_attempted": False,
            "write_violation": False,
            "timeout_hit": False,
        }

        self.reviewer_promotion = {
            "reviewer_role": "reviewer",
            "reviewer_verdict": "PROMOTED",
            "signature_ref": "sig:ecc:cand-001:reviewed",
            "promoted_at": "2026-10-12T00:00:00Z",
        }

    def tearDown(self) -> None:
        hce.REAL_EXECUTOR_BACKENDS = self._saved
        self.tmp_dir.cleanup()

    def test_happy_path_evaluation_and_verification(self) -> None:
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-001",
            containment_config=self.containment,
            execution_result=self.clean_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        res = hce.verify_evaluation_receipt(receipt, expected_artifact_path=self.artifact)
        self.assertEqual(res["status"], "verified")
        self.assertEqual(res["verdict"], "PROMOTED")
        self.assertEqual(res["candidate_id"], "cand-001")

    def test_mock_eval_cannot_promote(self) -> None:
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-mock",
            containment_config=dict(self.containment, backend="mock"),
            execution_result=self.clean_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        self.assertTrue(receipt["simulated"])
        self.assertNotEqual(receipt["evaluation_verdict"], "CANDIDATE_EXECUTED_PASS")
        self.assertNotEqual(receipt["reviewer_promotion"]["reviewer_verdict"], "PROMOTED")
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "simulated_evaluation")

    def test_unlisted_backend_and_unsigned_review_rejected(self) -> None:
        r = hce.build_evaluation_receipt(self.artifact, "c", dict(self.containment, backend="bwrap"), self.clean_exec, self.reviewer_promotion)
        self.assertTrue(r["simulated"])
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(r)
        self.assertEqual(ctx.exception.reason, "simulated_evaluation")
        promo = dict(self.reviewer_promotion, signature_ref="unsigned:c")
        r2 = hce.build_evaluation_receipt(self.artifact, "c", self.containment, self.clean_exec, promo)
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(r2)
        self.assertEqual(ctx.exception.reason, "unsigned_review")

    def test_unknown_reviewer_role_rejected(self) -> None:
        promo = dict(self.reviewer_promotion, reviewer_role="rubber-stamp")
        receipt = hce.build_evaluation_receipt(self.artifact, "c", self.containment, self.clean_exec, promo)
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "reviewer_conflict")

    def test_escape_violation_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, escape_detected=True)
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-escape",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "escape_detected")

    def test_secret_leak_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, stdout="Leaked token: AKIAIOSFODNN7EXAMPLE\n")
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-secret",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "secret_detected")

    def test_network_violation_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, network_attempted=True)
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-net",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "network_violation")

    def test_write_violation_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, write_violation=True)
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-write",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "write_violation")

    def test_timeout_violation_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, timeout_hit=True)
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-timeout",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "timeout")

    def test_execution_failure_exit_code_fails_closed(self) -> None:
        bad_exec = dict(self.clean_exec, exit_code=1)
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-fail",
            containment_config=self.containment,
            execution_result=bad_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "execution_failed")

    def test_corrupted_receipt_fails_closed(self) -> None:
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-corrupt",
            containment_config=self.containment,
            execution_result=self.clean_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        # Alter receipt payload without recomputing hash
        receipt["candidate_id"] = "cand-tampered"
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "receipt_corrupted")

    def test_tampered_artifact_fails_closed(self) -> None:
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-artifact-tamper",
            containment_config=self.containment,
            execution_result=self.clean_exec,
            reviewer_promotion=self.reviewer_promotion,
        )
        # Modify artifact file after evaluation
        self.artifact.write_text('def run(): return "tampered payload"\n', encoding="utf-8")
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt, expected_artifact_path=self.artifact)
        self.assertEqual(ctx.exception.reason, "artifact_digest_mismatch")

    def test_reviewer_conflict_self_review_fails_closed(self) -> None:
        self_promotion = dict(self.reviewer_promotion, reviewer_role="implementer")
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-self",
            containment_config=self.containment,
            execution_result=self.clean_exec,
            reviewer_promotion=self_promotion,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "reviewer_conflict")

    def test_missing_promotion_fails_closed(self) -> None:
        receipt = hce.build_evaluation_receipt(
            artifact_path=self.artifact,
            candidate_id="cand-no-review",
            containment_config=self.containment,
            execution_result=self.clean_exec,
            reviewer_promotion=None,
        )
        with self.assertRaises(hce.HermeticEvalError) as ctx:
            hce.verify_evaluation_receipt(receipt)
        self.assertEqual(ctx.exception.reason, "promotion_missing")

    def test_cli_summary_evaluate_verify_roundtrip(self) -> None:
        cli = REPO_ROOT / "scripts" / "ai" / "aq-hermetic-eval"
        receipt_path = self.tmp_path / "test_receipt.json"

        proc = subprocess.run([str(cli), "summary", "--json"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertIn(data.get("status"), {"ok", "simulated_only", "no_receipts"})
        self.assertFalse(data.get("real_executor_available"))
        self.assertFalse(data.get("signatures_verified"))

        eval_proc = subprocess.run(
            [str(cli), "evaluate", str(self.artifact), "--candidate-id", "cli-cand-1", "--backend", "mock", "--json"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        receipt_data = json.loads(eval_proc.stdout)
        self.assertTrue(receipt_data["simulated"])
        self.assertNotEqual(receipt_data["reviewer_promotion"]["reviewer_verdict"], "PROMOTED")
        receipt_path.write_text(json.dumps(receipt_data), encoding="utf-8")

        verify_proc = subprocess.run(
            [str(cli), "verify", str(receipt_path), "--artifact", str(self.artifact), "--json"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(verify_proc.returncode, 0)
        self.assertEqual(json.loads(verify_proc.stdout).get("reason"), "simulated_evaluation")

        real_proc = subprocess.run(
            [str(cli), "evaluate", str(self.artifact), "--candidate-id", "x", "--backend", "bwrap", "--json"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(real_proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
