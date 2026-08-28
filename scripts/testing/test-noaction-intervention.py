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


def make_call_llama_mock(responses: list, snapshots: list, call_kwargs: list | None = None):
    """Returns responses in sequence (last one repeats if exhausted); records
    a shallow copy of `messages` on every call."""
    async def _fake_call_llama(messages, **kwargs):
        snapshots.append(list(messages))
        if call_kwargs is not None:
            call_kwargs.append(dict(kwargs))
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


async def test_dogfood_budget_only_constrains_initial_call():
    """The 192-token cap is exact opt-in and does not alter later turns."""
    ex = make_executor()
    task = Task(id="t-dogfood-budget", objective="fix retry", status=TaskStatus.RUNNING)
    snapshots, call_kwargs = [], []
    ex._call_llama = make_call_llama_mock(
        [edit_call_json(), "COMPLETED: edit applied."], snapshots, call_kwargs
    )
    with patch.dict(os.environ, {"AQ_LOCAL_DOGFOOD_BUDGET": "1"}):
        await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)
    check("dogfood first call uses the 192-token cap",
          call_kwargs[0]["max_tokens"] == ae._DOGFOOD_FIRST_CALL_MAX_TOKENS)
    check("dogfood post-tool turn keeps the normal task budget",
          call_kwargs[1]["max_tokens"] == ae.AGENT_TASK_MAX_TOKENS)

    ex = make_executor()
    snapshots, call_kwargs = [], []
    ex._call_llama = make_call_llama_mock([PROSE_PLAN], snapshots, call_kwargs)
    await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)
    check("non-dogfood first call keeps the normal tool-call budget",
          call_kwargs[0]["max_tokens"] == ae.AGENT_TOOL_CALL_MAX_TOKENS)


async def test_dogfood_gbnf_repair_budget_is_unchanged():
    """Dogfood's first-call cap must not shrink grammar repair or synthesis."""
    ex = make_executor()
    task = Task(id="t-dogfood-gbnf", objective="fix retry", status=TaskStatus.RUNNING)
    snapshots, call_kwargs = [], []
    malformed = '{"function":"edit_file","arguments":{"old_string":"' + ("x" * 100)
    ex._call_llama = make_call_llama_mock(
        [malformed, "still malformed", "COMPLETED: rejected malformed call."], snapshots, call_kwargs
    )
    with patch.dict(os.environ, {"AQ_LOCAL_DOGFOOD_BUDGET": "1"}), patch.object(
        ae, "_LOCAL_GBNF_REPAIR_ENABLED", True
    ):
        await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)
    check("dogfood GBNF repair keeps the normal repair budget",
          call_kwargs[1]["max_tokens"] == ae.AGENT_TOOL_CALL_MAX_TOKENS)
    check("dogfood malformed synthesis keeps its 256-token budget",
          call_kwargs[2]["max_tokens"] == 256)


async def test_dogfood_payload_receipt_rejects_before_http_without_raw_content():
    """Oversized opt-in payloads emit counts only and never enter HTTP transport."""
    ex = make_executor()
    messages = [{"role": "system", "content": "secret-prompt-" + ("x" * 15_000)}]
    with tempfile.TemporaryDirectory() as tmp:
        progress = Path(tmp) / "progress.json"
        with patch.dict(os.environ, {
            "AQ_LOCAL_DOGFOOD_BUDGET": "1",
            # Pin the fail-closed ceiling explicitly instead of relying on the module default,
            # so this probe stays valid when the default limit is retuned (it was raised
            # 14_000 -> 32_000, which had silently disabled this test's rejection path).
            "AQ_DOGFOOD_PAYLOAD_JSON_LIMIT": "8000",
            "AGENT_PROGRESS_FILE": str(progress),
            "LLAMA_USE_STREAMING": "1",
        }):
            try:
                await ex._call_llama(messages, max_tokens=77, task_type="caller-private-type", call_number=9)
                rejected = False
            except RuntimeError as exc:
                rejected = "before HTTP" in str(exc)
        receipt_doc = progress.read_text(encoding="utf-8")
        receipt = json.loads(receipt_doc)["payload_budget"]
    required = {"budget_mode", "call_number", "task_type_class", "system_unicode_chars",
                "non_system_unicode_chars", "tools_unicode_chars", "grammar_unicode_chars",
                "payload_json_unicode_chars", "estimated_tokens", "max_tokens"}
    check("dogfood oversized payload fails before HTTP", rejected)
    check("dogfood receipt has deterministic count-only fields",
          set(receipt) == required and receipt["call_number"] == 9 and receipt["max_tokens"] == 77
          and receipt["task_type_class"] == "unknown"
          # exceeded the pinned AQ_DOGFOOD_PAYLOAD_JSON_LIMIT (8000) set above, so the
          # before-HTTP rejection was legitimate rather than spurious
          and receipt["payload_json_unicode_chars"] > 8000)
    check("dogfood receipt does not leak raw task or prompt content",
          "secret-prompt-" not in receipt_doc and "caller-private-type" not in receipt_doc)


def test_dogfood_receipt_counts_grammar_without_content():
    payload = {"messages": [{"role": "user", "content": "hello"}], "tools": [{"name": "read"}],
               "grammar": "root ::= \"tool\"", "max_tokens": 192}
    receipt = ae._dogfood_payload_budget_receipt(payload, task_type="agent", call_number=1)
    check("dogfood receipt counts tools and grammar", receipt["tools_unicode_chars"] > 0 and receipt["grammar_unicode_chars"] > 0)
    check("dogfood receipt carries no raw grammar", "root ::= " not in json.dumps(receipt))
    unicode_payload = {"messages": [{"role": "user", "content": "é"}], "max_tokens": 1}
    unicode_receipt = ae._dogfood_payload_budget_receipt(unicode_payload, task_type="code", call_number=2)
    check("dogfood payload budget counts Unicode characters, not UTF-8 bytes",
          unicode_receipt["non_system_unicode_chars"] == 1
          and unicode_receipt["payload_json_unicode_chars"] == len(json.dumps(
              unicode_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
          )))


def test_self_improvement_prompt_classifier_is_semantic():
    ex = make_executor()
    tools = [{"name": "read_file", "parameters": {"type": "object", "properties": {}}}]
    bounded = ex._get_system_prompt(
        AgentType.AGENT,
        tools,
        objective_hint="bounded one-file test improvement slice",
    )
    explicit = ex._get_system_prompt(
        AgentType.AGENT,
        tools,
        objective_hint="run a self-improvement slice for an open issue",
    )
    check("ordinary bounded slices omit the backlog workflow",
          "SELF-IMPROVEMENT SLICE" not in bounded)
    check("explicit self-improvement work retains the backlog workflow",
          "SELF-IMPROVEMENT SLICE" in explicit)


def test_short_context_prune_finds_pair_after_extra_system_context():
    messages = [
        {"role": "system", "content": "contract"},
        {"role": "user", "content": "task"},
        {"role": "system", "content": "projected context"},
        {"role": "assistant", "content": "old read"},
        {"role": "tool", "content": "old result"},
        {"role": "assistant", "content": "latest read"},
        {"role": "tool", "content": "latest result"},
    ]
    pruned, changed = ae._shed_oldest_assistant_tool_pair(messages)
    check("short-context pruning locates the first complete pair", changed)
    check("short-context pruning preserves projected system context",
          pruned[:3] == messages[:3])
    check("short-context pruning preserves the latest assistant/tool pair",
          pruned[-2:] == messages[-2:] and len(pruned) == 5)


async def test_midtask_loading_recovery_replays_only_after_ready():
    """A 502 followed by the explicit loading 503 waits and replays once."""
    ex = make_executor()
    task = Task(
        id="t-midtask-reload", objective="summarize the bounded evidence",
        task_type="analysis", status=TaskStatus.RUNNING,
    )
    calls: list[dict] = []

    async def _fake_call(_messages, **kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise Exception('llama.cpp error: 502 {"error":{"message":"upstream disconnected"}}')
        if len(calls) == 2:
            raise Exception('llama.cpp error: 503 {"error":{"message":"Loading model"}}')
        return "COMPLETED: model recovered.", 9

    ex._call_llama = AsyncMock(side_effect=_fake_call)
    ex._local_model_is_ready = AsyncMock(side_effect=[False, True])
    with patch.object(ae.asyncio, "sleep", new=AsyncMock()):
        result, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("mid-task reload makes exactly one replay after the existing retry",
          ex._call_llama.await_count == 3 and result == "COMPLETED: model recovered.")
    check("mid-task reload polls through not-ready then ready",
          ex._local_model_is_ready.await_count == 2)
    check("mid-task replay preserves the reduced retry request unchanged",
          calls[1] == calls[2])
    check("mid-task reload wait is fixed and bounded at 120 seconds",
          ae._LOCAL_MODEL_LOADING_RETRY_TIMEOUT_SECONDS <= 120.0)


async def test_midtask_nonloading_503_remains_terminal():
    """Only the exact local loading response is recoverable."""
    ex = make_executor()
    task = Task(id="t-midtask-nonloading", objective="make the bounded edit", status=TaskStatus.RUNNING)
    ex._call_llama = AsyncMock(side_effect=[
        Exception('llama.cpp error: 502 {"error":{"message":"upstream disconnected"}}'),
        Exception('llama.cpp error: 503 {"error":{"message":"capacity exhausted"}}'),
    ])
    ex._local_model_is_ready = AsyncMock()

    try:
        await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)
        terminal = False
    except Exception as exc:
        terminal = "503" in str(exc) and "capacity exhausted" in str(exc)
    check("non-loading 503 remains terminal", terminal)
    check("non-loading 503 does not poll local readiness",
          ex._local_model_is_ready.await_count == 0)


async def test_midtask_reload_wait_respects_smaller_wall_remainder():
    """The fixed 120s recovery window cannot outlive the enclosing task budget."""
    ex = make_executor()
    probe_timeouts: list[float] = []

    async def _not_ready(timeout_seconds):
        probe_timeouts.append(timeout_seconds)
        return False

    ex._local_model_is_ready = AsyncMock(side_effect=_not_ready)
    sleep = AsyncMock()
    with patch.object(ae.time, "monotonic", side_effect=[0.0, 0.0, 0.3]), patch.object(
        ae.asyncio, "sleep", new=sleep
    ):
        ready = await ex._wait_for_local_model_ready(0.25)

    check("smaller task-wall remainder bounds total reload wait", not ready)
    check("each readiness probe is capped by the remaining wait budget",
          probe_timeouts == [0.25])
    check("a slow final probe cannot sleep past its consumed deadline",
          sleep.await_count == 0)


async def test_midtask_switchboard_readiness_requires_direct_llama_url():
    """A switchboard 200 is not evidence that the local model is loaded."""
    ex = make_executor()
    ex.llama_endpoint = "http://switchboard.example"
    with patch.dict(os.environ, {
        "SWITCHBOARD_URL": "http://switchboard.example",
        "LLAMA_URL": "http://llama.example",
    }):
        direct_endpoint = ex._local_model_health_endpoint()
    with patch.dict(os.environ, {"SWITCHBOARD_URL": "http://switchboard.example"}, clear=True):
        no_direct_endpoint = ex._local_model_health_endpoint()
        false_ready = await ex._local_model_is_ready(1.0)

    check("switchboard-routed reload probes canonical direct LLAMA_URL",
          direct_endpoint == "http://llama.example")
    check("switchboard aggregate health cannot create false model readiness",
          no_direct_endpoint is None and not false_ready)


async def main():
    test_retry_excerpt_contract()
    await test_prose_plan_then_edit_completes()
    await test_prose_twice_still_completes()
    await test_retry_response_is_bounded()
    await test_malformed_tool_retry_paths_and_training_capture()
    await test_kill_switch_restores_immediate_completion()
    await test_refusal_is_never_intervened_on()
    await test_dogfood_budget_only_constrains_initial_call()
    await test_dogfood_gbnf_repair_budget_is_unchanged()
    await test_dogfood_payload_receipt_rejects_before_http_without_raw_content()
    test_dogfood_receipt_counts_grammar_without_content()
    test_self_improvement_prompt_classifier_is_semantic()
    test_short_context_prune_finds_pair_after_extra_system_context()
    await test_midtask_loading_recovery_replays_only_after_ready()
    await test_midtask_nonloading_503_remains_terminal()
    await test_midtask_reload_wait_respects_smaller_wall_remainder()
    await test_midtask_switchboard_readiness_requires_direct_llama_url()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
