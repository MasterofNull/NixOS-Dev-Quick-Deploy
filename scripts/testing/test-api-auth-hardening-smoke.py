#!/usr/bin/env python3
"""Regression: check-api-auth-hardening.sh must validate the CURRENT coordinator
auth middleware layout, and fail on missing middleware rather than a stale filename.

Backlog: security-auth-hardening-smoke-stale-source. The smoke previously hard-coded
ai-stack/mcp-servers/hybrid-coordinator/http_server.py, which no longer exists —
coordinator auth moved to middleware/auth.py + core/auth_middleware.py. That made
the check fail on `missing http server source` regardless of real auth health.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "testing" / "check-api-auth-hardening.sh"
AUTH_MW = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "middleware" / "auth.py"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    text = SMOKE.read_text()

    # 1. Must NOT depend on the stale monolithic source path.
    if "http_server.py" in text:
        _fail("smoke still references stale http_server.py — should inspect middleware/auth.py")

    # 2. Must inspect the current auth middleware source.
    if "middleware/auth.py" not in text:
        _fail("smoke does not reference the current auth source middleware/auth.py")

    # 3. Must check the real middleware symbol, and fail (not warn) when it is absent.
    if "create_api_key_middleware" not in text:
        _fail("smoke does not check for create_api_key_middleware")
    if 'fail "api_key middleware missing' not in text and "fail \"api_key middleware missing" not in text:
        _fail("smoke does not FAIL on missing api_key middleware")

    # 4. Guard fails on missing middleware SOURCE, not a stale filename.
    if 'fail "auth middleware source missing' not in text:
        _fail("smoke does not fail on missing auth middleware source")

    # 5. The canonical middleware really defines the symbol the smoke asserts.
    if "def create_api_key_middleware" not in AUTH_MW.read_text():
        _fail("middleware/auth.py no longer defines create_api_key_middleware — real regression")

    # 6. End-to-end: the smoke passes against the current tree (exit 0).
    result = subprocess.run(["bash", str(SMOKE)], capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        _fail(f"smoke exited {result.returncode} against current tree; stderr: {result.stderr}")

    print("PASS: auth-hardening smoke validates current middleware layout (not stale filename)")


if __name__ == "__main__":
    main()
