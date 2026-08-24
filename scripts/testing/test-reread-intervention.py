#!/usr/bin/env python3
"""
Regression test for the repeated-read stagnation INTERVENTION (2026-08-18).

Root cause this guards against: the local (Qwen) agent's repeated-read
stagnation guard (agent_executor.py, `_REPEATED_READ_PATH_LIMIT` /
"Repeated-read stagnation") aborted a task the FIRST time a file was
re-read past the threshold — even when the relevant code was already
front-loaded verbatim in context under "## Relevant prior knowledge".
That threw away tasks local could have completed.

Fix under test: on the FIRST breach for a given file path, inject a
one-shot edit-forcing intervention as the read_file TOOL RESULT (role:
"tool" — the message the model actually sees as the outcome of its own
last tool call) instead of aborting, then let the loop continue. Only a
SECOND breach (the model re-reads again after the nudge) still aborts.

This drives the real `_execute_with_tools` tool-use loop with `_call_llama`
and `tool_registry` mocked out, so the assertions exercise the actual
control flow (not just static string presence in the source, which the
existing test-exploration-stagnation-guard.py already covers for the
sibling exploration guard).

Coverage:
  1. First breach (Nth identical-path read) injects the intervention as a
     role:"tool" message containing both "edit_file" and "Relevant prior
     knowledge" — NOT an abort.
  2. The intervention fires exactly once (single occurrence across the
     whole run).
  3. A second breach (model re-reads again after the nudge) still aborts
     with the original "Repeated-read stagnation" / "Aborting" message.
  4. AQ_REREAD_INTERVENTION=0 restores the original plain-abort-on-first-
     breach behavior (kill switch).
"""
from __future__ import annotations

import asyncio
import importlib.util
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

# ToolCall lives in tool_registry, imported into agent_executor's namespace or module.
if ToolCall is None:
    import tool_registry as _tr
    ToolCall = _tr.ToolCall

FAKE_PATH = "/fake/repeated.py"

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

    def _fake_parse(_response: str):
        _call_seq["n"] += 1
        return ToolCall(
            id=f"call-{_call_seq['n']}",
            tool_name="read_file",
            arguments={"file_path": FAKE_PATH},
        )

    async def _fake_execute(tool_call):
        tool_call.status = "completed"
        # A field that varies per call (call_seq) so the OLDER generic
        # identical-result-prefix guard (_STAGNATION_THRESHOLD_READ=3,
        # tool-name-only, not path-aware) doesn't fire first and mask the
        # path-specific guard this test targets — mirrors real read_file
        # results, which vary in incidental metadata across repeats.
        tool_call.result = {
            "success": True,
            "content": "SAME FILE CONTENT EVERY TIME",
            "call_seq": _call_seq["n"],
        }
        return tool_call

    def _fake_format(tool_call) -> str:
        import json as _json
        return _json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.parse_tool_call_from_llama.side_effect = _fake_parse
    reg.execute_tool_call = AsyncMock(side_effect=_fake_execute)
    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


def make_call_llama_mock(snapshots: list):
    """Records a shallow copy of `messages` on every call; always answers
    with a read_file tool-call for FAKE_PATH so the model 'keeps re-reading'."""
    async def _fake_call_llama(messages, **kwargs):
        snapshots.append(list(messages))
        response = f'{{"function": "read_file", "arguments": {{"file_path": "{FAKE_PATH}"}}}}'
        return response, 10
    return AsyncMock(side_effect=_fake_call_llama)


async def test_first_breach_injects_intervention_not_abort():
    """(1) + (2): Nth identical-path read → role:"tool" intervention message
    containing "edit_file" and "Relevant prior knowledge", fired exactly once."""
    # _REREAD_INTERVENTION_ENABLED defaults True (module-level, resolved at
    # import time) — no env var needed for the enabled path.
    os.environ["AI_AGENT_REPEATED_READ_PATH_LIMIT"] = "2"
    ex = make_executor()
    task = Task(id="t-intervention", objective="fix the thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    ex._call_llama = make_call_llama_mock(snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    # 3 LLM calls expected: read#1 (no breach) -> read#2 (breach#1, intervention,
    # continue) -> read#3 (breach#2, abort — no 4th call).
    check("exactly 3 _call_llama calls (1 clean read, 1 breach->intervention, 1 breach->abort)",
          ex._call_llama.await_count == 3)

    intervention_tool_msgs = [
        m for snap in snapshots for m in snap
        if m.get("role") == "tool"
        and "Relevant prior knowledge" in (m.get("content") or "")
    ]
    check("intervention delivered as role:'tool' message", len(intervention_tool_msgs) >= 1)
    check("intervention message mentions edit_file",
          all("edit_file" in m["content"] for m in intervention_tool_msgs))
    check("intervention fires exactly once (single occurrence across the whole run)",
          len(intervention_tool_msgs) == 1)

    # The call AFTER the intervention (call 3) must have seen it in its own
    # message history — proves it reaches the model on the NEXT turn, not
    # just logged.
    check("the LLM call following the breach sees the intervention in its own context",
          any(
              m.get("role") == "tool" and "Relevant prior knowledge" in (m.get("content") or "")
              for m in snapshots[-1]
          ))

    check("final result is still a plain abort (second breach) after the one-shot nudge failed to land an edit",
          "Aborting" in final_msg and "Repeated-read stagnation" in final_msg)


async def test_kill_switch_restores_plain_abort():
    """(4): AQ_REREAD_INTERVENTION=0 restores original abort-on-first-breach.

    _REREAD_INTERVENTION_ENABLED is a module-level constant resolved once at
    import time (same pattern as _READ_FILE_GATE_ENABLED) — the running loop
    reads the module attribute directly, not os.environ, each call. So the
    kill switch is exercised by patching the module attribute, mirroring how
    test-read-file-gate.py patches ae._LOCAL_ALLOW_COMMIT.
    """
    os.environ["AI_AGENT_REPEATED_READ_PATH_LIMIT"] = "2"
    ex = make_executor()
    task = Task(id="t-killswitch", objective="fix the thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    ex._call_llama = make_call_llama_mock(snapshots)

    from unittest.mock import patch as _patch
    with _patch.object(ae, "_REREAD_INTERVENTION_ENABLED", False):
        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("kill switch: only 2 _call_llama calls (abort fires on the FIRST breach, no intervention turn)",
          ex._call_llama.await_count == 2)
    check("kill switch: final result is the plain abort message",
          "Aborting" in final_msg and "Repeated-read stagnation" in final_msg)
    no_intervention = not any(
        m.get("role") == "tool" and "Relevant prior knowledge" in (m.get("content") or "")
        for snap in snapshots for m in snap
    )
    check("kill switch: no intervention message ever injected", no_intervention)


def make_range_sequence_executor(calls: list[tuple[str, dict]]) -> AgentExecutor:
    """Hermetic executor whose registry records only real disk-tool executions."""
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None
    ex.remote_probe_timeout_seconds = 5
    ex._prompt_extensions_cache = None

    reg = MagicMock()
    reg.get_tools_for_model.return_value = [
        {"name": "read_file", "description": "read a file"},
        {"name": "edit_file", "description": "edit a file"},
    ]
    reg.tools = {}
    parse_index = {"n": 0}

    def _parse(response: str):
        if response == "COMPLETED: bounded edit applied":
            return None
        tool_name, arguments = calls[parse_index["n"]]
        parse_index["n"] += 1
        return ToolCall(id=f"range-{parse_index['n']}", tool_name=tool_name, arguments=arguments)

    async def _execute(tool_call):
        tool_call.status = "completed"
        if tool_call.tool_name == "read_file":
            tool_call.result = {
                "success": True,
                "content": f"EXACT {tool_call.arguments['start_line']}-{tool_call.arguments['end_line']}",
                "metadata": {
                    "lines": tool_call.arguments["end_line"] - tool_call.arguments["start_line"] + 1,
                },
            }
        else:
            tool_call.result = {"success": True, "changed": True}
        return tool_call

    reg.parse_tool_call_from_llama.side_effect = _parse
    reg.execute_tool_call = AsyncMock(side_effect=_execute)
    reg.format_tool_result.side_effect = lambda tc: str(tc.result or tc.error)
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


def make_sequence_llama(snapshots: list, responses: list[str]):
    async def _call(messages, **kwargs):
        snapshots.append(list(messages))
        return responses.pop(0), 10
    return AsyncMock(side_effect=_call)


async def test_range_coverage_intercepts_redundancy_then_allows_edit():
    """A fully-covered re-read never hits the registry, but its correction reaches
    the next turn and the model may still select an ordinary edit_file action."""
    # Keep the legacy path-count intervention out of this focused range test:
    # it is independently covered above and would otherwise preempt call three.
    os.environ["AI_AGENT_REPEATED_READ_PATH_LIMIT"] = "4"
    calls = [
        ("read_file", {"file_path": FAKE_PATH, "start_line": 100, "end_line": 150}),
        # Non-overlap must still execute normally.
        ("read_file", {"file_path": FAKE_PATH, "start_line": 160, "end_line": 170}),
        # Fully covered by 100-150: intercepted before disk/tool execution.
        ("read_file", {"file_path": FAKE_PATH, "start_line": 110, "end_line": 120}),
        ("edit_file", {"file_path": FAKE_PATH, "old_string": "old", "new_string": "new"}),
    ]
    ex = make_range_sequence_executor(calls)
    snapshots: list = []
    ex._call_llama = make_sequence_llama(
        snapshots,
        [
            '{"function":"read_file","arguments":{}}',
            '{"function":"read_file","arguments":{}}',
            '{"function":"read_file","arguments":{}}',
            '{"function":"edit_file","arguments":{}}',
            "COMPLETED: bounded edit applied",
        ],
    )
    task = Task(id="t-range-intercept", objective="edit one known region", status=TaskStatus.RUNNING)
    capture = MagicMock()
    with patch.object(ae, "training_capture", capture):
        final_msg, _ = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    executed_names = [call.args[0].tool_name for call in ex.tool_registry.execute_tool_call.await_args_list]
    check("first exact ranged read executes", executed_names.count("read_file") == 2)
    check("non-overlapping exact ranged read executes", len(executed_names) == 3)
    check("fully-covered range does not execute the disk-backed read", len(task.tool_calls_made) == 4)
    check("model-selected edit executes after correction", "edit_file" in executed_names)
    captured_tools = [
        call.kwargs["model_provenance"]["tool"]
        for call in capture.capture_success.call_args_list
    ]
    check("synthetic redundant read is not captured as a positive training success",
          captured_tools.count("read_file") == 2)
    check("genuine ranged reads and the subsequent edit retain positive capture",
          sorted(captured_tools) == ["edit_file", "read_file", "read_file"])
    correction_seen_next_turn = any(
        message.get("role") == "tool" and "REREAD GUARD" in (message.get("content") or "")
        for message in snapshots[3]
    )
    check("corrective role-tool result reaches the next model turn", correction_seen_next_turn)
    check("successful edit can complete normally", final_msg == "COMPLETED: bounded edit applied")


async def test_second_redundant_range_fails_closed():
    """After one correction, another covered range aborts without another disk read."""
    os.environ["AI_AGENT_REPEATED_READ_PATH_LIMIT"] = "4"
    calls = [
        ("read_file", {"file_path": FAKE_PATH, "start_line": 100, "end_line": 150}),
        ("read_file", {"file_path": FAKE_PATH, "start_line": 110, "end_line": 120}),
        ("read_file", {"file_path": FAKE_PATH, "start_line": 105, "end_line": 110}),
    ]
    ex = make_range_sequence_executor(calls)
    snapshots: list = []
    ex._call_llama = make_sequence_llama(
        snapshots,
        ['{"function":"read_file","arguments":{}}'] * 3,
    )
    task = Task(id="t-range-defiance", objective="edit one known region", status=TaskStatus.RUNNING)
    final_msg, _ = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("second redundant range aborts fail-closed", "repeated defiance is aborted fail-closed" in final_msg)
    check("only the original ranged read reached disk execution",
          ex.tool_registry.execute_tool_call.await_count == 1)


async def main():
    await test_first_breach_injects_intervention_not_abort()
    await test_kill_switch_restores_plain_abort()
    await test_range_coverage_intercepts_redundancy_then_allows_edit()
    await test_second_redundant_range_fails_closed()

    os.environ.pop("AI_AGENT_REPEATED_READ_PATH_LIMIT", None)

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
