#!/usr/bin/env python3
"""Executable M0 contract tests for the read-only Agent Ops projector."""
from __future__ import annotations

import importlib.util
import json
import sys
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
