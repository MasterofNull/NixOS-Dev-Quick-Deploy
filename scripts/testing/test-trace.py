#!/usr/bin/env python3
"""Tests for the distributed trace primitive (WS5) on the event bus.

Exit criterion: any run is diagnosable from its trace alone. The error test
proves a deep failure is pinpointed by span name + error message.

Run: python3 scripts/testing/test-trace.py
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(REPO))


def _fresh(tmp):
    os.environ["A2A_EVENT_LOG"] = str(Path(tmp) / "ev.jsonl")
    for k in ("AQ_TRACE_ID", "AQ_SPAN_ID"):
        os.environ.pop(k, None)
    import event_log
    importlib.reload(event_log)
    import trace as T
    importlib.reload(T)
    return T


def test_nested_spans_and_tree():
    with tempfile.TemporaryDirectory() as d:
        T = _fresh(d)
        with T.span("intent", agent="claude") as root:
            tid = root.trace_id
            with T.span("dispatch", agent="claude"):
                with T.span("model.generate", agent="local"):
                    pass
        roots = T.reconstruct(tid)
        assert len(roots) == 1 and roots[0].name == "intent"
        assert roots[0].children[0].name == "dispatch"
        assert roots[0].children[0].children[0].name == "model.generate"
        assert all(n.status == "ok" for n in roots)
        print("PASS nested spans reconstruct into a tree")


def test_error_is_diagnosable_from_trace():
    with tempfile.TemporaryDirectory() as d:
        T = _fresh(d)
        try:
            with T.span("intent", agent="claude") as root:
                tid = root.trace_id
                with T.span("tool.write_file", agent="local"):
                    raise RuntimeError("permission denied")
        except RuntimeError:
            pass
        tree = T.render_tree(tid)
        assert "permission denied" in tree, tree
        assert "✗ tool.write_file" in tree, tree
        # The failing span carries the error; parent marked error too (propagated).
        roots = T.reconstruct(tid)
        failing = roots[0].children[0]
        assert failing.status == "error" and "permission denied" in failing.error
        print("PASS failure diagnosable from trace alone")


def test_cross_process_propagation_via_env():
    with tempfile.TemporaryDirectory() as d:
        T = _fresh(d)
        # Parent sets the ambient trace/span; a "child process" reads env and continues.
        with T.span("parent", agent="claude") as p:
            tid = p.trace_id
            # Simulate child: env now has AQ_TRACE_ID + AQ_SPAN_ID.
            assert os.environ["AQ_TRACE_ID"] == tid
            child_parent = os.environ["AQ_SPAN_ID"]
            with T.span("child", agent="local") as c:
                assert c.trace_id == tid, "child joined a different trace"
                assert c.parent_span_id == child_parent, "child did not parent to caller span"
        print("PASS cross-process trace propagation via env")


def test_incomplete_span_shown():
    with tempfile.TemporaryDirectory() as d:
        T = _fresh(d)
        import event_log
        from contracts.events import Envelope
        # Emit only a start (crash before end).
        tid = "deadbeef" * 4
        event_log.append(Envelope(agent="local", type="trace.span.start",
                                   subject="stuck.op", trace_id=tid, span_id="s1",
                                   payload={"start_ts": 1.0}))
        tree = T.render_tree(tid)
        assert "incomplete" in tree.lower(), tree
        print("PASS incomplete (crashed) span surfaced, not swallowed")


def test_untraced_events_ignored():
    with tempfile.TemporaryDirectory() as d:
        T = _fresh(d)
        import event_log
        event_log.emit("claude", "pulse.append", payload={"action": "x"})  # no trace_id
        with T.span("traced", agent="claude") as s:
            tid = s.trace_id
        roots = T.reconstruct(tid)
        assert len(roots) == 1 and roots[0].name == "traced"
        print("PASS untraced events excluded from traces")


if __name__ == "__main__":
    test_nested_spans_and_tree()
    test_error_is_diagnosable_from_trace()
    test_cross_process_propagation_via_env()
    test_incomplete_span_shown()
    test_untraced_events_ignored()
    print("ALL PASS")
