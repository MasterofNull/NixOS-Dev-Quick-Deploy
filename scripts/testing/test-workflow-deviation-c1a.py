#!/usr/bin/env python3
"""Focused C1A tests: metric schema, fail-closed receipt, PRSI shadow intake."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO_DIR = ROOT / "ai-stack/autonomous-improvement"
AI_LIB = ROOT / "scripts/ai/lib"
for path in (str(AUTO_DIR), str(AI_LIB)):
    if path not in sys.path:
        sys.path.insert(0, path)

if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    psycopg2_stub.extensions = types.SimpleNamespace(connection=object)
    psycopg2_stub.connect = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("PostgreSQL must not be opened by the offline C1A test")
    )
    extras_stub = types.ModuleType("psycopg2.extras")
    extras_stub.execute_values = lambda *args, **kwargs: None
    extras_stub.RealDictCursor = object
    sys.modules["psycopg2"] = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub

from trend_database import TrendDatabase  # noqa: E402
from workflow_deviation import validate  # noqa: E402
from workflow_deviation_io import DeviationWriteError, append_receipt  # noqa: E402
from autonomous_loop import AutonomousLoop  # noqa: E402


def load_prsi():
    path = ROOT / "scripts/automation/prsi-orchestrator.py"
    spec = importlib.util.spec_from_file_location("prsi_orchestrator_c1a", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    current = tmp_path / "current.db"
    with sqlite3.connect(current) as conn:
        conn.execute("""CREATE TABLE routing_decisions (
            timestamp TEXT, tier TEXT, success BOOLEAN, response_time_ms INTEGER
        )""")
        conn.execute(
            "INSERT INTO routing_decisions VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), "local", 1, 123),
        )
    metrics = TrendDatabase(routing_metrics_db=current).collect_routing_metrics()
    assert {metric.metric_name for metric in metrics} == {
        "local_routing_pct", "routing_success_rate", "routing_latency_ms"
    }
    assert next(m for m in metrics if m.metric_name == "local_routing_pct").metric_value == 1.0
    print("PASS: current routing_decisions schema normalized")

    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as conn:
        conn.execute("CREATE TABLE routing_log (timestamp TEXT, cache_hit BOOLEAN, cache_miss BOOLEAN, used_local BOOLEAN)")
        conn.execute(
            "INSERT INTO routing_log VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), 1, 0, 1),
        )
    legacy_metrics = TrendDatabase(routing_metrics_db=legacy).collect_routing_metrics()
    assert {metric.metric_name for metric in legacy_metrics} == {"cache_hit_rate", "local_routing_pct"}
    print("PASS: legacy routing_log remains typed and readable")

    unknown = tmp_path / "unknown.db"
    with sqlite3.connect(unknown) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
    try:
        TrendDatabase(routing_metrics_db=unknown).collect_routing_metrics()
    except RuntimeError as exc:
        assert str(exc) == "routing-metrics-schema-unsupported"
    else:
        raise AssertionError("unknown routing schema must fail closed")
    print("PASS: unknown routing schema fails closed")

    receipt_path = tmp_path / "workflow-deviations.jsonl"

    class BrokenTrend:
        async def sync_metrics_pipeline(self, since_hours=24):
            raise RuntimeError("routing-metrics-schema-unsupported")

    class UnreachableTrigger:
        async def check_and_trigger(self):
            raise AssertionError("trigger must not run after observation failure")

    loop = AutonomousLoop.__new__(AutonomousLoop)
    loop.dry_run = False
    loop.trend_db = BrokenTrend()
    loop.trigger_engine = UnreachableTrigger()
    old_path = os.environ.get("AQ_WORKFLOW_DEVIATION_LOG_PATH")
    os.environ["AQ_WORKFLOW_DEVIATION_LOG_PATH"] = str(receipt_path)
    try:
        asyncio.run(loop.run_improvement_cycle(cycle_type="test"))
    except RuntimeError as exc:
        assert str(exc) == "metric-sync-failed"
    else:
        raise AssertionError("observation failure must produce non-success")
    finally:
        if old_path is None:
            os.environ.pop("AQ_WORKFLOW_DEVIATION_LOG_PATH", None)
        else:
            os.environ["AQ_WORKFLOW_DEVIATION_LOG_PATH"] = old_path
    records = [json.loads(line) for line in receipt_path.read_text().splitlines()]
    assert len(records) == 1
    validate(records[0])
    assert records[0]["reason_code"] == "observation.failed"
    assert "routing-metrics-schema-unsupported" not in receipt_path.read_text()
    print("PASS: observation failure emits validated receipt and raises")

    unsafe_receipt_path = tmp_path / "unsafe-receipt.jsonl"
    unsafe_receipt_path.symlink_to(tmp_path / "unsafe-target.jsonl")
    os.environ["AQ_WORKFLOW_DEVIATION_LOG_PATH"] = str(unsafe_receipt_path)
    try:
        asyncio.run(loop.run_improvement_cycle(cycle_type="test"))
    except RuntimeError as exc:
        assert str(exc) == "metric-sync-failed-and-deviation-receipt-unavailable"
    else:
        raise AssertionError("receipt failure must preserve non-success")
    finally:
        if old_path is None:
            os.environ.pop("AQ_WORKFLOW_DEVIATION_LOG_PATH", None)
        else:
            os.environ["AQ_WORKFLOW_DEVIATION_LOG_PATH"] = old_path
    print("PASS: receipt persistence failure remains fail-closed")

    symlink_target = tmp_path / "outside.jsonl"
    symlink_target.write_text("")
    symlink_path = tmp_path / "symlink.jsonl"
    symlink_path.symlink_to(symlink_target)
    try:
        append_receipt(symlink_path, records[0])
    except DeviationWriteError:
        pass
    else:
        raise AssertionError("symlink receipt target must be rejected")
    assert symlink_target.read_text() == ""
    print("PASS: symlink receipt target rejected without mutation")

    fifo_path = tmp_path / "fifo.jsonl"
    os.mkfifo(fifo_path)
    try:
        append_receipt(fifo_path, records[0])
    except DeviationWriteError:
        pass
    else:
        raise AssertionError("FIFO receipt target must be rejected")
    print("PASS: FIFO receipt target rejects without blocking")

    prsi = load_prsi()
    prsi._WORKFLOW_DEVIATIONS = receipt_path
    actions = prsi._fetch_workflow_deviation_actions()
    assert len(actions) == 1
    assert actions[0]["shadow_only"] is True
    assert actions[0]["root_issue_key"] == "autonomous-improvement-metric-sync-false-green"
    queue_path = tmp_path / "prsi-queue.json"
    state_path = tmp_path / "prsi-state.json"
    log_path = tmp_path / "prsi-actions.jsonl"
    prsi.QUEUE_PATH = queue_path
    prsi.STATE_PATH = state_path
    prsi.ACTIONS_LOG_PATH = log_path
    prsi._fetch_structured_actions = lambda since: (actions, {})
    prsi._load_policy = lambda: {"enabled": True, "max_execute_per_cycle": 5}
    prsi.cmd_sync(Namespace(since="1d"))
    queued = json.loads(queue_path.read_text())["actions"]
    assert len(queued) == 1 and queued[0]["status"] == "shadow_queued"
    try:
        prsi._set_approval(queued[0]["id"], "approve", "test-owner", "must deny")
    except PermissionError as exc:
        assert str(exc) == "shadow-only-action-cannot-be-approved"
    else:
        raise AssertionError("shadow-only action must not be approvable")

    # Defense in depth: even a corrupt/pre-existing approved shadow row is
    # demoted before selection and never reaches the optimizer subprocess.
    queued[0]["status"] = "approved"
    queue_path.write_text(json.dumps({"version": 1, "actions": queued, "meta": {}}))
    subprocess_called = {"value": False}

    def forbidden_subprocess(*args, **kwargs):
        subprocess_called["value"] = True
        raise AssertionError("shadow-only action reached aq-optimizer")

    prsi.subprocess.run = forbidden_subprocess
    assert prsi.cmd_execute(Namespace(limit=5, dry_run=False)) == 0
    assert subprocess_called["value"] is False
    after_execute = json.loads(queue_path.read_text())["actions"][0]
    assert after_execute["status"] == "shadow_queued"
    assert after_execute["execution"]["result"] == "blocked_shadow_only"
    print("PASS: PRSI shadow action cannot traverse approve or execute boundaries")

print("PASS: workflow deviation C1A")
