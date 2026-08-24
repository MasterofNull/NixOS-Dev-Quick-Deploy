#!/usr/bin/env python3
"""
Regression test for the NO-ACTION stagnation INTERVENTION (2026-08-18).

Root cause this guards against: on IMPLEMENTER tasks, the local (Qwen) agent
sometimes returns a prose PLAN with no parseable tool call at all — e.g.
"Thought: The task is to modify X so that ..." — and `_execute_with_tools`
(agent_executor.py), finding no tool call, treats that as the FINAL ANSWER
and completes the task with tool_call_count=0 and zero edits. Local narrated
what it would do and the loop accepted narration as done — a silent failure,
since the task's whole point was to EDIT a file and nothing was edited.

Fix under test: when the response has no parseable tool call AND the task is
an implementer/edit task (not analysis-only) AND no successful edit_file /
write_file has landed yet this run (`_edits_made == 0`) AND the prose is not
an explicit refusal/stop ("cannot safely...", "under-specified...", etc.),
inject ONE-SHOT corrective message (role:"user", mirroring the existing
malformed-tool-call-JSON nudge a few lines above it) telling the model to
call edit_file instead of narrating, then `continue` the loop instead of
completing. A SECOND prose-only response (intervention already sent) still
completes normally — never loops forever. A genuine refusal is never
intervened on, so a legitimate "I can't safely do this" exit still completes
immediately.

This drives the real `_execute_with_tools` tool-use loop with `_call_llama`
and `tool_registry` mocked out (same harness pattern as
test-reread-intervention.py), so the assertions exercise the actual control
flow, not just static string presence in the source.

Coverage:
  (a) Turn-1 prose-only response does NOT complete the task — the no-action
      intervention is injected (as a role:"user" message) and the loop
      continues instead of returning immediately.
  (b) Local then calls edit_file on turn 2 and the task completes with the
      edit landed (_edits_made == 1, execute_tool_call invoked with
      edit_file).
  (c) The intervention fires only once (single occurrence in the final
      message history).
  (d) A model that returns prose-only TWICE (never edits) still eventually
      completes — no infinite loop (2nd prose response completes because the
      one-shot flag is already spent).
  (e) AQ_NOACTION_INTERVENTION=0 restores immediate completion on a
      turn-1 prose-only response (kill switch).
  (bonus) An explicit refusal ("... this change is unsafe to make ...") on
      turn 1 is NEVER intervened on and completes immediately, preserving
      the legitimate "I can't safely do this" exit.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
sys.path.insert(0, str(LOCAL_AGENTS))

spec = importlib.util.spec_from_file_location("agent_executor", LOCAL_AGENTS / "agent_executor.py")
ae = importlib.util.module_from_spec(spec)
sys.modules.setdefault("httpx", MagicMock())
spec.loader.exec_module(ae)

AgentExecutor = ae.LocalAgentExecutor
AgentType = ae.AgentType
Task = ae.Task
TaskStatus = ae.TaskStatus
ToolCall = ae.ToolCall if hasattr(ae, "ToolCall") else None
if ToolCall is None:
    import tool_registry as _tr
    ToolCall = _tr.ToolCall

TARGET_FILE = "/fake/target.py"
PROSE_PLAN = (
    "Thought: The task is to modify the retry decorator so that it backs off "
    "exponentially instead of using a fixed delay. I would change the sleep "
    "call to multiply by 2 each attempt."
)
REFUSAL_PROSE = (
    "Thought: this change is unsafe to make without more information — the "
    "task is under-specified about which retry path to modify, so I am "
    "stopping here rather than guessing."
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


def make_executor() -> AgentExecutor:
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None  # skip working-memory prefetch httpx call
    ex.remote_probe_timeout_seconds = 5
    ex._prompt_extensions_cache = None

    reg = MagicMock()
    reg.get_tools_for_model.return_value = [
        {"name": "read_file", "description": "read a file"},
        {"name": "edit_file", "description": "edit a file"},
    ]
    reg.tools = {}

    _call_seq = {"n": 0}

    def _fake_parse(response: str):
        """Mirrors the real parser closely enough for this loop: a JSON
        {"function": "edit_file", ...} payload parses to a ToolCall; any
        prose (including the PROSE_PLAN / REFUSAL_PROSE / COMPLETED: text)
        returns None, exactly like the real parser on unstructured text."""
        stripped = response.strip()
        if not stripped.startswith('{"function"'):
            return None
        _call_seq["n"] += 1
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        return ToolCall(
            id=f"call-{_call_seq['n']}",
            tool_name=payload["function"],
            arguments=payload.get("arguments", {}),
        )

    async def _fake_execute(tool_call):
        tool_call.status = "completed"
        tool_call.result = {"success": True, "message": "edit applied"}
        return tool_call

    def _fake_format(tool_call) -> str:
        return json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.parse_tool_call_from_llama.side_effect = _fake_parse
    reg.execute_tool_call = AsyncMock(side_effect=_fake_execute)
    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


def edit_call_json() -> str:
    return json.dumps({
        "function": "edit_file",
        "arguments": {
            "file_path": TARGET_FILE,
            "old_string": "delay = 1",
            "new_string": "delay = 2 ** attempt",
        },
    })


def make_call_llama_mock(responses: list, snapshots: list):
    """Returns responses in sequence (last one repeats if exhausted); records
    a shallow copy of `messages` on every call."""
    async def _fake_call_llama(messages, **kwargs):
        snapshots.append(list(messages))
        idx = min(len(snapshots) - 1, len(responses) - 1)
        return responses[idx], 10
    return AsyncMock(side_effect=_fake_call_llama)


async def test_prose_plan_then_edit_completes():
    """(a) + (b) + (c): turn-1 prose plan does NOT complete the task; the
    no-action intervention fires once; turn-2 edit_file lands and the task
    then completes normally."""
    ex = make_executor()
    task = Task(id="t-noaction-edit", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [PROSE_PLAN, edit_call_json(), "COMPLETED: switched to exponential backoff."]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("(a) turn-1 prose did not complete immediately — 3 LLM calls happened "
          "(prose -> intervention -> edit -> final synthesis), not 1",
          ex._call_llama.await_count == 3)

    check("(b) edit_file was actually executed (tool result landed)",
          ex.tool_registry.execute_tool_call.await_count == 1)
    _executed_tool_names = [
        c.args[0].tool_name for c in ex.tool_registry.execute_tool_call.await_args_list
    ]
    check("(b) the executed tool was edit_file", _executed_tool_names == ["edit_file"])
    check("(b) task completed with the edit landed (final message reflects real completion)",
          "COMPLETED" in final_msg)

    last_snapshot = snapshots[-1]
    intervention_msgs = [
        m for m in last_snapshot
        if m.get("role") == "user"
        and "did NOT make it" in (m.get("content") or "")
        and "edit_file NOW" in (m.get("content") or "")
    ]
    check("(c) no-action intervention message present in final context",
          len(intervention_msgs) == 1)
    check("(c) no-action intervention fires exactly once (not duplicated)",
          len(intervention_msgs) == 1)


async def test_prose_twice_still_completes():
    """(d): a model that never calls a tool (prose plan, then prose again)
    still terminates — the one-shot flag prevents a second intervention, so
    the second prose-only response completes the loop instead of hanging."""
    ex = make_executor()
    task = Task(id="t-noaction-twice", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [PROSE_PLAN, "Thought: I still think the same change is needed but I will not call a tool."]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    final_msg, _tokens = await asyncio.wait_for(
        ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0),
        timeout=10,
    )

    check("(d) exactly 2 LLM calls (prose -> intervention -> prose again -> completes, no 3rd call)",
          ex._call_llama.await_count == 2)
    check("(d) no edit was ever executed", ex.tool_registry.execute_tool_call.await_count == 0)
    check("(d) loop terminated (did not hang) and returned the second prose response",
          final_msg.strip() == responses[1].strip())


async def test_retry_response_is_bounded():
    """A verbose failed turn must not consume the next turn's prompt budget."""
    ex = make_executor()
    task = Task(id="t-noaction-budget", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    oversized_plan = PROSE_PLAN * 100
    responses = [oversized_plan, "Thought: still no tool call."]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    retry_assistant = [
        message["content"] for message in snapshots[1]
        if message.get("role") == "assistant"
    ][-1]
    check("retry response is capped at the executable budget",
          len(retry_assistant) <= ae._RETRY_RESPONSE_CHAR_BUDGET)
    check("retry response truncation is explicit",
          "retry response truncated" in retry_assistant)


async def test_malformed_tool_retry_paths_and_training_capture():
    """GBNF repair and fallback synthesis share the bound without truncating evidence."""
    ex = make_executor()
    task = Task(id="t-malformed-budget", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    malformed = '{"function":"edit_file","arguments":{"old_string":"' + ("x" * 4_000)
    responses = [malformed, "repair still malformed", "COMPLETED: malformed call rejected."]
    ex._call_llama = make_call_llama_mock(responses, snapshots)
    capture = MagicMock()

    with patch.object(ae, "_LOCAL_GBNF_REPAIR_ENABLED", True), patch.object(ae, "training_capture", capture):
        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    repair_excerpt = [
        message["content"] for message in snapshots[1]
        if message.get("role") == "assistant"
    ][-1]
    synthesis_excerpt = [
        message["content"] for message in snapshots[2]
        if message.get("role") == "assistant"
    ][-1]
    expected = ae._bounded_retry_response(malformed)
    check("GBNF repair receives the exact bounded excerpt", repair_excerpt == expected)
    check("failed-repair synthesis receives the exact bounded excerpt", synthesis_excerpt == expected)
    check("malformed synthesis completes through its bounded fallback", final_msg.startswith("COMPLETED:"))
    captured = capture.capture_failure.call_args.kwargs
    check("training capture retains the full untruncated failed response",
          captured["bad_output"] == malformed and len(captured["bad_output"]) > len(expected))


def test_retry_excerpt_contract():
    short = "short malformed response"
    check("short retry responses remain byte-identical",
          ae._bounded_retry_response(short) == short)
    long = "H" * 900 + "T" * 200
    excerpt = ae._bounded_retry_response(long)
    marker = "\n...[retry response truncated]...\n"
    head_chars = ae._RETRY_RESPONSE_CHAR_BUDGET - len(marker) - 128
    expected = long[:head_chars] + marker + long[-128:]
    check("long retry excerpts preserve the deterministic head/tail contract",
          excerpt == expected and len(excerpt) == ae._RETRY_RESPONSE_CHAR_BUDGET)


async def test_kill_switch_restores_immediate_completion():
    """(e): AQ_NOACTION_INTERVENTION=0 (patched module attribute, same
    pattern test-reread-intervention.py uses for its own kill switch)
    restores the pre-fix behavior: turn-1 prose completes immediately."""
    ex = make_executor()
    task = Task(id="t-noaction-killswitch", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [PROSE_PLAN, edit_call_json()]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    with patch.object(ae, "_NOACTION_INTERVENTION_ENABLED", False):
        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("(e) kill switch: exactly 1 LLM call (prose completes immediately, no intervention turn)",
          ex._call_llama.await_count == 1)
    check("(e) kill switch: final message is the raw prose plan, unmodified",
          final_msg.strip() == PROSE_PLAN.strip())
    check("(e) kill switch: no edit was ever executed",
          ex.tool_registry.execute_tool_call.await_count == 0)


async def test_refusal_is_never_intervened_on():
    """(bonus): an explicit refusal/stop on turn 1 preserves the legitimate
    exit — completes immediately, same as the kill-switch path, even with
    the intervention enabled."""
    ex = make_executor()
    task = Task(id="t-noaction-refusal", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [REFUSAL_PROSE, edit_call_json()]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("(bonus) refusal completes immediately — exactly 1 LLM call",
          ex._call_llama.await_count == 1)
    check("(bonus) refusal message returned unmodified (no forced edit)",
          final_msg.strip() == REFUSAL_PROSE.strip())
    check("(bonus) no edit was ever executed on a genuine refusal",
          ex.tool_registry.execute_tool_call.await_count == 0)


async def main():
    test_retry_excerpt_contract()
    await test_prose_plan_then_edit_completes()
    await test_prose_twice_still_completes()
    await test_retry_response_is_bounded()
    await test_malformed_tool_retry_paths_and_training_capture()
    await test_kill_switch_restores_immediate_completion()
    await test_refusal_is_never_intervened_on()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
