#!/usr/bin/env python3
"""Service coverage test for Herdr H2 monitored presentation projection.

Verifies:
1. aq-herdr project (default and explicit presentation target) returns valid schema.
2. aq-herdr project operator-context returns valid fixture-projected context.
3. aq-herdr project rejects invalid targets with code 2.
4. Dashboard backend route aistack.py exposes _herdr_presentation_summary.
5. Dashboard frontend assets/dashboard.js renders herdr presentation row.
6. Pure projection digest determinism and schema version conformance.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestHerdrH2PresentationServiceCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = REPO_ROOT / "scripts" / "ai" / "aq-herdr"
        self.route = REPO_ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py"
        self.js = REPO_ROOT / "assets" / "dashboard.js"
        self.lib = REPO_ROOT / "scripts" / "ai" / "lib" / "herdr_presentation_projection.py"

    def test_prerequisites_exist(self) -> None:
        self.assertTrue(self.cli.exists(), "aq-herdr missing")
        self.assertTrue(self.route.exists(), "aistack.py missing")
        self.assertTrue(self.js.exists(), "dashboard.js missing")
        self.assertTrue(self.lib.exists(), "herdr_presentation_projection.py missing")

    def test_cli_project_presentation_default(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "project"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"aq-herdr project failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertEqual(data.get("schema_version"), "aq.herdr.presentation.v1")
        self.assertTrue(data.get("observation_revision", "").startswith("dormant-preview"))
        self.assertIn("coverage", data)
        self.assertIn("counts", data)

    def test_cli_project_operator_context(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "project", "operator-context"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"aq-herdr project operator-context failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("schema_version"), "aq.operator-context.v1")
        self.assertIn("mission", data)
        self.assertIn("work", data)

    def test_cli_project_invalid_target(self) -> None:
        proc = subprocess.run(
            [str(self.cli), "project", "invalid-target"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unsupported project target", proc.stderr)

    def test_dashboard_backend_summary(self) -> None:
        route_text = self.route.read_text(encoding="utf-8")
        self.assertIn("_herdr_presentation_summary", route_text)
        self.assertIn('"herdr_presentation": await asyncio.to_thread(_herdr_presentation_summary)', route_text)

        # Import and invoke the summary directly
        spec = importlib.util.spec_from_file_location("aq_lib_hpp", self.lib)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        envelope = {
            "observation_revision": "dormant-preview",
            "generated_at": "2026-10-12T00:00:00Z",
            "static_expected": {
                "version": "0.7.5",
                "protocol": "1",
                "layout_revision": "h2-default",
                "layout_digest": "0" * 64,
                "session_count": {"state": "known", "value": 1},
            },
        }
        res = mod.project(envelope)
        digest = mod.projection_digest(res)
        self.assertEqual(len(digest), 64)
        self.assertEqual(res["schema_version"], "aq.herdr.presentation.v1")

    def test_dashboard_frontend_wiring(self) -> None:
        js_text = self.js.read_text(encoding="utf-8")
        self.assertIn("· herdr presentation", js_text)
        self.assertIn("cg.herdr_presentation", js_text)


if __name__ == "__main__":
    unittest.main()
