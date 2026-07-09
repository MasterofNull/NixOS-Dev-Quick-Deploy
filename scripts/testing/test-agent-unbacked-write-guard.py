#!/usr/bin/env python3
"""Guard against local-agent false-success: a run that CLAIMS a file write but
never called a write tool must be non-substantive, not a completion.

Reproduces the real failure: local lane local-20260709-044240-6fy659 reported
"COMPLETED: Wrote local lane ratification output to .agents/plans/aqos-v1/local.md"
after 1 get_hint + 8 read_file + 0 writes.

Run: python3 scripts/testing/test-agent-unbacked-write-guard.py
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_loader("aq_agent_loop", loader=None)
mod = importlib.util.module_from_spec(spec)
# aq-agent-loop is an extensionless script; exec just the helpers we need by
# importing it as source with a shim for its heavy deps is overkill — instead
# load the module via importlib from the file path.
_src = (REPO / "scripts" / "ai" / "aq-agent-loop").read_text()


def _load():
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader("aq_agent_loop", str(REPO / "scripts" / "ai" / "aq-agent-loop"))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("aq_agent_loop", loader))
    try:
        loader.exec_module(m)
    except Exception:
        # The script may try heavy imports at module load; fall back to exec'ing
        # only the guard functions we test in an isolated namespace.
        ns = {"re": __import__("re")}
        import re as _re
        src = _src
        # Extract from the marker to the run_task def.
        start = src.index("# Write tools whose invocation")
        end = src.index("async def run_task")
        exec(compile(src[start:end], "aq-agent-loop-guard", "exec"), ns)
        return SimpleNamespace(**ns)
    return m


G = _load()


def tc(name):
    return SimpleNamespace(tool_name=name)


def test_unbacked_claim_flagged():
    result = ("COMPLETED: Wrote local lane ratification output to "
              ".agents/plans/aqos-v1/local.md with scores, amendments, risks, "
              "slice claims, and verdict.")
    reads = [tc("get_hint")] + [tc("read_file")] * 8
    assert G._claims_unbacked_write(result, reads) is True, "false success not caught"
    print("PASS unbacked write claim flagged (the real failure)")


def test_backed_claim_ok():
    result = "Wrote the analysis to .agents/plans/aqos-v1/local.md"
    calls = [tc("read_file"), tc("write_file")]
    assert G._claims_unbacked_write(result, calls) is False, "real write wrongly flagged"
    print("PASS backed write claim accepted")


def test_edit_tool_backs_claim():
    result = "Updated config/switchboard-profiles.yaml with the new profile"
    calls = [tc("edit_file")]
    assert G._claims_unbacked_write(result, calls) is False
    print("PASS edit_file backs an 'updated file' claim")


def test_no_write_claim_not_flagged():
    # Pure analysis with no file-write claim must not be flagged by this guard.
    result = "Recommendation: ratify with amendments. WS1 scores 9."
    assert G._claims_unbacked_write(result, [tc("read_file")]) is False
    print("PASS analysis-only result not flagged")


def test_dict_tool_calls_supported():
    result = "created new_module.py"
    assert G._claims_unbacked_write(result, [{"tool_name": "write_file"}]) is False
    assert G._claims_unbacked_write(result, [{"tool_name": "read_file"}]) is True
    print("PASS dict-shaped tool calls handled")


if __name__ == "__main__":
    test_unbacked_claim_flagged()
    test_backed_claim_ok()
    test_edit_tool_backs_claim()
    test_no_write_claim_not_flagged()
    test_dict_tool_calls_supported()
    print("ALL PASS")
