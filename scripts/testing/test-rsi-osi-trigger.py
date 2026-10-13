#!/usr/bin/env python3
"""
test-rsi-osi-trigger.py — Regression tests for OSI layer failure to RSI triggers,
sweep adapters, attention queue ingestion, and PRSI action intake.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_LIB = REPO_ROOT / "scripts" / "ai" / "lib"
AUTOMATION_DIR = REPO_ROOT / "scripts" / "automation"
sys.path.insert(0, str(AI_LIB))
sys.path.insert(0, str(AUTOMATION_DIR))

import rsi_lifecycle
import rsi_sweep
import importlib.util

from importlib.machinery import SourceFileLoader

# Dynamically import prsi-orchestrator
prsi_loader = SourceFileLoader("prsi_orchestrator", str(AUTOMATION_DIR / "prsi-orchestrator.py"))
prsi_spec = importlib.util.spec_from_loader(prsi_loader.name, prsi_loader)
prsi_orchestrator = importlib.util.module_from_spec(prsi_spec)
prsi_loader.exec_module(prsi_orchestrator)

# Dynamically import aq-health-spider
spider_loader = SourceFileLoader("aq_health_spider", str(REPO_ROOT / "scripts" / "ai" / "aq-health-spider"))
spider_spec = importlib.util.spec_from_loader(spider_loader.name, spider_loader)
aq_health_spider = importlib.util.module_from_spec(spider_spec)
spider_loader.exec_module(aq_health_spider)


class TestRsiOsiTrigger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        self.runtime_dir = self.tmp_dir / "collaboration"
        self.backlog_file = self.tmp_dir / "issues-backlog.md"
        self.workarounds_file = self.tmp_dir / "WORKAROUND-REGISTER.md"
        self.attention_file = self.tmp_dir / "ATTENTION.json"

        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        # Patch rsi_lifecycle paths
        self.patches = [
            patch.object(rsi_lifecycle, "_RUNTIME", self.runtime_dir),
            patch.object(rsi_lifecycle, "_BACKLOG", self.backlog_file),
            patch.object(rsi_lifecycle, "_WORKAROUNDS", self.workarounds_file),
            patch.object(rsi_lifecycle, "_event"),
            patch.object(prsi_orchestrator, "REPO_ROOT", self.tmp_dir),
            patch.object(prsi_orchestrator, "_RSI_INCIDENTS", self.runtime_dir / "rsi-incidents.json"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_prsi_path_safety_accepts_operational_targets(self):
        """Verify _is_safe_rsi_path accepts operational targets and rejects path traversal."""
        safe_operational = [
            "osi:layer:1",
            "osi:layer:3",
            "osi:osi-layered",
            "service:ai-switchboard",
            "systemd:ai-aidb.service",
            "systemd:failed-units",
            "port:8085",
            "network:socket",
            "attention:attn-13acb7b4",
            "dashboard:osi-layered",
            "aq-qa check 0.10.50",
            "http://127.0.0.1:8889/api/health/layered",
        ]
        for target in safe_operational:
            self.assertTrue(
                prsi_orchestrator._is_safe_rsi_path(target),
                f"Expected safe path for operational target: {target}",
            )

        unsafe_paths = [
            "../../../etc/shadow",
            "/etc/passwd",
            "",
            None,
            123,
            "x" * 300,
        ]
        for target in unsafe_paths:
            self.assertFalse(
                prsi_orchestrator._is_safe_rsi_path(target),
                f"Expected unsafe path for invalid target: {target}",
            )

    def test_aq_rsi_hook_osi_cli(self):
        """Verify aq-rsi-hook osi command records failure into rsi-incidents and backlog."""
        hook_script = REPO_ROOT / "scripts" / "ai" / "aq-rsi-hook"
        env = dict(os.environ)
        env["RSI_RUNTIME_DIR"] = str(self.runtime_dir)
        env["RSI_BACKLOG_FILE"] = str(self.backlog_file)
        env["RSI_WORKAROUNDS_FILE"] = str(self.workarounds_file)

        proc = subprocess.run(
            [sys.executable, str(hook_script), "osi", "3", "socket bind failed: EADDRINUSE"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, f"Hook stderr: {proc.stderr}")
        self.assertIn("RSI incident recorded for OSI layer 3", proc.stdout)

        # Verify ledger updated
        ledger_path = self.runtime_dir / "rsi-incidents.json"
        self.assertTrue(ledger_path.exists())
        state = json.loads(ledger_path.read_text())
        incidents = state.get("incidents", {})
        self.assertEqual(len(incidents), 1)

        inc = next(iter(incidents.values()))
        self.assertEqual(inc["producer"], "osi-layer-hook")
        self.assertEqual(inc["path"], "osi:layer:3")
        self.assertEqual(inc["authority"], "osi-hook")
        self.assertIn("socket bind failed: EADDRINUSE", inc["error"])
        self.assertEqual(inc["status"], "open")
        self.assertEqual(inc["severity"], "high")

        # Verify issues-backlog updated
        self.assertTrue(self.backlog_file.exists())
        backlog_text = self.backlog_file.read_text()
        self.assertIn("[OPEN] rsi-", backlog_text)
        self.assertIn("osi-layer-hook failure in osi:layer:3", backlog_text)

    def test_prsi_ingests_osi_incidents(self):
        """Verify prsi-orchestrator fetches open OSI layer incidents into action queue."""
        rsi_lifecycle.failure(
            agent="osi-monitor",
            subject="osi:layer:3",
            producer="osi-layer-hook",
            path="osi:layer:3",
            authority="osi-hook",
            os_error="port 8085 refused connection",
            severity="high",
            root_fix="restart switchboard",
        )
        candidates = prsi_orchestrator._fetch_rsi_incident_actions()
        self.assertEqual(len(candidates), 1)
        action = candidates[0]
        self.assertEqual(action["type"], "maintenance")
        self.assertEqual(action["topic"], "rsi-incident-recovery")
        self.assertEqual(action["incident_path"], "osi:layer:3")
        self.assertEqual(action["incident_severity"], "high")
        self.assertFalse(action["requires_owner"])

    def test_prsi_ingests_attention_queue(self):
        """Verify prsi-orchestrator fetches pending high/critical attention queue alerts."""
        attention_data = {
            "schema_version": "1.0",
            "alerts": [
                {
                    "id": "attn-osi-layer4-down",
                    "source": "health-spider",
                    "severity": "high",
                    "autonomy_boundary": "human_gate",
                    "title": "OSI Layer 4 Transport Degraded",
                    "detail": "Switchboard HTTP 502",
                    "proposed_action": "Restart switchboard",
                    "status": "pending",
                },
                {
                    "id": "attn-minor",
                    "source": "health-spider",
                    "severity": "low",
                    "autonomy_boundary": "auto_ok",
                    "title": "Minor log note",
                    "detail": "info only",
                    "status": "pending",
                },
            ],
        }
        attention_file = self.tmp_dir / ".agents" / "attention" / "ATTENTION.json"
        attention_file.parent.mkdir(parents=True, exist_ok=True)
        attention_file.write_text(json.dumps(attention_data))

        state, findings, d = rsi_sweep.adapter_attention_queue(attention_file=attention_file)
        self.assertEqual(state, "findings")
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["subject"], "attention:attn-osi-layer4-down")
        self.assertEqual(f["path"], "attention:attn-osi-layer4-down")

        # Record finding to rsi ledger
        rsi_lifecycle.failure(
            agent="rsi-steward",
            subject=f["subject"],
            producer=f["producer"],
            path=f["path"],
            authority=f["authority"],
            os_error=f["os_error"],
            severity=f["severity"],
            root_fix=f["root_fix"],
        )

        actions = prsi_orchestrator._fetch_rsi_incident_actions()
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action["incident_path"], "attention:attn-osi-layer4-down")
        self.assertEqual(action["incident_severity"], "high")
        self.assertEqual(action["topic"], "rsi-incident-recovery")

    def test_health_spider_osi_degraded_triggers_rsi(self):
        """Verify aq-health-spider handle_anomaly on osi-layered triggers rsi_failure."""
        spider = aq_health_spider.HealthSpider()
        spider._queue_prsi = AsyncMock()

        anomaly = {
            "type": "dashboard_degraded",
            "zone": "dashboard",
            "probe": "osi-layered",
            "url": "http://127.0.0.1:8889/api/health/layered",
            "reason": "osi_layered_failed=2",
            "timestamp": 123456789.0,
        }

        # Run handle_anomaly
        result = asyncio.run(spider.handle_anomaly(anomaly))
        self.assertTrue(result)
        spider._queue_prsi.assert_called_once_with(anomaly)

        # Verify incident logged in rsi ledger
        ledger_path = self.runtime_dir / "rsi-incidents.json"
        self.assertTrue(ledger_path.exists())
        state = json.loads(ledger_path.read_text())
        incidents = state.get("incidents", {})
        self.assertEqual(len(incidents), 1)

        inc = next(iter(incidents.values()))
        self.assertEqual(inc["producer"], "health-spider:osi-layered")
        self.assertEqual(inc["path"], "osi:osi-layered")
        self.assertEqual(inc["authority"], "osi-health-probe")
        self.assertEqual(inc["severity"], "high")
        self.assertIn("osi_layered_failed=2", inc["error"])


if __name__ == "__main__":
    unittest.main()
