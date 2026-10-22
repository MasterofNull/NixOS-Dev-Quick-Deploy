#!/usr/bin/env python3
"""Hermetic unit tests for aq-mcp-conformance."""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai"))

from importlib.machinery import SourceFileLoader

conformance_mod = SourceFileLoader("aq_mcp_conformance", str(REPO_ROOT / "scripts" / "ai" / "aq-mcp-conformance")).load_module()
audit_server = conformance_mod.audit_server
audit_all_servers = conformance_mod.audit_all_servers


class TestMcpConformance(unittest.TestCase):
    def test_fixture_legacy_server(self):
        """Test a mock legacy 2024-11-05 server fixture."""
        script = """
import sys, json
for line in sys.stdin:
    req = json.loads(line)
    if req['method'] == 'initialize':
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {'protocolVersion': '2024-11-05'}})+ '\\n')
        sys.stdout.flush()
    elif req['method'] == 'tools/list':
        tools = [{'name': 'toolA'}, {'name': 'toolB'}]
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {'tools': tools}})+ '\\n')
        sys.stdout.flush()
    else:
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'error': {'code': -32601, 'message': 'Method not found'}})+ '\\n')
        sys.stdout.flush()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            f_path = f.name

        try:
            spec = {"command": sys.executable, "args": [f_path], "env": {}}
            report = asyncio.run(audit_server("mock-legacy", spec, timeout=3.0))
            self.assertTrue(report["reachable"])
            self.assertEqual(report["protocol_version"], "2024-11-05")
            self.assertFalse(report["has_server_discover"])
            self.assertTrue(report["deterministic_tool_order"])
            self.assertEqual(report["tools_count"], 2)
            self.assertFalse(report["spec_2026_07_28_compliant"])
        finally:
            os.unlink(f_path)

    def test_fixture_spec_2026_server(self):
        """Test a mock spec 2026-07-28 compliant server fixture."""
        script = """
import sys, json
for line in sys.stdin:
    req = json.loads(line)
    if req['method'] == 'server/discover':
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {'protocolVersion': '2026-07-28', 'capabilities': {}}})+ '\\n')
        sys.stdout.flush()
    elif req['method'] == 'initialize':
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {'protocolVersion': '2026-07-28'}})+ '\\n')
        sys.stdout.flush()
    elif req['method'] == 'tools/list':
        tools = [
            {'name': 'query', 'outputSchema': {'type': 'object'}, 'ttlMs': 5000},
            {'name': 'search', 'outputSchema': {'type': 'object'}, 'ttlMs': 5000}
        ]
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {'tools': tools}})+ '\\n')
        sys.stdout.flush()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            f_path = f.name

        try:
            spec = {"command": sys.executable, "args": [f_path], "env": {}}
            report = asyncio.run(audit_server("mock-2026", spec, timeout=3.0))
            self.assertTrue(report["reachable"])
            self.assertEqual(report["protocol_version"], "2026-07-28")
            self.assertTrue(report["has_server_discover"])
            self.assertTrue(report["deterministic_tool_order"])
            self.assertEqual(report["tools_with_output_schema"], 2)
            self.assertEqual(report["tools_with_ttl"], 2)
            self.assertTrue(report["spec_2026_07_28_compliant"])
        finally:
            os.unlink(f_path)


if __name__ == "__main__":
    unittest.main()
