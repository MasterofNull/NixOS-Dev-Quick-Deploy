#!/usr/bin/env python3
"""Automated tests for Autonomous On-Call Incident Daemon (`aq-oncalld`, Slice DP-3).

Verifies:
  1. Incident intake, confidence thresholding, and correlation deduplication.
  2. Monotonic epoch fencing (fences out stale workers).
  3. Ambient credential scrubbing and workspace containment.
  4. Candidate SHA256 binding and drift detection.
  5. Independent model reviewer gate (Rule 18 anti-self-review).
  6. End-to-end remediation lifecycle state transitions.
  7. CLI utility integration (aq-oncalld status, verify, trigger).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ai" / "lib"))

from oncalld_engine import (
    OnCallDaemonEngine,
    OnCallIncident,
    OnCallStorage,
    RemediationClaim,
    EpochFencingError,
    ContainmentViolationError,
    ReviewIntegrityError,
    compute_candidate_sha256,
    verify_candidate_binding,
    scrub_credentials,
    verify_worktree_containment,
)


class TestOnCallDaemon(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_oncalld_")
        self.state_dir = Path(self.temp_dir) / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.delegation_dir = Path(self.temp_dir) / "delegation"
        self.delegation_dir.mkdir(parents=True, exist_ok=True)
        self._orig_delegation = os.environ.get("AQ_DELEGATION_DIR")
        self._orig_simulate = os.environ.get("AQ_ONCALL_SIMULATE_WORKTREE")
        os.environ["AQ_DELEGATION_DIR"] = str(self.delegation_dir)
        os.environ["AQ_ONCALL_SIMULATE_WORKTREE"] = "1"
        self.engine = OnCallDaemonEngine(
            repo_root=_REPO_ROOT,
            state_dir=self.state_dir,
            confidence_threshold=0.70
        )

    def tearDown(self) -> None:
        if self._orig_delegation is not None:
            os.environ["AQ_DELEGATION_DIR"] = self._orig_delegation
        else:
            os.environ.pop("AQ_DELEGATION_DIR", None)
        if self._orig_simulate is not None:
            os.environ["AQ_ONCALL_SIMULATE_WORKTREE"] = self._orig_simulate
        else:
            os.environ.pop("AQ_ONCALL_SIMULATE_WORKTREE", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_admission_and_deduplication(self) -> None:
        """Test intake evaluation, confidence gating, and correlation deduplication."""
        # 1. Non-actionable record should be rejected
        rec_noise = {
            "source": "api-gateway",
            "severity": "info",
            "actionable": False,
            "confidence": 0.95,
            "summary": "Routine health ping"
        }
        self.assertIsNone(self.engine.admit_incident(rec_noise))

        # 2. Low confidence record should be rejected
        rec_low_conf = {
            "source": "database",
            "severity": "critical",
            "actionable": True,
            "confidence": 0.55,
            "summary": "Suspected query timeout"
        }
        self.assertIsNone(self.engine.admit_incident(rec_low_conf))

        # 3. Valid actionable incident should be admitted
        rec_valid = {
            "incident_id": "test-inc-01",
            "source": "hybrid-coordinator",
            "severity": "critical",
            "incident_class": "crash",
            "actionable": True,
            "confidence": 0.92,
            "correlation_key": "hybrid-coordinator:crash:oom",
            "summary": "Process terminated with SIGKILL (OOM)",
            "reproduction_cmd": "exit 1"
        }
        inc = self.engine.admit_incident(rec_valid)
        self.assertIsNotNone(inc)
        self.assertEqual(inc.incident_id, "test-inc-01")
        self.assertEqual(inc.status, "ADMITTED")

        # 4. Duplicate with same correlation_key should be deduplicated
        inc_dup = self.engine.admit_incident(rec_valid)
        self.assertIsNone(inc_dup)

    def test_02_monotonic_epoch_fencing(self) -> None:
        """Test monotonic epoch increment and rejection of stale worker claims."""
        inc = self.engine.admit_incident({
            "incident_id": "test-inc-fencing",
            "source": "switchboard",
            "severity": "high",
            "incident_class": "timeout",
            "actionable": True,
            "confidence": 0.88,
            "correlation_key": "swb:timeout",
            "summary": "SSE stream timeout"
        })
        self.assertIsNotNone(inc)

        # First claim gets epoch 1
        claim1 = self.engine.claim_incident(inc.incident_id, claimant_lane="codex")
        self.assertEqual(claim1.epoch, 1)

        # Second claim increments epoch to 2 (fences out claim 1)
        claim2 = self.engine.claim_incident(inc.incident_id, claimant_lane="local")
        self.assertEqual(claim2.epoch, 2)

        # Worker with stale claim 1 attempts to save progress -> raises EpochFencingError
        claim1.state = "DIAGNOSING"
        with self.assertRaises(EpochFencingError):
            self.engine.storage.save_claim(claim1, expected_epoch=1)

        # Worker with active claim 2 saves successfully
        claim2.state = "DIAGNOSING"
        self.engine.storage.save_claim(claim2, expected_epoch=2)
        saved = self.engine.storage.get_claim(claim2.claim_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.state, "DIAGNOSING")

    def test_03_credential_scrubbing_and_containment(self) -> None:
        """Test ambient credential scrubbing and worktree boundary containment."""
        dirty_env = {
            "PATH": "/nix/var/nix/profiles/default/bin:/usr/bin",
            "USER": "hyperd",
            "HOME": "/home/hyperd",
            "GITHUB_TOKEN": "ghp_1234567890abcdef",
            "GH_TOKEN": "ghp_secret",
            "SOPS_AGE_KEY": "AGE-SECRET-KEY-XYZ",
            "SSH_AUTH_SOCK": "/run/user/1000/ssh.sock",
            "OPENAI_API_KEY": "sk-proj-xyz",
            "ANTHROPIC_API_KEY": "sk-ant-abc",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "MY_CUSTOM_SECRET": "topsecret",
            "TERM": "xterm-256color"
        }
        scrubbed = scrub_credentials(dirty_env)

        # Sensitive variables stripped
        self.assertNotIn("GITHUB_TOKEN", scrubbed)
        self.assertNotIn("GH_TOKEN", scrubbed)
        self.assertNotIn("SOPS_AGE_KEY", scrubbed)
        self.assertNotIn("SSH_AUTH_SOCK", scrubbed)
        self.assertNotIn("OPENAI_API_KEY", scrubbed)
        self.assertNotIn("ANTHROPIC_API_KEY", scrubbed)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", scrubbed)
        self.assertNotIn("MY_CUSTOM_SECRET", scrubbed)

        # Safe system variables preserved
        self.assertEqual(scrubbed.get("USER"), "hyperd")
        self.assertEqual(scrubbed.get("HOME"), "/home/hyperd")
        self.assertEqual(scrubbed.get("AQ_ONCALL_CONFINED"), "1")
        self.assertEqual(scrubbed.get("AQ_DELEGATE_HANDBACK"), "1")

        # Worktree containment checks
        allowed_path = str(_REPO_ROOT / ".agents" / "delegation" / "worktrees" / "claim-123")
        self.assertTrue(verify_worktree_containment(allowed_path, _REPO_ROOT))

        # Root repo must NOT be treated as isolated worktree
        self.assertFalse(verify_worktree_containment(str(_REPO_ROOT), _REPO_ROOT))
        self.assertFalse(verify_worktree_containment("/tmp/random", _REPO_ROOT))

    def test_04_candidate_sha_binding_and_drift_detection(self) -> None:
        """Test candidate SHA binding and drift detection."""
        tree_hash = "a1b2c3d4e5f67890"
        proofs = "=== PASS 56/56 Tier-0 gates ==="

        t_hash, p_hash, candidate_sha = compute_candidate_sha256(tree_hash, proofs)
        self.assertEqual(t_hash, tree_hash)
        self.assertTrue(verify_candidate_binding(candidate_sha, tree_hash, proofs))

        # Drift in tree hash invalidates binding
        drifted_tree = "9999999999999999"
        self.assertFalse(verify_candidate_binding(candidate_sha, drifted_tree, proofs))

        # Drift in test proofs invalidates binding
        drifted_proofs = "=== PASS 55/56 Tier-0 gates (1 failed) ==="
        self.assertFalse(verify_candidate_binding(candidate_sha, tree_hash, drifted_proofs))

    def test_05_independent_reviewer_gate(self) -> None:
        """Test Rule 18 independent model review gate and self-review rejection."""
        inc = self.engine.admit_incident({
            "incident_id": "test-inc-review",
            "source": "aidb",
            "severity": "critical",
            "incident_class": "crash",
            "actionable": True,
            "confidence": 0.95,
            "correlation_key": "aidb:crash",
            "summary": "Vector database segmentation fault"
        })
        self.assertIsNotNone(inc)
        claim = self.engine.claim_incident(inc.incident_id, claimant_lane="codex")

        # 1. Rule 18 violation: claimant "codex" attempting to self-review
        with self.assertRaises(ReviewIntegrityError):
            self.engine.complete_remediation(
                claim_id=claim.claim_id,
                git_tree_hash="tree123",
                test_proofs="PASS all checks",
                reviewer_lane="codex"  # Self-review forbidden!
            )

        # 2. Distinct model lane "antigravity" conducts review -> PASS
        completed = self.engine.complete_remediation(
            claim_id=claim.claim_id,
            git_tree_hash="tree123",
            test_proofs="PASS all checks",
            reviewer_lane="antigravity"
        )
        self.assertEqual(completed.reviewer_lane, "antigravity")
        self.assertEqual(completed.reviewer_verdict, "PASS")
        self.assertEqual(completed.state, "PR_STAGED")

    def test_06_remediation_lifecycle_state_machine(self) -> None:
        """Test full incident lifecycle state progression."""
        inc = self.engine.admit_incident({
            "incident_id": "test-inc-lifecycle",
            "source": "dashboard",
            "severity": "medium",
            "incident_class": "health_check_failure",
            "actionable": True,
            "confidence": 0.85,
            "correlation_key": "dashboard:health",
            "summary": "Health endpoint latency spike",
            "reproduction_cmd": "exit 1"
        })
        self.assertEqual(inc.status, "ADMITTED")

        claim = self.engine.claim_incident(inc.incident_id, claimant_lane="local")
        self.assertEqual(claim.state, "ISOLATING")

        # Worktree setup
        self.engine.create_isolated_worktree(claim)
        self.assertEqual(claim.state, "REPRODUCING")

        # Complete remediation
        completed = self.engine.complete_remediation(
            claim_id=claim.claim_id,
            git_tree_hash="final_tree_abc",
            test_proofs="PASS 56/56 checks",
            reviewer_lane="codex"
        )
        self.assertEqual(completed.state, "PR_STAGED")

        # Incident updated to RESOLVED
        updated_inc = self.engine.storage.get_incident(inc.incident_id)
        self.assertIsNotNone(updated_inc)
        self.assertEqual(updated_inc.status, "RESOLVED")

        # Summary verification
        summary = self.engine.health_summary()
        self.assertEqual(summary["resolved_incidents"], 1)
        self.assertEqual(summary["staged_prs"], 1)

    def test_07_cli_integration(self) -> None:
        """Test aq-oncalld CLI invocation and command outputs."""
        aq_oncalld_bin = _REPO_ROOT / "scripts" / "ai" / "aq-oncalld"

        # 1. --verify
        res_verify = subprocess.run(
            [sys.executable, str(aq_oncalld_bin), "--verify", "--state-dir", str(self.state_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_verify.returncode, 0)
        self.assertIn("PASS", res_verify.stdout)

        # 2. --status --json
        res_status = subprocess.run(
            [sys.executable, str(aq_oncalld_bin), "--status", "--json", "--state-dir", str(self.state_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_status.returncode, 0)
        data = json.loads(res_status.stdout)
        self.assertIn("status", data)
        self.assertIn("confidence_threshold", data)

        # 3. --trigger with JSON payload
        trigger_payload = json.dumps({
            "incident_id": "test-cli-inc",
            "source": "llama-cpp",
            "severity": "high",
            "incident_class": "crash",
            "actionable": True,
            "confidence": 0.95,
            "correlation_key": "llama:crash",
            "summary": "Inference worker died",
            "suggested_lane": "codex"
        })
        res_trigger = subprocess.run(
            [sys.executable, str(aq_oncalld_bin), "--trigger", trigger_payload, "--json", "--state-dir", str(self.state_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_trigger.returncode, 0)
        trig_data = json.loads(res_trigger.stdout)
        self.assertEqual(trig_data["status"], "claimed")
        self.assertEqual(trig_data["incident_id"], "test-cli-inc")


def main() -> int:
    print("=== Testing Autonomous On-Call Incident Daemon (DP-3) ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOnCallDaemon)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"\n7/7 fixtures passed.")
        print("ALL 7 FIXTURES PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
