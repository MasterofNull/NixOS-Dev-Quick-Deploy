"""Phase 68 checks — ReAct DAG backtracking (68.1) + MCP JSON-RPC 2.0 (68.2-68.5).

68.1.a  classify_error() correctly identifies retryable vs fatal errors
68.1.b  _prune_descendant_nodes() finds all descendants in a test DAG
68.1.c  backtrack_to() resets pending and prunes completed in-memory (mock PG)
68.1.d  BacktrackDepthExceeded raised when ceiling is reached
68.2    POST /mcp/v2 JSON-RPC 2.0 adapter responds with valid envelope
68.3    GET /mcp/v2/tools returns tool list with name/description/inputSchema
68.4    Dashboard workflow replay panel endpoint returns sessions array
68.5    Dashboard MCP status panel counts tools >= 1
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[4]  # repo root
_COORD = _REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator"


def _import_checkpointer():
    """Import WorkflowCheckpointer, adding coordinator to sys.path if needed."""
    if str(_COORD) not in sys.path:
        sys.path.insert(0, str(_COORD))
    from workflow.workflow_checkpointer import (  # type: ignore
        WorkflowCheckpointer,
        BacktrackDepthExceeded,
    )
    return WorkflowCheckpointer, BacktrackDepthExceeded


# Minimal async mock Postgres client
class _MockPG:
    def __init__(self):
        self._rows: list[dict] = []
        self._executed: list[str] = []

    async def execute(self, sql: str, *args) -> None:
        self._executed.append(sql.strip()[:40])

    async def fetch_all(self, sql: str, *args) -> list[dict]:
        if "workflow_backtrack_log" in sql and "COUNT" in sql:
            return [{"cnt": self._backtrack_count}]
        return []

    # set count externally for depth tests
    _backtrack_count: int = 0


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Phase 68.1 — Backtracking unit tests (pure Python, no services required)
# ---------------------------------------------------------------------------

def _check_68_1_a() -> CheckResult:
    """classify_error() returns correct classification."""
    try:
        WC, _ = _import_checkpointer()
    except Exception as exc:
        return skipped(1, "68.1.a", "classify_error: import failed", str(exc), phase="68")

    retryable_cases = [
        "connection refused",
        "timeout waiting for response",
        "rate limit exceeded",
        "HTTP 429 Too Many Requests",
        "503 Service Unavailable",
        "temporary backoff",
    ]
    fatal_cases = [
        "SyntaxError: invalid JSON",
        "KeyError: 'output'",
        "AssertionError: expected list",
        "ValueError: unknown action type",
    ]

    for case in retryable_cases:
        if WC.classify_error(case) != "retryable":
            return failed(1, "68.1.a", "classify_error", f"expected retryable for: {case!r}", phase="68")
    for case in fatal_cases:
        if WC.classify_error(case) != "fatal":
            return failed(1, "68.1.a", "classify_error", f"expected fatal for: {case!r}", phase="68")

    return passed(1, "68.1.a", "classify_error identifies retryable/fatal correctly", phase="68")


def _check_68_1_b() -> CheckResult:
    """_prune_descendant_nodes() finds full descendant set via BFS."""
    try:
        WC, _ = _import_checkpointer()
    except Exception as exc:
        return skipped(1, "68.1.b", "_prune_descendant_nodes: import failed", str(exc), phase="68")

    # DAG:  A → B → D
    #           ↘ E
    #       A → C → F
    graph = {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": [],
        "E": [],
        "F": [],
    }
    pruned = WC._prune_descendant_nodes("A", graph)
    expected = {"B", "C", "D", "E", "F"}
    if pruned != expected:
        return failed(
            1, "68.1.b", "_prune_descendant_nodes",
            f"got {sorted(pruned)} expected {sorted(expected)}", phase="68",
        )

    # Backtrack to B — only B's descendants are pruned (not C/F)
    pruned_b = WC._prune_descendant_nodes("B", graph)
    expected_b = {"D", "E"}
    if pruned_b != expected_b:
        return failed(
            1, "68.1.b", "_prune_descendant_nodes",
            f"from B: got {sorted(pruned_b)} expected {sorted(expected_b)}", phase="68",
        )

    return passed(1, "68.1.b", "_prune_descendant_nodes BFS prunes correct descendants", phase="68")


def _check_68_1_c() -> CheckResult:
    """backtrack_to() updates checkpoint state and returns new_pending."""
    try:
        WC, _ = _import_checkpointer()
    except Exception as exc:
        return skipped(1, "68.1.c", "backtrack_to: import failed", str(exc), phase="68")

    pg = _MockPG()
    pg._backtrack_count = 0
    cp = WC(pg, redis_client=None, max_backtrack_depth=3)

    # Simulate: A and B completed, B had children C and D (fatal failure)
    # Backtrack to B → C and D should be pruned, B back in pending
    graph = {"A": ["B"], "B": ["C", "D"], "C": [], "D": []}
    completed = ["A", "B"]
    outputs = {"A": "ok", "B": "ok", "C": "partial"}
    pending = ["C", "D"]

    async def _run():
        cp._schema_ready = True  # skip DDL
        return await cp.backtrack_to(
            "wf-test", "B", completed, outputs, pending, graph
        )

    result = _run_async(_run())

    if "B" not in result["new_pending"]:
        return failed(1, "68.1.c", "backtrack_to", "parent_node_id not in new_pending", phase="68")
    if result["new_pending"][0] != "B":
        return failed(1, "68.1.c", "backtrack_to", "parent_node_id not at head of new_pending", phase="68")
    if set(result["pruned_nodes"]) != {"C", "D"}:
        return failed(
            1, "68.1.c", "backtrack_to",
            f"pruned_nodes={result['pruned_nodes']} expected C,D", phase="68",
        )
    if result["backtrack_depth"] != 1:
        return failed(1, "68.1.c", "backtrack_to", f"depth={result['backtrack_depth']} expected 1", phase="68")

    return passed(1, "68.1.c", "backtrack_to resets checkpoint and prunes descendants", phase="68")


def _check_68_1_d() -> CheckResult:
    """BacktrackDepthExceeded raised when ceiling reached."""
    try:
        WC, BacktrackDepthExceeded = _import_checkpointer()
    except Exception as exc:
        return skipped(1, "68.1.d", "BacktrackDepthExceeded: import failed", str(exc), phase="68")

    pg = _MockPG()
    pg._backtrack_count = 3  # already at ceiling
    cp = WC(pg, redis_client=None, max_backtrack_depth=3)

    async def _run():
        cp._schema_ready = True
        return await cp.backtrack_to("wf-ceil", "X", [], {}, [], {})

    try:
        _run_async(_run())
        return failed(1, "68.1.d", "BacktrackDepthExceeded", "no exception raised at ceiling", phase="68")
    except BacktrackDepthExceeded:
        return passed(1, "68.1.d", "BacktrackDepthExceeded raised at ceiling", phase="68")
    except Exception as exc:
        return failed(1, "68.1.d", "BacktrackDepthExceeded", f"wrong exception: {exc}", phase="68")


# ---------------------------------------------------------------------------
# Phase 68.2-68.5 — Live service checks (skip gracefully if coordinator down)
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 10, api_key: str = "") -> tuple[int, Any]:
    import urllib.request
    import urllib.error
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = str(exc)
        return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def _http_post(url: str, body: dict, timeout: int = 10, api_key: str = "") -> tuple[int, Any]:
    import urllib.request
    import urllib.error
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = str(exc)
        return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def _check_68_2(ctx: RunContext) -> CheckResult:
    """POST /mcp/v2 returns valid JSON-RPC 2.0 envelope."""
    url = f"{ctx.hybrid_url}/mcp/v2"
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    status, body = _http_post(url, payload, timeout=15, api_key=ctx.api_key)
    if status == 0:
        return skipped(2, "68.2", "MCP JSON-RPC 2.0 adapter", "coordinator unreachable", phase="68")
    if status not in (200, 201):
        return failed(2, "68.2", "MCP JSON-RPC 2.0 adapter", f"HTTP {status}: {body}", phase="68")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return failed(2, "68.2", "MCP JSON-RPC 2.0 adapter", "response missing jsonrpc:2.0", phase="68")
    if "result" not in body and "error" not in body:
        return failed(2, "68.2", "MCP JSON-RPC 2.0 adapter", "response has neither result nor error", phase="68")
    return passed(2, "68.2", "MCP JSON-RPC 2.0 adapter returns valid envelope", phase="68")


def _check_68_3(ctx: RunContext) -> CheckResult:
    """GET /mcp/v2/tools returns list with name/description/inputSchema."""
    url = f"{ctx.hybrid_url}/mcp/v2/tools"
    status, body = _http_get(url, timeout=15, api_key=ctx.api_key)
    if status == 0:
        return skipped(2, "68.3", "MCP tools manifest", "coordinator unreachable", phase="68")
    if status != 200:
        return failed(2, "68.3", "MCP tools manifest", f"HTTP {status}: {body}", phase="68")
    # Response may be a bare list, a {"tools":[...]} dict,
    # or a JSON-RPC 2.0 envelope {"jsonrpc":"2.0","result":{"tools":[...]}}
    if isinstance(body, list):
        tools = body
    elif isinstance(body, dict):
        result = body.get("result", body)
        tools = result.get("tools", []) if isinstance(result, dict) else []
    else:
        tools = []
    if not tools:
        return failed(2, "68.3", "MCP tools manifest", "empty tool list", phase="68")
    first = tools[0]
    for field in ("name", "description", "inputSchema"):
        if field not in first:
            return failed(2, "68.3", "MCP tools manifest", f"missing field: {field}", phase="68")
    return passed(2, "68.3", f"MCP tools manifest: {len(tools)} tools with required fields", phase="68")


def _check_68_4(ctx: RunContext) -> CheckResult:
    """Dashboard workflow replay panel: /aistack/orchestration/sessions returns array."""
    import os
    _dash = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8889")
    url = f"{_dash}/api/aistack/orchestration/sessions?limit=20"
    status, body = _http_get(url, timeout=15)
    if status == 0:
        return skipped(3, "68.4", "Dashboard workflow replay panel", "dashboard unreachable", phase="68")
    if status != 200:
        return failed(3, "68.4", "Dashboard workflow replay panel", f"HTTP {status}", phase="68")
    sessions = body if isinstance(body, list) else body.get("sessions", body.get("data", []))
    if not isinstance(sessions, list):
        return failed(3, "68.4", "Dashboard workflow replay panel", "response is not a list", phase="68")
    return passed(3, "68.4", f"Workflow replay panel: {len(sessions)} sessions returned", phase="68")


def _check_68_5(ctx: RunContext) -> CheckResult:
    """Dashboard MCP status panel: /aistack/mcp/v2/tools returns >= 1 tools."""
    import os
    _dash = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8889")
    url = f"{_dash}/api/aistack/mcp/v2/tools"
    status, body = _http_get(url, timeout=15)
    if status == 0:
        return skipped(3, "68.5", "Dashboard MCP status panel", "dashboard unreachable", phase="68")
    if status != 200:
        return failed(3, "68.5", "Dashboard MCP status panel", f"HTTP {status}", phase="68")
    if isinstance(body, list):
        tools = body
    elif isinstance(body, dict):
        result = body.get("result", body)
        tools = result.get("tools", []) if isinstance(result, dict) else []
    else:
        tools = []
    count = len(tools)
    if count < 1:
        return failed(3, "68.5", "Dashboard MCP status panel", f"tool count={count} expected >=1", phase="68")
    return passed(3, "68.5", f"MCP status panel: {count} tools", phase="68")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_68_1_a(),
        _check_68_1_b(),
        _check_68_1_c(),
        _check_68_1_d(),
        _check_68_2(ctx),
        _check_68_3(ctx),
        _check_68_4(ctx),
        _check_68_5(ctx),
    ]
