#!/usr/bin/env python3
"""
OSINT Tools MCP Server

Provides automated reconnaissance capabilities aligned with the OSINT-Systems PRD.
Implements the 'Core Trinity' (BBOT, Maigret, MOSAIC) via async subprocesses,
returning structural truth to the Verbatim Fact Ledger.
"""

import sys
import json
import asyncio
import shutil
from typing import Dict, Any

TOOL_TIMEOUT_SECONDS = 30


async def run_tool(command: list[str], tool: str, target: str) -> Dict[str, Any]:
    """Run a local OSINT command with bounded output and timeout."""
    executable = command[0]
    if shutil.which(executable) is None:
        return {
            "tool": tool,
            "target": target,
            "status": "unavailable",
            "error": f"{executable} is not installed in PATH",
        }

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return {
            "tool": tool,
            "target": target,
            "status": "timeout",
            "error": f"tool exceeded {TOOL_TIMEOUT_SECONDS}s timeout",
        }

    if process.returncode != 0:
        return {
            "tool": tool,
            "target": target,
            "status": "failed",
            "error": stderr.decode(errors="replace").strip()[:2000],
        }

    return {
        "tool": tool,
        "target": target,
        "status": "success",
        "raw_output": stdout.decode(errors="replace")[:2000],
    }


async def run_maigret(username: str) -> Dict[str, Any]:
    """Run Maigret for username enumeration."""
    if not username:
        return {"tool": "maigret", "status": "failed", "error": "username is required"}
    if shutil.which("maigret"):
        return await run_tool(["maigret", username, "--json", "report", "--timeout", "30"], "maigret", username)
    # Maigret is currently blocked by an insecure PyPDF2 dependency in nixpkgs.
    # Fall back to Sherlock for the same identity-enumeration class.
    result = await run_tool(["sherlock", username, "--print-found", "--no-color"], "sherlock", username)
    result["requested_tool"] = "maigret"
    result["degraded"] = result.get("status") == "success"
    result["degradation_reason"] = "maigret unavailable; used sherlock fallback"
    return result

async def run_bbot(target: str) -> Dict[str, Any]:
    """Run BBOT for recursive infrastructure mapping."""
    # BBOT is still being provisioned in the Nix overlay
    return {
        "tool": "bbot",
        "target": target,
        "status": "provisioning",
        "note": "BBOT derivation is pending. Use maigret or mosaic for now."
    }

async def run_mosaic(selector: str) -> Dict[str, Any]:
    """Run MOSAIC for behavioral analysis."""
    if not selector:
        return {"tool": "mosaic", "status": "failed", "error": "selector is required"}
    return await run_tool(["mosaic-osint", "--target", selector], "mosaic", selector)

def build_response(call_id: str, result: Dict[str, Any]) -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": call_id,
        "result": result
    })

def build_error(call_id: str, code: int, message: str) -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": call_id,
        "error": {
            "code": code,
            "message": message
        }
    })

async def handle_request(line: str):
    try:
        req = json.loads(line)
        if req.get("method") == "initialize":
            protocol_version = req.get("params", {}).get("protocolVersion", "2024-11-05")
            print(build_response(req.get("id"), {
                "protocolVersion": protocol_version,
                "serverInfo": {"name": "osint-tools", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }), flush=True)
            return

        if req.get("method") == "tools/list":
            print(build_response(req.get("id"), {
                "tools": [
                    {
                        "name": "maigret",
                        "description": "Enumerate username across social platforms (Identity Pillar)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"username": {"type": "string"}},
                            "required": ["username"]
                        }
                    },
                    {
                        "name": "bbot",
                        "description": "Recursive infrastructure mapping (Infrastructure Pillar)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"target": {"type": "string"}},
                            "required": ["target"]
                        }
                    },
                    {
                        "name": "mosaic",
                        "description": "Behavioral analysis and hypothesis generation (AI-Native Pillar)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"selector": {"type": "string"}},
                            "required": ["selector"]
                        }
                    }
                ]
            }), flush=True)
            return

        if req.get("method") == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})

            if name == "maigret":
                res = await run_maigret(args.get("username", ""))
            elif name == "bbot":
                res = await run_bbot(args.get("target", ""))
            elif name == "mosaic":
                res = await run_mosaic(args.get("selector", ""))
            else:
                print(build_error(req.get("id"), -32601, "Method not found"), flush=True)
                return

            print(build_response(req.get("id"), {"content": [{"type": "text", "text": json.dumps(res)}]}), flush=True)
            return

    except Exception as e:
        pass # Ignore malformed json

async def main():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        await handle_request(line.decode('utf-8').strip())

if __name__ == "__main__":
    asyncio.run(main())
