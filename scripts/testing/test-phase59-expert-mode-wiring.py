#!/usr/bin/env python3
"""Guard Phase 59.4 expert-mode integration from import/runtime regressions."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def imports_name(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == module_name for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            return True
    return False


def main() -> None:
    route_handler = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py"
    trace_collector = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/trace_collector.py"
    search_router = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py"
    env_contract = ROOT / "config/env-contract.yaml"

    if "_read_secret_file" not in route_handler.read_text(encoding="utf-8"):
        fail("route_handler must include the AIDB history secret reader")
    if not imports_name(route_handler, "pathlib"):
        fail("route_handler _read_secret_file requires pathlib.Path import")

    trace_text = trace_collector.read_text(encoding="utf-8")
    top_import_block = trace_text.split("logger = logging.getLogger", 1)[0]
    if "import psutil" in top_import_block:
        fail("trace_collector must not require psutil at module import time")
    if "gen_ai.maeah.hardware.cpu_percent" not in trace_text:
        fail("trace_collector hardware metrics must remain visible in trace attrs")

    search_text = search_router.read_text(encoding="utf-8")
    if "async def sql_search" not in search_text or '"sql_results"' not in search_text:
        fail("SearchRouter must expose SQL recall results for expert-mode self-healing")

    contract_text = env_contract.read_text(encoding="utf-8")
    if "AIDB_TOOL_SCHEMA_CACHE" not in contract_text:
        fail("AIDB_TOOL_SCHEMA_CACHE must be documented in env-contract.yaml")

    print("PASS: phase59 expert-mode wiring")


if __name__ == "__main__":
    main()
