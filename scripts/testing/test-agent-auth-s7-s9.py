#!/usr/bin/env python3
"""
Unit and integration tests for AUTH-S7 (Client migration to UDS / TCP fallback)
and AUTH-S9 (Probe/classify unverified services and fail-closed key validation).
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.ai.lib.uds_client import split_uds_url, request_http_or_uds
from scripts.ai.lib.service_classifier import (
    SERVICES,
    probe_service_tcp,
    verify_aidb_fail_closed_empty_key,
    classify_service_auth,
    probe_all_services,
    check_host_origin_enforcement,
)


class TestAgentAuthS7(unittest.TestCase):
    def test_split_uds_url(self):
        sock, path = split_uds_url("unix:///run/ai-hybrid/agent.sock:/hints?q=test")
        self.assertEqual(sock, "/run/ai-hybrid/agent.sock")
        self.assertEqual(path, "/hints?q=test")

        sock2, path2 = split_uds_url("unix:///run/ai-hybrid/agent.sock/health")
        self.assertEqual(sock2, "/run/ai-hybrid/agent.sock")
        self.assertEqual(path2, "/health")

    def test_request_http_tcp_live(self):
        res = request_http_or_uds("http://127.0.0.1:8003/health")
        self.assertIn("status", res)
        self.assertEqual(res["status"], "healthy")

    def test_request_http_uds_fallback_to_tcp(self):
        # Socket path does not exist, should fall back to TCP url
        res = request_http_or_uds(
            "unix:///tmp/nonexistent-test.sock/health",
            tcp_fallback_url="http://127.0.0.1:8003",
        )
        self.assertIn("status", res)
        self.assertEqual(res["status"], "healthy")


class TestAgentAuthS9(unittest.TestCase):
    def test_services_catalog(self):
        for expected in ("aidb", "coordinator", "ralph", "llama", "switchboard", "dashboard"):
            self.assertIn(expected, SERVICES)

    def test_verify_aidb_fail_closed_empty_key(self):
        self.assertFalse(verify_aidb_fail_closed_empty_key(None))
        self.assertFalse(verify_aidb_fail_closed_empty_key(""))
        self.assertFalse(verify_aidb_fail_closed_empty_key("   "))
        self.assertTrue(verify_aidb_fail_closed_empty_key("valid-secret-token"))

    def test_classify_service_auth(self):
        report = classify_service_auth("coordinator")
        self.assertEqual(report["name"], "coordinator")
        self.assertEqual(report["port"], 8003)
        self.assertTrue(report["socket_capable"])

    def test_probe_all_services(self):
        all_reports = probe_all_services()
        self.assertEqual(len(all_reports), 6)
        names = {r["name"] for r in all_reports}
        self.assertEqual(names, {"aidb", "coordinator", "ralph", "llama", "switchboard", "dashboard"})

    def test_check_host_origin_enforcement(self):
        # Coordinator on 8003 enforces Host/Origin guard (AUTH-S1) returning 421 or 403 on invalid host
        res = check_host_origin_enforcement("http://127.0.0.1:8003/health", invalid_host="malicious.internal")
        self.assertTrue(res.get("enforced"))


if __name__ == "__main__":
    unittest.main()
