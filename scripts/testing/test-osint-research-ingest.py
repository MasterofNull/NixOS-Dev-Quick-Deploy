#!/usr/bin/env python3
"""Validate passive OSINT research ingest without live web requests."""

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


async def _fake_workflow(**_kwargs):
    return {
        "status": "ok",
        "workflow": {"slug": "website-market-research", "inputs": {"topic": "demo"}},
        "results": [
            {
                "source_name": "official-source",
                "requested_url": "https://example.com/research",
                "selectors": ["main"],
                "status": "ok",
                "result": {
                    "title": "Example Research",
                    "text_excerpt": "Public evidence about audience, positioning, and visual references.",
                    "links": ["https://example.com/about"],
                },
            }
        ],
        "fetch": {"metrics": {"page_requests": 1}},
    }


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
    sys.modules["research_workflows"] = types.SimpleNamespace(run_curated_research_workflow=_fake_workflow)


def _assert_repo_manifest_has_website_design_workflow() -> None:
    manifest_path = ROOT / "config" / "curated-web-research-sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflows = {workflow.get("slug"): workflow for workflow in manifest.get("workflows", [])}
    workflow = workflows.get("website-design-research")
    assert workflow, "website-design-research workflow missing from curated source manifest"
    urls = {source.get("url", "") for source in workflow.get("sources", [])}
    assert "https://web.dev/learn/design/" in urls
    assert "https://www.w3.org/WAI/WCAG22/quickref/" in urls
    assert "https://www.nngroup.com/articles/" in urls


async def main() -> int:
    _assert_repo_manifest_has_website_design_workflow()
    _install_mcp_stubs()
    import extensions.mcp_handlers as mcp_handlers

    stored = []

    async def _fake_store_memory(**kwargs):
        stored.append(kwargs)
        return {"ok": True, "id": f"osint-{len(stored)}"}

    async def _fake_recall_memory(**_kwargs):
        return {
            "results": [
                {
                    "score": 0.91,
                    "summary": "OSINT website-market-research: Example Research",
                    "content": "Public evidence about audience, positioning, and visual references.",
                    "metadata": {
                        "namespace": "osint-intelligence",
                        "schema": "stix-2.1-lite",
                        "source_url": "https://example.com/research",
                        "source_name": "official-source",
                        "workflow": "website-market-research",
                        "fact_type": "public_web_extract",
                        "record": {
                            "title": "Example Research",
                            "content": "Public evidence about audience, positioning, and visual references.",
                            "source_url": "https://example.com/research",
                        },
                    },
                },
                {
                    "score": 0.88,
                    "summary": "Non OSINT",
                    "content": "Should be filtered",
                    "metadata": {"namespace": "other"},
                },
            ]
        }

    mcp_handlers._store_memory = _fake_store_memory
    mcp_handlers._recall_memory = _fake_recall_memory
    names = {tool.name for tool in mcp_handlers.TOOL_DEFINITIONS}
    assert "osint_research_ingest" in names, "MCP tool missing from coordinator surface"
    assert "osint_research_query" in names, "MCP query tool missing from coordinator surface"
    response = await mcp_handlers.dispatch_tool(
        "osint_research_ingest",
        {"workflow": "website-market-research", "inputs": {"topic": "demo"}},
    )
    assert len(response) == 1
    payload = json.loads(response[0].text)
    assert payload["namespace"] == "osint-intelligence"
    assert payload["schema"] == "stix-2.1-lite"
    assert payload["ledger_count"] == 1
    record = payload["ledger_records"][0]
    assert record["type"] == "observed-data"
    assert record["source_url"] == "https://example.com/research"
    assert record["fact_type"] == "public_web_extract"
    assert "Public evidence" in record["content"]
    assert payload["persisted_count"] == 0

    persisted_response = await mcp_handlers.dispatch_tool(
        "osint_research_ingest",
        {"workflow": "website-market-research", "inputs": {"topic": "demo"}, "persist": True},
    )
    persisted_payload = json.loads(persisted_response[0].text)
    assert persisted_payload["persisted_count"] == 1
    assert len(stored) == 1
    assert stored[0]["memory_type"] == "semantic"
    assert stored[0]["metadata"]["namespace"] == "osint-intelligence"
    assert stored[0]["metadata"]["schema"] == "stix-2.1-lite"

    query_response = await mcp_handlers.dispatch_tool(
        "osint_research_query",
        {"query": "audience positioning", "limit": 5},
    )
    query_payload = json.loads(query_response[0].text)
    assert query_payload["namespace"] == "osint-intelligence"
    assert query_payload["count"] == 1
    assert query_payload["evidence"][0]["source_url"] == "https://example.com/research"

    print("PASS: passive OSINT research ingest/query emits bounded osint-intelligence ledger records")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
