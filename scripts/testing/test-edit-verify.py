#!/usr/bin/env python3
"""
Regression test for the POST-EDIT VERIFY-AND-COACH gate (2026-08-25).

issues-backlog: local-correctness-baseline-and-verify-gate. Governing value:
CLAUDE.md Rule 21 (collaborative stewardship — help local reach its best
self). This is STEWARDSHIP scaffolding, not a punitive gate.

Root cause this guards against: with the tool-call grammar and edit-feedback
fixes landed, local now RELIABLY LANDS edits — but measured dogfood runs show
~0 of those landed edits are actually CORRECT. Two dominant failure modes:
  1. DEAD CODE — local adds a new function/branch (e.g.
     `_gemini_cooldown_status()`) but never wires it in / calls it anywhere
     else in the file. The edit "looks" like a fix but changes no behavior
     on the live path.
  2. NO-OP — local edits only a comment or whitespace, no behavioral change,
     doesn't fix the issue.

Fix under test (agent_executor.py, `_execute_with_tools`, the
`elif result.tool_name in ("edit_file", "write_file", "write_region")`
branch, guarded by `_EDIT_VERIFY_ENABLED`): after a successful edit lands,
run the cheap STATIC checks in `_verify_edit_quality` (no LLM, no test run)
on that edit's diff. A failing check injects SPECIFIC coaching as the next
tool result (role:"tool") and `continue`s the loop instead of counting the
edit toward `_edits_made`, bounded to `_EDIT_VERIFY_MAX_PER_FILE` fires per
file (mirrors the `_EDIT_FEEDBACK_ENABLED` one-shot pattern) so a
persistently-trivial edit still eventually passes through rather than
looping forever.

This drives the real `_execute_with_tools` tool-use loop with `_call_llama`
and `tool_registry` mocked out (same harness pattern as
test-edit-feedback.py / test-reread-intervention.py) against REAL temp files
on disk, so `_verify_edit_quality` reads real post-edit content — the
assertions exercise the actual control flow, not just static string
presence in the source.

Coverage:
  (a) A comment/whitespace-only edit_file call triggers the no-op coach
      (role:"tool", names the reason) and the loop continues instead of
      completing.
  (b) A real behavioral edit_file call passes clean — no coaching message is
      ever injected, and the edit counts toward `_edits_made`.
  (c) An edit_file call that ADDS a new function but never calls it anywhere
      else in the file triggers the dead-code coach, naming the function.
  (d) An edit_file call that adds a new function AND calls it in the same
      edit passes clean (referenced, not dead).
  (e) Coaching fires at most `_EDIT_VERIFY_MAX_PER_FILE` times for a file
      whose edits never stop being trivial — the loop does not coach
      forever; it eventually falls through and ends normally.
  (f) AQ_EDIT_VERIFY=0 (kill switch) restores the plain accept-on-success
      behavior — no coaching is ever injected, even for a comment-only edit.

THIRD failure mode — LINT / name-resolution (issues-backlog:
local-edit-third-failure-mode-undefined-name): an edit that PARSES fine and
isn't dead code but still crashes at runtime (e.g. `re.match(...)` used with
no `import re`). Added to `_verify_edit_quality` via `_lint_check_edited_file`
+ `_lint_diff_python` / `_lint_diff_shell` (pyflakes/`bash -n`+shellcheck,
diffed against the pre-edit file so only NEW breakage is coached, never
pre-existing lint debt).
  (g) An edit adding `re.match(...)` to a file with no `import re` triggers
      the lint coach, naming `re` and suggesting the import fix. pyflakes's
      actual undefined-name detection is MOCKED (`ae._pyflakes_messages`) so
      this test is deterministic regardless of whether pyflakes happens to be
      installed on the box running it (it is not, in this repo's Nix
      environment — see (k) for the real, unmocked fallback path).
  (h) The same shape of edit in a file that already has `import re` passes
      clean — zero coaching.
  (i) A pre-existing lint issue elsewhere in the file, untouched by the edit,
      is never flagged — only issues the edit itself introduces are coached.
  (j) A bash (.sh) file where the edit introduces a real syntax error (an
      `if` with no matching `fi`) is flagged via the REAL `bash -n` subprocess
      (no mocking — bash is always present) naming the break.
  (k) Fail-safe: with pyflakes AND shellcheck both simulated absent
      (`_pyflakes_messages`/`_shellcheck_error_messages` return None, the real
      "unavailable" sentinel), the lint check degrades to compile-only syntax
      checking — a genuine SyntaxError is still coached, and the loop never
      crashes either way.
"""
from __future__ import annotations

import asyncio
import importlib.util
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


def coach_msgs_in_final_state(snapshots: list) -> list:
    """Count edit-verify coaching occurrences in the FINAL snapshot only.

    `snapshots` records `messages` (by reference-copy) at the START of every
    `_call_llama` invocation. Because `messages` only ever grows, the final
    snapshot is the superset of every prior one — summing across all
    snapshots would multiply a single injected message by however many turns
    follow it.
    """
    if not snapshots:
        return []
    return [
        m for m in snapshots[-1]
        if m.get("role") == "tool"
        and ("does not change the program's behavior" in (m.get("content") or "")
             or "dead code" in (m.get("content") or "")
             or "not imported/defined" in (m.get("content") or "")
             or "will break the file" in (m.get("content") or ""))
    ]


def make_target_file(tmp_dir: Path, content: str) -> str:
    p = tmp_dir / "target.py"
    p.write_text(content, encoding="utf-8")
    return str(p)


def make_target_file_named(tmp_dir: Path, name: str, content: str) -> str:
    p = tmp_dir / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def make_executor() -> AgentExecutor:
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None
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


def make_edit_exec(target_path: str):
    """Real edit_file-shaped executor: replaces old_string with new_string on
    the real temp file, mirroring builtin_tools/file_operations.py exactly
    (first occurrence, fails if old_string absent)."""
    async def _exec(tool_call):
        tool_call.status = "completed"
        content = Path(target_path).read_text(encoding="utf-8")
        old = tool_call.arguments.get("old_string", "")
        new = tool_call.arguments.get("new_string", "")
        if old and old in content:
            Path(target_path).write_text(content.replace(old, new, 1), encoding="utf-8")
            tool_call.result = {"success": True, "replacements": 1}
        else:
            tool_call.result = {"success": False, "error": f"old_string not found in {target_path}"}
        return tool_call
    return _exec


def make_edit_call(call_id: str, target_path: str, old_string: str, new_string: str) -> ToolCall:
    return ToolCall(
        id=call_id, tool_name="edit_file",
        arguments={"file_path": target_path, "old_string": old_string, "new_string": new_string},
    )


async def test_noop_edit_triggers_coach_then_real_fix_completes():
    """(a): a comment-only edit triggers the no-op coach + retry; a real
    behavioral retry afterward completes normally."""
    initial = (
        "def process(items):\n"
        "    # TODO: handle empty input\n"
        "    return [i for i in items if i]\n"
    )
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-noop", objective="fix process() to also strip whitespace", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            if n == 1:
                # Comment/whitespace-only change — no behavioral difference.
                return make_edit_call(
                    "call-1", target_path,
                    "    # TODO: handle empty input",
                    "    # TODO: handle empty input and whitespace",
                )
            if n == 2:
                # Real behavioral fix.
                return make_edit_call(
                    "call-2", target_path,
                    "    return [i for i in items if i]",
                    "    return [i.strip() for i in items if i and i.strip()]",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            n = calls["n"] + 1
            if n <= 2:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: fixed process() to strip whitespace.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("no-op coach delivered as role:'tool' message", len(coach_msgs) >= 1)
        check("no-op coach names the comment/whitespace-only problem",
              any("comment" in m["content"].lower() for m in coach_msgs))
        check("no-op coach fires exactly once (real fix follows immediately)", len(coach_msgs) == 1)
        check("task completes (no abort) after the real fix",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())

        final_content = Path(target_path).read_text(encoding="utf-8")
        check("the real behavioral edit actually landed on disk",
              "i.strip()" in final_content)


async def test_real_edit_passes_clean():
    """(b): a genuine behavioral edit_file call is accepted with zero
    coaching — the verify gate must not false-positive on real fixes."""
    initial = "def add(a, b):\n    return a + b\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-real-edit", objective="fix add() to also accept a default for b", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_edit_call(
                    "call-1", target_path,
                    "def add(a, b):",
                    "def add(a, b=0):",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            if calls["n"] < 1:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: added default for b.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("no coaching injected for a real behavioral edit", len(coach_msgs) == 0)
        check("task completes normally", "COMPLETED" in final_msg or "added default" in final_msg)
        check("the edit landed on disk", "a, b=0" in Path(target_path).read_text(encoding="utf-8"))


async def test_dead_code_added_def_triggers_coach():
    """(c): adding a new function that's never called elsewhere in the file
    triggers the dead-code coach, naming the function."""
    initial = "def handle(event):\n    return event\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-dead-code", objective="add cooldown handling to handle()", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            if n == 1:
                # Adds a new function but never calls it anywhere.
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(event):\n    return event\n",
                    "def handle(event):\n    return event\n\n\ndef _cooldown_status():\n    return True\n",
                )
            if n == 2:
                # Wires the new function into the live path.
                return make_edit_call(
                    "call-2", target_path,
                    "def handle(event):\n    return event\n",
                    "def handle(event):\n    if _cooldown_status():\n        return None\n    return event\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            n = calls["n"] + 1
            if n <= 2:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: wired cooldown status into handle().", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("dead-code coach delivered as role:'tool' message", len(coach_msgs) >= 1)
        check("dead-code coach names the unreferenced function",
              any("_cooldown_status" in m["content"] for m in coach_msgs))
        check("dead-code coach says nothing calls it",
              any("nothing calls it" in m["content"] for m in coach_msgs))
        check("task completes after wiring the function in",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())


async def test_referenced_def_passes_clean():
    """(d): adding a function AND calling it in the SAME edit is not dead
    code — must pass with zero coaching."""
    initial = "def handle(event):\n    return event\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-referenced-def", objective="add cooldown handling to handle()", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(event):\n    return event\n",
                    "def _cooldown_status():\n    return True\n\n\n"
                    "def handle(event):\n    if _cooldown_status():\n        return None\n    return event\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            if calls["n"] < 1:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: added cooldown status check.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("no coaching injected — the added function IS called", len(coach_msgs) == 0)
        check("task completes normally", "COMPLETED" in final_msg or "cooldown" in final_msg)


async def test_coaching_bounded_per_file():
    """(e): a file whose edits never stop being trivial (no-op) gets coached
    at most _EDIT_VERIFY_MAX_PER_FILE times, then falls through and the loop
    ends normally rather than coaching forever."""
    initial = "def handle(event):\n    # placeholder\n    return event\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-bounded", objective="fix handle() to validate event", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            # Every turn is a distinct comment-only edit (always trivial) so the
            # gate would coach forever if it weren't bounded.
            return make_edit_call(
                f"call-{n}", target_path,
                "    # placeholder" if n == 1 else f"    # placeholder v{n - 1}",
                f"    # placeholder v{n}",
            )

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=8)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check(
            f"coaching fires at most {ae._EDIT_VERIFY_MAX_PER_FILE} times for a persistently-trivial file",
            len(coach_msgs) <= ae._EDIT_VERIFY_MAX_PER_FILE,
        )
        check("coaching fires at least once before falling through", len(coach_msgs) >= 1)
        check("the loop terminates (bounded max_tool_calls, never hangs)", isinstance(final_msg, str))


async def test_lint_undefined_name_triggers_coach():
    """(g): an edit that adds `re.match(...)` to a file with no `import re`
    triggers the lint coach, naming `re`. pyflakes is mocked via
    `ae._pyflakes_messages` (see module docstring) so this is deterministic
    regardless of whether pyflakes happens to be installed."""
    initial = "def handle(value):\n    return value\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-lint-undef", objective="reject blank values in handle()", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            if n == 1:
                # Uses re.match with no import anywhere in the file — undefined name.
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(value):\n    return value\n",
                    "def handle(value):\n    if re.match(r'^\\s*$', value):\n        return None\n    return value\n",
                )
            if n == 2:
                # Fix: add the missing import.
                return make_edit_call(
                    "call-2", target_path,
                    "def handle(value):\n    if re.match",
                    "import re\n\n\ndef handle(value):\n    if re.match",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            n = calls["n"] + 1
            if n <= 2:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: rejected blank values with re.match and imported re.", 10

        def _fake_pyflakes(content, _label):
            # Mirrors real pyflakes: undefined-name finding iff `re` is used
            # without an `import re` anywhere in the content being checked.
            return ["undefined name 're'"] if "re.match" in content and "import re" not in content else []

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        with patch.object(ae, "_pyflakes_messages", side_effect=_fake_pyflakes):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("lint coach delivered as role:'tool' message", len(coach_msgs) >= 1)
        check("lint coach names the undefined `re`", any("`re`" in m["content"] for m in coach_msgs))
        check("lint coach suggests the fix (add import)",
              any("import re" in m["content"] for m in coach_msgs))
        check("task completes after the import is added",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())
        check("the import fix actually landed on disk",
              "import re" in Path(target_path).read_text(encoding="utf-8"))


async def test_lint_clean_when_import_present():
    """(h): the same shape of edit in a file that already has `import re`
    passes clean — zero coaching."""
    initial = "import re\n\n\ndef handle(value):\n    return value\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-lint-clean", objective="reject blank values in handle()", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(value):\n    return value\n",
                    "def handle(value):\n    if re.match(r'^\\s*$', value):\n        return None\n    return value\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            if calls["n"] < 1:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: rejected blank values with re.match.", 10

        def _fake_pyflakes(_content, _label):
            return []  # import re already present — nothing undefined

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        with patch.object(ae, "_pyflakes_messages", side_effect=_fake_pyflakes):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("no lint coaching when re is already imported", len(coach_msgs) == 0)
        check("task completes normally", "COMPLETED" in final_msg or "re.match" in final_msg)
        check("the edit landed on disk", "re.match" in Path(target_path).read_text(encoding="utf-8"))


async def test_lint_ignores_preexisting_issue():
    """(i): a pre-existing lint issue elsewhere in the file, untouched by the
    edit, is never flagged — only NEW issues the edit itself introduces."""
    initial = (
        "def helper():\n"
        "    return unknown_var\n\n\n"
        "def handle(value):\n"
        "    return value\n"
    )
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-lint-preexisting", objective="make handle() return a default for empty input", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            if calls["n"] == 1:
                # Real behavioral edit, unrelated to helper()'s pre-existing bug.
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(value):\n    return value\n",
                    "def handle(value):\n    return value if value else 'default'\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            if calls["n"] < 1:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: added default fallback in handle().", 10

        def _fake_pyflakes(content, _label):
            # The pre-existing bug is present in BOTH pre- and post-edit content
            # (the edit never touches helper()) — same finding count both sides.
            return ["undefined name 'unknown_var'"] if "unknown_var" in content else []

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        with patch.object(ae, "_pyflakes_messages", side_effect=_fake_pyflakes):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("pre-existing (untouched) lint issue is never flagged", len(coach_msgs) == 0)
        check("task completes normally", "COMPLETED" in final_msg or "default" in final_msg)


async def test_lint_shell_syntax_error_introduced():
    """(j): a bash file where the edit introduces a real syntax error (an
    `if` with no matching `fi`) is flagged via the REAL `bash -n` subprocess
    — no mocking, bash is always present."""
    initial = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        "greet() {\n"
        "  echo \"hello\"\n"
        "}\n\n"
        "greet\n"
    )
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file_named(Path(td), "target.sh", initial)
        ex = make_executor()
        task = Task(id="t-lint-shell", objective="make greet() accept an optional name argument", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            if n == 1:
                # Introduces an `if` with no matching `fi` — real bash -n syntax error.
                return make_edit_call(
                    "call-1", target_path,
                    "greet() {\n  echo \"hello\"\n}\n",
                    "greet() {\n  if [ -n \"$1\" ]; then\n    echo \"hello, $1\"\n  echo \"hello\"\n}\n",
                )
            if n == 2:
                # Fix: close the if block.
                return make_edit_call(
                    "call-2", target_path,
                    "    echo \"hello, $1\"\n  echo \"hello\"\n}\n",
                    "    echo \"hello, $1\"\n  else\n    echo \"hello\"\n  fi\n}\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            n = calls["n"] + 1
            if n <= 2:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: greet() now accepts an optional name argument.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("shell lint coach delivered as role:'tool' message", len(coach_msgs) >= 1)
        check("shell lint coach names the bash -n break",
              any("bash -n" in m["content"] for m in coach_msgs))
        check("task completes after the fi is added",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())
        final_content = Path(target_path).read_text(encoding="utf-8")
        check("the fix actually landed on disk",
              any(ln.strip() == "fi" for ln in final_content.splitlines()))


async def test_lint_failsafe_without_pyflakes_or_shellcheck():
    """(k): with pyflakes AND shellcheck both simulated absent
    (`_pyflakes_messages`/`_shellcheck_error_messages` return None — the real
    "unavailable" sentinel), the lint check degrades to compile-only syntax
    checking. A genuine SyntaxError is still coached; the loop never crashes
    either way (the fail-safe contract, which is what's actually load-bearing
    here)."""
    initial = "def handle(value):\n    return value\n"
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-lint-failsafe", objective="add validation to handle()", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            n = calls["n"]
            if n == 1:
                # Genuine syntax error (unbalanced parens) — must still be
                # caught via the compile-only fallback.
                return make_edit_call(
                    "call-1", target_path,
                    "def handle(value):\n    return value\n",
                    "def handle(value:\n    return value\n",
                )
            if n == 2:
                # Fix the syntax error.
                return make_edit_call(
                    "call-2", target_path,
                    "def handle(value:\n    return value\n",
                    "def handle(value):\n    return value if value else None\n",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            n = calls["n"] + 1
            if n <= 2:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: fixed the syntax error and added validation.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        with patch.object(ae, "_pyflakes_messages", return_value=None), \
             patch.object(ae, "_shellcheck_error_messages", return_value=None):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("compile-only fallback still catches a real SyntaxError", len(coach_msgs) >= 1)
        check("coach message flags the break without crashing the loop",
              any("break the file" in m["content"] or "SyntaxError" in m["content"] for m in coach_msgs))
        check("task completes after the syntax fix (no crash, no hang)",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())
        check("the fix actually landed on disk",
              "value if value else None" in Path(target_path).read_text(encoding="utf-8"))


async def test_kill_switch_restores_plain_accept():
    """(f): AQ_EDIT_VERIFY=0 restores plain accept-on-success — no coaching
    is ever injected, even for a comment-only edit."""
    initial = (
        "def process(items):\n"
        "    # TODO: handle empty input\n"
        "    return [i for i in items if i]\n"
    )
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td), initial)
        ex = make_executor()
        task = Task(id="t-killswitch", objective="fix process() to also strip whitespace", status=TaskStatus.RUNNING)
        snapshots: list = []
        calls = {"n": 0}

        def _fake_parse(_response: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_edit_call(
                    "call-1", target_path,
                    "    # TODO: handle empty input",
                    "    # TODO: handle empty input and whitespace",
                )
            return None

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            if calls["n"] < 1:
                return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10
            return "COMPLETED: updated the comment.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_edit_exec(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        with patch.object(ae, "_EDIT_VERIFY_ENABLED", False):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        coach_msgs = coach_msgs_in_final_state(snapshots)
        check("kill switch: no coaching ever injected", len(coach_msgs) == 0)
        check("kill switch: task still completes normally on the plain accept",
              "COMPLETED" in final_msg or "comment" in final_msg.lower())


async def test_freshness_gaming_edit_triggers_coach():
    """A timestamp-only bump on a freshness field (dogfood-07: faking freshness
    instead of regenerating the artifact) is rejected with the gaming coach; a
    real content change on the same file passes clean."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "graph.json"
        pre = '{"generated": "2026-07-01T16:10:40Z", "total_nodes": 10}\n'
        # (1) gaming: only the "generated" date changed
        p.write_text('{"generated": "2026-07-02T16:10:40Z", "total_nodes": 10}\n', encoding="utf-8")
        v = ae._verify_edit_quality(
            "edit_file",
            {"file_path": str(p),
             "old_string": '"generated": "2026-07-01T16:10:40Z"',
             "new_string": '"generated": "2026-07-02T16:10:40Z"'},
            str(p), pre, "refresh the stale architecture graph",
        )
        check("freshness-gaming timestamp bump is rejected", not v.passed)
        check("freshness-gaming verdict reason", v.reason == "freshness_timestamp_gaming")
        check("freshness coach steers to regenerate, not hand-edit the date",
              "regenerat" in v.coaching_message.lower())
        # (2) real content change on a freshness-bearing file passes
        p.write_text('{"generated": "2026-07-01T16:10:40Z", "total_nodes": 42}\n', encoding="utf-8")
        v2 = ae._verify_edit_quality(
            "edit_file",
            {"file_path": str(p),
             "old_string": '"total_nodes": 10', "new_string": '"total_nodes": 42'},
            str(p), pre, "increase the recorded node total",
        )
        check("real content change on a timestamped file passes the freshness check", v2.passed)


async def test_behavioral_verify_catches_semantic_wrong_fix():
    """The behavioral gate runs the task's actual check post-edit: a clean edit
    that FAILS the check is coached (catches semantic wrong-fixes the static checks
    pass, e.g. dogfood-03); a clean edit that PASSES the check is accepted; and with
    no check configured the gate is a no-op. A check that can't run is fail-safe."""
    orig = ae._BEHAVIORAL_VERIFY_CMD
    try:
        # disabled -> None (static-only)
        ae._BEHAVIORAL_VERIFY_CMD = ""
        check("behavioral gate disabled when no command set", ae._behavioral_verify("x.py") is None)
        # passing check -> None
        ae._BEHAVIORAL_VERIFY_CMD = "true"
        check("passing check accepts (None)", ae._behavioral_verify("x.py") is None)
        # failing check -> failure output surfaced
        ae._BEHAVIORAL_VERIFY_CMD = "echo 'AssertionError: wrong behavior'; exit 1"
        out = ae._behavioral_verify("x.py")
        check("failing check surfaces its output", out is not None and "AssertionError" in out)
        # end-to-end: a clean edit that fails the check is coached
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.py"
            p.write_text("x = 2\n", encoding="utf-8")
            ae._BEHAVIORAL_VERIFY_CMD = "exit 3"
            v = ae._verify_edit_quality(
                "edit_file", {"file_path": str(p), "old_string": "x = 1", "new_string": "x = 2"},
                str(p), "x = 1", "fix x")
            check("clean edit failing the behavioral check is rejected", not v.passed)
            check("behavioral verdict reason", v.reason == "behavioral_verify_failed")
            check("behavioral coach names it a behavior bug, not syntax",
                  "behavior" in v.coaching_message.lower())
            # same edit, check now passes -> accepted
            ae._BEHAVIORAL_VERIFY_CMD = "true"
            v2 = ae._verify_edit_quality(
                "edit_file", {"file_path": str(p), "old_string": "x = 1", "new_string": "x = 2"},
                str(p), "x = 1", "fix x")
            check("clean edit passing the behavioral check is accepted", v2.passed)
    finally:
        ae._BEHAVIORAL_VERIFY_CMD = orig


async def main():
    await test_noop_edit_triggers_coach_then_real_fix_completes()
    await test_freshness_gaming_edit_triggers_coach()
    await test_behavioral_verify_catches_semantic_wrong_fix()
    await test_real_edit_passes_clean()
    await test_dead_code_added_def_triggers_coach()
    await test_referenced_def_passes_clean()
    await test_coaching_bounded_per_file()
    await test_lint_undefined_name_triggers_coach()
    await test_lint_clean_when_import_present()
    await test_lint_ignores_preexisting_issue()
    await test_lint_shell_syntax_error_introduced()
    await test_lint_failsafe_without_pyflakes_or_shellcheck()
    await test_kill_switch_restores_plain_accept()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
