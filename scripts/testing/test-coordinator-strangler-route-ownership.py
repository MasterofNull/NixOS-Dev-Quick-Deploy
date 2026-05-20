#!/usr/bin/env python3
"""Static contract checks for hybrid-coordinator R2 Strangler Fig route ownership.

This deliberately avoids importing router.py: the extracted services still depend on
runtime-only PYTHONPATH wiring while the refactor is in progress. The contract we
need before deployment is narrower and stricter: moved routes must have exactly one
active owner, and http_server.py must configure closure-backed services before
calling router.create_app().
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"

HTTP_SERVER = HC / "http_server.py"
ROUTER = HC / "router.py"
STATUS_SERVICE = HC / "core" / "status_service.py"
MEMORY_SERVICE = HC / "memory" / "memory_service.py"
QUERY_SERVICE = HC / "query" / "query_service.py"
ORCH_SERVICE = HC / "workflow" / "orchestration_service.py"

MOVED_ROUTES = {
    # R2.2 StatusService
    "/status": STATUS_SERVICE,
    "/api/hardware/state": STATUS_SERVICE,
    "/stats/delegate": STATUS_SERVICE,
    # R2.3 MemoryService
    "/api/memory/facts": MEMORY_SERVICE,
    "/memory/journal": MEMORY_SERVICE,
    "/memory/journal/stats": MEMORY_SERVICE,
    # R2.4 QueryService
    "/query": QUERY_SERVICE,
    "/api/query": QUERY_SERVICE,
    "/augment_query": QUERY_SERVICE,
    # R2.5 OrchestrationService
    "/v1/orchestrate": ORCH_SERVICE,
    "/search/tree": ORCH_SERVICE,
}

ROUTER_REGISTRATIONS = [
    "_register_status_routes(app)",
    "_register_memory_routes(app)",
    "_register_query_routes(app)",
    "_register_orchestration_routes(app)",
]

CONFIGURE_BEFORE_CREATE_APP = [
    ("_orchestration_service.configure", "_create_router_app"),
    ("_query_service.configure", "_create_router_app"),
]


def active_routes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = getattr(func, "attr", "")
        if not attr.startswith("add_"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        route = node.args[0].value
        if isinstance(route, str) and route.startswith("/"):
            routes.append(route)
    return routes


def assert_contains_all(text: str, snippets: Iterable[str], path: Path) -> None:
    for snippet in snippets:
        if snippet not in text:
            raise AssertionError(f"{path}: missing snippet {snippet!r}")


def main() -> int:
    http_routes = set(active_routes(HTTP_SERVER))
    for route, owner in MOVED_ROUTES.items():
        owner_routes = active_routes(owner)
        if route not in owner_routes:
            raise AssertionError(f"{owner}: missing active registration for {route}")
        if route in http_routes:
            raise AssertionError(f"{HTTP_SERVER}: still actively registers moved route {route}")

    router_text = ROUTER.read_text(encoding="utf-8")
    assert_contains_all(router_text, ROUTER_REGISTRATIONS, ROUTER)

    http_text = HTTP_SERVER.read_text(encoding="utf-8")
    for before, after in CONFIGURE_BEFORE_CREATE_APP:
        before_idx = http_text.find(before)
        after_idx = http_text.find(after)
        if before_idx == -1 or after_idx == -1:
            raise AssertionError(f"{HTTP_SERVER}: missing configure/create_app marker {before!r} or {after!r}")
        if before_idx > after_idx:
            raise AssertionError(f"{HTTP_SERVER}: {before} must occur before {after}")

    print("PASS: coordinator Strangler Fig route ownership is coherent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
