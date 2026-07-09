#!/usr/bin/env python3
"""Validate the OSINT MCP wrapper without running live reconnaissance."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "ai-stack/mcp-servers/osint-tools/server.py"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    requests = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"},
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            "",
        ]
    )
    proc = subprocess.run(
        ["python3", str(SERVER)],
        input=requests,
        text=True,
        capture_output=True,
        timeout=5,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        fail(proc.stderr.strip() or f"osint server exited {proc.returncode}")

    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        fail(f"expected initialize and tools/list responses, got {len(lines)}")
    if lines[0]["result"]["serverInfo"]["name"] != "osint-tools":
        fail("initialize response must identify osint-tools")
    if lines[0]["result"].get("protocolVersion") != "2025-06-18":
        fail("initialize response must negotiate the client protocol version")

    tools = {tool["name"] for tool in lines[1]["result"]["tools"]}
    expected = {"maigret", "bbot", "mosaic"}
    if tools != expected:
        fail(f"unexpected OSINT tool set: {sorted(tools)}")

    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    roles = (ROOT / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
    services = (ROOT / "nix/modules/services/mcp-servers.nix").read_text(encoding="utf-8")
    if "pkgs.maigret" in roles or "pkgs.mosaic-osint" in roles:
        fail("system packages must not activate insecure Maigret/MOSAIC derivations")
    if "pkgs.maigret" in services or "pkgs.mosaic-osint" in services:
        fail("ai-osint-tools service PATH must not include insecure Maigret/MOSAIC derivations")
    if "do not permit insecure PyPDF2" not in flake:
        fail("osint dev shell must document the Maigret/MOSAIC hold")

    print("PASS: osint-tools MCP contract")


if __name__ == "__main__":
    main()
