#!/usr/bin/env python3
"""Executable M0 contract tests for the read-only Agent Ops projector."""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

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
        for metric in ops.METRICS:
            self.assertEqual(self.projection["metrics"][metric], expected[metric])
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
