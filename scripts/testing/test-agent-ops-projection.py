#!/usr/bin/env python3
"""Executable M0 contract tests for the read-only Agent Ops projector."""
from __future__ import annotations

import ast
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "scripts/ai/lib/agent_ops_projection.py"
SCHEMA = REPO / "config/schemas/agent-ops-projection.schema.json"
FIXTURE = REPO / "scripts/testing/fixtures/agent-ops-projection-golden.json"
spec = importlib.util.spec_from_file_location("agent_ops_projection_m0", MODULE)
assert spec and spec.loader
ops = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ops
spec.loader.exec_module(ops)

tui_loader = SourceFileLoader("agent_ops_tui_m1", str(REPO / "scripts/ai/aq-tui-dashboard"))
tui_spec = importlib.util.spec_from_loader(tui_loader.name, tui_loader)
assert tui_spec and tui_spec.loader
tui = importlib.util.module_from_spec(tui_spec)
sys.modules[tui_spec.name] = tui
tui_spec.loader.exec_module(tui)


def _healthy_review_facts() -> dict:
    return {
        "contract_version": "aq.review-feedback-facts.v1",
        "receipt_schema_version": "aq.review-round-receipt.v1",
        "candidate_schema_version": "aq.learning-candidate.v1",
        "subject_hash": "a" * 64,
        "pass_id": "pass-1",
        "baseline_hash": "b" * 64,
        "baseline_state": "aligned",
        "terminal_decision": "accepted",
        "revision": 1,
        "superseded": False,
        "binding_required": 2,
        "binding_received": 2,
        "roster_complete": True,
        "required_lanes": 2,
        "received_lanes": 2,
        "parked_lanes": 0,
        "unavailable_lanes": 0,
        "abstained_lanes": 0,
        "oldest_wait_s": 0,
        "open_findings": 0,
        "critical_undisposed": 0,
        "disposed_findings": 0,
        "promotion_state": "not_assessed",
        "promotion_pending": 0,
        "feedback_freshness": "fresh",
        "feedback_freshness_age_s": 0,
        "lanes": [
            {"lane": "claude", "role": "reviewer", "model_tier": "flagship",
             "eligibility": "binding_flagship", "state": "submitted", "verdict": "pass"},
            {"lane": "codex", "role": "reviewer", "model_tier": "flagship",
             "eligibility": "binding_flagship", "state": "submitted", "verdict": "pass"},
        ],
        "reason_codes": [],
    }


class AgentOpsProjectionM0(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.projection = ops.project_agent_ops(
            now=cls.fixture["now"], registry=cls.fixture["registry"],
            processes=cls.fixture["processes"], inbox=cls.fixture["inbox"],
        )

    def test_01_closed_schema_and_projection(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema).validate(self.projection)
        bad = json.loads(json.dumps(self.projection)); bad["unknown"] = True
        self.assertTrue(list(Draft202012Validator(self.schema).iter_errors(bad)))

    def test_02_golden_counts_metrics_and_health(self) -> None:
        expected = self.fixture["expected"]
        self.assertEqual(self.projection["health"]["verdict"], expected["health"])
        self.assertEqual(len(self.projection["work"]), expected["work_count"])
        for metric in ops.LEGACY_METRICS:
            self.assertEqual(self.projection["metrics"][metric], expected[metric])
        self.assertTrue(all(self.projection["metrics"][metric] is None for metric in ops.REVIEW_METRICS))
        self.assertTrue(set(expected["required_reasons"]).issubset(self.projection["health"]["reason_codes"]))

    def test_03_registry_pid_start_time_and_phase_correlation(self) -> None:
        item = next(v for v in self.projection["work"] if v["work_id"] == "local-task-1")
        self.assertEqual((item["visibility"], item["phase"], item["progress_age_s"]), ("tracked", "prefill", 10))
        stale = next(v for v in self.projection["work"] if v["work_id"] == "claude-stale")
        self.assertEqual((stale["state"], stale["visibility"]), ("stale", "blocked"))

    def test_04_terminal_live_conflict_fails_closed(self) -> None:
        item = next(v for v in self.projection["work"] if v["work_id"] == "codex-terminal-live")
        self.assertEqual((item["state"], item["visibility"], item["reason_code"]),
                         ("conflict", "blocked", "terminal_process_alive"))

    def test_05_wrapper_child_and_pgid_escape_deduplicate_by_cgroup(self) -> None:
        groups, _ = ops.collapse_processes(self.fixture["processes"])
        task = next(v for v in groups if v["dedup_group"].startswith("cgroup:") and 101 in v["members"])
        escaped = next(v for v in groups if 702 in v["members"])
        self.assertEqual(len(task["members"]), self.fixture["expected"]["dedup_group_member_count"])
        self.assertEqual(set(escaped["members"]), {701, 702})

    def test_06_argv_boundaries_ignore_incidental_exec_text(self) -> None:
        proc = ops.ProcessFact.from_mapping(next(v for v in self.fixture["processes"] if v["pid"] == 501))
        self.assertEqual(ops.executable_kind(proc), ("unknown", "unknown"))
        card = next(v for v in self.projection["work"] if (v.get("pid_identity") or {}).get("pid") == 501)
        self.assertEqual((card["state"], card["visibility"]), ("untracked", "blocked"))

    def test_07_proc_permission_denial_is_blocked_not_exception(self) -> None:
        card = next(v for v in self.projection["work"] if v["reason_code"] == "proc_permission_denied")
        self.assertEqual((card["state"], card["visibility"], card["freshness"]),
                         ("untracked", "blocked", "unavailable"))

    def test_08_missing_cgroup_is_measured_and_blocked(self) -> None:
        self.assertEqual(self.projection["metrics"]["cgroup_correlation_failures_total"], 1)
        cards = [v for v in self.projection["work"] if (v["dedup_group"] or "").startswith("ancestry:")]
        self.assertTrue(any(v["visibility"] == "blocked" for v in cards))

    def test_09_untrusted_progress_never_renews_phase(self) -> None:
        item = next(v for v in self.projection["work"] if v["work_id"] == "local-forged-progress")
        self.assertEqual((item["visibility"], item["reason_code"], item["phase"]),
                         ("degraded", "progress_untrusted", None))

    def test_10_inbox_lifecycle_states_and_latency(self) -> None:
        pending = next(v for v in self.projection["work"] if v["work_id"].endswith("pending-review.md"))
        limbo = next(v for v in self.projection["work"] if v["work_id"].endswith("output-not-archived.md"))
        missing = next(v for v in self.projection["work"] if v["work_id"].endswith("missing-output.md"))
        self.assertEqual((pending["state"], pending["visibility"]), ("queued", "tracked"))
        self.assertEqual(limbo["visibility"], "degraded")
        self.assertEqual((missing["state"], missing["artifact"], missing["terminal_reason"]),
                         ("terminal", "missing", "missing_output"))

    def test_11_daemon_is_idle_not_active_work(self) -> None:
        daemon = next(v for v in self.projection["work"] if v["reason_code"] == "idle_daemon")
        self.assertEqual((daemon["state"], daemon["visibility"]), ("idle", "tracked"))

    def test_12_sensitive_fields_and_metric_cardinality(self) -> None:
        ops.assert_redacted(self.projection)
        self.assertFalse(any(name in {"run_id", "pid", "prompt", "raw_command"} for name in self.projection["metrics"]))
        bad = json.loads(json.dumps(self.projection)); bad["work"][0]["prompt"] = "secret"
        with self.assertRaisesRegex(ops.ProjectionError, "sensitive_field_exposed"):
            ops.assert_redacted(bad)

    def test_13_contract_health_is_stable(self) -> None:
        first = ops.contract_health(self.projection)
        second = ops.contract_health(json.loads(json.dumps(self.projection)))
        self.assertEqual(first, second)
        self.assertEqual(first["work_count"], self.fixture["expected"]["work_count"])
        self.assertFalse(first["healthy"])
        self.assertEqual(first["dispatch_health"], "unavailable")

    def test_13b_dispatch_contract_is_unavailable_until_injected(self) -> None:
        dispatch = self.projection["dispatch_contract"]
        self.assertEqual((dispatch["health"], dispatch["broker_state"]), ("unavailable", "not_assessed"))
        self.assertTrue(all(value is None for value in dispatch["counts"].values()))
        injected = json.loads(json.dumps(dispatch))
        injected.update(health="healthy", broker_state="healthy", reason_codes=[])
        injected["adapter_health"] = {lane: "healthy" for lane in injected["adapter_health"]}
        injected["coverage_health"] = {gate: "healthy" for gate in injected["coverage_health"]}
        injected["counts"] = {"queued": 1, "running": 2, "parked": 3, "terminal": 4}
        projection = ops.project_agent_ops(
            now=self.fixture["now"], registry=self.fixture["registry"],
            processes=self.fixture["processes"], inbox=self.fixture["inbox"],
            dispatch_contract=injected, review_feedback_facts=_healthy_review_facts(),
        )
        Draft202012Validator(self.schema).validate(projection)
        self.assertTrue(ops.contract_health(projection)["healthy"])

    def test_13c_cgroup_and_sensitive_dispatch_values_are_redacted(self) -> None:
        rendered = json.dumps(self.projection)
        self.assertNotIn("/agent/", rendered)
        bad = json.loads(json.dumps(self.projection)); bad["dispatch_contract"]["prompt_digest"] = "canary"
        with self.assertRaisesRegex(ops.ProjectionError, "sensitive_field_exposed"):
            ops.assert_redacted(bad)

    def test_14_snapshot_and_argv_bounds_fail_closed(self) -> None:
        with self.assertRaisesRegex(ops.ProjectionError, "process_snapshot_too_large"):
            ops.collapse_processes([{"pid": i, "error": "permission_denied"} for i in range(1, ops.MAX_PROCESSES + 2)])
        bad = dict(next(v for v in self.fixture["processes"] if v["pid"] == 501))
        bad["argv"] = ["x"] * (ops.MAX_ARGV + 1)
        with self.assertRaisesRegex(ops.ProjectionError, "process_argv_invalid"):
            ops.ProcessFact.from_mapping(bad)

    def _m1_sources(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        proc = root / "proc"; registry = root / "registry.jsonl"
        outputs = root / "outputs"; inbox = root / "inbox"; archive = root / "archive"
        for directory in (proc, outputs, inbox, archive):
            directory.mkdir(parents=True, exist_ok=True)
        process = proc / "10"; process.mkdir()
        fields = ["S", "1", "10", "10"] + ["0"] * 15 + ["1234"]
        (process / "stat").write_text("10 (claude worker) " + " ".join(fields), encoding="utf-8")
        (process / "cmdline").write_bytes(b"/repo/delegate-to-claude\0--wait\0")
        (process / "cgroup").write_text("0::/agent/m1.scope\n", encoding="utf-8")
        os.symlink("/repo/delegate-to-claude", process / "exe")
        registry.write_text(json.dumps({
            "id": "claude-m1", "agent": "claude", "role": "implementer",
            "status": "running", "pid": 10, "pid_start_time": 1234,
            "description": "PROMPT_CANARY secret-token",
        }) + "\n", encoding="utf-8")
        (outputs / "claude-m1.log.progress.json").write_text(json.dumps({
            "trusted": True, "producer": "dispatcher", "phase": "generation",
            "observed_at": self.fixture["now"] - 2,
        }), encoding="utf-8")
        (inbox / "review.md").write_text(
            "Write `.agents/plans/example/antigravity.md` after review.", encoding="utf-8"
        )
        return proc, registry, outputs, inbox, archive

    def test_15_m1_bounded_readers_feed_pure_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roots = self._m1_sources(Path(tmp))
            projection = tui.read_agent_ops_projection(
                proc_root=roots[0], registry_path=roots[1], outputs_dir=roots[2],
                inbox_dir=roots[3], archive_root=roots[4], use_cache=False,
            )
            item = next(v for v in projection["work"] if v["work_id"] == "claude-m1")
            self.assertEqual((item["state"], item["visibility"], item["phase"]),
                             ("running", "tracked", "generation"))
            rendered = json.dumps(projection)
            self.assertNotIn("PROMPT_CANARY", rendered)
            self.assertNotIn("secret-token", rendered)
            Draft202012Validator(self.schema).validate(projection)

    def test_16_m1_symlink_and_malformed_sources_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); proc, registry, outputs, inbox, archive = self._m1_sources(root)
            real = root / "real-registry"; real.write_bytes(registry.read_bytes())
            registry.unlink(); registry.symlink_to(real)
            projection = tui.read_agent_ops_projection(
                proc_root=proc, registry_path=registry, outputs_dir=outputs,
                inbox_dir=inbox, archive_root=archive, use_cache=False,
            )
            self.assertEqual(projection["health"]["verdict"], "blocked")
            self.assertIn("registry_source_not_regular", projection["health"]["reason_codes"])

            registry.unlink(); registry.write_text("{not-json}\n", encoding="utf-8")
            projection = tui.read_agent_ops_projection(
                proc_root=proc, registry_path=registry, outputs_dir=outputs,
                inbox_dir=inbox, archive_root=archive, use_cache=False,
            )
            self.assertIn("registry_record_malformed", projection["health"]["reason_codes"])

            registry.write_text(json.dumps({
                "id": "../../escape", "agent": "claude", "status": "running",
            }) + "\n", encoding="utf-8")
            (inbox / "linked.md").symlink_to(inbox / "review.md")
            projection = tui.read_agent_ops_projection(
                proc_root=proc, registry_path=registry, outputs_dir=outputs,
                inbox_dir=inbox, archive_root=archive, use_cache=False,
            )
            self.assertIn("registry_task_id_invalid", projection["health"]["reason_codes"])
            self.assertIn("inbox_source_not_regular", projection["health"]["reason_codes"])
            self.assertEqual(tui.tail_output("../../escape"), [])
            self.assertEqual(tui._read_progress("../../escape"), {})

    def test_17_m1_source_byte_and_count_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "oversized"
            path.write_bytes(b"x" * 9)
            with self.assertRaisesRegex(tui.SourceReadError, "source_too_large"):
                tui._bounded_regular_bytes(path, 8)
            proc = Path(tmp) / "proc"; proc.mkdir()
            for pid in range(1, ops.MAX_PROCESSES + 2):
                (proc / str(pid)).mkdir()
            facts, errors = tui.read_proc_facts(proc)
            self.assertEqual(facts, [])
            self.assertEqual(errors, ["process_snapshot_too_large"])

    def test_18_m1_pid_reuse_and_untrusted_progress_stay_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roots = self._m1_sources(Path(tmp))
            row = json.loads(roots[1].read_text(encoding="utf-8"))
            row["pid_start_time"] = 9999
            roots[1].write_text(json.dumps(row) + "\n", encoding="utf-8")
            progress_path = roots[2] / "claude-m1.log.progress.json"
            progress_path.write_text(json.dumps({
                "trusted": True, "producer": "model", "phase": "generation",
                "observed_at": self.fixture["now"],
            }), encoding="utf-8")
            projection = tui.read_agent_ops_projection(
                proc_root=roots[0], registry_path=roots[1], outputs_dir=roots[2],
                inbox_dir=roots[3], archive_root=roots[4], use_cache=False,
            )
            item = next(v for v in projection["work"] if v["work_id"] == "claude-m1")
            self.assertEqual((item["state"], item["visibility"], item["phase"]),
                             ("stale", "blocked", None))

    def test_19_m1_cache_expires_and_converges_after_process_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roots = self._m1_sources(Path(tmp))
            tui._cache["projection"] = (0.0, {})
            first = tui.read_agent_ops_projection(
                proc_root=roots[0], registry_path=roots[1], outputs_dir=roots[2],
                inbox_dir=roots[3], archive_root=roots[4], use_cache=True,
            )
            self.assertEqual(next(v for v in first["work"] if v["work_id"] == "claude-m1")["state"],
                             "running")
            for child in (roots[0] / "10").iterdir():
                child.unlink()
            (roots[0] / "10").rmdir()
            tui._cache["projection"] = (tui._now() - 3, first)
            second = tui.read_agent_ops_projection(
                proc_root=roots[0], registry_path=roots[1], outputs_dir=roots[2],
                inbox_dir=roots[3], archive_root=roots[4], use_cache=True,
            )
            item = next(v for v in second["work"] if v["work_id"] == "claude-m1")
            self.assertEqual((item["state"], item["reason_code"]),
                             ("stale", "registry_process_missing"))


class AgentOpsProjectionC05B(unittest.TestCase):
    """C0.5B pure injected review/feedback health contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def projection(self, facts: dict | None = None, dispatch: dict | None = None) -> dict:
        return ops.project_agent_ops(
            now=1784127600, registry=[], processes=[], inbox=[],
            dispatch_contract=dispatch, review_feedback_facts=facts,
        )

    def assertProjectionError(self, reason: str, facts: dict) -> None:
        with self.assertRaisesRegex(ops.ProjectionError, f"^{reason}$"):
            ops.project_review_feedback(facts)

    def test_c05b_01_absent_is_unavailable_not_assessed_and_null(self) -> None:
        projection = self.projection()
        review = projection["review_feedback"]
        self.assertEqual((review["health"], review["assessment"]), ("unavailable", "not_assessed"))
        self.assertEqual((review["baseline_state"], review["terminal_decision"]),
                         ("not_assessed", "not_assessed"))
        nullable = {key for key, value in review.items() if value is None}
        self.assertEqual(nullable, {
            "subject_hash", "pass_id", "revision", "superseded", "binding_required",
            "binding_received", "roster_complete", "required_lanes", "received_lanes",
            "parked_lanes", "unavailable_lanes", "abstained_lanes", "oldest_wait_s",
            "open_findings", "critical_undisposed", "disposed_findings", "promotion_pending",
            "freshness_age_s",
        })
        self.assertTrue(all(projection["metrics"][name] is None for name in ops.REVIEW_METRICS))
        self.assertEqual(review["reason_codes"], ["review_feedback_not_assessed"])

    def test_c05b_02_complete_aligned_binding_acceptance_is_healthy(self) -> None:
        review = ops.project_review_feedback(_healthy_review_facts())
        self.assertEqual((review["health"], review["assessment"], review["finding_state"]),
                         ("healthy", "assessed", "clear"))

    def test_c05b_03_missing_required_lane_is_incomplete_degraded(self) -> None:
        facts = _healthy_review_facts()
        facts.update(terminal_decision="incomplete", roster_complete=False,
                     received_lanes=1, binding_received=1, oldest_wait_s=30)
        facts["lanes"][1].update(state="nonterminal", verdict=None)
        review = ops.project_review_feedback(facts)
        self.assertEqual(review["health"], "degraded")
        self.assertIn("review_roster_incomplete", review["reason_codes"])

    def test_c05b_04_parked_lane_accounts_but_never_satisfies_quorum(self) -> None:
        facts = _healthy_review_facts()
        facts.update(terminal_decision="incomplete", roster_complete=True, received_lanes=1,
                     binding_received=1, parked_lanes=1, oldest_wait_s=120)
        facts["lanes"][1].update(state="parked", verdict=None)
        review = ops.project_review_feedback(facts)
        self.assertEqual((review["health"], review["parked_lanes"], review["binding_received"]),
                         ("degraded", 1, 1))

    def test_c05b_05_unavailable_is_distinct_from_explicit_abstention(self) -> None:
        unavailable = _healthy_review_facts()
        unavailable.update(terminal_decision="incomplete", roster_complete=True, received_lanes=1,
                           binding_received=1, unavailable_lanes=1)
        unavailable["lanes"][1].update(state="unavailable", verdict=None)
        abstain = _healthy_review_facts()
        abstain.update(terminal_decision="incomplete", binding_received=1, abstained_lanes=1)
        abstain["lanes"][1]["verdict"] = "abstain"
        left = ops.project_review_feedback(unavailable)
        right = ops.project_review_feedback(abstain)
        self.assertEqual((left["unavailable_lanes"], left["abstained_lanes"]), (1, 0))
        self.assertEqual((right["unavailable_lanes"], right["abstained_lanes"]), (0, 1))

    def test_c05b_06_baseline_mismatch_blocks(self) -> None:
        facts = _healthy_review_facts(); facts["baseline_state"] = "mismatched"
        review = ops.project_review_feedback(facts)
        self.assertEqual(review["health"], "blocked")
        self.assertIn("review_baseline_mismatch", review["reason_codes"])

    def test_c05b_07_subject_policy_roster_and_criteria_drift_block(self) -> None:
        for reason in ("review_subject_drift", "review_policy_drift", "review_roster_drift", "review_criteria_drift"):
            facts = _healthy_review_facts(); facts["reason_codes"] = [reason]
            self.assertEqual(ops.project_review_feedback(facts)["health"], "blocked", reason)

    def test_c05b_08_self_review_and_material_rewriter_cannot_bind(self) -> None:
        for reason in ("review_self_review", "review_material_rewriter"):
            facts = _healthy_review_facts(); facts["reason_codes"] = [reason]
            self.assertEqual(ops.project_review_feedback(facts)["health"], "blocked", reason)

    def test_c05b_09_insufficient_binding_quorum_fails_closed(self) -> None:
        facts = _healthy_review_facts(); facts.update(binding_received=1, terminal_decision="incomplete")
        facts["lanes"][1]["verdict"] = "fail"
        review = ops.project_review_feedback(facts)
        self.assertEqual(review["health"], "degraded")
        self.assertIn("review_quorum_incomplete", review["reason_codes"])

    def test_c05b_10_revision_required_exposes_revision(self) -> None:
        facts = _healthy_review_facts(); facts.update(terminal_decision="revision_required", revision=2)
        review = ops.project_review_feedback(facts)
        self.assertEqual((review["health"], review["terminal_decision"], review["revision"]),
                         ("degraded", "revision_required", 2))

    def test_c05b_11_superseded_receipt_is_blocked(self) -> None:
        facts = _healthy_review_facts(); facts["superseded"] = True
        review = ops.project_review_feedback(facts)
        self.assertEqual(review["health"], "blocked")
        self.assertIn("review_subject_superseded", review["reason_codes"])

    def test_c05b_12_critical_undisposed_advisory_finding_blocks(self) -> None:
        facts = _healthy_review_facts(); facts.update(open_findings=1, critical_undisposed=1)
        review = ops.project_review_feedback(facts)
        self.assertEqual((review["health"], review["finding_state"]), ("blocked", "blocked"))

    def test_c05b_13_disposition_preserves_history_without_blocking(self) -> None:
        facts = _healthy_review_facts(); facts.update(open_findings=0, critical_undisposed=0, disposed_findings=1)
        review = ops.project_review_feedback(facts)
        self.assertEqual((review["health"], review["finding_state"], review["disposed_findings"]),
                         ("healthy", "clear", 1))

    def test_c05b_14_promotion_and_freshness_project_deterministically(self) -> None:
        facts = _healthy_review_facts()
        facts.update(promotion_state="canary", promotion_pending=1,
                     feedback_freshness="stale", feedback_freshness_age_s=90)
        review = ops.project_review_feedback(facts)
        self.assertEqual((review["health"], review["promotion_state"], review["freshness"]),
                         ("degraded", "canary", "stale"))

    def test_c05b_15_missing_promotion_facts_are_not_assessed(self) -> None:
        review = self.projection()["review_feedback"]
        self.assertEqual((review["promotion_state"], review["promotion_pending"]), ("not_assessed", None))

    def test_c05b_16_malformed_unknown_enum_hash_bounds_fail_closed(self) -> None:
        cases = []
        unknown = _healthy_review_facts(); unknown["unknown"] = True
        cases.append(("review_facts_shape_invalid", unknown))
        enum = _healthy_review_facts(); enum["baseline_state"] = "maybe"
        cases.append(("review_baseline_state_invalid", enum))
        bad_hash = _healthy_review_facts(); bad_hash["subject_hash"] = "x"
        cases.append(("review_subject_hash_invalid", bad_hash))
        negative = _healthy_review_facts(); negative["revision"] = -1
        cases.append(("review_revision_invalid", negative))
        oversized = _healthy_review_facts(); oversized["lanes"] = oversized["lanes"] * 33
        cases.append(("review_lanes_invalid", oversized))
        long_id = _healthy_review_facts(); long_id["pass_id"] = "a" * 129
        cases.append(("review_pass_id_invalid", long_id))
        nested = _healthy_review_facts(); nested["lanes"][0]["unknown"] = True
        cases.append(("review_lane_shape_invalid", nested))
        for reason, facts in cases:
            self.assertProjectionError(reason, facts)

    def test_c05b_17_inconsistent_totals_fail_closed(self) -> None:
        cases = []
        binding = _healthy_review_facts(); binding["binding_received"] = 3
        cases.append(("review_binding_totals_invalid", binding))
        roster = _healthy_review_facts(); roster["received_lanes"] = 3
        cases.append(("review_roster_totals_invalid", roster))
        abstain = _healthy_review_facts(); abstain["abstained_lanes"] = 3
        cases.append(("review_abstention_totals_invalid", abstain))
        unavailable = _healthy_review_facts(); unavailable.update(parked_lanes=2, unavailable_lanes=1)
        cases.append(("review_unavailable_totals_invalid", unavailable))
        for reason, facts in cases:
            self.assertProjectionError(reason, facts)

    def test_c05b_17b_empty_missing_and_incomplete_lane_rosters_fail_closed(self) -> None:
        empty = _healthy_review_facts(); empty["lanes"] = []
        self.assertProjectionError("review_received_lanes_observation_mismatch", empty)
        missing = _healthy_review_facts(); missing.pop("lanes")
        self.assertProjectionError("review_facts_shape_invalid", missing)
        incomplete = _healthy_review_facts()
        incomplete.update(received_lanes=1, binding_received=1)
        incomplete["lanes"] = incomplete["lanes"][:1]
        self.assertProjectionError("review_complete_roster_unrepresented", incomplete)

    def test_c05b_17c_claimed_counters_must_match_lane_states(self) -> None:
        received = _healthy_review_facts(); received["received_lanes"] = 1
        parked = _healthy_review_facts()
        parked.update(received_lanes=1, binding_received=1, parked_lanes=0,
                      terminal_decision="incomplete", roster_complete=True)
        parked["lanes"][1].update(state="parked", verdict=None)
        unavailable = _healthy_review_facts()
        unavailable.update(received_lanes=1, binding_received=1, unavailable_lanes=0,
                           terminal_decision="incomplete", roster_complete=True)
        unavailable["lanes"][1].update(state="unavailable", verdict=None)
        abstained = _healthy_review_facts(); abstained["lanes"][1]["verdict"] = "abstain"
        for reason, facts in (
            ("review_received_lanes_observation_mismatch", received),
            ("review_parked_lanes_observation_mismatch", parked),
            ("review_unavailable_lanes_observation_mismatch", unavailable),
            ("review_abstained_lanes_observation_mismatch", abstained),
        ):
            self.assertProjectionError(reason, facts)

    def test_c05b_17d_recused_advisory_and_abstaining_lanes_cannot_bind(self) -> None:
        for field, value in (("eligibility", "recused"), ("eligibility", "advisory"),
                             ("verdict", "abstain")):
            facts = _healthy_review_facts(); facts["lanes"][1][field] = value
            if field == "verdict":
                facts["abstained_lanes"] = 1
            self.assertProjectionError("review_binding_received_observation_mismatch", facts)

    def test_c05b_17e_embedded_or_nonreviewer_lanes_cannot_bind(self) -> None:
        for field, value in (("model_tier", "embedded"), ("role", "implementer")):
            facts = _healthy_review_facts(); facts["lanes"][1][field] = value
            self.assertProjectionError("review_binding_received_observation_mismatch", facts)

    def test_c05b_18_lane_permutation_has_stable_output_and_digest(self) -> None:
        first = _healthy_review_facts(); second = json.loads(json.dumps(first))
        second["lanes"].reverse()
        left = ops.project_review_feedback(first); right = ops.project_review_feedback(second)
        self.assertEqual(left, right)
        self.assertEqual(ops.stable_digest(left), ops.stable_digest(right))

    def test_c05b_19_sensitive_fields_and_raw_prose_are_rejected(self) -> None:
        facts = _healthy_review_facts(); facts["prompt"] = "secret"
        self.assertProjectionError("review_facts_shape_invalid", facts)
        projection = self.projection(_healthy_review_facts())
        projection["review_feedback"]["raw_error"] = "provider prose"
        with self.assertRaisesRegex(ops.ProjectionError, "sensitive_field_exposed"):
            ops.assert_redacted(projection)

    def test_c05b_20_input_is_not_mutated(self) -> None:
        facts = _healthy_review_facts(); before = json.dumps(facts, sort_keys=True)
        ops.project_review_feedback(facts)
        self.assertEqual(json.dumps(facts, sort_keys=True), before)

    def test_c05b_21_projection_path_has_no_live_authority_or_clock(self) -> None:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
        from_imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        forbidden = {"os", "subprocess", "socket", "random", "time", "task_registry"}
        self.assertFalse(forbidden.intersection(imports | from_imports))
        with mock.patch.object(ops, "_iso", side_effect=AssertionError("clock/output path used")):
            self.assertEqual(ops.project_review_feedback(_healthy_review_facts())["health"], "healthy")

    def test_c05b_22_v2_schema_is_closed_at_all_new_boundaries(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        projection = self.projection(_healthy_review_facts())
        Draft202012Validator(self.schema).validate(projection)
        for mutate in (
            lambda value: value.update(unknown=True),
            lambda value: value["review_feedback"].update(unknown=True),
            lambda value: value["review_feedback"]["lanes"][0].update(unknown=True),
        ):
            bad = json.loads(json.dumps(projection)); mutate(bad)
            self.assertTrue(list(Draft202012Validator(self.schema).iter_errors(bad)))

    def test_c05b_23_metrics_are_fixed_numeric_or_null(self) -> None:
        projection = self.projection(_healthy_review_facts())
        self.assertEqual(set(projection["metrics"]), set(ops.METRICS))
        self.assertTrue(all(value is None or (isinstance(value, int) and not isinstance(value, bool))
                            for value in projection["metrics"].values()))
        self.assertFalse(any(name in {"subject_hash", "pass_id", "lane", "prompt", "path"}
                             for name in projection["metrics"]))

    def test_c05b_24_legacy_projection_contract_remains_present(self) -> None:
        projection = self.projection()
        self.assertEqual(set(ops.LEGACY_METRICS), {
            "inbox_pending_count", "inbox_processing_duration_seconds",
            "cgroup_correlation_failures_total",
        })
        self.assertIn("dispatch_contract", projection)
        self.assertIn("work", projection)

    def test_c05b_25_m2a_read_only_show_tests_are_frozen_and_not_imported(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        for number in range(33, 42):
            self.assertIn(f"def test_m2a_{number}_", source)
        module_source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("show_m2a", module_source)
        self.assertNotRegex(module_source, r"(?:import|from)\s+[^\n]*task_registry")

    def test_c05b_26_contract_health_requires_dispatch_and_review_health(self) -> None:
        projection = self.projection()
        health = ops.contract_health(projection)
        self.assertFalse(health["healthy"])
        self.assertEqual((health["review_feedback_health"], health["review_terminal_decision"],
                          health["feedback_promotion_state"]),
                         ("unavailable", "not_assessed", "not_assessed"))
        dispatch = json.loads(json.dumps(projection["dispatch_contract"]))
        dispatch.update(health="healthy", broker_state="healthy", reason_codes=[])
        dispatch["adapter_health"] = {lane: "healthy" for lane in dispatch["adapter_health"]}
        dispatch["coverage_health"] = {gate: "healthy" for gate in dispatch["coverage_health"]}
        dispatch["counts"] = {"queued": 0, "running": 0, "parked": 0, "terminal": 0}
        self.assertTrue(ops.contract_health(self.projection(_healthy_review_facts(), dispatch))["healthy"])

    def test_c05b_27_repeated_projection_has_stable_canonical_digest(self) -> None:
        facts = _healthy_review_facts()
        first = self.projection(facts); second = self.projection(json.loads(json.dumps(facts)))
        self.assertEqual(first, second)
        self.assertEqual(ops.contract_health(first)["digest"], ops.contract_health(second)["digest"])


class AgentOpsProjectionM2A(unittest.TestCase):
    """M2A adversarial tests: transactional writer, queued grace, barrier, and privacy."""

    @classmethod
    def setUpClass(cls) -> None:
        # Load task_registry module
        import importlib.util
        lib = REPO / "scripts/ai/lib/task_registry.py"
        spec = importlib.util.spec_from_file_location("task_registry_m2a", lib)
        assert spec and spec.loader
        cls.tr_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tr_mod)  # type: ignore[union-attr]

    def _make_registry(self, tmp: Path) -> "object":
        reg_dir = tmp / "delegation"
        reg_dir.mkdir(parents=True, exist_ok=True)
        return self.tr_mod.TaskRegistry(reg_dir, repo_root=tmp)

    # ── begin / concurrency / no lost rows ────────────────────────────────────

    def test_m2a_01_begin_creates_queued_record(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            rec = r.begin("m2a-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            self.assertEqual(rec["status"], "queued")
            self.assertEqual(rec["record_version"], 1)
            self.assertEqual(rec["record_revision"], 1)
            self.assertEqual(rec["admission_producer"], "dispatcher")
            self.assertNotIn("pid", rec)
            self.assertNotIn("pid_start_time", rec)

    def test_m2a_02_begin_rejects_duplicate_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("dup-id", "local", "implementer", "writer", "research", "none")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "duplicate_task_id"):
                r.begin("dup-id", "claude", "reviewer", "read_only", "code_review", "none")

    def test_m2a_03_concurrent_begins_no_lost_rows(self) -> None:
        import threading
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            errors: list[Exception] = []

            def _worker(idx: int) -> None:
                try:
                    r.begin(f"concurrent-{idx}", "codex", "implementer", "writer",
                            "code_generation", "file_output")
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            records = r._m2a_read_records()
            ids = {rec.get("task_id") for rec in records}
            self.assertEqual(ids, {f"concurrent-{i}" for i in range(10)})

    def test_m2a_04_stable_lock_inode_survives_multiple_ops(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("lock-t1", "claude", "implementer", "writer", "testing", "file_output")
            lock_path = r._m2a_lock_path()
            self.assertTrue(lock_path.exists())
            inode_before = lock_path.stat().st_ino
            r.begin("lock-t2", "local", "researcher", "read_only", "research", "none")
            self.assertEqual(lock_path.stat().st_ino, inode_before)

    # ── symlink / non-regular file rejection ──────────────────────────────────

    def test_m2a_05_symlink_registry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("sym-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            reg = r.registry_file
            real = reg.parent / "real.jsonl"
            reg.rename(real)
            reg.symlink_to(real)
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "symlink"):
                r.begin("sym-t2", "local", "reviewer", "read_only", "code_review", "none")

    def test_m2a_06_symlink_lock_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            lock_path = r._m2a_lock_path()
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            real = lock_path.parent / "real.lock"
            real.write_bytes(b"")
            lock_path.symlink_to(real)
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "symlink"):
                r.begin("sym-t3", "local", "implementer", "writer", "testing", "none")

    # ── malformed / oversized / unknown field rejection ───────────────────────

    def test_m2a_07_malformed_registry_line_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.registry_file.parent.mkdir(parents=True, exist_ok=True)
            r.registry_file.write_text("{not valid json}\n", encoding="utf-8")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "malformed"):
                r.begin("bad-t1", "local", "implementer", "writer", "research", "none")

    def test_m2a_08_oversized_record_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.registry_file.parent.mkdir(parents=True, exist_ok=True)
            big_line = json.dumps({"id": "x", "data": "A" * 5000})
            r.registry_file.write_text(big_line + "\n", encoding="utf-8")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "too_large"):
                r.begin("big-t1", "local", "implementer", "writer", "research", "none")

    def test_m2a_09_invalid_lane_role_class_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "lane_invalid"):
                r.begin("inv-t1", "gemini", "implementer", "writer", "code_generation", "file_output")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "role_invalid"):
                r.begin("inv-t2", "claude", "unknown_role", "writer", "code_generation", "file_output")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "task_class_invalid"):
                r.begin("inv-t3", "claude", "implementer", "writer", "raw_prompt", "file_output")

    def test_m2a_10_task_id_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "task_id_invalid"):
                r.begin("../../escape", "local", "implementer", "writer", "research", "none")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "task_id_invalid"):
                r.begin("", "local", "implementer", "writer", "research", "none")

    # ── stale revisions ───────────────────────────────────────────────────────

    def test_m2a_11_stale_revision_attach_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("stale-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "stale_revision"):
                r.attach_process("stale-t1", 1234, 56789, expected_revision=99)

    def test_m2a_12_stale_revision_transition_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("stale-t2", "codex", "implementer", "writer", "code_generation", "file_output")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "stale_revision"):
                r.transition_m2a("stale-t2", "cancelled", expected_revision=42)

    # ── illegal transitions ───────────────────────────────────────────────────

    def test_m2a_13_illegal_transitions_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("ill-t1", "local", "implementer", "writer", "code_generation", "file_output")
            # queued → done is not a legal direct transition
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "illegal_transition"):
                r.transition_m2a("ill-t1", "done")
            # queued → waiting is not legal
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "illegal_transition"):
                r.transition_m2a("ill-t1", "waiting")

    def test_m2a_14_terminal_state_idempotent_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("term-t1", "claude", "implementer", "writer", "testing", "file_output")
            r.transition_m2a("term-t1", "cancelled")
            # cancelled → cancelled is idempotent (legal)
            rec = r.transition_m2a("term-t1", "cancelled")
            self.assertEqual(rec["status"], "cancelled")
            # cancelled → running is illegal
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "illegal_transition"):
                r.transition_m2a("term-t1", "running")

    def test_m2a_15_legacy_record_cannot_attach_or_transition(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.registry_file.parent.mkdir(parents=True, exist_ok=True)
            legacy = json.dumps({"id": "legacy-1", "status": "running", "pid": 999})
            r.registry_file.write_text(legacy + "\n", encoding="utf-8")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "legacy_record_cannot"):
                r.attach_process("legacy-1", 1234, 5678)
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "legacy_record_cannot"):
                r.transition_m2a("legacy-1", "done")

    # ── queued grace / future-skew bounds ─────────────────────────────────────

    def test_m2a_16_queued_grace_within_30s_is_degraded(self) -> None:
        now = 1784127600
        rec = {
            "record_version": 1, "task_id": "grace-t1", "lane": "claude",
            "role": "implementer", "access": "writer", "task_class": "code_generation",
            "artifact_expectation": "file_output", "created_epoch": now - 10,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        projection = ops.project_agent_ops(now=now, registry=[rec], processes=[], inbox=[])
        item = next(v for v in projection["work"] if v["work_id"] == "grace-t1")
        self.assertEqual(item["state"], "queued")
        self.assertEqual(item["visibility"], "degraded")
        self.assertEqual(item["reason_code"], "registry_queued_grace")

    def test_m2a_17_queued_grace_expired_after_30s_is_stale(self) -> None:
        now = 1784127600
        rec = {
            "record_version": 1, "task_id": "expired-t1", "lane": "claude",
            "role": "implementer", "access": "writer", "task_class": "code_generation",
            "artifact_expectation": "file_output", "created_epoch": now - 31,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        projection = ops.project_agent_ops(now=now, registry=[rec], processes=[], inbox=[])
        item = next(v for v in projection["work"] if v["work_id"] == "expired-t1")
        self.assertEqual(item["state"], "stale")
        self.assertEqual(item["visibility"], "blocked")
        self.assertEqual(item["reason_code"], "registry_queued_expired")

    def test_m2a_18_queued_future_skew_beyond_5s_is_stale(self) -> None:
        now = 1784127600
        rec = {
            "record_version": 1, "task_id": "skew-t1", "lane": "local",
            "role": "researcher", "access": "read_only", "task_class": "research",
            "artifact_expectation": "none", "created_epoch": now + 10,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        projection = ops.project_agent_ops(now=now, registry=[rec], processes=[], inbox=[])
        item = next(v for v in projection["work"] if v["work_id"] == "skew-t1")
        self.assertEqual(item["state"], "stale")
        self.assertEqual(item["visibility"], "blocked")
        self.assertEqual(item["reason_code"], "registry_queued_future_skew")

    def test_m2a_19_queued_grace_never_authoritative_tracked(self) -> None:
        now = 1784127600
        rec = {
            "record_version": 1, "task_id": "noauth-t1", "lane": "codex",
            "role": "implementer", "access": "writer", "task_class": "testing",
            "artifact_expectation": "none", "created_epoch": now - 5,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        projection = ops.project_agent_ops(now=now, registry=[rec], processes=[], inbox=[])
        item = next(v for v in projection["work"] if v["work_id"] == "noauth-t1")
        self.assertNotEqual(item["visibility"], "tracked",
                            "PID-less queued row must never be authoritative tracked")

    # ── privacy canaries ──────────────────────────────────────────────────────

    def test_m2a_20_privacy_canaries_absent_from_new_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("priv-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            content = r.registry_file.read_text(encoding="utf-8")
            for canary in ("prompt", "argv", "cmdline", "secret", "env", "raw_command", "digest"):
                self.assertNotIn(canary, content,
                                 f"Privacy canary {canary!r} found in new record")

    def test_m2a_21_privacy_canaries_absent_from_projection(self) -> None:
        now = 1784127600
        rec = {
            "record_version": 1, "task_id": "priv-proj-t1", "lane": "claude",
            "role": "implementer", "access": "writer", "task_class": "code_generation",
            "artifact_expectation": "file_output", "created_epoch": now - 2,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        projection = ops.project_agent_ops(now=now, registry=[rec], processes=[], inbox=[])
        rendered = json.dumps(projection)
        for canary in ("PROMPT_CANARY", "secret", "argv", "cmdline", "raw_command"):
            self.assertNotIn(canary, rendered)
        ops.assert_redacted(projection)

    def test_m2a_22_new_record_has_no_prompt_derived_digest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            rec = r.begin("digest-t1", "local", "researcher", "read_only", "analysis", "none")
            for key in rec:
                self.assertNotRegex(key, r"(digest|hash|sha|checksum)",
                                    f"Prompt-derived digest field {key!r} found in new record")

    # ── barrier primitive (Step E hermetic proof) ─────────────────────────────

    @unittest.skipUnless(hasattr(os, "fork"), "fork not available on this platform")
    def test_m2a_23_barrier_eof_never_execs_provider(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sentinel = Path(d) / "ran"
            provider = ["python3", "-c", f"open('{sentinel}', 'w').write('ran')"]
            barrier = self.tr_mod.ExecBarrier(timeout_s=5.0)
            child_pid = barrier.fork_child(provider)
            barrier.close_without_release()
            _, status = os.waitpid(child_pid, 0)
            exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
            self.assertFalse(sentinel.exists(),
                             "Provider ran despite EOF (no release) — barrier failed")
            self.assertEqual(exit_code, 1)

    @unittest.skipUnless(hasattr(os, "fork"), "fork not available on this platform")
    def test_m2a_24_barrier_release_execs_provider(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sentinel = Path(d) / "ran"
            provider = ["python3", "-c", f"open('{sentinel}', 'w').write('ran')"]
            barrier = self.tr_mod.ExecBarrier(timeout_s=5.0)
            child_pid = barrier.fork_child(provider)
            barrier.release(child_pid, 0)
            os.waitpid(child_pid, 0)
            self.assertTrue(sentinel.exists(),
                            "Provider did not run after barrier release")

    @unittest.skipUnless(hasattr(os, "fork"), "fork not available on this platform")
    def test_m2a_25_barrier_timeout_never_execs_provider(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sentinel = Path(d) / "ran"
            provider = ["python3", "-c", f"open('{sentinel}', 'w').write('ran')"]
            barrier = self.tr_mod.ExecBarrier(timeout_s=0.1)
            child_pid = barrier.fork_child(provider)
            # Do not release — child should timeout and exit
            _, status = os.waitpid(child_pid, 0)
            self.assertFalse(sentinel.exists(),
                             "Provider ran despite barrier timeout — barrier failed")
            barrier.close_without_release()

    def test_m2a_26_barrier_double_release_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            barrier = self.tr_mod.ExecBarrier(timeout_s=5.0)
            # Manually close the pipe ends to avoid resource leak in unit-test context
            os.close(barrier._read_fd)
            barrier._child_pid = 99999
            barrier._released = True
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "barrier_already_released"):
                barrier.release(99999, 0)
            os.close(barrier._write_fd)

    def test_m2a_27_barrier_pid_mismatch_raises(self) -> None:
        barrier = self.tr_mod.ExecBarrier(timeout_s=5.0)
        os.close(barrier._read_fd)
        os.close(barrier._write_fd)
        barrier._child_pid = 12345
        with self.assertRaisesRegex(self.tr_mod.RegistryError, "barrier_pid_mismatch"):
            barrier.release(99999, 0)

    def test_m2a_28_barrier_invalid_start_time_raises(self) -> None:
        barrier = self.tr_mod.ExecBarrier(timeout_s=5.0)
        os.close(barrier._read_fd)
        os.close(barrier._write_fd)
        barrier._child_pid = 12345
        with self.assertRaisesRegex(self.tr_mod.RegistryError, "barrier_invalid_start_time"):
            barrier.release(12345, -1)

    # ── adoption guard: schema validates M2A records ──────────────────────────

    def test_m2a_29_schema_validates_new_record_no_unknown_fields(self) -> None:
        from jsonschema import Draft202012Validator
        schema_path = REPO / "config/schemas/delegation-task-record.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        good = {
            "record_version": 1, "task_id": "schema-t1", "lane": "claude",
            "role": "implementer", "access": "writer", "task_class": "code_generation",
            "artifact_expectation": "file_output", "created_epoch": 1784127600,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
        }
        Draft202012Validator(schema).validate(good)
        bad = dict(good)
        bad["prompt"] = "secret text"
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        self.assertTrue(errors, "Schema accepted a record with a 'prompt' field")

    def test_m2a_30_schema_validates_transition_request(self) -> None:
        from jsonschema import Draft202012Validator
        schema = json.loads(
            (REPO / "config/schemas/delegation-task-record.schema.json").read_text(encoding="utf-8")
        )
        good = {
            "op": "transition", "task_id": "schema-t2",
            "record_revision": 3, "to_status": "done", "terminal_reason": "done",
        }
        Draft202012Validator(schema).validate(good)
        # Unknown field must be rejected
        bad = dict(good); bad["raw_prompt"] = "x"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(bad)))

    def test_m2a_31_schema_rejects_pid_in_new_record(self) -> None:
        from jsonschema import Draft202012Validator
        schema = json.loads(
            (REPO / "config/schemas/delegation-task-record.schema.json").read_text(encoding="utf-8")
        )
        with_pid = {
            "record_version": 1, "task_id": "pid-t1", "lane": "local",
            "role": "implementer", "access": "writer", "task_class": "testing",
            "artifact_expectation": "none", "created_epoch": 1784127600,
            "record_revision": 1, "admission_producer": "dispatcher", "status": "queued",
            "pid": 1234,
        }
        errors = list(Draft202012Validator(schema).iter_errors(with_pid))
        self.assertTrue(errors, "Schema accepted a new_record with a 'pid' field")

    # ── reconcile_m2a ─────────────────────────────────────────────────────────

    def test_m2a_32_reconcile_marks_dead_pid_stale(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.begin("recon-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            # Spin up and immediately collect a real process so its PID is guaranteed dead.
            proc = subprocess.Popen(["true"])
            dead_pid = proc.pid
            proc.wait()
            r.attach_process("recon-t1", dead_pid, 0)
            result = r.reconcile_m2a()
            self.assertIn("recon-t1", result["reconciled"])
            rec = r.show_m2a("recon-t1")
            self.assertEqual(rec["status"], "stale")

    # ─── read-only show snapshot ───────────────────────────────────────────────

    @staticmethod
    def _record(task_id: str, revision: int = 1) -> dict:
        return {
            "record_version": 1, "task_id": task_id, "lane": "codex",
            "role": "reviewer", "access": "read_only", "task_class": "code_review",
            "artifact_expectation": "none", "created_epoch": 1784127600,
            "record_revision": revision, "admission_producer": "dispatcher",
            "status": "queued",
        }

    @staticmethod
    def _write_records(path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_m2a_33_show_without_lock_does_not_create_lock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            self._write_records(r.registry_file, [self._record("read-t1")])
            lock_path = r._m2a_lock_path()
            self.assertFalse(lock_path.exists())
            self.assertEqual(r.show_m2a("read-t1")["record_revision"], 1)
            self.assertFalse(lock_path.exists(), "read-only show created the writer lock")

    def test_m2a_34_show_never_uses_writer_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            self._write_records(r.registry_file, [self._record("read-t2")])
            with mock.patch.object(
                r, "_m2a_transact", side_effect=AssertionError("writer transaction used")
            ):
                self.assertEqual(r.show_m2a("read-t2")["task_id"], "read-t2")

    def test_m2a_35_missing_show_creates_no_directory_or_lock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reg_dir = root / "absent" / "delegation"
            r = self.tr_mod.TaskRegistry(reg_dir, repo_root=root)
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "task_not_found"):
                r.show_m2a("missing")
            self.assertFalse(reg_dir.exists())
            self.assertFalse(r._m2a_lock_path().exists())

    def test_m2a_36_show_opens_no_write_capable_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            self._write_records(r.registry_file, [self._record("read-t3")])
            real_open = os.open
            observed_flags: list[int] = []

            def read_only_open(path, flags, *args, **kwargs):
                if Path(path) == r.registry_file:
                    observed_flags.append(flags)
                    self.assertEqual(flags & os.O_ACCMODE, os.O_RDONLY)
                    self.assertFalse(flags & (os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(self.tr_mod.os, "open", side_effect=read_only_open):
                self.assertEqual(r.show_m2a("read-t3")["task_id"], "read-t3")
            self.assertEqual(len(observed_flags), 1)

    def test_m2a_37_show_rejects_symlink_and_non_regular_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            real = r.registry_file.parent / "real.jsonl"
            self._write_records(real, [self._record("read-t4")])
            r.registry_file.symlink_to(real)
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "symlink"):
                r.show_m2a("read-t4")
            r.registry_file.unlink()
            r.registry_file.mkdir()
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "not_regular"):
                r.show_m2a("read-t4")

    def test_m2a_38_show_reads_opened_inode_across_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            self._write_records(r.registry_file, [self._record("old", 1)])
            replacement = r.registry_file.parent / "replacement.jsonl"
            self._write_records(replacement, [self._record("new", 2)])
            real_open = os.open
            swapped = False

            def open_then_replace(path, flags, *args, **kwargs):
                nonlocal swapped
                fd = real_open(path, flags, *args, **kwargs)
                if Path(path) == r.registry_file and not swapped:
                    os.replace(replacement, r.registry_file)
                    swapped = True
                return fd

            with mock.patch.object(self.tr_mod.os, "open", side_effect=open_then_replace):
                self.assertEqual(r.show_m2a("old")["record_revision"], 1)
            self.assertEqual(r.show_m2a("new")["record_revision"], 2)

    def test_m2a_39_show_preserves_malformed_and_record_bounds_failures(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            r.registry_file.write_text("{bad json}\n", encoding="utf-8")
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "malformed"):
                r.show_m2a("bad")
            r.registry_file.write_text(
                json.dumps({"task_id": "big", "data": "A" * 5000}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.tr_mod.RegistryError, "record_too_large"):
                r.show_m2a("big")

    def test_m2a_40_cli_show_leaves_registry_tree_unchanged(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            registry = tmp / "delegation" / "registry.jsonl"
            self._write_records(registry, [self._record("cli-read")])
            before = (
                sorted(path.name for path in registry.parent.iterdir()),
                registry.stat().st_ino,
                registry.stat().st_mtime_ns,
                registry.read_bytes(),
            )
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts/ai/aq-delegation-registry"),
                 "--registry", str(registry), "show", "cli-read"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["record"]["task_id"], "cli-read")
            after = (
                sorted(path.name for path in registry.parent.iterdir()),
                registry.stat().st_ino,
                registry.stat().st_mtime_ns,
                registry.read_bytes(),
            )
            self.assertEqual(after, before)
            self.assertFalse((registry.parent / "registry.jsonl.lock").exists())

    def test_m2a_41_concurrent_atomic_replace_show_is_whole_snapshot(self) -> None:
        import threading

        with tempfile.TemporaryDirectory() as d:
            r = self._make_registry(Path(d))
            task_id = "concurrent-read"
            self._write_records(r.registry_file, [self._record(task_id, 1)])
            errors: list[BaseException] = []

            def writer() -> None:
                try:
                    for revision in range(2, 102):
                        replacement = r.registry_file.parent / f"swap-{revision}.jsonl"
                        self._write_records(replacement, [self._record(task_id, revision)])
                        os.replace(replacement, r.registry_file)
                except BaseException as exc:  # pragma: no cover - reported in parent thread
                    errors.append(exc)

            thread = threading.Thread(target=writer)
            thread.start()
            observed: list[int] = []
            while thread.is_alive():
                observed.append(r.show_m2a(task_id)["record_revision"])
            thread.join()
            observed.append(r.show_m2a(task_id)["record_revision"])
            self.assertEqual(errors, [])
            self.assertTrue(observed)
            self.assertTrue(all(1 <= revision <= 101 for revision in observed))
            self.assertEqual(observed[-1], 101)


if __name__ == "__main__":
    unittest.main(verbosity=2)
