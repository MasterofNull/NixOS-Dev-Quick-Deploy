#!/usr/bin/env python3
"""Verification for modern MCP 2026-07-28 Bridge."""
import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE = REPO_ROOT / "scripts" / "ai" / "mcp-bridge-hybrid.py"

class TestMcpBridgeModern(unittest.TestCase):
    def _run_rpc(self, requests):
        input_data = "\n".join(json.dumps(r) for r in requests) + "\n"
        proc = subprocess.run(
            ["python3", str(BRIDGE)],
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"Bridge failed: {proc.stderr}")
        responses = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                responses.append(json.loads(line))
        return responses

    def test_enforces_modern_initialize(self):
        req = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}}]
        res = self._run_rpc(req)
        self.assertEqual(len(res), 1)
        result = res[0].get("result", {})
        self.assertEqual(result.get("protocolVersion"), "2026-07-28")
        self.assertEqual(result.get("capabilities", {}).get("tools", {}).get("cacheScope"), "session")
        self.assertEqual(result.get("capabilities", {}).get("tools", {}).get("ttlMs"), 300000)

    def test_server_discover(self):
        req = [{"jsonrpc": "2.0", "id": 2, "method": "server/discover", "params": {}}]
        res = self._run_rpc(req)
        self.assertEqual(len(res), 1)
        result = res[0].get("result", {})
        self.assertEqual(result.get("protocolVersion"), "2026-07-28")
        self.assertIn("tools", result)
        self.assertTrue(len(result["tools"]) > 0)

    def test_deterministic_sorted_tools(self):
        req = [{"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}]
        res = self._run_rpc(req)
        self.assertEqual(len(res), 1)
        tools = res[0].get("result", {}).get("tools", [])
        names = [t["name"] for t in tools]
        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
