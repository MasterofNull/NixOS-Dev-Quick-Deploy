#!/usr/bin/env python3
"""Static contract checks for extracted hybrid coordinator ops handlers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
OPS_HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "ops_handlers.py"


def assert_contains(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def main() -> int:
    http_server_source = HTTP_SERVER.read_text(encoding="utf-8")
    source = OPS_HANDLERS.read_text(encoding="utf-8")

    assert_contains(http_server_source, "import ops_handlers", "http_server should import ops_handlers")
    assert_contains(http_server_source, "ops_handlers.init(", "http_server should initialize ops_handlers")
    assert_contains(http_server_source, "ops_handlers.register_routes(http_app)", "http_server should register extracted ops routes")

    assert_contains(source, 'http_app.router.add_get("/health", handle_health)', "missing /health route")
    assert_contains(source, 'http_app.router.add_get("/health/detailed", handle_health_detailed)', "missing /health/detailed route")
    assert_contains(source, 'http_app.router.add_get("/alerts", handle_alerts_list)', "missing /alerts route")
    assert_contains(source, 'http_app.router.add_post("/feedback", handle_feedback)', "missing /feedback route")
    assert_contains(source, 'http_app.router.add_post("/cache/invalidate", handle_cache_invalidate)', "missing /cache/invalidate route")
    assert_contains(source, 'http_app.router.add_get("/learning/stats", handle_learning_stats)', "missing /learning/stats route")
    assert_contains(source, 'http_app.router.add_get("/model/status", handle_model_status)', "missing /model/status route")

    assert_contains(source, "async def handle_health(", "missing extracted health handler")
    assert_contains(source, "async def handle_feedback(", "missing extracted feedback handler")
    assert_contains(source, "async def handle_metrics(", "missing extracted metrics handler")
    assert_contains(source, "async def handle_alert_test_create(", "missing extracted alert test handler")

    print("PASS: hybrid coordinator ops handler extraction source contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
