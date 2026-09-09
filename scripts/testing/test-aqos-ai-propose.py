#!/usr/bin/env python3
"""Tests for the offline AI-proposal call (P2-b).

No real network call is ever made: `aqos_ai_propose._post_chat` is
monkeypatched with a fake in every case. This proves:

  1. The request actually attaches the json_schema constraint (+ nested
     chat_template_kwargs enable_thinking:false) and reads the endpoint from
     the LLAMA_URL env var (never a hardcoded value).
  2. Defense in depth (OWASP LLM01): even a mocked reply that simulates a
     bypassed schema constraint (an injection payload) is rejected by
     aqos_ai_proposal.validate_proposal() -- the constraint is never trusted
     alone.
  3. A clean mocked reply is accepted and normalized.
  4. An HTTP failure/timeout fails closed with reason "proposal_unavailable".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB_DIR = REPO / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import aqos_ai_propose as ai_propose  # noqa: E402

CATALOG_PATH = REPO / "config" / "aqos-module-catalog-v1.json"
MODULE_CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
SCHEMA_PATH = REPO / "config" / "schemas" / "aqos-ai-proposal-v1.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

HARDWARE_SUMMARY = {
    "summary_version": "aqos-hardware-summary/v1",
    "hardware_identity_sha256": "0" * 64,
    "evidence_status": "sufficient",
    "gpu_count": 1,
}

CLEAN_SELECTION = {
    "artifact_type": "ai_proposal",
    "schema_version": "aqos-install-plan/v1",
    "selection": {
        "golden_profile": "profile.gaming",
        "roles": ["role.gaming"],
        "include_local_ai": False,
    },
}

_failures: list[str] = []
_count = 0


def _reply_with(content) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _fake_post(captured: dict):
    """Return a _post_chat replacement that records (url, payload, timeout)
    into `captured` and returns whatever `captured['reply']` is set to."""

    def _post(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return captured["reply"]

    return _post


def _run(monkeypatch_env=None, monkeypatch_endpoint=None, reply=None, raises=None):
    """Call propose_selection with _post_chat monkeypatched; restore after."""
    original_post = ai_propose._post_chat
    original_environ = dict(__import__("os").environ)
    import os

    captured: dict = {"reply": reply}
    try:
        if monkeypatch_env:
            os.environ.update(monkeypatch_env)

        if raises is not None:
            def _post(url, payload, timeout):
                captured["url"] = url
                captured["payload"] = payload
                captured["timeout"] = timeout
                raise raises

            ai_propose._post_chat = _post
        else:
            ai_propose._post_chat = _fake_post(captured)

        result = ai_propose.propose_selection(
            HARDWARE_SUMMARY, MODULE_CATALOG, endpoint=monkeypatch_endpoint
        )
        return result, captured
    finally:
        ai_propose._post_chat = original_post
        os.environ.clear()
        os.environ.update(original_environ)


def check(name: str, cond: bool) -> None:
    global _count
    _count += 1
    if not cond:
        _failures.append(name)


# 1. Request attaches the json_schema constraint + enable_thinking:false
#    nested in chat_template_kwargs, and reads endpoint from LLAMA_URL.
result, captured = _run(
    monkeypatch_env={"LLAMA_URL": "http://127.0.0.1:19999"},
    reply=_reply_with(json.dumps(CLEAN_SELECTION)),
)
check("reads endpoint from LLAMA_URL env var", captured["url"] == "http://127.0.0.1:19999/v1/chat/completions")
payload = captured["payload"]
check("payload attaches response_format json_schema", payload.get("response_format", {}).get("type") == "json_schema")
check(
    "payload's json_schema.schema matches the closed proposal schema",
    payload["response_format"]["json_schema"]["schema"] == SCHEMA,
)
check(
    "payload nests enable_thinking:false in chat_template_kwargs (not top-level)",
    payload.get("chat_template_kwargs", {}).get("enable_thinking") is False,
)
check("payload does not set a top-level enable_thinking (silently ignored)", "enable_thinking" not in payload)
check("clean reply -> ok True", result.get("ok") is True)
check(
    "clean reply -> normalized selection",
    result.get("selection") == {
        "golden_profile": "profile.gaming",
        "roles": ["role.gaming"],
        "include_local_ai": False,
    },
)

# 2. explicit endpoint kwarg overrides env var (still never hardcoded).
result2, captured2 = _run(
    monkeypatch_env={"LLAMA_URL": "http://127.0.0.1:19999"},
    monkeypatch_endpoint="http://127.0.0.1:8080",
    reply=_reply_with(json.dumps(CLEAN_SELECTION)),
)
check(
    "explicit endpoint kwarg wins over env var",
    captured2["url"] == "http://127.0.0.1:8080/v1/chat/completions",
)

# 3. Default endpoint (no env, no kwarg) falls back to the documented
#    127.0.0.1:8080 default -- exercised via env var absence.
import os as _os  # noqa: E402

_os.environ.pop("LLAMA_URL", None)
result3, captured3 = _run(reply=_reply_with(json.dumps(CLEAN_SELECTION)))
check(
    "default endpoint falls back to 127.0.0.1:8080",
    captured3["url"] == "http://127.0.0.1:8080/v1/chat/completions",
)

# 4. DEFENSE IN DEPTH: a mocked reply simulating a bypassed json_schema
#    constraint -- a non-catalog value carrying shell metacharacters --
#    must still be rejected by validate_proposal(). Proves the constraint
#    is never trusted alone (OWASP LLM01).
injected = {
    "artifact_type": "ai_proposal",
    "schema_version": "aqos-install-plan/v1",
    "selection": {
        "golden_profile": "profile.gaming; rm -rf /",
        "roles": [],
        "include_local_ai": False,
    },
}
result_inj, _ = _run(reply=_reply_with(json.dumps(injected)))
check("injection-shaped reply rejected: ok False", result_inj.get("ok") is False)
check(
    "injection-shaped reply rejected as unknown_profile",
    result_inj.get("reason") == "unknown_profile",
)

# 5. A reply carrying an out-of-catalog role (still schema-shaped) is
#    rejected too -- a "successfully constrained" but wrong-content reply
#    must not be trusted just because it parsed.
injected_role = {
    "artifact_type": "ai_proposal",
    "schema_version": "aqos-install-plan/v1",
    "selection": {
        "golden_profile": "profile.gaming",
        "roles": ["role.does-not-exist"],
        "include_local_ai": False,
    },
}
result_role, _ = _run(reply=_reply_with(json.dumps(injected_role)))
check("out-of-catalog role rejected: ok False", result_role.get("ok") is False)
check("out-of-catalog role rejected as unknown_role", result_role.get("reason") == "unknown_role")

# 6. HTTP failure/timeout fails closed.
result_fail, _ = _run(raises=TimeoutError("timed out"))
check("HTTP timeout -> ok False", result_fail.get("ok") is False)
check("HTTP timeout -> reason proposal_unavailable", result_fail.get("reason") == "proposal_unavailable")

result_fail2, _ = _run(raises=OSError("connection refused"))
check("HTTP connection error -> ok False", result_fail2.get("ok") is False)
check("HTTP connection error -> reason proposal_unavailable", result_fail2.get("reason") == "proposal_unavailable")

# 7. Malformed reply shape (no choices) fails closed the same way.
result_malformed, _ = _run(reply={"unexpected": "shape"})
check("malformed reply shape -> ok False", result_malformed.get("ok") is False)
check(
    "malformed reply shape -> reason proposal_unavailable",
    result_malformed.get("reason") == "proposal_unavailable",
)

# 8. Non-JSON content string fails closed via validate_proposal's json_invalid
#    (still routed through the authoritative gate, not a special case).
result_badjson, _ = _run(reply=_reply_with("not json at all"))
check("non-JSON content -> ok False", result_badjson.get("ok") is False)
check("non-JSON content -> reason json_invalid", result_badjson.get("reason") == "json_invalid")

if _failures:
    for failure in _failures:
        print(f"FAIL: {failure}")
    print(f"test-aqos-ai-propose: ok {_count - len(_failures)}/{_count}")
    sys.exit(1)

print(f"test-aqos-ai-propose: ok {_count}/{_count}")
