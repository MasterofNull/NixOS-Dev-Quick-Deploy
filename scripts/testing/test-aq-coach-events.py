#!/usr/bin/env python3
"""Regression test for aq-coach-events (read-only coaching-telemetry viewer).

Surfaces edit_verify_coach events from agent-run-events.jsonl so local's
edit-quality trajectory is measurable (issues-backlog: observability gap after
the 2026-08-29 guard-active dogfood run). This pins the parsing/grouping so the
viewer stays honest: it counts only real edit_verify_coach events, groups by
failure-mode prefix, is fail-soft on malformed/missing input, and never writes.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "ai" / "aq-coach-events"

# aq-coach-events has no .py suffix, so importlib cannot infer a loader from the
# path — construct a SourceFileLoader explicitly.
_loader = importlib.machinery.SourceFileLoader("aq_coach_events", str(TOOL))
spec = importlib.util.spec_from_loader("aq_coach_events", _loader)
mod = importlib.util.module_from_spec(spec)
_loader.exec_module(mod)

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


def _write(tmp: Path, lines: list[str]) -> str:
    p = tmp / "events.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def main() -> int:
    check("reason_class splits on ':'",
          mod.reason_class("destructive_deletion:route") == "destructive_deletion")
    check("reason_class no colon -> whole",
          mod.reason_class("noop_comment_or_whitespace_only") == "noop_comment_or_whitespace_only")
    check("reason_class None -> unknown", mod.reason_class(None) == "unknown")

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rows = [
            json.dumps({"event_type": "edit_verify_coach", "reason": "dead_code:foo",
                        "file_path": "a.py", "ts": "t1"}),
            json.dumps({"event_type": "edit_verify_coach", "reason": "lint_new_error:undefined name 're'",
                        "file_path": "b.py", "ts": "t2"}),
            json.dumps({"event_type": "edit_verify_coach", "reason": "destructive_deletion:route",
                        "file_path": "c.py", "ts": "t3"}),
            # noise that must be ignored:
            json.dumps({"event_type": "agent_step_start", "ts": "t4"}),
            json.dumps({"event_type": "tool_result", "reason": "edit_verify_coach lookalike", "ts": "t5"}),
            "not json at all {",  # malformed line -> skipped, no crash
        ]
        path = _write(tmp, rows)
        events = mod.load_coach_events(path)
        check("loads only the 3 real coach events (ignores other types + malformed)",
              len(events) == 3)
        check("preserves chronological order", [e["ts"] for e in events] == ["t1", "t2", "t3"])

        report = mod.build_report(events, last=2)
        check("total == 3", report["total"] == 3)
        check("grouped by failure mode",
              report["by_failure_mode"] == {"dead_code": 1, "lint_new_error": 1, "destructive_deletion": 1})
        check("last=2 returns the 2 most recent", [e["ts"] for e in report["recent"]] == ["t2", "t3"])
        check("recent carries the failure_mode + file",
              report["recent"][-1]["failure_mode"] == "destructive_deletion"
              and report["recent"][-1]["file_path"] == "c.py")

        # fail-soft: missing file -> empty, no raise
        check("missing file -> empty list",
              mod.load_coach_events(str(tmp / "nope.jsonl")) == [])

        # end-to-end main() JSON path (exit 0, valid JSON)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main(["--path", path, "--json", "--last", "1"])
        out = json.loads(buf.getvalue())
        check("main --json exits 0 + emits valid report",
              rc == 0 and out["total"] == 3 and out["recent"][0]["ts"] == "t3")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
