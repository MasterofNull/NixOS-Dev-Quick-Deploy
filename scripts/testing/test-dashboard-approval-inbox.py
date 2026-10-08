#!/usr/bin/env python3
"""HTTP contract tests against isolated canonical inbox fixtures."""
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))
route = importlib.import_module("api.routes.approval_inbox")
inbox = importlib.import_module("approval_inbox")


class ApprovalInboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.secret = secrets.token_urlsafe(18)
        (root / "queue.json").write_text(json.dumps({"actions": [
            {"id": "a", "status": "pending_approval", "risk": "high", "action": "Restart worker",
             "reason": self.secret},
        ]}))
        (root / "incidents.json").write_text(json.dumps({"incidents": {
            "b": {"status": "open", "severity": "medium", "agent": "local",
                  "error": "token=" + self.secret},
        }}))
        env = patch.dict(os.environ, {
            "PRSI_ACTION_QUEUE_PATH": str(root / "queue.json"),
            "PRSI_INCIDENTS_FILE": str(root / "incidents.json"),
            "AQ_APPROVAL_INBOX_DIR": str(root),
        })
        env.start()
        self.addCleanup(env.stop)
        attention = patch.object(inbox, "_attention_pending", return_value=[])
        attention.start()
        self.addCleanup(attention.stop)
        app = FastAPI()
        app.include_router(route.router, prefix="/api")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_canonical_projection(self):
        response = self.client.get("/api/approval-inbox")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"tag", "needs_approval", "deferred", "counts", "generated_at"})
        self.assertEqual(data["tag"], inbox.snapshot_tag(inbox.collect()))
        self.assertEqual(data["counts"], {"needs_approval": 1, "deferred": 1, "total": 2})
        self.assertEqual(data["needs_approval"], [{"n": 1, "severity": "high", "title": "Approve action: Restart worker", "source": "prsi-queue", "id": "prsi:a"}])
        self.assertEqual(data["deferred"][0]["n"], 2)
        self.assertEqual(data["deferred"][0]["id"], "rsi:b")
        self.assertNotIn(self.secret, response.text)
        from datetime import datetime
        self.assertIsNotNone(datetime.fromisoformat(data["generated_at"]).tzinfo)

    def test_failure_is_safe_and_unavailable(self):
        with patch.object(inbox, "collect_with_status", side_effect=RuntimeError(self.secret)):
            with self.assertLogs(route.logger, level="WARNING") as logs:
                response = self.client.get("/api/approval-inbox")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertNotIn(self.secret, response.text + str(logs.output))

    def test_no_mutating_methods(self):
        self.assertEqual(route.router.routes[0].methods, {"GET"})
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.client.request(method, "/api/approval-inbox").status_code, 405)

    def test_empty_inbox(self):
        with patch.object(inbox, "collect_with_status", return_value=([], [])):
            data = self.client.get("/api/approval-inbox").json()
        self.assertEqual(data["counts"]["total"], 0)
        self.assertEqual(data["needs_approval"], [])
        self.assertEqual(data["deferred"], [])

    def test_registration_and_polling(self):
        main = (ROOT / "dashboard/backend/api/main.py").read_text()
        self.assertIn('app.include_router(approval_inbox_mod.router, prefix="/api"', main)
        client = (ROOT / "assets/dashboard.js").read_text()
        self.assertIn('apiFetch("/approval-inbox")', client)
        self.assertIn('setInterval(loadApprovalInbox, 30_000)', client)
        self.assertIn('id="approvalInboxDetails"', (ROOT / "dashboard.html").read_text())

    def test_degraded_unreadable_queue(self):
        """Unreadable PRSI queue → status=degraded with degraded_sources."""
        import stat
        root = Path(self.tmp.name)
        queue_path = root / "queue.json"
        # Make queue unreadable (skip if root)
        if os.getuid() != 0:
            os.chmod(queue_path, 0o000)
            try:
                response = self.client.get("/api/approval-inbox")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data.get("status"), "degraded")
                self.assertIn("degraded_sources", data)
                self.assertTrue(any(str(queue_path) in s.get("path", "") for s in data["degraded_sources"]))
                # Items should still be populated from incidents
                self.assertEqual(data["counts"]["deferred"], 1)
            finally:
                os.chmod(queue_path, 0o644)
        else:
            self.skipTest("root can read mode 0o000 files")

    def test_degraded_corrupt_json(self):
        """Corrupt JSON in queue → status=degraded."""
        root = Path(self.tmp.name)
        queue_path = root / "queue.json"
        queue_path.write_text("{ invalid json")
        response = self.client.get("/api/approval-inbox")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "degraded")
        self.assertIn("degraded_sources", data)
        self.assertTrue(any("JSONDecodeError" in s.get("error", "") for s in data["degraded_sources"]))

    def test_missing_queue_not_degraded(self):
        """Missing queue file (no actions) is OK, not degraded."""
        root = Path(self.tmp.name)
        queue_path = root / "queue.json"
        queue_path.unlink()
        response = self.client.get("/api/approval-inbox")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotEqual(data.get("status"), "degraded")
        # Deferred should still have the incident
        self.assertEqual(data["counts"]["deferred"], 1)

    def test_degraded_in_collect_with_status(self):
        """collect_with_status() distinguishes missing vs unreadable."""
        root = Path(self.tmp.name)
        queue_path = root / "queue.json"

        # Missing file: no degradation
        queue_path.unlink()
        items, degraded = inbox.collect_with_status()
        self.assertEqual(degraded, [])

        # Corrupt file: degradation
        queue_path.write_text("broken")
        items, degraded = inbox.collect_with_status()
        self.assertTrue(len(degraded) > 0)
        self.assertTrue(any("JSONDecodeError" in d.get("error", "") for d in degraded))


if __name__ == "__main__":
    unittest.main(verbosity=2)
