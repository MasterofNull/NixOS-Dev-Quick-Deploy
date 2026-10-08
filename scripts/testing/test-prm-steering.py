#!/usr/bin/env python3
"""FE-1 process-reward steering: behavioral-verify as a candidate-preference signal.

Drives the real _execute_with_tools loop (same harness as test-edit-verify.py)
against real temp files with a real AQ_EDIT_VERIFY_CMD. Covers: OFF unchanged,
ON prefers the verified alternative, candidate cap, wall-budget, telemetry.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("tev", HERE / "test-edit-verify.py")
tev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tev)
ae, AgentType, Task, TaskStatus, check = tev.ae, tev.AgentType, tev.Task, tev.TaskStatus, tev.check

ORIG = "def f():\n    return 0\n"
VERIFY = "grep -q 'return 2' {file}"


async def run_case(*, steer: bool, alt_edit: str, max_cands: str = "2", budget: str = "900"):
    """alt_edit: new_string of the steering-time candidate (first edit is always the failing 'return 1')."""
    os.environ["AQ_PRM_STEERING"] = "1" if steer else "0"
    os.environ["AQ_PRM_MAX_CANDIDATES"] = max_cands
    os.environ["AQ_PRM_WALL_BUDGET_S"] = budget
    with tempfile.TemporaryDirectory() as td:
        events = Path(td) / "events.jsonl"
        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(events)
        target = tev.make_target_file(Path(td), ORIG)
        ex = tev.make_executor()
        mk = lambda cid, new: tev.make_edit_call(cid, target, "    return 0", new)  # noqa: E731
        by_resp = {
            "EDIT_BAD": lambda: mk("c1", "    return 1"),
            "EDIT_ALT": lambda: tev.make_edit_call("c2", target, "    return 0", alt_edit),
            "EDIT_FIX": lambda: tev.make_edit_call("c3", target, "    return 1", "    return 2"),
        }
        script = ["EDIT_BAD"] + (["EDIT_ALT"] if steer else []) + ["EDIT_FIX", "COMPLETED: done."]
        calls = {"n": 0}

        async def _llama(messages, **kw):
            r = script[min(calls["n"], len(script) - 1)]
            calls["n"] += 1
            return r, 5

        ex._call_llama = AsyncMock(side_effect=_llama)
        ex.tool_registry.parse_tool_call_from_llama.side_effect = lambda resp: by_resp[resp]() if resp in by_resp else None
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=tev.make_edit_exec(target))
        task = Task(id="t-prm", objective="make f return 2", status=TaskStatus.RUNNING)
        orig_cmd = ae._BEHAVIORAL_VERIFY_CMD
        ae._BEHAVIORAL_VERIFY_CMD = VERIFY
        try:
            await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)
        finally:
            ae._BEHAVIORAL_VERIFY_CMD = orig_cmd
        await asyncio.sleep(0.3)
        evs = []
        if events.exists():
            evs = [json.loads(l) for l in events.read_text().splitlines() if l.strip()]
        prm = [e for e in evs if e.get("event_type") == "prm_steering"]
        return Path(target).read_text(), prm, calls["n"]


async def main():
    # OFF: no steering event, loop unchanged (coach path then the model's own fix)
    content, prm, _ = await run_case(steer=False, alt_edit="    return 2")
    check("OFF: no prm_steering telemetry", prm == [])
    check("OFF: existing coach path still reaches the fix", "return 2" in content)

    # ON: verified alternative preferred; telemetry recorded
    content, prm, n = await run_case(steer=True, alt_edit="    return 2")
    check("ON: verified alternative left on disk", "return 2" in content and "return 1" not in content)
    check("ON: one prm_steering event", len(prm) == 1)
    e = prm[0] if prm else {}
    check("ON: telemetry candidates=2 verified_index=1", e.get("candidates") == 2 and e.get("verified_index") == 1)
    check("ON: telemetry extra_steps=1 and wall_s present", e.get("extra_steps") == 1 and "wall_s" in e)

    # ON but alternative also fails: no verified index; falls back to gate (model's own later fix lands)
    content, prm, _ = await run_case(steer=True, alt_edit="    return 3")
    check("ON/alt fails: verified_index None", bool(prm) and prm[0].get("verified_index") is None)
    check("ON/alt fails: gate fallback still reaches the fix", "return 2" in content)

    # cap: max 1 candidate -> no alternative requested
    _, prm, _ = await run_case(steer=True, alt_edit="    return 2", max_cands="1")
    check("cap=1: no steering event", prm == [])

    # wall budget exhausted -> no alternative requested
    _, prm, _ = await run_case(steer=True, alt_edit="    return 2", budget="0")
    check("budget=0: no steering event", prm == [])

    print(f"\n{tev.PASS}/{tev.PASS + tev.FAIL} tests passed")
    sys.exit(0 if tev.FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
