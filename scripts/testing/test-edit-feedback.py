#!/usr/bin/env python3
"""
Regression test for the EDIT-FAILURE FEEDBACK intervention (2026-08-20).

Root cause this guards against: with the tool-call grammar fixed, the local
(Qwen) agent now reliably emits valid `edit_file` tool calls — but a 12-task
dogfood run showed ~80% of tasks still failing because `edit_file` fails on
an `old_string` byte-mismatch (the model paraphrases, or reconstructs
old_string from a partial view of the file) and then blindly retries the
SAME mismatch until the task hits its time cap. Example: 1 edit_file
attempt, 3 mismatch failures, no edit landed.

Fix under test (agent_executor.py, `_execute_with_tools`, the
`elif result.tool_name in ("edit_file", "write_file")` branch): on the
FIRST `old_string`-mismatch failure for a given target file, instead of
returning the plain failure, inject the file's EXACT current text for the
region the model was trying to edit as the tool result (role:"tool") with
instructions to copy an exact substring as the retry old_string. Bounded to
`_EDIT_FEEDBACK_MAX_PER_FILE` (default 2) fires per file so a persistently-
failing edit still eventually ends via the existing tool-failure-stagnation
guard rather than looping forever.

This drives the real `_execute_with_tools` tool-use loop with `_call_llama`
and `tool_registry` mocked out (same harness pattern as
test-reread-intervention.py / test-noaction-intervention.py) against a REAL
temp file on disk, so `_build_edit_mismatch_feedback` reads real content —
the assertions exercise the actual control flow, not just static string
presence in the source.

Coverage:
  1. Turn-1 edit_file with a NON-matching old_string -> mismatch failure ->
     the loop injects exact-content feedback (role:"tool", contains the
     real file text AND "retry") instead of the bare failure.
  2. Turn-2 edit_file with a byte-matching old_string (copied from the
     feedback) -> succeeds -> task completes normally (no abort).
  3. Feedback fires at most `_EDIT_FEEDBACK_MAX_PER_FILE` times for a file
     that never produces a matching old_string — the loop does not inject
     feedback forever; it eventually aborts via the pre-existing
     tool-failure-stagnation guard.
  4. AQ_EDIT_FEEDBACK=0 (kill switch) restores the plain-failure behavior —
     no exact-region feedback is ever injected.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
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

REAL_FILE_CONTENT = (
    "def process_data(items):\n"
    "    result = []\n"
    "    for item in items:\n"
    "        if item.is_valid():\n"
    "            result.append(item.value)\n"
    "    return result\n"
)
# Byte-matching anchor — an exact substring of the real file.
MATCHING_OLD_STRING = "        if item.is_valid():\n            result.append(item.value)"
# Paraphrased / partial-view reconstruction — NOT a byte-match.
MISMATCH_OLD_STRING = "for item in items:\n    if item.is_valid:\n        result.append(item.value())"

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


def feedback_msgs_in_final_state(snapshots: list) -> list:
    """Count feedback occurrences in the FINAL snapshot only.

    `snapshots` records `messages` (by reference-copy) at the START of every
    `_call_llama` invocation. Because `messages` only ever grows (nothing is
    removed), a message injected once persists into every snapshot recorded
    AFTER it — summing occurrences across all snapshots multiplies a single
    injected message by however many turns follow it. The final snapshot is
    the superset of every prior one, so it alone reflects how many times a
    given message was actually added to the conversation.
    """
    if not snapshots:
        return []
    return [
        m for m in snapshots[-1]
        if m.get("role") == "tool" and "edit_file FAILED" in (m.get("content") or "")
    ]


def make_target_file(tmp_dir: Path) -> str:
    p = tmp_dir / "target.py"
    p.write_text(REAL_FILE_CONTENT, encoding="utf-8")
    return str(p)


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
        {"name": "edit_file", "description": "edit a file"},
    ]
    reg.tools = {}

    def _fake_format(tool_call) -> str:
        import json as _json
        return _json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


def make_mismatch_then_match_mocks(ex: AgentExecutor, target_path: str, snapshots: list):
    """Turn 1: mismatch old_string. Turn 2: matching old_string. Turn 3: prose completion."""
    _call_seq = {"n": 0}

    def _fake_parse(_response: str):
        _call_seq["n"] += 1
        n = _call_seq["n"]
        if n == 1:
            return ToolCall(
                id="call-1", tool_name="edit_file",
                arguments={
                    "file_path": target_path,
                    "old_string": MISMATCH_OLD_STRING,
                    "new_string": "REPLACED-1",
                },
            )
        if n == 2:
            return ToolCall(
                id="call-2", tool_name="edit_file",
                arguments={
                    "file_path": target_path,
                    "old_string": MATCHING_OLD_STRING,
                    "new_string": "        if item.is_valid():\n            result.append(item.value * 2)",
                },
            )
        return None  # turn 3: prose completion, no tool call

    async def _fake_call_llama(messages, **kwargs):
        snapshots.append(list(messages))
        n = _call_seq["n"] + 1
        if n <= 2:
            return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
        return "COMPLETED: applied the fix after correcting old_string.", 10

    ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
    ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_execute_for(target_path))
    ex._call_llama = AsyncMock(side_effect=_fake_call_llama)


def make_execute_for(target_path: str):
    async def _exec(tool_call):
        tool_call.status = "completed"
        content = Path(target_path).read_text(encoding="utf-8")
        old = tool_call.arguments.get("old_string", "")
        if old and old in content:
            new = tool_call.arguments.get("new_string", "")
            Path(target_path).write_text(content.replace(old, new, 1), encoding="utf-8")
            tool_call.result = {"success": True, "replacements": 1}
        else:
            snippet = content[:400]
            tool_call.result = {
                "success": False,
                "error": f"old_string not found in {target_path}. File starts with:\n{snippet}",
            }
        return tool_call
    return _exec


async def test_mismatch_then_match_completes():
    """(1) + (2): mismatch injects exact-content feedback; matching retry completes."""
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td))
        ex = make_executor()
        task = Task(id="t-edit-feedback", objective="fix the thing", status=TaskStatus.RUNNING)
        snapshots: list = []
        make_mismatch_then_match_mocks(ex, target_path, snapshots)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        feedback_tool_msgs = feedback_msgs_in_final_state(snapshots)
        check("feedback delivered as role:'tool' message", len(feedback_tool_msgs) >= 1)
        check("feedback contains the real file's exact current text",
              all("if item.is_valid():" in m["content"] for m in feedback_tool_msgs))
        check("feedback message instructs a retry",
              all("retry" in m["content"].lower() for m in feedback_tool_msgs))
        check("feedback fires exactly once for this file", len(feedback_tool_msgs) == 1)
        check("task completes (no abort) after the matching retry",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())
        check("completion prose reflects the fix",
              "COMPLETED" in final_msg or "applied the fix" in final_msg)

        final_content = Path(target_path).read_text(encoding="utf-8")
        check("the matching-old_string edit actually landed on disk",
              "item.value * 2" in final_content)


async def test_feedback_bounded_per_file():
    """(3): a file that never produces a matching old_string gets feedback at
    most _EDIT_FEEDBACK_MAX_PER_FILE times, then falls through to plain
    failures until the pre-existing tool-failure-stagnation guard aborts."""
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td))
        ex = make_executor()
        task = Task(id="t-edit-feedback-bounded", objective="fix the thing", status=TaskStatus.RUNNING)
        snapshots: list = []

        def _fake_parse(_response: str):
            return ToolCall(
                id="call-mismatch", tool_name="edit_file",
                arguments={
                    "file_path": target_path,
                    "old_string": MISMATCH_OLD_STRING,
                    "new_string": "REPLACED",
                },
            )

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_execute_for(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        feedback_tool_msgs = feedback_msgs_in_final_state(snapshots)
        check(
            f"feedback fires at most {ae._EDIT_FEEDBACK_MAX_PER_FILE} times for a persistently-failing file",
            len(feedback_tool_msgs) <= ae._EDIT_FEEDBACK_MAX_PER_FILE,
        )
        check("feedback fires at least once before the guard takes over", len(feedback_tool_msgs) >= 1)
        check("the loop eventually ends (never loops forever) via the pre-existing failure guard",
              "Aborting" in final_msg or "stagnation" in final_msg.lower())


async def test_kill_switch_restores_plain_failure():
    """(4): AQ_EDIT_FEEDBACK=0 restores plain-failure behavior — no feedback injected."""
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td))
        ex = make_executor()
        task = Task(id="t-edit-feedback-killswitch", objective="fix the thing", status=TaskStatus.RUNNING)
        snapshots: list = []
        make_mismatch_then_match_mocks(ex, target_path, snapshots)

        with patch.object(ae, "_EDIT_FEEDBACK_ENABLED", False):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        feedback_tool_msgs = feedback_msgs_in_final_state(snapshots)
        check("kill switch: no exact-region feedback ever injected", len(feedback_tool_msgs) == 0)
        # The mismatch-then-match script still ultimately succeeds (turn 2 matches,
        # turn 3 completes) — the kill switch only removes the FEEDBACK, not the
        # model's own eventual correct retry.
        check("kill switch: task still completes normally on its own matching retry",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())


async def main():
    await test_mismatch_then_match_completes()
    await test_feedback_bounded_per_file()
    await test_kill_switch_restores_plain_failure()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
