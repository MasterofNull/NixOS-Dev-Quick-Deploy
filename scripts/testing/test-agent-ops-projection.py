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


if __name__ == "__main__":
    unittest.main(verbosity=2)
