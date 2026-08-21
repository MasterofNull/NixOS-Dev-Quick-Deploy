#!/usr/bin/env python3
"""
Tests for the LLM record/replay cassette harness.

Modules under test:
  ai-stack/local-agents/llm_cassette.py   — request_key, Cassette, mode/path/on_miss
  ai-stack/local-agents/agent_executor.py — the two _call_llama wiring points

Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md

Covers:
  (a) request_key is stable + excludes volatile fields
  (b) record -> lookup round trip (same instance + a freshly-loaded instance)
  (c) multi-row-per-key consumed in call order
  (d) replay mode returns recorded content WITHOUT touching the network, in BOTH
      the streaming and legacy (non-streaming) _call_llama branches
  (e) on_miss error/passthrough/empty behaviors
  (f) mode=off is a strict no-op — live HTTP path taken, cassette file never written
  (g) golden end-to-end: record a stubbed run of _execute_with_tools (network
      stubbed with canned turns, not a live APU call), then REPLAY the identical
      task through the real _execute_with_tools fully offline and confirm identical
      loop behavior (same final answer, same tool-call outcomes, zero network I/O).

Bonus (DoD payoff demonstration, not just a unit check): a synthetic cassette row
carrying a run_command tool call whose "command" argument ends in the literal
`\\n},\\n` artifact this session hit live (the local model's streaming/GBNF tool-call
parser leaking the JSON envelope's closing punctuation into the argument value) is
recorded, then replayed fully offline through the real parse + execute path, proving
the already-committed strip fix in builtin_tools/shell_tools.py:147 resolves it
deterministically — no 30-40 min live APU run required.

Run: python3 scripts/testing/test-llm-cassette.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

import httpx  # noqa: E402
import llm_cassette  # noqa: E402
from agent_executor import AgentType, LocalAgentExecutor, Task  # noqa: E402
from shared.llm_config import build_llama_payload  # noqa: E402
from tool_registry import ToolRegistry  # noqa: E402
from builtin_tools.shell_tools import register_shell_tools  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Shared test fixtures / fakes
# ---------------------------------------------------------------------------

_CASSETTE_ENV_VARS = ("AQ_LLM_CASSETTE_MODE", "AQ_LLM_CASSETTE", "AQ_LLM_CASSETTE_ON_MISS")


@contextlib.contextmanager
def cassette_env(mode: Optional[str] = None, path: Optional[str] = None, on_miss: Optional[str] = None):
    """Save/restore the cassette env vars around a test and reset llm_cassette's
    process-wide Cassette cache so a prior test's cursor/path never leaks in."""
    saved = {k: os.environ.get(k) for k in _CASSETTE_ENV_VARS}
    try:
        for var, val in (("AQ_LLM_CASSETTE_MODE", mode), ("AQ_LLM_CASSETTE", path), ("AQ_LLM_CASSETTE_ON_MISS", on_miss)):
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)
        llm_cassette.reset_cache()
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        llm_cassette.reset_cache()


@contextlib.contextmanager
def env_var(name: str, value: Optional[str]):
    saved = os.environ.get(name)
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        yield
    finally:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved


class _ExplodingAsyncClient:
    """Any attempt to construct httpx.AsyncClient explodes. Proves a replay hit (or
    mode=replay generally) never touches the network."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("network touched — httpx.AsyncClient must not be constructed on a replay hit")


class _FakeResponse:
    def __init__(self, status_code: int, json_data: Dict[str, Any]):
        self.status_code = status_code
        self._json = json_data
        self.text = json.dumps(json_data)

    def json(self) -> Dict[str, Any]:
        return self._json


def _make_single_response_client(response: _FakeResponse):
    """A fake httpx.AsyncClient whose .post() always returns the same canned
    response — used to prove the LIVE path executes (mode=off)."""

    class _Ctx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, timeout=None, headers=None):
            return response

    return _Ctx


def _make_scripted_client(turns: List[str]):
    """A fake httpx.AsyncClient that returns each of `turns` in order, one per POST
    call — used to drive a multi-turn _execute_with_tools loop deterministically
    without a live APU."""
    turns_iter = iter(turns)

    class _Ctx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, timeout=None, headers=None):
            try:
                content = next(turns_iter)
            except StopIteration:
                raise AssertionError(
                    "scripted client ran out of canned turns — the loop made more LLM "
                    "calls than the test expected"
                )
            return _FakeResponse(200, {
                "choices": [{"message": {"content": content}}],
                "usage": {"total_tokens": 10},
            })

    return _Ctx


# ---------------------------------------------------------------------------
# (a) request_key: stable + excludes volatile fields
# ---------------------------------------------------------------------------

def test_request_key_stable_and_excludes_volatile() -> None:
    base = {
        "messages": [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "do the thing"},
        ],
        "max_tokens": 256,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
        "repeat_penalty": 1.08,
        "repeat_last_n": 64,
        "frequency_penalty": 0.05,
        "cache_prompt": True,
    }
    k1 = llm_cassette.request_key(base)
    k1_again = llm_cassette.request_key(json.loads(json.dumps(base)))
    assert_true(k1 == k1_again, "request_key must be deterministic across repeated calls")

    volatile_changed = dict(base)
    volatile_changed["cache_prompt"] = False
    volatile_changed["repeat_penalty"] = 1.5
    volatile_changed["repeat_last_n"] = 32
    volatile_changed["chat_template_kwargs"] = {"enable_thinking": True}
    k2 = llm_cassette.request_key(volatile_changed)
    assert_true(
        k1 == k2,
        "request_key must exclude volatile fields (cache_prompt/repeat_penalty/"
        "repeat_last_n/chat_template_kwargs)",
    )

    semantic_changed = dict(base)
    semantic_changed["messages"] = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "do a DIFFERENT thing"},
    ]
    k3 = llm_cassette.request_key(semantic_changed)
    assert_true(k1 != k3, "request_key must change when message content changes")

    grammar_changed = dict(base)
    grammar_changed["grammar"] = "root ::= object"
    k4 = llm_cassette.request_key(grammar_changed)
    assert_true(k1 != k4, "request_key must change when grammar changes")

    kt1 = llm_cassette.request_key(base, task_type="agent")
    kt2 = llm_cassette.request_key(base, task_type="research")
    assert_true(kt1 != kt2, "request_key must vary with task_type")
    assert_true(kt1 != k1, "request_key with an explicit task_type must differ from without")
    print("PASS (a): request_key stability + volatile-field exclusion")


# ---------------------------------------------------------------------------
# (b) record -> lookup round trip
# ---------------------------------------------------------------------------

def test_record_lookup_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        cass = llm_cassette.Cassette(cpath)
        payload = {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 10}
        key = llm_cassette.request_key(payload)
        cass.record(key, payload, "hello back", 7, {"note": "unit-test"})

        hit = cass.lookup(key)
        assert_true(hit == ("hello back", 7), f"same-instance lookup must round-trip, got {hit}")

        # A freshly-constructed instance must read the same row back from disk.
        cass2 = llm_cassette.Cassette(cpath)
        hit2 = cass2.lookup(key)
        assert_true(hit2 == ("hello back", 7), f"fresh-instance lookup must round-trip from disk, got {hit2}")
        assert_true(cass2.lookup(key) is None, "a 2nd lookup with only one recorded row must miss")
    print("PASS (b): record -> lookup round trip (same instance + fresh reload)")


# ---------------------------------------------------------------------------
# (c) multi-row-per-key consumed in call order
# ---------------------------------------------------------------------------

def test_multi_row_per_key_call_order() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        cass = llm_cassette.Cassette(cpath)
        payload = {"messages": [{"role": "user", "content": "same request twice"}]}
        key = llm_cassette.request_key(payload)
        cass.record(key, payload, "first call output", 10)
        cass.record(key, payload, "second call output", 20)

        h1 = cass.lookup(key)
        h2 = cass.lookup(key)
        h3 = cass.lookup(key)
        assert_true(h1 == ("first call output", 10), f"1st lookup must return the 1st recorded row, got {h1}")
        assert_true(h2 == ("second call output", 20), f"2nd lookup must return the 2nd recorded row, got {h2}")
        assert_true(h3 is None, "3rd lookup with only 2 recorded rows must miss")
    print("PASS (c): multi-row-per-key consumed in call order")


# ---------------------------------------------------------------------------
# (d) replay mode returns recorded content WITHOUT touching the network —
#     both the streaming and legacy _call_llama branches.
# ---------------------------------------------------------------------------

async def _run_replay_no_network(streaming: bool) -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "replay-no-network probe"},
        ]
        max_tokens = 128
        task_type = "agent"

        # Build the SAME payload _call_llama would build for this branch (GBNF is off
        # by default in this test env, so no "grammar" key) to derive a matching key.
        kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": None, "task_type": task_type}
        if streaming:
            kwargs["stream"] = True
        payload = build_llama_payload(messages, **kwargs)
        key = llm_cassette.request_key(payload, task_type)

        cass = llm_cassette.Cassette(cpath)
        cass.record(key, payload, "replayed content, no network involved", 99)

        with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "true" if streaming else "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
            try:
                executor = LocalAgentExecutor(fallback_endpoint="")
                content, tokens = await executor._call_llama(
                    messages, max_tokens=max_tokens, task_type=task_type,
                )
            finally:
                httpx.AsyncClient = saved_client

        branch = "streaming" if streaming else "legacy"
        assert_true(
            (content, tokens) == ("replayed content, no network involved", 99),
            f"replay ({branch} branch) must return the recorded row, got {(content, tokens)}",
        )


def test_replay_returns_recorded_content_without_network() -> None:
    asyncio.run(_run_replay_no_network(streaming=True))
    asyncio.run(_run_replay_no_network(streaming=False))
    print("PASS (d): replay returns recorded content with zero network I/O (streaming + legacy branches)")


# ---------------------------------------------------------------------------
# (e) on_miss policies
# ---------------------------------------------------------------------------

def test_on_miss_policies() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "empty_cassette.jsonl")
        Path(cpath).write_text("")  # cassette exists but has no matching row
        payload = {"messages": [{"role": "user", "content": "never recorded"}], "max_tokens": 5}

        with cassette_env(mode="replay", path=cpath, on_miss="error"):
            try:
                llm_cassette.replay_lookup(payload)
                raise AssertionError("expected ReplayMiss for on_miss=error")
            except llm_cassette.ReplayMiss as e:
                assert_true(bool(e.key), "ReplayMiss must carry the computed key")

        with cassette_env(mode="replay", path=cpath, on_miss="passthrough"):
            result = llm_cassette.replay_lookup(payload)
            assert_true(result is None, "on_miss=passthrough must return None (fall through to live)")

        with cassette_env(mode="replay", path=cpath, on_miss="empty"):
            result = llm_cassette.replay_lookup(payload)
            assert_true(result == ("", 0), f"on_miss=empty must return ('', 0), got {result}")
    print("PASS (e): on_miss policies (error raises ReplayMiss / passthrough -> None / empty -> ('',0))")


# ---------------------------------------------------------------------------
# (f) mode=off is a strict no-op
# ---------------------------------------------------------------------------

async def _run_mode_off_is_noop() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "unused_cassette.jsonl")
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "off-mode probe"}]

        live_response = _FakeResponse(200, {
            "choices": [{"message": {"content": "LIVE-PATH-TAKEN"}}],
            "usage": {"total_tokens": 11},
        })

        # mode omitted entirely -> "off" (the sacrosanct default).
        with cassette_env(mode=None, path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _make_single_response_client(live_response)  # type: ignore[assignment]
            try:
                executor = LocalAgentExecutor(fallback_endpoint="")
                content, tokens = await executor._call_llama(messages, max_tokens=64, task_type="agent")
            finally:
                httpx.AsyncClient = saved_client

        assert_true(
            (content, tokens) == ("LIVE-PATH-TAKEN", 11),
            f"mode=off must take the live path unmodified, got {(content, tokens)}",
        )
        assert_true(not Path(cpath).exists(), "mode=off must never write to a cassette file")


def test_mode_off_is_noop() -> None:
    asyncio.run(_run_mode_off_is_noop())
    print("PASS (f): mode=off is a strict no-op — live path taken, zero cassette I/O")


# ---------------------------------------------------------------------------
# (g) golden end-to-end: record (stubbed) -> replay through the real
#     _execute_with_tools, offline, identical loop behavior.
# ---------------------------------------------------------------------------

def _golden_task() -> Task:
    return Task(
        id="golden-e2e",
        objective="Run the probe command with run_command and report the result.",
        # "research" is an analysis-only task_type — avoids the no-action edit-forcing
        # intervention (agent_executor.py ~L1672) so the loop terminates in exactly
        # 2 LLM turns: one tool call, one prose final answer.
        task_type="research",
    )


async def _run_golden_e2e() -> Dict[str, Any]:
    turn1 = '{"function": "run_command", "arguments": {"command": "echo golden-e2e-probe"}}'
    turn2 = "Command executed successfully. Task complete."

    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "golden.jsonl")
        saved_client = httpx.AsyncClient
        try:
            # --- Pass 1: record. Network is STUBBED with canned turns (not a live APU
            # call) — this is the harness's own record path, exercised end-to-end. ---
            with cassette_env(mode="record", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
                httpx.AsyncClient = _make_scripted_client([turn1, turn2])  # type: ignore[assignment]
                registry1 = ToolRegistry(db_path=Path(td) / "audit_record.db")
                register_shell_tools(registry1)
                executor1 = LocalAgentExecutor(tool_registry=registry1, fallback_endpoint="")
                task1 = _golden_task()
                record_response, _record_tokens = await executor1._execute_with_tools(
                    task1, AgentType.AGENT, max_tool_calls=5,
                )

            assert_true(Path(cpath).exists(), "record pass must create the cassette file")
            recorded_rows = sum(1 for line in Path(cpath).read_text().splitlines() if line.strip())
            assert_true(
                recorded_rows == 2,
                f"record pass must write exactly 2 rows (2 distinct LLM turns), got {recorded_rows}",
            )

            # --- Pass 2: replay. Network EXPLODES if touched — proves it's offline. ---
            with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
                httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
                registry2 = ToolRegistry(db_path=Path(td) / "audit_replay.db")
                register_shell_tools(registry2)
                executor2 = LocalAgentExecutor(tool_registry=registry2, fallback_endpoint="")
                task2 = _golden_task()
                task2.id = "golden-e2e-replay"
                replay_response, _replay_tokens = await executor2._execute_with_tools(
                    task2, AgentType.AGENT, max_tool_calls=5,
                )
        finally:
            httpx.AsyncClient = saved_client

        return {
            "record_response": record_response,
            "replay_response": replay_response,
            "record_tool_calls": [(tc.tool_name, tc.status, tc.result) for tc in task1.tool_calls_made],
            "replay_tool_calls": [(tc.tool_name, tc.status, tc.result) for tc in task2.tool_calls_made],
        }


def test_golden_e2e_record_then_replay_through_execute_with_tools() -> None:
    outcome = asyncio.run(_run_golden_e2e())
    assert_true(
        outcome["record_response"] == outcome["replay_response"] == "Command executed successfully. Task complete.",
        f"replay must reproduce the identical final answer, got {outcome}",
    )
    assert_true(
        outcome["record_tool_calls"] == outcome["replay_tool_calls"],
        f"replay must reproduce identical tool-call outcomes, got {outcome}",
    )
    assert_true(
        len(outcome["replay_tool_calls"]) == 1 and outcome["replay_tool_calls"][0][0] == "run_command",
        f"replay must reproduce exactly the one run_command call, got {outcome['replay_tool_calls']}",
    )
    assert_true(
        outcome["replay_tool_calls"][0][1] == "completed" and outcome["replay_tool_calls"][0][2].get("success") is True,
        f"replay must reproduce a successful run_command execution, got {outcome['replay_tool_calls']}",
    )
    print(
        "PASS (g): golden end-to-end — record (stubbed) -> replay through the real "
        "_execute_with_tools, fully offline, identical loop behavior"
    )


# ---------------------------------------------------------------------------
# DoD payoff demonstration: record + replay a synthetic run_command call carrying
# this session's live tool-call-JSON-artifact tail ("...\n},\n"), proving the
# committed strip fix (builtin_tools/shell_tools.py:147) resolves it offline.
# ---------------------------------------------------------------------------

async def _run_artifact_strip_replay_demo() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "artifact_demo_cassette.jsonl")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "grep the codebase for a pattern"},
        ]
        max_tokens = 128
        task_type = "agent"

        # The malformed content this session actually produced live: the model's
        # streaming/GBNF tool-call parser leaked the JSON envelope's closing
        # punctuation into the "command" string's value.
        artifact_content = (
            '{"function": "run_command", "arguments": '
            '{"command": "echo artifact-strip-fix-works\n},\n"}}'
        )

        kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": None, "task_type": task_type}
        payload = build_llama_payload(messages, **kwargs)
        key = llm_cassette.request_key(payload, task_type)
        cass = llm_cassette.Cassette(cpath)
        cass.record(key, payload, artifact_content, 37, {"demo": "run_command-artifact-tail"})

        with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
            try:
                registry = ToolRegistry(db_path=Path(td) / "artifact_audit.db")
                register_shell_tools(registry)
                executor = LocalAgentExecutor(tool_registry=registry, fallback_endpoint="")
                content, tokens = await executor._call_llama(
                    messages, max_tokens=max_tokens, task_type=task_type,
                )
            finally:
                httpx.AsyncClient = saved_client

        assert_true(content == artifact_content, "replay must return the exact recorded artifact-tailed content, offline")
        assert_true(tokens == 37, "replay must return the recorded token count")

        # Run the REPLAYED content through the real loop-side handling: parse the tool
        # call, then execute it via the already-committed artifact-strip fix.
        tool_call = registry.parse_tool_call_from_llama(content)
        assert_true(tool_call is not None, "parse_tool_call_from_llama must parse the artifact-tailed JSON")
        assert_true(tool_call.tool_name == "run_command", f"expected run_command, got {tool_call.tool_name}")
        raw_command = tool_call.arguments.get("command", "")
        assert_true(
            raw_command.endswith("\n},\n"),
            f"parsed command must still carry the raw artifact tail (the fix strips it downstream, "
            f"in run_command_handler, not in parsing) — got {raw_command!r}",
        )

        result = await registry.execute_tool_call(tool_call)
        return {"raw_command": raw_command, "status": result.status, "result": result.result}


def test_artifact_strip_fix_resolves_via_offline_replay() -> None:
    outcome = asyncio.run(_run_artifact_strip_replay_demo())
    assert_true(
        outcome["status"] == "completed"
        and isinstance(outcome["result"], dict)
        and outcome["result"].get("success") is True
        and "artifact-strip-fix-works" in (outcome["result"].get("stdout") or ""),
        f"the committed artifact-strip fix (shell_tools.py:147) must make the "
        f"\\n}},\\n-tailed run_command call succeed on replay, got {outcome}",
    )
    print(
        "PASS (DoD demo): run_command call with the live '\\n},\\n' artifact tail, "
        "recorded once and replayed fully offline, resolves via the committed "
        "shell_tools.py strip fix — outcome=" + json.dumps(outcome)
    )


# ---------------------------------------------------------------------------

def main() -> int:
    test_request_key_stable_and_excludes_volatile()
    test_record_lookup_roundtrip()
    test_multi_row_per_key_call_order()
    test_replay_returns_recorded_content_without_network()
    test_on_miss_policies()
    test_mode_off_is_noop()
    test_golden_e2e_record_then_replay_through_execute_with_tools()
    test_artifact_strip_fix_resolves_via_offline_replay()
    print("PASS: llm-cassette record/replay harness — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
