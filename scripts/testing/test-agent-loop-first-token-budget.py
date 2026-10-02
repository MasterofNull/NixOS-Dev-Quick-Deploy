#!/usr/bin/env python3
"""
Regression test for RSI incident e5d253ff: fixed 900s first-token timeout
cancelled a 4.7k-token prompt (needed ~930s at ~5 tok/s) 30s before its first
token, and the client then retried the SAME prompt with max_tokens=512, which
re-processes the full prompt and fails identically.

Covers: budget scales with prompt size / measured rate, floor, cap, unavailable
metrics fallback, no same-prompt retry after a first-token timeout, other
errors still retry.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
sys.path.insert(0, str(LOCAL_AGENTS))
_tmp = tempfile.NamedTemporaryFile(prefix="ft-budget-events-", suffix=".jsonl", delete=False)
_tmp.close()
os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = _tmp.name

spec = importlib.util.spec_from_file_location("agent_executor", LOCAL_AGENTS / "agent_executor.py")
ae = importlib.util.module_from_spec(spec)
sys.modules.setdefault("httpx", MagicMock())
spec.loader.exec_module(ae)

FAIL = 0


def check(name: str, cond: bool) -> None:
    global FAIL
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAIL += 1


def make_executor():
    ex = ae.LocalAgentExecutor.__new__(ae.LocalAgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None
    ex.remote_probe_timeout_seconds = 5
    ex._prompt_extensions_cache = None
    reg = MagicMock()
    reg.get_tools_for_model.return_value = [{"name": "run_command", "description": "x"}]
    reg.tools = {}
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in ae.AgentType}
    return ex


def test_budget_math():
    f = ae._compute_first_token_budget
    # Incident: 4.7k tokens at 5 tok/s -> 940s raw, x2 = 1880s (> old 900s fixed)
    check("scales with prompt size and rate (4700 tok @ 5 tok/s, x2 = 1880s)",
          abs(f(900.0, 4700, 5.0) - 1880.0) < 1e-6)
    check("faster rate shrinks need, floor holds (4700 tok @ 50 tok/s -> floor 900)",
          f(900.0, 4700, 50.0) == 900.0)
    check("larger prompt -> larger budget", f(900.0, 9400, 5.0) > f(900.0, 4700, 5.0))
    check("cap applies (100k tok @ 1 tok/s capped at 3600)", f(900.0, 100000, 1.0, cap_s=3600.0) == 3600.0)
    check("custom cap honored", f(900.0, 100000, 1.0, cap_s=2000.0) == 2000.0)
    check("cap below floor never lowers the floor", f(900.0, 100000, 1.0, cap_s=100.0) == 900.0)
    check("unavailable rate (None) -> fixed base", f(900.0, 4700, None) == 900.0)
    check("zero rate -> fixed base", f(900.0, 4700, 0.0) == 900.0)


def test_metrics_parse_and_estimate():
    txt = "# HELP x\nllamacpp:prompt_tokens_total 10\nllamacpp:prompt_tokens_seconds 4.93\n"
    check("parses llamacpp:prompt_tokens_seconds", ae._parse_prompt_eval_rate(txt) == 4.93)
    check("missing metric -> None", ae._parse_prompt_eval_rate("foo 1\n") is None)
    check("garbage value -> None", ae._parse_prompt_eval_rate("llamacpp:prompt_tokens_seconds abc\n") is None)
    check("zero value -> None", ae._parse_prompt_eval_rate("llamacpp:prompt_tokens_seconds 0\n") is None)
    check("estimate chars/4", ae._estimate_prompt_tokens([{"content": "a" * 400}, {"content": "b" * 400}]) == 200)
    check("estimate handles None content", ae._estimate_prompt_tokens([{"content": None}]) >= 1)


async def test_fetch_rate_unavailable():
    ex = make_executor()
    ex._local_model_health_endpoint = lambda: None
    check("no endpoint -> None", await ex._fetch_prompt_eval_rate() is None)
    ex._local_model_health_endpoint = lambda: "http://127.0.0.1:9"  # nothing listens
    check("unreachable /metrics -> None (fallback to fixed value)", await ex._fetch_prompt_eval_rate() is None)


async def test_no_retry_after_first_token_timeout():
    ex = make_executor()
    task = ae.Task(id="t-ft", objective="x", status=ae.TaskStatus.RUNNING)
    ex._call_llama = AsyncMock(side_effect=ae._FirstTokenTimeout("LLM first-token timeout: no content within 900s"))
    raised = None
    try:
        await ex._execute_with_tools(task, ae.AgentType.AGENT, max_tool_calls=3)
    except RuntimeError as e:
        raised = e
    check("first-token timeout fails fast", raised is not None)
    check("exactly ONE _call_llama attempt (same prompt not retried)", ex._call_llama.await_count == 1)
    check("message explains max_tokens cannot help", raised is not None and "Not retrying" in str(raised)
          and "first-token timeout" in str(raised))


async def test_other_errors_still_retry():
    ex = make_executor()
    task = ae.Task(id="t-other", objective="x", status=ae.TaskStatus.RUNNING)
    ex._call_llama = AsyncMock(side_effect=[RuntimeError("connection reset"), ("COMPLETED: done", 5), ("COMPLETED: done", 5)])
    try:
        await ex._execute_with_tools(task, ae.AgentType.AGENT, max_tool_calls=3)
    except Exception:
        pass
    check("transient error triggers a retry (>=2 attempts)", ex._call_llama.await_count >= 2)
    check("retry uses reduced max_tokens=512", ex._call_llama.await_args_list[1].kwargs.get("max_tokens") == 512)


def main() -> int:
    test_budget_math()
    test_metrics_parse_and_estimate()
    asyncio.run(test_fetch_rate_unavailable())
    asyncio.run(test_no_retry_after_first_token_timeout())
    asyncio.run(test_other_errors_still_retry())
    print("FAIL" if FAIL else "ok first-token budget regression")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
