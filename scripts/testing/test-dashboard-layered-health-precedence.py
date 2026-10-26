#!/usr/bin/env python3
"""
Unit test for get_layered_health evidence precedence:
Ensures verified host QAEvidenceStore results take priority over in-memory stale cache.
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "dashboard" / "backend"))

from api.routes import health


class TestLayeredHealthEvidencePrecedence(unittest.TestCase):
    def test_persisted_evidence_takes_precedence_over_stale_cache(self):
        stale_result = {"phase": "0", "passed": 120, "failed": 30, "tests": []}
        health._layered_cache["result"] = stale_result
        health._layered_cache["expires_at"] = 9999999999.0

        authoritative = {
            "phase": "0",
            "passed": 204,
            "failed": 1,
            "tests": [{"id": "0.1.1", "status": "PASS"}],
        }
        with patch("api.routes.health._load_persisted_qa_results", return_value=authoritative):
            res = asyncio.run(health.get_layered_health())
            self.assertEqual(res.get("passed"), 204)
            self.assertEqual(res.get("failed"), 1)
            self.assertTrue(res.get("cached"))


if __name__ == "__main__":
    unittest.main()
