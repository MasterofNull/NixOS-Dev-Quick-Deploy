"""Grep-guard (agent-auth AUTH-S0): API keys/tokens must be compared in constant time.

Fails on `==` / `!=` between a credential-looking name and an API-key-looking
name in the services that authenticate with X-API-Key.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MCP = ROOT / "ai-stack" / "mcp-servers"
FILES = [
    *sorted((MCP / "hybrid-coordinator").rglob("*.py")),
    MCP / "aidb" / "server.py",
    MCP / "nixos-docs" / "server.py",
    MCP / "embeddings-service" / "server.py",
    ROOT / "dashboard" / "backend" / "api" / "routes" / "models.py",
]
CRED = r"(?:token|provided|req_key|presented|header_token|bearer|\bkey|api_key|x_api_key)"
KEY = r"(?:[\w.]*API_KEY|[\w.]*api_key|expected|configured_api_key|_api_key)"
PATTERNS = [
    re.compile(rf"\b{CRED}\s*[!=]=\s*{KEY}\b"),
    re.compile(rf"\b{KEY}\s*[!=]=\s*{CRED}\b"),
]


class ApiKeyCompareGuard(unittest.TestCase):
    def test_no_variable_time_key_compare(self):
        hits = []
        for path in FILES:
            if "tests" in path.parts or not path.exists():
                continue
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                code = line.split("#", 1)[0]
                if any(p.search(code) for p in PATTERNS):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
        self.assertEqual(hits, [], "use shared.api_key_auth.keys_equal / hmac.compare_digest")

    def test_guard_detects_a_violation(self):
        self.assertTrue(any(p.search("if token != configured_api_key:") for p in PATTERNS))
        self.assertTrue(any(p.search("if _api_key and req_key != _api_key:") for p in PATTERNS))
        self.assertFalse(any(p.search("if keys_equal(token, API_KEY):") for p in PATTERNS))


if __name__ == "__main__":
    unittest.main()
