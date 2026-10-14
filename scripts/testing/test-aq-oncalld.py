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
    WorktreeIsolationError,
    DuplicateClaimError,
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
        self._orig_test_mode = os.environ.get("AQ_ONCALL_TEST_MODE")
        os.environ["AQ_ONCALL_TEST_MODE"] = "1"
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
        if self._orig_test_mode is not None:
            os.environ["AQ_ONCALL_TEST_MODE"] = self._orig_test_mode
        else:
            os.environ.pop("AQ_ONCALL_TEST_MODE", None)
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
        claim2 = self.engine.claim_incident(inc.incident_id, claimant_lane="local", takeover=True)
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
            "GITHUB_TOKEN": "placeholder",
            "GH_TOKEN": "placeholder",
            "SOPS_AGE_KEY": "placeholder",
            "SSH_AUTH_SOCK": "placeholder",
            "OPENAI_API_KEY": "placeholder",
            "ANTHROPIC_API_KEY": "placeholder",
            "AWS_SECRET_ACCESS_KEY": "placeholder",
            "MY_CUSTOM_SECRET": "placeholder",
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

        # 2. Distinct lane is assigned, but NO verdict exists until a real reviewer records one
        completed = self.engine.complete_remediation(
            claim_id=claim.claim_id,
            git_tree_hash="tree123",
            test_proofs="PASS all checks",
            reviewer_lane="antigravity"
        )
        self.assertEqual(completed.reviewer_lane, "antigravity")
        self.assertIsNone(completed.reviewer_verdict)
        self.assertEqual(completed.state, "AWAITING_REVIEW")

        # 3. Real verdict with drifted tree is refused; matching one moves to PENDING_PR
        with self.assertRaises(ReviewIntegrityError):
            self.engine.record_review(claim.claim_id, "antigravity", "PASS", "ok", "other", "PASS all checks")
        done = self.engine.record_review(claim.claim_id, "antigravity", "PASS", "ok", "tree123", "PASS all checks")
        self.assertEqual(done.state, "PENDING_PR")
        self.assertEqual(done.reviewer_verdict, "PASS")

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
        self.assertEqual(completed.state, "AWAITING_REVIEW")

        # No reviewer ran and no PR exists: incident must NOT be RESOLVED
        updated_inc = self.engine.storage.get_incident(inc.incident_id)
        self.assertIsNotNone(updated_inc)
        self.assertEqual(updated_inc.status, "CLAIMED")

        summary = self.engine.health_summary()
        self.assertEqual(summary["resolved_incidents"], 0)
        self.assertEqual(summary["staged_prs"], 0)
        self.assertEqual(summary["awaiting_review"], 1)

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

    # ── DP-3 review-revision regressions (F1-F6) ─────────────────────────────

    def _admit_claim(self, iid: str, key: str):
        inc = self.engine.admit_incident({
            "incident_id": iid, "source": "svc", "severity": "high", "incident_class": "crash",
            "actionable": True, "confidence": 0.9, "correlation_key": key, "summary": "s",
            "reproduction_cmd": "exit 1",
        })
        self.assertIsNotNone(inc)
        return self.engine.claim_incident(inc.incident_id, claimant_lane="codex")

    def test_08_f1_no_fabricated_pass_or_pr(self) -> None:
        claim = self._admit_claim("f1", "k-f1")
        done = self.engine.complete_remediation(claim.claim_id, "tree", "PASS ok", reviewer_lane="antigravity")
        self.assertIsNone(done.reviewer_verdict)
        self.assertIsNone(done.pr_branch)
        self.assertNotIn(done.state, ("PR_STAGED", "AWAIT_OPERATOR"))
        self.assertNotEqual(self.engine.storage.get_incident("f1").status, "RESOLVED")
        src = (_REPO_ROOT / "scripts/ai/lib/oncalld_engine.py").read_text()
        self.assertNotIn("_conduct_review", src)

    def test_09_f2_worktree_failure_fails_closed(self) -> None:
        os.environ.pop("AQ_ONCALL_SIMULATE_WORKTREE", None)
        claim = self._admit_claim("f2", "k-f2")
        claim.worktree_branch = "bad..branch name"  # git rejects this ref name
        with self.assertRaises(WorktreeIsolationError):
            self.engine.create_isolated_worktree(claim)
        self.assertFalse(Path(claim.worktree_path).exists())
        self.assertEqual(self.engine.storage.get_claim(claim.claim_id).state, "FAILED")

    def test_10_f3_reproduction_is_confined_or_deferred(self) -> None:
        import shutil as _sh
        from unittest import mock
        claim = self._admit_claim("f3", "k-f3")
        self.engine.create_isolated_worktree(claim)
        with mock.patch("oncalld_engine.shutil.which", return_value=None), \
             mock.patch("oncalld_engine.subprocess.run") as run:
            res = self.engine.reproduce_incident(claim)
            run.assert_not_called()
        self.assertTrue(res.get("deferred"))
        self.assertEqual(res["reason"], "no_sandbox_available")
        # Missing worktree must never fall back to running in the repo root
        claim.worktree_path = str(self.delegation_dir / "worktrees" / "missing")
        with mock.patch("oncalld_engine.subprocess.run") as run:
            res = self.engine.reproduce_incident(claim)
            run.assert_not_called()
        self.assertEqual(res["reason"], "no_isolated_worktree")
        if _sh.which("bwrap"):
            claim2 = self._admit_claim("f3b", "k-f3b")
            self.engine.create_isolated_worktree(claim2)
            r = self.engine.reproduce_incident(claim2, custom_cmd="exit 3")
            self.assertEqual(r.get("confined"), "bwrap")

    def test_11_f4_one_implementer_per_incident(self) -> None:
        claim = self._admit_claim("f4", "k-f4")
        with self.assertRaises(DuplicateClaimError):
            self.engine.claim_incident("f4", claimant_lane="local")
        # DB-level backstop: a raw second active claim is rejected by the unique index
        dup = RemediationClaim(
            claim_id="claim-f4-x", incident_id="f4", epoch=99, claimant_lane="local",
            worktree_path=claim.worktree_path, worktree_branch="b", state="ISOLATING",
            created_at="t", updated_at="t")
        with self.assertRaises(DuplicateClaimError):
            self.engine.storage.save_claim(dup)
        # Same correlation key admitted twice (even with different ids) yields one incident
        again = self.engine.admit_incident({
            "incident_id": "f4-twin", "source": "svc", "severity": "high", "incident_class": "crash",
            "actionable": True, "confidence": 0.9, "correlation_key": "k-f4"})
        self.assertIsNone(again)

    def test_12_f5_route_offloads_blocking_calls(self) -> None:
        import ast
        src = (_REPO_ROOT / "dashboard/backend/api/routes/aistack.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.AsyncFunctionDef) and n.name == "post_oncall_trigger")
        body = ast.get_source_segment(src, fn)
        self.assertIn("asyncio.to_thread", body)
        self.assertNotIn("create_isolated_worktree", body)
        self.assertNotIn("subprocess", body)

    def test_13_f6_heartbeat_only_from_daemon_loop(self) -> None:
        s0 = self.engine.health_summary()
        self.assertEqual(s0["heartbeat"]["state"], "unknown")
        self.assertIsNone(s0["last_heartbeat"])
        self.assertEqual(s0["status"], "unverified")
        self.engine.run_daemon(max_iterations=1, interval=0)
        s1 = self.engine.health_summary()
        self.assertEqual(s1["heartbeat"]["state"], "alive")
        self.assertIsNotNone(s1["last_heartbeat"])
        # Old heartbeat reads as stale
        hb = json.loads(self.engine.heartbeat_path.read_text())
        hb["ts"] = "2000-01-01T00:00:00+00:00"
        self.engine.heartbeat_path.write_text(json.dumps(hb))
        s2 = self.engine.health_summary()
        self.assertEqual(s2["heartbeat"]["state"], "stale")
        self.assertEqual(s2["status"], "stale")

    def test_14_old_schema_duplicates_migrate_not_memory_fallback(self) -> None:
        import sqlite3
        db = Path(self.temp_dir) / "old" / "oncall.db"
        db.parent.mkdir()
        conn = sqlite3.connect(str(db))
        conn.executescript("""
            CREATE TABLE oncall_incidents (incident_id TEXT PRIMARY KEY, title TEXT, source TEXT,
              severity TEXT, incident_class TEXT, confidence REAL, correlation_key TEXT NOT NULL,
              reproduction_cmd TEXT, status TEXT NOT NULL, raw_details TEXT, created_at TEXT, updated_at TEXT);
            INSERT INTO oncall_incidents VALUES ('a','t','s','HIGH','CRASH',0.9,'k','', 'ADMITTED','{}','1','1');
            INSERT INTO oncall_incidents VALUES ('b','t','s','HIGH','CRASH',0.9,'k','', 'ADMITTED','{}','2','2');
        """)
        conn.commit(); conn.close()
        st = OnCallStorage(db)
        self.assertFalse(st._fallback_memory)
        self.assertEqual(st.get_incident("a").status, "REJECTED")
        self.assertEqual(st.get_incident("b").status, "ADMITTED")
        # fallback, when forced, is visible in health_summary
        eng = OnCallDaemonEngine(repo_root=_REPO_ROOT, state_dir=self.state_dir)
        eng.storage._fallback_memory = True
        eng.storage._mem_conn = sqlite3.connect(":memory:")
        eng.storage._mem_conn.row_factory = sqlite3.Row
        eng.storage._init_db()
        hs = eng.health_summary()
        self.assertTrue(hs["storage_fallback_memory"])
        self.assertEqual(hs["status"], "degraded")

    def test_15_failed_claim_releases_and_operator_paths(self) -> None:
        claim = self._admit_claim("r1", "k-r1")
        self.engine.complete_remediation(claim.claim_id, "tree", "FAIL tests", reviewer_lane="antigravity")
        self.assertEqual(self.engine.storage.get_claim(claim.claim_id).state, "FAILED")
        self.assertEqual(self.engine.storage.get_incident("r1").status, "ADMITTED")  # claimable, not RESOLVED
        c2 = self.engine.claim_incident("r1", claimant_lane="local")  # re-claim works
        self.engine.requeue_incident("r1", actor="op", note="retry")
        self.assertEqual(self.engine.storage.get_claim(c2.claim_id).state, "FAILED")
        inc = self.engine.storage.get_incident("r1")
        self.assertEqual(inc.status, "ADMITTED")
        self.engine.resolve_incident("r1", actor="op", note="fixed by hand")
        inc = self.engine.storage.get_incident("r1")
        self.assertEqual(inc.status, "RESOLVED")
        last = inc.raw_details["operator_actions"][-1]
        self.assertEqual((last["action"], last["actor"]), ("resolve", "op"))
        self.assertTrue(last["ts"])
        aq = _REPO_ROOT / "scripts" / "ai" / "aq-oncalld"
        res = subprocess.run([sys.executable, str(aq), "--requeue", "nope", "--state-dir", str(self.state_dir)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)

    def test_16_simulate_requires_test_mode_marker(self) -> None:
        os.environ.pop("AQ_ONCALL_TEST_MODE", None)
        claim = self._admit_claim("s1", "k-s1")
        claim.worktree_branch = "bad..branch name"
        with self.assertRaises(WorktreeIsolationError):
            self.engine.create_isolated_worktree(claim)  # SIMULATE=1 alone must not bypass git
        os.environ["AQ_ONCALL_TEST_MODE"] = "1"
        claim2 = self._admit_claim("s2", "k-s2")
        with self.assertLogs("aq-oncalld", level="WARNING"):
            self.engine.create_isolated_worktree(claim2)

    def test_17_self_review_leaves_state_unchanged(self) -> None:
        claim = self._admit_claim("v1", "k-v1")
        before = self.engine.storage.get_claim(claim.claim_id)
        with self.assertRaises(ReviewIntegrityError):
            self.engine.complete_remediation(claim.claim_id, "t", "PASS", reviewer_lane="codex")
        after = self.engine.storage.get_claim(claim.claim_id)
        self.assertEqual(after.state, before.state)
        self.assertNotEqual(after.state, "REVIEWING")
        self.assertIsNone(after.candidate_sha256)


def main() -> int:
    print("=== Testing Autonomous On-Call Incident Daemon (DP-3) ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOnCallDaemon)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"\n{result.testsRun}/{result.testsRun} fixtures passed.")
        print(f"ALL {result.testsRun} FIXTURES PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
