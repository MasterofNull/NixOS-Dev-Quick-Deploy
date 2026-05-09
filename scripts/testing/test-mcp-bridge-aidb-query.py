#!/usr/bin/env python3
"""Regression checks for MCP bridge AIDB query fallback behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "scripts" / "ai" / "mcp-bridge-hybrid.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_bridge():
    spec = importlib.util.spec_from_file_location("mcp_bridge_hybrid", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert_true(spec is not None and spec.loader is not None, "expected import spec for mcp bridge")
    spec.loader.exec_module(module)
    return module


def main() -> int:
    bridge = _load_bridge()
    post_calls = []
    get_calls = []

    def fake_post(url: str, payload: dict, key: str, timeout: int = 30):
        post_calls.append((url, payload, timeout))
        return {"error": "Not Found", "status": 404}

    def fake_get(url: str, key: str, timeout: int = 10):
        get_calls.append((url, timeout))
        return {
            "documents": [
                {
                    "title": "Operational Perspective",
                    "project": "NixOS-Dev-Quick-Deploy",
                    "relative_path": "docs/example.md",
                    "content": "context",
                    "content_type": "text/markdown",
                    "status": "approved",
                    "imported_at": "2026-05-09T00:00:00+00:00",
                }
            ]
        }

    bridge._post = fake_post
    bridge._get = fake_get

    result = bridge._query_aidb_knowledge(
        "agent operational perspective",
        limit=3,
        project="NixOS-Dev-Quick-Deploy",
        timeout=15,
    )

    assert_true(post_calls and post_calls[0][0].endswith("/query"), "expected legacy /query attempt first")
    assert_true(get_calls and "/documents?" in get_calls[0][0], "expected documents search fallback URL")
    assert_true("search=agent+operational+perspective" in get_calls[0][0], "expected query encoded into documents search")
    assert_true("project=NixOS-Dev-Quick-Deploy" in get_calls[0][0], "expected project filter in documents search")
    assert_true(result.get("source") == "documents_search_fallback", "expected fallback source marker")
    assert_true(len(result.get("results") or []) == 1, "expected normalized documents result list")

    print("PASS: mcp bridge falls back to AIDB documents search when /query is unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
