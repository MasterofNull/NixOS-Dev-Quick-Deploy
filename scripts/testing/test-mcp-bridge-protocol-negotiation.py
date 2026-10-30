#!/usr/bin/env python3
"""MCP lifecycle version negotiation for scripts/ai/mcp-bridge-hybrid.py."""
import json
import subprocess
import unittest
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent.parent / "ai" / "mcp-bridge-hybrid.py"


def rpc(requests):
    proc = subprocess.run(
        ["python3", str(BRIDGE)],
        input="\n".join(json.dumps(r) for r in requests) + "\n",
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]


def init(version):
    params = {} if version is None else {"protocolVersion": version}
    return rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params}])[0]["result"]


class TestNegotiation(unittest.TestCase):
    def test_echoes_supported_versions(self):
        for v in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05", "2026-07-28"):
            self.assertEqual(init(v)["protocolVersion"], v)

    def test_unknown_versions_get_client_safe_fallback(self):
        for v in ("2099-01-01", "2023-01-01", "garbage", None):
            self.assertEqual(init(v)["protocolVersion"], "2025-06-18")

    def test_no_hardcoded_version_in_responses(self):
        # discover must reflect the negotiated version, never a literal.
        for v, want in (("2025-06-18", "2025-06-18"), ("2099-01-01", "2025-06-18"),
                        ("2026-07-28", "2026-07-28")):
            r = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": v}},
                     {"jsonrpc": "2.0", "id": 2, "method": "server/discover",
                      "params": {}}])
            self.assertEqual(r[0]["result"]["protocolVersion"], want)
            self.assertEqual(r[1]["result"]["protocolVersion"], want)
        src = BRIDGE.read_text()
        self.assertEqual(src.count('"protocolVersion": "'), 0)

    def test_cache_hints_only_for_2026(self):
        self.assertIn("cacheScope", init("2026-07-28")["capabilities"]["tools"])
        self.assertNotIn("cacheScope", init("2025-06-18")["capabilities"]["tools"])

    def test_structured_content_gated(self):
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "no_such_tool", "arguments": {}}}
        def has_sc(v):
            r = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": v}}, call])[1]["result"]
            return "structuredContent" in r
        self.assertTrue(has_sc("2025-06-18"))
        self.assertFalse(has_sc("2025-03-26"))


if __name__ == "__main__":
    unittest.main()
