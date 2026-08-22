#!/usr/bin/env python3
"""
Regression test for the missing HARD termination bound in the local agent
tool-use loop (HIGH — Codex independent review finding 5, 2026-08-21).
See: .agent/collaboration/codex-review-local-agent-batch-20260821.md finding 5.

THE DEFECT this guards against: `_execute_with_tools` (agent_executor.py) used
`while True` with no enforced exit. `max_tool_calls` was accepted as a
parameter but explicitly IGNORED (old docstring: "Deprecated compatibility
parameter... governed by stagnation/progress guards... not by a fixed
tool-call ceiling"). The stagnation guards only catch a tool returning the
SAME result repeatedly — an agent that alternates tool calls with results
that keep CHANGING (but make no real forward progress) resets every
stagnation counter and can loop indefinitely, burning the APU with no exit.

THE FIX under test: two hard, always-enforced backstops, checked at the top
of every loop iteration (before the next LLM call is made):
  1. Hard tool-call ceiling: `max_tool_calls` param (if > 0) else
     AQ_AGENT_MAX_TOOL_CALLS env (if set) else a built-in default of 40.
  2. Hard wall-clock budget: `wall_budget_s` param (if > 0) else
     AQ_AGENT_WALL_BUDGET_S env (if set) else a built-in default of 3600s.
Both bounds are ALWAYS enforced (never unbounded) but overridable per call
or via env for a deliberately long-running task. The existing
stagnation/progress guards (identical-result abort, no-action intervention,
edit-feedback, etc.) still fire FIRST — they are checked mid-iteration,
before the loop ever reaches the top of the next iteration where these hard
bounds are checked.

This drives the real `_execute_with_tools` tool-use loop with `_call_llama`
and `tool_registry` mocked out (same harness pattern as
test-reread-intervention.py / test-noaction-intervention.py), so the
assertions exercise the actual control flow.

Coverage:
  (a) No override anywhere -> the loop terminates at the built-in default
      tool-call ceiling (40), not before, not never, with a distinct
      "Hard tool-call ceiling" terminal message.
  (a2) Explicit max_tool_calls param overrides (lowers) the ceiling.
  (a3) AQ_AGENT_MAX_TOOL_CALLS env overrides the ceiling when the param is
       unset (0).
  (b) A tiny wall_budget_s param terminates a loop that would otherwise run
      well past it (guard-evading mock + high tool-call ceiling) with a
      distinct "Hard wall-clock budget" terminal message.
  (b2) AQ_AGENT_WALL_BUDGET_S env overrides the wall budget when the param
       is unset (0.0).
  (c) [covered by a2/a3/b2] the override raises/changes the bound in both
      directions (param and env, for both bounds).
  (d) Existing stagnation guards still fire FIRST when applicable — an
      IDENTICAL-result loop aborts via the pre-existing stagnation guard
      long before either hard bound would trip.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
sys.path.insert(0, str(LOCAL_AGENTS))

# Redirect Phase-E event telemetry to a throwaway file for the whole test run —
# _emit_agent_event re-reads this env var on every call, so setting it once
# before the module's async event-emission tasks fire is sufficient. Keeps the
# real /var/lib/ai-stack telemetry file untouched by this test.
_EVENTS_TMP = tempfile.NamedTemporaryFile(prefix="agent-loop-bounds-events-", suffix=".jsonl", delete=False)
_EVENTS_TMP.close()
os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = _EVENTS_TMP.name

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


def _clear_bound_envs() -> None:
    os.environ.pop("AQ_AGENT_MAX_TOOL_CALLS", None)
    os.environ.pop("AQ_AGENT_WALL_BUDGET_S", None)


def make_executor() -> AgentExecutor:
    """Bare executor instance (bypasses __init__ / real llama.cpp / httpx),
    same construction pattern as the sibling intervention regression tests."""
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None  # skip working-memory prefetch httpx call
    ex.remote_probe_timeout_seconds = 5
    ex._prompt_extensions_cache = None

    reg = MagicMock()
    reg.get_tools_for_model.return_value = [
        {"name": "run_command", "description": "run a shell command"},
        {"name": "edit_file", "description": "edit a file"},
    ]
    reg.tools = {}

    _parse_seq = {"n": 0}

    def _fake_parse(response: str):
        _parse_seq["n"] += 1
        payload = json.loads(response)
        return ToolCall(
            id=f"call-{_parse_seq['n']}",
            tool_name=payload["function"],
            arguments=payload.get("arguments", {}),
        )

    async def _fake_execute(tool_call):
        tool_call.status = "completed"
        tool_call.result = {"success": True, "exit_code": 0, **tool_call.arguments}
        return tool_call

    def _fake_format(tool_call) -> str:
        return json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.parse_tool_call_from_llama.side_effect = _fake_parse
    reg.execute_tool_call = AsyncMock(side_effect=_fake_execute)
    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


def make_evading_call_llama(snapshots: list):
    """Always returns a NEW, successful run_command tool call with a distinct
    argument each turn — evades every stagnation guard (identical-result,
    file-not-found, tool-failure, exploration, observation all key off either
    a fixed tool name unrelated to run_command or an UNCHANGING result) while
    still counting as forward-looking activity. This is exactly the failure
    mode the hard bounds exist to catch: a loop no smart guard will abort."""
    counter = {"n": 0}

    async def _fake_call_llama(messages, **kwargs):
        counter["n"] += 1
        n = counter["n"]
        snapshots.append(n)
        response = json.dumps({
            "function": "run_command",
            "arguments": {"command": f"echo step-{n}"},
        })
        return response, 5

    return AsyncMock(side_effect=_fake_call_llama), counter


def make_evading_slow_call_llama(sleep_s: float, snapshots: list):
    """Same evasion shape as make_evading_call_llama but sleeps `sleep_s`
    per call — used to make real wall-clock time pass deterministically
    (the sleep is a floor, so elapsed time can only be >= expected)."""
    counter = {"n": 0}

    async def _fake_call_llama(messages, **kwargs):
        await asyncio.sleep(sleep_s)
        counter["n"] += 1
        n = counter["n"]
        snapshots.append(n)
        response = json.dumps({
            "function": "run_command",
            "arguments": {"command": f"echo step-{n}"},
        })
        return response, 5

    return AsyncMock(side_effect=_fake_call_llama), counter


def make_identical_result_call_llama():
    """Always the SAME run_command call with the SAME arguments — this is the
    case the pre-existing generic stagnation guard (identical tool+result,
    threshold 5 for non-read_file tools) is designed to catch."""
    async def _fake_call_llama(messages, **kwargs):
        response = json.dumps({
            "function": "run_command",
            "arguments": {"command": "echo always-the-same"},
        })
        return response, 5

    return AsyncMock(side_effect=_fake_call_llama)


# ---------------------------------------------------------------------------
# (a) default hard tool-call ceiling (no override anywhere) = 40
# ---------------------------------------------------------------------------

async def test_default_ceiling_terminates_at_40():
    _clear_bound_envs()
    ex = make_executor()
    task = Task(id="t-default-ceiling", objective="do a bounded thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    ex._call_llama, counter = make_evading_call_llama(snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("terminates at exactly the built-in default ceiling (40 tool calls, 40 LLM calls)",
          counter["n"] == 40)
    check("terminal message names the hard tool-call ceiling and the value 40",
          "Hard tool-call ceiling" in final_msg and "40" in final_msg)
    check("terminal message is distinguishable from a stagnation message",
          "Stagnation" not in final_msg)
    check("task.tool_calls_made recorded exactly 40 completed tool calls",
          len(task.tool_calls_made) == 40)


# ---------------------------------------------------------------------------
# (a2) explicit max_tool_calls param overrides (lowers) the default ceiling
# ---------------------------------------------------------------------------

async def test_param_override_lowers_ceiling():
    _clear_bound_envs()
    ex = make_executor()
    task = Task(id="t-param-override", objective="do a bounded thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    ex._call_llama, counter = make_evading_call_llama(snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=3)

    check("explicit max_tool_calls=3 param is HONORED (not ignored) — terminates at 3, not 40",
          counter["n"] == 3)
    check("terminal message names the overridden ceiling (3)",
          "Hard tool-call ceiling" in final_msg and "3 reached" in final_msg)


# ---------------------------------------------------------------------------
# (a3) AQ_AGENT_MAX_TOOL_CALLS env overrides the ceiling when param is unset
# ---------------------------------------------------------------------------

async def test_env_override_changes_ceiling():
    _clear_bound_envs()
    os.environ["AQ_AGENT_MAX_TOOL_CALLS"] = "4"
    try:
        ex = make_executor()
        task = Task(id="t-env-override", objective="do a bounded thing", status=TaskStatus.RUNNING)
        snapshots: list = []
        ex._call_llama, counter = make_evading_call_llama(snapshots)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        check("AQ_AGENT_MAX_TOOL_CALLS=4 env override applies when param is unset (0) — terminates at 4",
              counter["n"] == 4)
        check("terminal message names the env-overridden ceiling (4)",
              "Hard tool-call ceiling" in final_msg and "4 reached" in final_msg)
    finally:
        _clear_bound_envs()


# ---------------------------------------------------------------------------
# (b) wall-clock budget terminates a loop that would otherwise run
# ---------------------------------------------------------------------------

async def test_wall_clock_budget_terminates_early():
    _clear_bound_envs()
    ex = make_executor()
    task = Task(id="t-wall-budget", objective="do a bounded thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    # 120ms/call floor via real asyncio.sleep; 150ms budget. High tool-call
    # ceiling (1000) proves the WALL-CLOCK bound is what stops the loop, not
    # the tool-call ceiling — the evading mock would happily run to 1000.
    ex._call_llama, counter = make_evading_slow_call_llama(0.12, snapshots)

    final_msg, _tokens = await ex._execute_with_tools(
        task, AgentType.AGENT, max_tool_calls=1000, wall_budget_s=0.15,
    )

    check("terminates well short of the tool-call ceiling (proves wall-clock, not ceiling, fired)",
          0 < counter["n"] < 1000)
    check("terminal message names the wall-clock budget, not the tool-call ceiling",
          "Hard wall-clock budget" in final_msg and "Hard tool-call ceiling" not in final_msg)
    check("terminal message reports the configured budget (0.15s -> rendered as 0s at .0f precision, so check the raw substring)",
          "wall-clock budget" in final_msg)


# ---------------------------------------------------------------------------
# (b2) AQ_AGENT_WALL_BUDGET_S env overrides the wall budget when unset (0.0)
# ---------------------------------------------------------------------------

async def test_env_override_changes_wall_budget():
    _clear_bound_envs()
    os.environ["AQ_AGENT_WALL_BUDGET_S"] = "0.15"
    try:
        ex = make_executor()
        task = Task(id="t-wall-env", objective="do a bounded thing", status=TaskStatus.RUNNING)
        snapshots: list = []
        ex._call_llama, counter = make_evading_slow_call_llama(0.12, snapshots)

        final_msg, _tokens = await ex._execute_with_tools(
            task, AgentType.AGENT, max_tool_calls=1000, wall_budget_s=0.0,
        )

        check("AQ_AGENT_WALL_BUDGET_S=0.15 env override applies when param is unset (0.0)",
              0 < counter["n"] < 1000)
        check("terminal message names the wall-clock budget",
              "Hard wall-clock budget" in final_msg)
    finally:
        _clear_bound_envs()


# ---------------------------------------------------------------------------
# (d) existing stagnation guards still fire FIRST when applicable
# ---------------------------------------------------------------------------

async def test_stagnation_guard_still_fires_before_hard_ceiling():
    _clear_bound_envs()
    ex = make_executor()
    task = Task(id="t-stagnation-first", objective="do a bounded thing", status=TaskStatus.RUNNING)
    ex._call_llama = make_identical_result_call_llama()

    # Default ceiling (40) is far above where the identical-result stagnation
    # guard (threshold 5 for non-read_file tools) fires — proves the smart
    # guard preempts the dumb backstop rather than the other way round.
    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("identical-result loop is caught by the pre-existing stagnation guard, not the hard ceiling",
          "Stagnation detected" in final_msg)
    check("stagnation abort happens well before the default hard ceiling (40) would ever trip",
          len(task.tool_calls_made) < 40)
    check("stagnation abort happens at the documented threshold (5 for non-read_file tools)",
          len(task.tool_calls_made) == 5)


async def main():
    await test_default_ceiling_terminates_at_40()
    await test_param_override_lowers_ceiling()
    await test_env_override_changes_ceiling()
    await test_wall_clock_budget_terminates_early()
    await test_env_override_changes_wall_budget()
    await test_stagnation_guard_still_fires_before_hard_ceiling()

    _clear_bound_envs()
    try:
        os.unlink(_EVENTS_TMP.name)
    except OSError:
        pass

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
