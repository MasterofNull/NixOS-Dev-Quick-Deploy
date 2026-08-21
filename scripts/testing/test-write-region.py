#!/usr/bin/env python3
"""
Regression test for the write_region line-range rewrite tool (2026-08-20).

Root cause this addresses (see .agent/PROMOTED-BUG-PATTERNS.md / Aider's
per-model edit-format research): the local (Qwen) agent's #1 remaining edit
failure is `edit_file` old_string MISMATCH — search/replace requires a
byte-exact old_string, and weak/quantized models cannot reliably reproduce
one from a partial view of a file, so they churn on 'old_string not found'.
Aider's published per-model data is why it DEFAULTS weak/local models to
"whole"-format edits (rewrite the unit, no matching) rather than
search/replace. We already front-load code to local WITH line-number
citations (e.g. '[file:271-290]'), so a line-range rewrite needs NO
old_string at all — just the line numbers already shown.

Fix under test: `write_region(file_path, start_line, end_line, new_text)`
(ai-stack/local-agents/builtin_tools/file_operations.py) replaces lines
[start_line, end_line] (1-indexed, inclusive) with new_text — no fuzzy
matching, deterministic. Registered in the tool registry exactly like
edit_file/write_file (so it reaches the model-visible tool schema AND the
GBNF grammar's function enum, which derives from the registry's enabled
tools — see agent_executor.py `_tool_call_grammar`). Gated behind
AQ_WRITE_REGION (default "1"; "0" hides the tool entirely). A successful
call counts toward `_edits_made` (the no-action guard) exactly like
edit_file/write_file.

Coverage:
  (a) a valid line-range replace produces the exact expected file content
  (b) out-of-range start/end returns a clear error with the current line
      count — no crash, no partial write (file left byte-identical)
  (c) inserting at EOF (start_line == end_line == line_count + 1) works
  (d) a successful write_region call counts as an edit for the no-action
      guard — driven through the REAL `_execute_with_tools` loop
  (e) AQ_WRITE_REGION=0 hides the tool from the registry (and therefore
      from the model-visible schema + GBNF enum, which both derive from
      registry.tools)
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
BUILTINS = LOCAL_AGENTS / "builtin_tools"
sys.path.insert(0, str(LOCAL_AGENTS))
sys.path.insert(0, str(BUILTINS))

from tool_registry import ToolRegistry  # noqa: E402
import file_operations  # noqa: E402

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


ORIGINAL_CONTENT = (
    "line one\n"
    "line two\n"
    "line three\n"
    "line four\n"
    "line five\n"
)


def make_target_file(tmp_dir: Path) -> Path:
    p = tmp_dir / "target.txt"
    p.write_text(ORIGINAL_CONTENT, encoding="utf-8")
    return p


async def test_valid_replace_produces_exact_content():
    """(a) a valid line-range replace produces the exact expected file content."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p),
            start_line=2,
            end_line=3,
            new_text="line two REPLACED\nline three REPLACED\n",
        )
        check("valid replace reports success", result.get("success") is True)
        check("valid replace reports correct start_line", result.get("start_line") == 2)
        check("valid replace reports correct end_line", result.get("end_line") == 3)

        expected = (
            "line one\n"
            "line two REPLACED\n"
            "line three REPLACED\n"
            "line four\n"
            "line five\n"
        )
        actual = p.read_text(encoding="utf-8")
        check("file content matches exactly after replace", actual == expected)


async def test_single_line_replace():
    """A single-line region (start_line == end_line) replaces just that line."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=1, end_line=1, new_text="ONLY LINE ONE CHANGED\n",
        )
        check("single-line replace succeeds", result.get("success") is True)
        expected = "ONLY LINE ONE CHANGED\n" + "".join(ORIGINAL_CONTENT.splitlines(keepends=True)[1:])
        check("single-line replace content exact", p.read_text(encoding="utf-8") == expected)


async def test_out_of_range_returns_error_no_crash_no_partial_write():
    """(b) out-of-range start/end returns an error with the current line count
    (no crash, no partial write — file left byte-identical)."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        before = p.read_text(encoding="utf-8")

        # end_line way past EOF
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=2, end_line=999, new_text="X\n",
        )
        check("out-of-range end_line reports failure", result.get("success") is False)
        check("out-of-range error includes current_line_count", result.get("current_line_count") == 5)
        check("out-of-range error message is descriptive", "5 lines" in result.get("error", ""))
        check("out-of-range: file unchanged (no partial write)", p.read_text(encoding="utf-8") == before)

        # start_line < 1
        result2 = await file_operations.write_region_handler(
            file_path=str(p), start_line=0, end_line=1, new_text="X\n",
        )
        check("start_line < 1 reports failure", result2.get("success") is False)
        check("start_line < 1: file unchanged", p.read_text(encoding="utf-8") == before)

        # start_line > end_line
        result3 = await file_operations.write_region_handler(
            file_path=str(p), start_line=3, end_line=2, new_text="X\n",
        )
        check("start_line > end_line reports failure", result3.get("success") is False)
        check("start_line > end_line: file unchanged", p.read_text(encoding="utf-8") == before)

        # missing file — no crash
        result4 = await file_operations.write_region_handler(
            file_path=str(Path(td) / "does-not-exist.txt"), start_line=1, end_line=1, new_text="X\n",
        )
        check("missing file reports failure (no crash)", result4.get("success") is False)
        check("missing file error is descriptive", "not found" in result4.get("error", "").lower())


async def test_insert_at_eof():
    """(c) inserting at EOF (start_line == end_line == line_count + 1) works."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=6, end_line=6, new_text="line six APPENDED\n",
        )
        check("EOF insert reports success", result.get("success") is True)
        expected = ORIGINAL_CONTENT + "line six APPENDED\n"
        check("EOF insert appends without disturbing existing lines", p.read_text(encoding="utf-8") == expected)


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
        {"name": "write_region", "description": "line-range rewrite"},
    ]
    reg.tools = {}

    def _fake_format(tool_call) -> str:
        import json as _json
        return _json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


async def test_counts_as_edit_for_noaction_guard():
    """(d) a successful write_region call counts toward `_edits_made`, so a
    prose-only completion AFTER it does NOT trigger the no-action
    intervention (mirrors test-noaction-intervention.py's pattern for
    edit_file/write_file)."""
    with tempfile.TemporaryDirectory() as td:
        target_path = str(make_target_file(Path(td)))
        ex = make_executor()
        task = Task(id="t-write-region-noaction", objective="rewrite lines 2-3", status=TaskStatus.RUNNING)

        _call_seq = {"n": 0}

        def _fake_parse(_response: str):
            _call_seq["n"] += 1
            if _call_seq["n"] == 1:
                return ToolCall(
                    id="call-1", tool_name="write_region",
                    arguments={
                        "file_path": target_path,
                        "start_line": 2,
                        "end_line": 3,
                        "new_text": "REPLACED TWO\nREPLACED THREE\n",
                    },
                )
            return None  # turn 2: prose-only completion, no tool call

        async def _fake_execute(tool_call):
            tool_call.status = "completed"
            result = await file_operations.write_region_handler(**tool_call.arguments)
            tool_call.result = result
            return tool_call

        call_log = []

        async def _fake_call_llama(messages, **kwargs):
            call_log.append(list(messages))
            n = _call_seq["n"] + 1
            if n <= 1:
                return (
                    f'{{"function": "write_region", "arguments": '
                    f'{{"file_path": "{target_path}", "start_line": 2, "end_line": 3, '
                    f'"new_text": "REPLACED TWO\\nREPLACED THREE\\n"}}}}',
                    10,
                )
            return "COMPLETED: rewrote lines 2-3 with write_region.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=_fake_execute)
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        noaction_msgs = [
            m for m in (call_log[-1] if call_log else [])
            if m.get("role") == "user" and "Call edit_file NOW" in (m.get("content") or "")
        ]
        check(
            "no-action intervention NOT injected after a successful write_region "
            "(it already counted as an edit)",
            len(noaction_msgs) == 0,
        )
        check(
            "task completes normally (no stagnation/abort)",
            "Aborting" not in final_msg and "stagnation" not in final_msg.lower(),
        )
        check("completion reflects the write_region fix", "COMPLETED" in final_msg)

        actual = Path(target_path).read_text(encoding="utf-8")
        check(
            "the write_region edit actually landed on disk",
            "REPLACED TWO" in actual and "REPLACED THREE" in actual,
        )


def test_env_flag_hides_tool():
    """(e) AQ_WRITE_REGION=0 hides the tool from the registry entirely — and
    therefore from get_tools_for_model()'s output, which is the same source
    the GBNF grammar enum (agent_executor._tool_call_grammar) derives from."""
    with patch.dict(os.environ, {"AQ_WRITE_REGION": "0"}):
        registry_off = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_off)
        check("AQ_WRITE_REGION=0: write_region absent from registry.tools",
              "write_region" not in registry_off.tools)
        model_tool_names_off = {t["name"] for t in registry_off.get_tools_for_model()}
        check("AQ_WRITE_REGION=0: write_region absent from model-visible schema",
              "write_region" not in model_tool_names_off)

    with patch.dict(os.environ, {"AQ_WRITE_REGION": "1"}):
        registry_on = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_on)
        check("AQ_WRITE_REGION=1: write_region present in registry.tools",
              "write_region" in registry_on.tools)
        model_tool_names_on = {t["name"] for t in registry_on.get_tools_for_model()}
        check("AQ_WRITE_REGION=1: write_region present in model-visible schema",
              "write_region" in model_tool_names_on)

    # Default (env var unset) is ON.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AQ_WRITE_REGION", None)
        registry_default = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_default)
        check("AQ_WRITE_REGION unset: defaults to ON",
              "write_region" in registry_default.tools)


async def main():
    await test_valid_replace_produces_exact_content()
    await test_single_line_replace()
    await test_out_of_range_returns_error_no_crash_no_partial_write()
    await test_insert_at_eof()
    await test_counts_as_edit_for_noaction_guard()
    test_env_flag_hides_tool()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
