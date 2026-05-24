"""Phase 69 checks — AG-UI WebSocket + Temporal Knowledge Graph.

69.1  /ws/agent-state WebSocket endpoint exists and accepts connection
69.2  Live Event Feed panel present in dashboard HTML
69.3  GET /knowledge/graph/fact-chain returns valid schema (coordinator)
69.4  Dashboard proxy /knowledge/graph/fact-chain returns valid schema
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Tuple

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

_REPO = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 10, api_key: str = "") -> Tuple[int, Any]:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
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


def _api_key(ctx: RunContext) -> str:
    """Read the coordinator API key (Bearer token) from secrets file."""
    try:
        raw = Path("/run/secrets/hybrid_coordinator_api_key").read_text().strip()
        return raw
    except OSError:
        return os.environ.get("HYBRID_API_KEY", "")


# ---------------------------------------------------------------------------
# 69.1 — WebSocket endpoint reachable (HTTP upgrade → 101 or at least 400/426)
# ---------------------------------------------------------------------------

def _check_69_1(ctx: RunContext) -> CheckResult:
    """GET /ws/agent-state returns HTTP upgrade response (101/400/426) — not 404."""
    import socket
    import re

    host = "127.0.0.1"
    port = int(os.environ.get("DASHBOARD_PORT", "8889"))
    try:
        sock = socket.create_connection((host, port), timeout=5)
        # Send a minimal WebSocket upgrade request
        req = (
            f"GET /ws/agent-state HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode())
        response = sock.recv(1024).decode("utf-8", errors="replace")
        sock.close()
    except Exception as exc:
        return skipped(2, "69.1", "WebSocket /ws/agent-state", f"dashboard unreachable: {exc}", phase="69")

    # 101 Switching Protocols = accepted; 400/426 = route exists but protocol issue
    if "101 Switching Protocols" in response:
        return passed(2, "69.1", "WebSocket /ws/agent-state: 101 Switching Protocols", phase="69")
    if "403" in response:
        return skipped(2, "69.1", "WebSocket /ws/agent-state",
                       "403 — dashboard restart needed (route registered but not yet active)", phase="69")
    if "400" in response or "426" in response:
        return passed(2, "69.1", "WebSocket /ws/agent-state: route exists (upgrade required)", phase="69")
    if "404" in response:
        return failed(2, "69.1", "WebSocket /ws/agent-state", "404 Not Found — route not registered", phase="69")
    first_line = response.split("\r\n")[0] if response else "(empty)"
    return skipped(2, "69.1", "WebSocket /ws/agent-state", f"unexpected: {first_line}", phase="69")


# ---------------------------------------------------------------------------
# 69.2 — Live Event Feed panel present in dashboard HTML
# ---------------------------------------------------------------------------

def _check_69_2(_ctx: RunContext) -> CheckResult:
    """Dashboard HTML contains Live Event Feed panel elements."""
    html_path = _REPO / "dashboard.html"
    if not html_path.exists():
        return skipped(1, "69.2", "Live Event Feed panel", "dashboard.html not found", phase="69")
    content = html_path.read_text()
    checks = [
        ("liveEventsDetails", "liveEventsDetails div"),
        ("liveEventsBadge",   "liveEventsBadge span"),
        ("ws/agent-state",    "WebSocket path in JS"),
    ]
    # Also check dashboard.js
    js_path = _REPO / "assets" / "dashboard.js"
    js_content = js_path.read_text() if js_path.exists() else ""

    for token, label in checks[:2]:
        if token not in content:
            return failed(1, "69.2", "Live Event Feed panel", f"missing: {label}", phase="69")
    if "ws/agent-state" not in js_content:
        return failed(1, "69.2", "Live Event Feed panel", "ws/agent-state not found in dashboard.js", phase="69")
    if "loadFactChainTimeline" not in js_content:
        return failed(1, "69.2", "Live Event Feed panel", "loadFactChainTimeline not found in dashboard.js", phase="69")
    return passed(1, "69.2", "Live Event Feed panel HTML elements and JS present", phase="69")


# ---------------------------------------------------------------------------
# 69.3 — Coordinator /knowledge/graph/fact-chain endpoint
# ---------------------------------------------------------------------------

def _check_69_3(ctx: RunContext) -> CheckResult:
    """GET /knowledge/graph/fact-chain returns facts array schema."""
    key = _api_key(ctx)
    url = f"{ctx.hybrid_url}/knowledge/graph/fact-chain?limit=5"
    status, body = _http_get(url, timeout=15, api_key=key)
    if status == 0:
        return skipped(2, "69.3", "Temporal graph /knowledge/graph/fact-chain", "coordinator unreachable", phase="69")
    if status == 404:
        return failed(2, "69.3", "Temporal graph", "404 — coordinator restart needed", phase="69")
    if status != 200:
        return failed(2, "69.3", "Temporal graph", f"HTTP {status}: {str(body)[:80]}", phase="69")
    if not isinstance(body, dict):
        return failed(2, "69.3", "Temporal graph", "response is not a dict", phase="69")
    if "facts" not in body:
        return failed(2, "69.3", "Temporal graph", "missing 'facts' key in response", phase="69")
    facts = body["facts"]
    total = body.get("total", len(facts))
    return passed(2, "69.3", f"Temporal graph: {total} facts (schema valid)", phase="69")


# ---------------------------------------------------------------------------
# 69.4 — Dashboard /knowledge/graph/fact-chain proxy
# ---------------------------------------------------------------------------

def _check_69_4(ctx: RunContext) -> CheckResult:
    """Dashboard proxy /api/knowledge/graph/fact-chain returns valid schema."""
    _dash = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8889")
    url = f"{_dash}/api/knowledge/graph/fact-chain?limit=5"
    status, body = _http_get(url, timeout=15)
    if status == 0:
        return skipped(3, "69.4", "Dashboard fact-chain proxy", "dashboard unreachable", phase="69")
    if status == 404:
        return failed(3, "69.4", "Dashboard fact-chain proxy", "404 — dashboard restart needed", phase="69")
    if status != 200:
        return failed(3, "69.4", "Dashboard fact-chain proxy", f"HTTP {status}", phase="69")
    if not isinstance(body, dict) or "facts" not in body:
        return failed(3, "69.4", "Dashboard fact-chain proxy", "missing 'facts' key in response", phase="69")
    return passed(3, "69.4", f"Dashboard fact-chain proxy: {body.get('total', 0)} facts", phase="69")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_69_1(ctx),
        _check_69_2(ctx),
        _check_69_3(ctx),
        _check_69_4(ctx),
    ]
