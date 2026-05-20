#!/usr/bin/env python3
"""Static contract checks for MAEAH AM-C1/AM-C2 API surface."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAI_A2A = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "openai_a2a_handlers.py"
DASH_MAIN = ROOT / "dashboard" / "backend" / "api" / "main.py"
MODEL_ROUTES = ROOT / "dashboard" / "backend" / "api" / "routes" / "models.py"
COMBINED_PRD = ROOT / ".agents" / "plans" / "multi-agent-edge-harness" / "COMBINED-PRD.md"


def require(source: str, needle: str, message: str) -> None:
    if needle not in source:
        raise AssertionError(message)


def require_route_auth(routes: str, decorator: str, function_name: str) -> None:
    pattern = rf"@router\.{decorator}\([^\n]+\)\nasync def {function_name}\([^)]*\):(?P<body>.*?)(?=\n@router\.|\ndef _stub_catalog|\Z)"
    match = re.search(pattern, routes, flags=re.S)
    if not match:
        raise AssertionError(f"missing route function for {decorator} {function_name}")
    body = match.group("body")
    if "_check_auth(request)" not in body:
        raise AssertionError(f"{function_name} must call _check_auth(request)")


def main() -> int:
    openai = OPENAI_A2A.read_text(encoding="utf-8")
    dash = DASH_MAIN.read_text(encoding="utf-8")
    routes = MODEL_ROUTES.read_text(encoding="utf-8")
    prd = COMBINED_PRD.read_text(encoding="utf-8")

    require(openai, 'async def handle_openai_responses', "missing /v1/responses handler")
    require(openai, 'http_app.router.add_post("/v1/responses", handle_openai_responses)', "missing /v1/responses route")
    require(openai, '"X-OpenAI-Responses-Compat"', "responses shim should advertise compatibility boundary")
    require(openai, 'path="chat/completions"', "responses shim should route through chat/completions until native support exists")

    require(dash, 'prefix="/admin/v1"', "dashboard must expose canonical /admin/v1 model lifecycle aliases")
    require(dash, 'prefix="/api"', "dashboard must preserve /api compatibility aliases")
    require(routes, 'str(request.url.path).startswith("/admin/v1/")', "admin route detection missing")
    require(routes, 'request.method.upper() not in {"GET", "HEAD", "OPTIONS"}', "mutating admin auth boundary missing")
    require(routes, 'X-Dashboard-Internal', "admin lifecycle auth should allow explicit dashboard-internal header")
    require(routes, 'admin lifecycle operation requires API key', "admin mutating routes must reject loopback-only access")

    for decorator, function_name in (
        ("post", "start_download"),
        ("post", "promote_model"),
        ("post", "rollback_model"),
        ("post", "cancel_download"),
        ("post", "reset_failed_model"),
        ("post", "add_model"),
        ("delete", "delete_model"),
    ):
        require_route_auth(routes, decorator, function_name)

    require(routes, '@router.post("/models")', "missing user-defined model add route")
    require(routes, '@router.delete("/models/{model_id}")', "missing user-defined model delete route")

    require(prd, 'POST /v1/responses', "PRD must document /v1/responses")
    require(prd, '/admin/v1/models', "PRD must document /admin/v1 model lifecycle")

    print("PASS: MAEAH API surface contract is normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
