#!/usr/bin/env python3
"""Regression tests for hybrid runtime auth/profile policy resolution."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HC_ROOT = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
AUTH_PATH = HC_ROOT / "middleware" / "auth.py"
sys.path.insert(0, str(HC_ROOT))

# middleware.auth only needs Config.API_KEY for middleware construction. Keep the
# unit test isolated from strict service env requirements in core.config.
config = types.ModuleType("config")
config.Config = type("Config", (), {"API_KEY": "secret"})
sys.modules["config"] = config

spec = importlib.util.spec_from_file_location("hybrid_auth", AUTH_PATH)
auth = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(auth)


def assert_context(path, remote, headers, api_key, mode, profile, status=0):
    ctx, code = auth.resolve_auth_context(path, remote, headers, api_key)
    assert code == status, (ctx, code)
    if status == 0:
        assert ctx["mode"] == mode, ctx
        assert ctx["profile"] == profile, ctx
    return ctx


def main() -> None:
    assert_context("/health", "203.0.113.10", {}, "secret", "public", "readonly-strict")
    assert_context("/query", "127.0.0.1", {}, "secret", "loopback-agent", "execute-guarded")
    assert_context(
        "/query",
        "127.0.0.1",
        {auth.AUTH_PROFILE_HEADER: "readonly-strict"},
        "secret",
        "loopback-agent",
        "readonly-strict",
    )
    assert_context(
        "/workflow/sessions",
        "203.0.113.10",
        {auth.API_KEY_HEADER: "secret", auth.AUTH_PROFILE_HEADER: "worktree-guarded"},
        "secret",
        "api-key",
        "worktree-guarded",
    )
    assert_context("/workflow/sessions", "203.0.113.10", {auth.API_KEY_HEADER: "wrong"}, "secret", "", "", status=401)
    bad, code = auth.resolve_auth_context(
        "/query",
        "127.0.0.1",
        {auth.AUTH_PROFILE_HEADER: "worktree-guarded"},
        "secret",
    )
    assert code == 403 and "not allowed" in bad.get("error", ""), (bad, code)
    summary = auth.auth_profile_policy_summary()
    assert summary["profile_header"] == auth.AUTH_PROFILE_HEADER
    assert summary["modes"]["api-key"]["default_profile"] == "execute-guarded"
    print("PASS: hybrid auth/profile policy resolution")


if __name__ == "__main__":
    main()
