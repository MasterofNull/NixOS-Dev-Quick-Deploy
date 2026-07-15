#!/usr/bin/env python3
"""Hermetic R0 characterizations for local delegation reliability (D1-D11)."""
from __future__ import annotations

import importlib.util
import json
import os
import resource
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "scripts/ai/lib/local_delegation_reliability.py"
POLICY_PATH = REPO / "config/local-delegation-runtime-policy.json"
SCHEMA_PATH = REPO / "config/schemas/local-delegation-runtime-policy.schema.json"
FIXTURE_PATH = REPO / "scripts/testing/fixtures/local-delegation-reliability-golden.json"

spec = importlib.util.spec_from_file_location("local_delegation_reliability_r0", MODULE_PATH)
assert spec and spec.loader
lr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lr
spec.loader.exec_module(lr)


class ReliabilityR0(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.before = {entry["path"]: (REPO / entry["path"]).read_bytes() for entry in cls.fixture["live_sources"]}
        cls.state_roots = [REPO / ".agents/delegation", REPO / ".agent/collaboration"]
        cls.state_before = {str(root.relative_to(REPO)): lr.tree_manifest(root) for root in cls.state_roots}

    @classmethod
    def tearDownClass(cls) -> None:
        after = {path: (REPO / path).read_bytes() for path in cls.before}
        if after != cls.before:
            raise AssertionError("R0 characterization mutated a frozen live source")
        state_after = {str(root.relative_to(REPO)): lr.tree_manifest(root) for root in cls.state_roots}
        if state_after != cls.state_before:
            raise AssertionError("R0 characterization mutated canonical delegation/collaboration state")

    def assertContractError(self, reason: str, callable_, *args, **kwargs) -> None:
        with self.assertRaises(lr.ContractError) as raised:
            callable_(*args, **kwargs)
        self.assertEqual(str(raised.exception), reason)

    def test_01_policy_and_closed_schema(self) -> None:
        self.assertEqual(lr.validate_policy(self.policy, self.schema), self.policy)
        self.assertFalse(self.schema["additionalProperties"])
        for section in ("identity", "liveness", "admission", "progress", "context"):
            self.assertFalse(self.schema["properties"][section]["additionalProperties"])
        self.assertEqual(self.policy["admission"]["authority"], "switchboard")
        self.assertEqual(self.policy["compatibility_aliases"], [])
        self.assertEqual(tuple(self.policy["metrics"]), lr.LOW_CARDINALITY_METRICS)
        injected = json.loads(json.dumps(self.policy)); injected["admission"]["unknown_authority"] = True
        self.assertContractError("schema_unknown_property:$.admission", lr.validate_policy, injected, self.schema)
        oversized = json.loads(json.dumps(self.policy)); oversized["identity"]["entropy_bytes"] = 33
        self.assertContractError("schema_maximum:$.identity.entropy_bytes", lr.validate_policy, oversized, self.schema)

    def test_02_live_manifest_and_d1_d11_static_characterization(self) -> None:
        manifest = lr.source_manifest(REPO, self.fixture["live_sources"])
        self.assertTrue(all(item["matches_frozen"] for item in manifest), manifest)
        covered = set()
        for entry in self.fixture["live_sources"]:
            covered.update(entry["defects"])
            result = lr.characterize_rules((REPO / entry["path"]).read_text(encoding="utf-8"), entry["characterizations"])
            self.assertTrue(result["all_present"], {entry["path"]: result})
        self.assertEqual(covered, {f"D{i}" for i in range(1, 12)})
        self.assertEqual(set(self.fixture["defects"]), covered)

    def test_03_identity_collision_rejection_and_propagation(self) -> None:
        vector = self.fixture["identity"]
        seen: set[str] = set()
        ids = [lr.allocate_run_id("aq", vector["same_time_ns"], i.to_bytes(16, "big"), seen) for i in range(vector["count"])]
        self.assertEqual(len(ids), len(set(ids)))
        repeated_seen: set[str] = set()
        lr.allocate_run_id("aq", 1, b"x" * 16, repeated_seen)
        self.assertContractError("identity_collision", lr.allocate_run_id, "aq", 1, b"x" * 16, repeated_seen)
        propagated = lr.propagate_identity(ids[0], vector["propagation"])
        self.assertEqual(set(propagated.values()), {ids[0]})

    def test_04_budget_provenance_and_legacy_drift(self) -> None:
        for vector in self.fixture["budget_vectors"]:
            resolved = lr.resolve_budget(self.policy, vector["class"])
            self.assertEqual(resolved, {"task_class": vector["class"], "max_tokens": vector["expected"], "source": "policy"})
        explicit = lr.resolve_budget(self.policy, "code", 1600)
        self.assertEqual(explicit["source"], "explicit")
        self.assertContractError("budget_undersized", lr.resolve_budget, self.policy, "code", 800)
        executor = (REPO / "ai-stack/local-agents/agent_executor.py").read_text(encoding="utf-8")
        shared = (REPO / "ai-stack/mcp-servers/shared/llm_config.py").read_text(encoding="utf-8")
        self.assertIn("AGENT_TOOL_CALL_MAX_TOKENS = 256", shared)
        self.assertIn("AGENT_TASK_MAX_TOKENS = 800", shared)
        self.assertIn("max_tokens=512", executor)
        self.assertIn("max_tokens=256", executor)

    def test_05_phase_separation_progress_and_finite_capability(self) -> None:
        vector = self.fixture["phase_vector"]
        self.assertGreater(lr.phase_deadline(self.policy, "queued"), vector["queue_elapsed_s"])
        prefill = lr.phase_deadline(self.policy, "prefill", input_tokens=vector["prefill_tokens"], prefill_tps=vector["prefill_tps"], cold_headroom_s=vector["cold_headroom_s"])
        self.assertEqual(prefill, 720.0)
        self.assertGreater(lr.phase_deadline(self.policy, "generating"), vector["generation_silence_s"])
        typed = {
            phase: lr.evaluate_liveness(self.policy, phase, lr.phase_deadline(self.policy, phase) + 1)
            for phase in ("queued", "prefill", "generating", "tool", "orphan")
        }
        self.assertEqual(typed, {"queued": "queue_timeout", "prefill": "prefill_timeout", "generating": "generation_silence", "tool": "tool_timeout", "orphan": "orphaned"})
        fresh = lr.validate_calibration({
            "model_revision": "m1", "profile_revision": "p1", "source": "benchmark", "measured_at": 1,
            "expires_at": 100, "cache_class": "cold", "sample_count": 10, "tps": 20.0,
            "uncertainty": 0.2, "headroom": 1.5,
        }, 50, 900)
        self.assertEqual(fresh["status"], "fresh"); self.assertEqual(fresh["uncertainty"], 0.2)
        stale = lr.validate_calibration({
            "model_revision": "m1", "profile_revision": "p1", "source": "benchmark", "measured_at": 1,
            "expires_at": 40, "cache_class": "warm", "sample_count": 10, "tps": 30.0,
            "uncertainty": 0.1, "headroom": 1.2,
        }, 50, 900)
        self.assertEqual(stale, {"status": "degraded_stale", "prefill_s": 900, "source": "conservative_policy"})
        for drift in self.fixture["clock_drift_seconds"]:
            clock = lr.monotonic_clock_evidence(1_000_000_000, 11_000_000_000, 100, 110 + drift)
            self.assertEqual(clock["elapsed_s"], 10.0); self.assertEqual(clock["host_drift_s"], drift)
            self.assertEqual(clock["lease_clock"], "monotonic")
        epoch = lr.Epoch(1, 2, 100, 60)
        self.assertEqual(epoch.consume(1, 50, 20), "continue")
        self.assertEqual(epoch.consume(2, 60, 50), "checkpoint_yield_requeue")
        self.assertTrue(epoch.yielded)
        self.assertContractError("self_renewal_forbidden", lr.Epoch(1, 1, 1, 1).consume, 1, 1, 1, actor="worker")
        capped = json.loads(json.dumps(self.policy)); capped["liveness"]["operator_wall_clock_s"] = 100
        self.assertEqual(lr.evaluate_liveness(capped, "generating", 1, total_elapsed_s=101), "operator_cap")

    def test_06_fairness_aging_residency_and_starvation(self) -> None:
        vector = self.fixture["fairness"]
        items = [lr.QueueItem(item["run_id"], item["enqueued_at"], item["priority"]) for item in vector["items"]]
        self.assertEqual(lr.fair_order(items, vector["now"], vector["aging_s"]), vector["expected_order"])
        # An adversary arriving at max base priority cannot starve an aged waiter forever.
        waiter = lr.QueueItem("waiter", 0, 0)
        for now in range(100, 2100, 100):
            adversary = lr.QueueItem(f"new-{now}", now, 10)
            if lr.fair_order([waiter, adversary], now, 100)[0] == "waiter":
                break
        else:
            self.fail("priority aging did not bound starvation")
        self.assertLessEqual(now, self.policy["admission"]["queue_age_slo_s"])
        self.assertGreater(self.policy["admission"]["max_residency_s"], 0)
        maximum = self.policy["admission"]["max_residency_s"]
        self.assertEqual(lr.residency_action(maximum - 1, maximum), "continue")
        self.assertEqual(lr.residency_action(maximum, maximum), "checkpoint_yield_requeue")

    def test_07_novelty_beyond_old_counts_and_duplicate_stop(self) -> None:
        guard = lr.DuplicateGuard(3, 5)
        for i in range(20):
            fp = lr.normalized_evidence("read_file", {"path": f"file-{i}"}, {"content": str(i)})
            self.assertEqual(guard.observe(fp), "accepted_novel")
        observations = lr.DuplicateGuard(3, 5)
        for i in range(15):
            self.assertEqual(observations.observe(lr.normalized_evidence("query", {"q": i}, {"answer": i})), "accepted_novel")
        repeated = lr.DuplicateGuard(3, 5)
        outcomes = [repeated.observe(lr.normalized_evidence("read_file", {"path": "missing"}, {"error": "missing", "timestamp": i})) for i in range(5)]
        self.assertIn("nudge_checkpoint", outcomes)
        self.assertEqual(outcomes[-1], "stagnation_duplicate_evidence")

    def test_08_trusted_progress_phase_correlation_and_tamper_rejection(self) -> None:
        run_id = lr.allocate_run_id("aq", 2, b"p" * 16)
        validator = lr.ProgressValidator(self.policy, run_id, 1)
        good = lr.ProgressRecord(run_id, 1, "op-1", "switchboard", 1, 10, "queued", "a", "b", "state_transition", "corr-1")
        self.assertEqual(validator.accept(good), "queued")
        forged = lr.ProgressRecord(run_id, 1, "op-2", "model", 2, 11, "checkpoint", "a", "b", "checkpoint")
        self.assertContractError("progress_producer_untrusted", validator.accept, forged)
        replay = lr.ProgressRecord(run_id, 1, "op-1", "switchboard", 2, 11, "queued", "a", "b", "novel", "corr-1")
        self.assertContractError("progress_replay", validator.accept, replay)
        reordered = lr.ProgressRecord(run_id, 1, "op-3", "switchboard", 3, 12, "queued", "a", "b", "novel", "corr-1")
        self.assertContractError("progress_sequence_invalid", validator.accept, reordered)
        unavailable = lr.ProgressValidator(self.policy, run_id, 1)
        no_correlation = lr.ProgressRecord(run_id, 1, "op-x", "switchboard", 1, 1, "prefill", "a", "b", "novel")
        self.assertContractError("phase_evidence_unavailable", unavailable.accept, no_correlation)
        first = lr.normalized_evidence("tool", {"x": 1, "timestamp": 1}, {"ok": True, "nonce": "a"})
        second = lr.normalized_evidence("tool", {"x": 1, "timestamp": 2}, {"ok": True, "nonce": "b"})
        self.assertEqual(first, second, "volatile-only changes must not renew progress")
        self.assertContractError("progress_sidecar_truncated", lr.parse_progress_sidecar, '{"run_id":')
        self.assertContractError("progress_sidecar_truncated", lr.parse_progress_sidecar, '{"run_id":"x"}')

    def test_09_cancellation_pid_identity_and_terminal_linearization(self) -> None:
        captured = lr.ProcessIdentity(10, 100, 10, 10)
        cancel = lr.Cancellation(); self.assertEqual(cancel.request(), "cancelling")
        self.assertEqual(cancel.request(), "cancelling")
        self.assertEqual(cancel.send_term(captured, captured), "sigterm_sent")
        self.assertEqual(cancel.send_term(captured, captured), "sigterm_sent")
        self.assertEqual(cancel.observe(captured, captured), "sigterm_waiting")
        self.assertEqual(cancel.observe(captured, captured, grace_expired=True), "sigkill_sent")
        self.assertEqual(cancel.observe(captured, captured, grace_expired=True), "sigkill_sent")
        self.assertEqual(cancel.observe(captured, None), "cancelled")
        self.assertEqual(cancel.terminal_publications, 1)
        self.assertEqual(cancel.signals, ["SIGTERM", "SIGKILL"])
        reused = lr.Cancellation(); reused.request()
        self.assertEqual(reused.observe(captured, lr.ProcessIdentity(10, 101, 10, 10)), "cancel_failed")
        self.assertEqual(reused.terminal_publications, 1)
        race = lr.Cancellation(); race.complete(); race.request()
        self.assertEqual(race.state, "completed"); self.assertEqual(race.terminal_publications, 1)
        failed = lr.Cancellation(); failed.request()
        self.assertEqual(failed.observe(captured, captured, grace_expired=True, kill_succeeded=False), "cancel_failed")

    def test_10_fenced_stable_lock_old_inode_and_death_before_release(self) -> None:
        process = lr.ProcessIdentity(20, 200, 20, 20)
        authority = lr.LeaseAuthority()
        lease = authority.acquire("dispatcher", "run-1", 1, str(REPO), ["src"], process)
        stable_inode = authority.stable_lock_inode
        old_record_inode = authority.record_inode
        authority.cas_update(lease.generation, opened_record_inode=old_record_inode)
        self.assertEqual(authority.stable_lock_inode, stable_inode)
        self.assertContractError("old_record_inode_rejected", authority.cas_update, lease.generation, opened_record_inode=old_record_inode)
        self.assertContractError("writer_lease_conflict", authority.acquire, "other", "run-2", 1, str(REPO), ["src/nested"], process)
        self.assertContractError("lease_path_traversal", lr.canonical_paths, str(REPO), ["../escape"])
        self.assertContractError("lease_symlink_traversal", lr.canonical_paths, str(REPO), ["link"], symlink_paths=[str(REPO / "link")])
        self.assertContractError("process_still_alive", authority.release, lease.generation, process)
        authority.release(lease.generation, None)
        self.assertIsNone(authority.active)
        # Replacement ordering is explicit: stable descriptor remains while record inode advances.
        self.assertGreater(authority.record_inode, old_record_inode)
        self.assertEqual(lr.validate_lease_commit_steps(["stable_lock", "generation_cas", "write_new", "file_fsync", "atomic_replace", "directory_fsync"]), "durable_fenced_commit")
        self.assertContractError("lease_commit_order_invalid", lr.validate_lease_commit_steps, ["stable_lock", "atomic_replace"])
        crashed = lr.LeaseAuthority(); crashed.acquire("dispatcher", "run-crash", 1, str(REPO), ["tmp"], process)
        self.assertContractError("descriptor_release_without_death", crashed.descriptor_owner_crash, False)
        self.assertEqual(crashed.descriptor_owner_crash(True), "kernel_descriptor_auto_release")
        self.assertIsNone(crashed.active)
        stale = lr.LeaseAuthority(); stale_lease = stale.acquire("dispatcher", "run-stale", 1, str(REPO), ["stale"], process)
        self.assertContractError("stale_recovery_live_owner", stale.recover_stale, stale_lease.generation, process)
        self.assertGreater(stale.recover_stale(stale_lease.generation, None), stale_lease.generation)

    def test_11_registry_cas_lost_update_and_stale_generation(self) -> None:
        registry = lr.Registry()
        stale_generation, _ = registry.snapshot()
        with ThreadPoolExecutor(max_workers=24) as pool:
            generations = list(pool.map(lambda i: registry.mutate_retry(f"task-{i}", "running"), range(1000)))
        self.assertEqual(len(registry.records), 1000)
        self.assertEqual(len(set(generations)), 1000)
        self.assertContractError("registry_generation_stale", registry.cas, stale_generation, {"lost": "update"})

    def test_12_context_compaction_oom_and_authority_cleanup(self) -> None:
        context = self.policy["context"]
        self.assertEqual(lr.context_admit(1000, context["reserved_output_tokens"], context["max_tokens"]), "admitted")
        self.assertContractError("context_overflow", lr.context_admit, context["max_tokens"], 1, context["max_tokens"])
        compacted = lr.compact_checkpoint([{"source": "a", "value": 1}, {"source": "b", "value": 2}])
        self.assertEqual(compacted["record_count"], 2)
        self.assertEqual(compacted["integrity"], lr.digest(compacted["provenance"]))
        self.assertContractError("oom_process_not_reaped", lr.oom_cleanup, True, True, False)
        cleanup = lr.oom_cleanup(True, True, True)
        self.assertFalse(cleanup["process_alive"]); self.assertFalse(cleanup["lease_held"])

    def test_13_switchboard_only_admission_no_slots_or_direct_bypass(self) -> None:
        self.assertEqual(lr.admission_route("switchboard", True, "switchboard"), "switchboard_admitted")
        self.assertEqual(lr.writer_admission_sequence(True), "switchboard_admitted")
        self.assertContractError("writer_lease_required_before_inference", lr.writer_admission_sequence, False)
        self.assertEqual(lr.admission_route("llama_health", False, "observer"), "observation_only")
        self.assertContractError("slots_poll_not_authority", lr.admission_route, "slots_poll", True, "switchboard")
        self.assertContractError("inference_admission_bypass", lr.admission_route, "llama_direct", True, "switchboard")
        self.assertContractError("inference_admission_bypass", lr.admission_route, "other", True, "worker")
        self.assertContractError("undeclared_environment_alias", lr.resolve_environment_override, self.fixture["environment"]["undeclared_alias"], [])
        self.assertEqual(lr.resolve_environment_override("DECLARED", ["DECLARED"]), "declared_override")

    def test_14_bidirectional_adoption_guard(self) -> None:
        live = [entry["path"] for entry in self.fixture["live_sources"]]
        result = lr.adoption_guard(REPO, "scripts/ai/lib/local_delegation_reliability.py", "config/local-delegation-runtime-policy.json", live)
        self.assertTrue(result["pure_module"]); self.assertEqual(result["live_consumers"], [])
        self.assertFalse(result["direct_inference_compliant"])

    def test_15_bounded_isolated_subprocess_characterization(self) -> None:
        code = (
            "import importlib.util,json,sys;"
            f"s=importlib.util.spec_from_file_location('r0',{str(MODULE_PATH)!r});"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
            f"e=m.execute_golden(m.Path({str(REPO)!r}),m.Path({str(FIXTURE_PATH)!r}),m.Path({str(POLICY_PATH)!r}),m.Path({str(SCHEMA_PATH)!r}));"
            "print(json.dumps({'current':all(e['current_characterized'].values()),'fixed':all(e['fixed_contract'].values()),'digest':e['fixed_contract_digest']}))"
        )
        def limits() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024, 64 * 1024))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        with tempfile.TemporaryDirectory() as temp:
            completed = subprocess.run(
                [sys.executable, "-I", "-c", code], cwd=temp,
                env={"HOME": temp, "PATH": os.environ.get("PATH", "")},
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=5, check=True, preexec_fn=limits,
            )
        self.assertLess(len(completed.stdout), 1024)
        subprocess_result = json.loads(completed.stdout)
        self.assertTrue(subprocess_result["current"]); self.assertTrue(subprocess_result["fixed"])
        self.assertEqual(subprocess_result["digest"], self.fixture["stable_digests"]["fixed_contract"])

    def test_16_contract_health_and_sanitized_reasons(self) -> None:
        evidence = lr.execute_golden(REPO, FIXTURE_PATH, POLICY_PATH, SCHEMA_PATH)
        self.assertTrue(all(evidence["current_characterized"].values()), evidence)
        self.assertTrue(all(evidence["fixed_contract"].values()), evidence)
        self.assertEqual(evidence["vector_digest"], self.fixture["stable_digests"]["vectors"])
        self.assertEqual(evidence["source_manifest_digest"], self.fixture["stable_digests"]["source_manifest"])
        self.assertEqual(evidence["fixed_contract_digest"], self.fixture["stable_digests"]["fixed_contract"])
        health = lr.contract_health(REPO, FIXTURE_PATH, POLICY_PATH, SCHEMA_PATH)
        self.assertTrue(health["healthy"]); self.assertEqual(health["failed_checks"], [])
        self.assertTrue(set(self.fixture["sanitized_terminal_reasons"]).issubset(lr.TERMINALS))
        self.assertEqual(self.fixture["environment"]["declared_overrides"], [])
        self.assertEqual(tuple(self.fixture["metrics"]), lr.LOW_CARDINALITY_METRICS)
        self.assertFalse(any("run_id" in metric or "prompt" in metric for metric in lr.LOW_CARDINALITY_METRICS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
