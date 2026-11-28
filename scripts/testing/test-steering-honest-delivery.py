#!/usr/bin/env python3
"""Steering must report only what it can deliver.

/loop/control steer and /agent-runs/{id}/guidance either enqueue to the control queue
agent_executor polls (active local-agent task) or answer "unsupported"; neither may claim
delivery nor write queues nothing reads. The CLI writer and cockpit dock are covered by
test-human-intervention.py.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CC_SRC = ROOT / "ai-stack" / "local-agents" / "control_channel.py"
EXECUTOR_SRC = ROOT / "ai-stack" / "local-agents" / "agent_executor.py"


class SteeringTestBase(unittest.TestCase):
    """Routes run against a throwaway repo root holding its own control_channel copy, so
    the queue root is derived exactly as production derives it (file location)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="test-steering-"))
        (cls.tmp / "ai-stack" / "local-agents").mkdir(parents=True)
        shutil.copy(CC_SRC, cls.tmp / "ai-stack" / "local-agents" / "control_channel.py")
        (cls.tmp / ".agents" / "delegation").mkdir(parents=True)
        (cls.tmp / ".agent" / "collaboration").mkdir(parents=True)
        cls.control_dir = cls.tmp / ".agents" / "delegation" / "control"
        cls.registry = cls.tmp / ".agents" / "delegation" / "registry.jsonl"
        cls.events = cls.tmp / "agent-run-events.jsonl"
        cls.spool = cls.tmp / "guidance-spool"
        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(cls.events)
        os.environ["AQ_AGENT_GUIDANCE_DIR"] = str(cls.spool)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(cls.tmp / "operator-audit.jsonl")
        mod: Any = importlib.reload(importlib.import_module("api.routes.aistack"))
        mod._repo_root = lambda: cls.tmp
        mod._CONTROL_CHANNEL_MOD = None
        cls.mod = mod
        app = FastAPI()
        app.include_router(mod.router, prefix="/api/aistack")
        # /loop/control is also mounted at /api in production; the router prefix is enough here.
        cls.client: Any = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        if cls.mod._http_session and not cls.mod._http_session.closed:
            cls.client.portal.call(cls.mod._http_session.close)
            cls.mod._http_session = None
        cls.client.__exit__(None, None, None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        shutil.rmtree(self.control_dir, ignore_errors=True)
        shutil.rmtree(self.spool, ignore_errors=True)
        self.events.write_text("", encoding="utf-8")
        rows = [
            {"id": "t-local-1", "agent": "local-agent", "status": "running"},
            {"id": "t-done-1", "agent": "local-agent", "status": "done"},
            {"id": "t-codex-1", "agent": "codex", "status": "running"},
            {"id": "t-direct-1", "agent": "local-direct", "status": "running"},
        ]
        self.registry.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def queue_files(self):
        return sorted(self.control_dir.glob("*.jsonl")) if self.control_dir.exists() else []

    def steer(self, agent, message="focus on the switchboard path"):
        return self.client.post(
            "/api/aistack/loop/control", json={"action": "steer", "agent": agent, "message": message}
        )

    def assert_unsupported(self, resp):
        self.assertEqual(resp.status_code, 422, resp.text)
        detail = resp.json()["detail"]
        self.assertEqual(detail["status"], "unsupported")
        self.assertTrue(detail["reason"])
        self.assertEqual(self.queue_files(), [], "refusal must leave no queue file")


class TestLoopControlSteer(SteeringTestBase):
    def test_active_local_task_appends_exactly_one_line_and_is_injected_once(self):
        resp = self.steer("t-local-1")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "queued")
        self.assertNotEqual(body["status"], "delivered")
        files = self.queue_files()
        self.assertEqual([f.name for f in files], ["t-local-1.jsonl"])
        lines = [ln for ln in files[0].read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual((rec["kind"], rec["text"]), ("inject", "focus on the switchboard path"))
        pulse = (self.tmp / ".agent" / "collaboration" / "PULSE.log").read_text(encoding="utf-8")
        self.assertIn("[steer]: t-local-1", pulse)

        # agent_executor polls with this exact call and cursor handling (see test below).
        cc = self.mod._control_channel_module()
        first, cursor = cc.poll("t-local-1", 0)
        self.assertEqual([m["text"] for m in first], ["focus on the switchboard path"])
        again, cursor = cc.poll("t-local-1", cursor)
        self.assertEqual(again, [], "message must not be re-injected")

    def test_executor_polls_the_same_queue_api(self):
        src = EXECUTOR_SRC.read_text(encoding="utf-8")
        self.assertIn("_cc.poll(task.id, _ctrl_cursor)", src)

    def test_invalid_id_unsupported(self):
        self.assert_unsupported(self.steer("../etc/passwd"))

    def test_unknown_id_unsupported(self):
        self.assert_unsupported(self.steer("t-nope-1"))

    def test_inactive_task_unsupported(self):
        self.assert_unsupported(self.steer("t-done-1"))

    def test_non_local_lane_unsupported(self):
        self.assert_unsupported(self.steer("t-codex-1"))
        self.assert_unsupported(self.steer("t-direct-1"))

    def test_orchestrator_and_lane_targets_unsupported(self):
        self.assert_unsupported(self.steer("orchestrator"))
        self.assert_unsupported(self.steer("lane-claude"))

    def test_write_failure_is_error_not_queued(self):
        self.control_dir.parent.mkdir(parents=True, exist_ok=True)
        self.control_dir.write_text("not a directory", encoding="utf-8")  # mkdir/open must fail
        try:
            resp = self.steer("t-local-1")
        finally:
            self.control_dir.unlink()
        self.assertGreaterEqual(resp.status_code, 500, resp.text)
        self.assertNotEqual(resp.json().get("status"), "queued")
        self.assertNotEqual(resp.json().get("detail", {}).get("status"), "queued")


class TestGuidanceRoute(SteeringTestBase):
    def guide(self, run_id, action="guidance"):
        return self.client.post(
            f"/api/aistack/agent-runs/{run_id}/guidance",
            json={"prompt": "verify worktrees first", "operator_id": "op", "action": action},
        )

    def audit_events(self):
        return [json.loads(ln) for ln in self.events.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def test_mapped_run_is_queued_via_control_channel(self):
        resp = self.guide("t-local-1")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["delivery_status"], "queued")
        self.assertIs(body["delivered"], False)
        lines = self.queue_files()[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["text"], "verify worktrees first")
        self.assertFalse(self.spool.exists() and any(self.spool.iterdir()), "no unread spool")
        self.assertEqual(len(self.audit_events()), 1, "audit event still written")

    def test_unmapped_run_is_unsupported_and_writes_no_spool(self):
        for run_id in ("run-root", "t-codex-1", "t-done-1"):
            resp = self.guide(run_id)
            self.assertEqual(resp.status_code, 200, resp.text)
            body = resp.json()
            self.assertEqual(body["delivery_status"], "unsupported")
            self.assertTrue(body["reason"])
            self.assertIs(body["delivered"], False)
        self.assertEqual(self.queue_files(), [])
        self.assertFalse(self.spool.exists() and any(self.spool.iterdir()), "no unread spool")
        self.assertEqual(len(self.audit_events()), 3, "audit event still written per call")

    def test_action_without_consumer_is_unsupported_even_for_mapped_task(self):
        body = self.guide("t-local-1", action="pause").json()
        self.assertEqual(body["delivery_status"], "unsupported")
        self.assertEqual(self.queue_files(), [])

    def with_audit_write_failing(self, run_id):
        blocker = self.tmp / "audit-blocker"
        blocker.write_text("file, so the events path parent cannot be a directory", encoding="utf-8")
        saved = self.mod._AGENT_RUN_EVENTS_PATH
        self.mod._AGENT_RUN_EVENTS_PATH = blocker / "events.jsonl"
        try:
            return self.guide(run_id)
        finally:
            self.mod._AGENT_RUN_EVENTS_PATH = saved
            blocker.unlink()

    def test_audit_write_failure_reports_persisted_false_when_mapped(self):
        body = self.with_audit_write_failing("t-local-1").json()
        self.assertIs(body["persisted"], False)

    def test_audit_write_failure_reports_persisted_false_when_unsupported(self):
        body = self.with_audit_write_failing("run-root").json()
        self.assertEqual(body["delivery_status"], "unsupported")
        self.assertIs(body["persisted"], False)
        self.assertEqual(self.queue_files(), [])

    def test_unsupported_persisted_matches_audit_write_and_never_a_queue_entry(self):
        body = self.guide("run-root").json()
        self.assertEqual(body["delivery_status"], "unsupported")
        self.assertIs(body["persisted"], True)
        self.assertEqual(len(self.audit_events()), 1)
        self.assertEqual(self.queue_files(), [])

    def test_write_failure_is_error(self):
        self.control_dir.parent.mkdir(parents=True, exist_ok=True)
        self.control_dir.write_text("not a directory", encoding="utf-8")
        try:
            resp = self.guide("t-local-1")
        finally:
            self.control_dir.unlink()
        self.assertGreaterEqual(resp.status_code, 500, resp.text)


if __name__ == "__main__":
    unittest.main()
