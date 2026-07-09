#!/usr/bin/env python3
"""Tests for the OpenAPI typed-client generator (WS6, god-tier prompt 9).

Run: python3 scripts/testing/test-api-client-gen.py
"""

import importlib.machinery
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
loader = importlib.machinery.SourceFileLoader("genclient", str(REPO / "scripts" / "ai" / "gen-api-client.py"))
G = importlib.util.module_from_spec(importlib.util.spec_from_loader("genclient", loader))
loader.exec_module(G)

_SPEC = {
    "openapi": "3.1.0",
    "paths": {
        "/api/scheduler/queue": {"get": {"summary": "Banded local-slot queue."}},
        "/api/trace/{trace_id}": {"get": {"summary": "Reconstructed span tree."}},
        "/api/loop/status": {"get": {}},
        "/health": {"get": {"summary": "not under /api — excluded"}},
        "/api/thing": {"post": {"summary": "post excluded"}},
    },
}


def test_generates_typed_methods():
    code = G.generate(_SPEC)
    assert "class AqDashboardClient" in code
    assert "def get_scheduler_queue(self)" in code
    assert "def get_trace_trace_id(self, trace_id: str)" in code, code
    assert "def get_loop_status(self)" in code
    print("PASS generates typed methods incl. path-param arg")


def test_excludes_non_api_and_non_get():
    code = G.generate(_SPEC)
    assert "health" not in code, "non-/api route must be excluded"
    assert "def post_" not in code and "thing" not in code, "non-GET must be excluded"
    print("PASS excludes non-/api and non-GET routes")


def test_generated_code_is_valid_python():
    import ast
    ast.parse(G.generate(_SPEC))
    print("PASS generated code parses as valid Python")


def test_method_name_derivation():
    assert G._method_name("/api/scheduler/queue", "get") == "get_scheduler_queue"
    assert G._method_name("/api/trace/{trace_id}", "get") == "get_trace_trace_id"
    assert G._path_params("/api/trace/{trace_id}") == ["trace_id"]
    print("PASS method-name + path-param derivation")


if __name__ == "__main__":
    test_generates_typed_methods()
    test_excludes_non_api_and_non_get()
    test_generated_code_is_valid_python()
    test_method_name_derivation()
    print("ALL PASS")
