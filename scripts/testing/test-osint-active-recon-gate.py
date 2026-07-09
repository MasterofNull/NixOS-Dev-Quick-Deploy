#!/usr/bin/env python3
"""Validate active OSINT recon stays policy-gated and machine-readable."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HC_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
LOCAL_AGENTS_DIR = ROOT / "ai-stack" / "local-agents"
for path in (HC_DIR, HC_DIR / "extensions", LOCAL_AGENTS_DIR, ROOT / "ai-stack" / "mcp-servers"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class _TextContent:
    def __init__(self, **kwargs):
        self.type = kwargs.get("type")
        self.text = kwargs.get("text")


class _Tool:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.inputSchema = kwargs.get("inputSchema")


def _install_mcp_stubs() -> None:
    mcp_types = types.SimpleNamespace(TextContent=_TextContent, Tool=_Tool)
    sys.modules.setdefault("mcp", types.SimpleNamespace(types=mcp_types))
    sys.modules.setdefault("mcp.types", mcp_types)
    sys.modules.setdefault("shared.tool_audit", types.SimpleNamespace(write_audit_entry=lambda *a, **k: None))
    sys.modules.setdefault(
        "shared.circuit_breaker",
        types.SimpleNamespace(
            CircuitBreakerRegistry=lambda *a, **k: {},
            CircuitBreakerOpenError=RuntimeError,
        ),
    )

    async def _retry(_call, fn, *args, **_kwargs):
        return await fn()

    sys.modules.setdefault("shared.retry_backoff", types.SimpleNamespace(retry_with_backoff=_retry))
    sys.modules.setdefault("tooling_manifest", types.SimpleNamespace(build_tooling_manifest=lambda: {}, workflow_tool_catalog=lambda: []))
    sys.modules.setdefault(
        "local_agents",
        types.SimpleNamespace(
            get_registry=lambda: types.SimpleNamespace(),
            initialize_builtin_tools=lambda _registry: None,
        ),
    )
    sys.modules.setdefault(
        "memory_manager",
        types.SimpleNamespace(
            coerce_memory_summary=lambda x: x,
            normalize_memory_type=lambda x: x,
            validate_memory_content=lambda summary, content: None,
        ),
    )


async def main() -> int:
    _install_mcp_stubs()
    import extensions.mcp_handlers as mcp_handlers
    from builtin_tools.ai_coordination import osint_recon_status_handler

    names = {tool.name for tool in mcp_handlers.TOOL_DEFINITIONS}
    assert "osint_recon_status" in names, "coordinator must expose osint_recon_status"
    assert "osint_recon" in names, "coordinator must keep gated osint_recon surface"
    assert "local_surface_scan" in names, "coordinator must expose bounded local surface scanner"

    status_response = await mcp_handlers.dispatch_tool("osint_recon_status", {"target": "exampleuser", "tool": "sherlock"})
    status_payload = json.loads(status_response[0].text)
    assert status_payload["status"] == "ok"
    assert status_payload["default_action"] == "deny"
    assert status_payload["selector_kind"] == "username"
    assert status_payload["runtimes"]["maigret"]["state"] == "blocked-insecure-package"
    assert status_payload["runtimes"]["bbot"]["state"] == "provisioning-only"
    assert "scope_ack=true" in status_payload["required_gates"]

    blocked_response = await mcp_handlers.dispatch_tool("osint_recon", {"target": "exampleuser", "tool": "maigret"})
    blocked_payload = json.loads(blocked_response[0].text)
    assert blocked_payload["status"] == "blocked"
    assert "maigret is held" in blocked_payload["reason"]
    assert blocked_payload["admission"]["safe_default_tools"] == ["osint_research_query", "osint_research_ingest"]

    no_scope_response = await mcp_handlers.dispatch_tool("osint_recon", {"target": "exampleuser", "tool": "sherlock"})
    no_scope_payload = json.loads(no_scope_response[0].text)
    assert no_scope_payload["status"] == "blocked"
    assert "scope_ack=true" in no_scope_payload["reason"]

    surface_response = await mcp_handlers.dispatch_tool(
        "local_surface_scan",
        {"urls": ["https://example.com/"], "timeout": 0.1},
    )
    surface_payload = json.loads(surface_response[0].text)
    assert surface_payload["policy"] == "authorized-local-private-http-only"
    assert surface_payload["exit_code"] == 2
    assert surface_payload["results"][0]["status"] == "refused"

    local_status = await osint_recon_status_handler(target="example.org", tool="bbot")
    assert local_status["success"] is True
    assert local_status["selector_kind"] == "domain"
    assert local_status["runtimes"]["mosaic"]["state"] == "blocked-insecure-package"

    print("PASS: active OSINT recon is fail-closed behind machine-readable admission gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
