#!/usr/bin/env python3
"""Tests for the A2A event bus v1 — envelope, log, projector, clobber-proofing.

The headline test (test_concurrent_clobber_resistance) reproduces the exact bug
this slice kills: two agents updating RESUME state concurrently, both survive.

Run: python3 scripts/testing/test-event-bus-a2a.py
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(REPO))


def _fresh_log(tmp: Path):
    os.environ["A2A_EVENT_LOG"] = str(tmp / "events.jsonl")
    # Never let a test's projection touch the real session anchor.
    os.environ["RESUME_JSON_PATH"] = str(tmp / "RESUME.json")
    os.environ["PULSE_LOG_PATH"] = str(tmp / "PULSE.log")


def test_envelope_idempotency_and_signing():
    from contracts.events import Envelope
    e = Envelope(agent="a", type="x.y", payload={"n": 1})
    assert e.event_id and e.verify()  # unsigned verifies in v1
    # With a key, signed verifies and tamper fails.
    key = b"test-key"
    s = e.signed(key)
    assert s.sig and s.verify(key)
    tampered = s.model_copy(update={"payload": {"n": 2}})
    assert not tampered.verify(key), "tampered payload must fail verification"
    # Present sig but no key -> reject.
    assert not s.verify(b""), "signed event with no key must not verify"
    print("PASS envelope signing + tamper detection")


def test_append_and_idempotent_read():
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        event_log.emit("a", "pulse.append", payload={"action": "write"}, event_id="dup1")
        event_log.emit("a", "pulse.append", payload={"action": "write"}, event_id="dup1")  # dup
        event_log.emit("b", "pulse.append", payload={"action": "commit"})
        evs = event_log.read_all()
        assert len(evs) == 2, f"idempotent dedup failed: {len(evs)}"
        print("PASS append + idempotent dedup")


def test_corrupt_line_skipped():
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        event_log.emit("a", "x.y")
        # Simulate a crash mid-append: a real torn write starts with the
        # leading "\n" the appender emits, then gets cut off.
        with open(event_log.log_path(), "a") as fh:
            fh.write('\n{"partial": ')
        event_log.emit("b", "x.z")
        evs = event_log.read_all()
        assert len(evs) == 2, "corrupt line must be skipped, valid events kept"
        print("PASS corrupt line skipped")


def test_per_field_merge_no_clobber():
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        import resume_projector as rp
        importlib.reload(rp)
        # Agent A sets objective; agent B (later) sets phase. Different fields.
        rp.emit_resume_update("claude", current_objective="ship WS2")
        time.sleep(0.01)
        rp.emit_resume_update("codex", phase="implementation")
        proj = rp.project_resume()
        assert proj["current_objective"] == "ship WS2", "A's field lost (clobber!)"
        assert proj["phase"] == "implementation", "B's field lost"
        assert set(proj["agent_snapshots"]) == {"claude", "codex"}
        print("PASS per-field merge — different fields both survive")


def test_same_field_lww_preserves_loser():
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        import resume_projector as rp
        importlib.reload(rp)
        rp.emit_resume_update("claude", current_objective="objective-A")
        time.sleep(0.01)
        rp.emit_resume_update("codex", current_objective="objective-B")
        proj = rp.project_resume()
        # Latest wins at top level...
        assert proj["current_objective"] == "objective-B"
        assert proj["_provenance"]["current_objective"]["agent"] == "codex"
        # ...but the loser is NOT lost — preserved in its agent snapshot.
        assert proj["agent_snapshots"]["claude"]["fields"]["current_objective"] == "objective-A"
        print("PASS same-field LWW — loser preserved (no silent loss)")


def test_concurrent_clobber_resistance():
    """The bug this slice kills: N agents write RESUME state at once, none lost."""
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        import resume_projector as rp
        importlib.reload(rp)

        agents = [f"agent{i}" for i in range(12)]

        def worker(name):
            for k in range(5):
                rp.emit_resume_update(name, resume_hint=f"{name}-hint-{k}")

        threads = [threading.Thread(target=worker, args=(a,)) for a in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        evs = event_log.read_all()
        assert len(evs) == 12 * 5, f"lost events under concurrency: {len(evs)}/60"
        proj = rp.project_resume(evs)
        # Every agent's latest snapshot survived.
        assert set(proj["agent_snapshots"]) == set(agents), "an agent's state was clobbered"
        for a in agents:
            assert proj["agent_snapshots"][a]["fields"]["resume_hint"] == f"{a}-hint-4"
        print(f"PASS concurrent clobber resistance — 60 events, {len(agents)} agents, zero loss")


def test_projector_honors_output_override():
    """write_resume must write ONLY to RESUME_JSON_PATH, never the real anchor."""
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        import resume_projector as rp
        importlib.reload(rp)
        rp.emit_resume_update("claude", current_objective="isolated")
        rp.write_resume()
        target = Path(d) / "RESUME.json"
        assert target.exists(), "projection did not write to the override path"
        real = REPO / ".agent" / "collaboration" / "RESUME.json"
        # The real file must not contain our sentinel objective.
        if real.exists():
            assert "isolated" not in real.read_text(), "projector wrote the REAL RESUME.json!"
        print("PASS projector honors output override (real anchor untouched)")


def test_backward_compatible_resume_shape():
    with tempfile.TemporaryDirectory() as d:
        _fresh_log(Path(d))
        import importlib
        import event_log
        importlib.reload(event_log)
        import resume_projector as rp
        importlib.reload(rp)
        rp.emit_resume_update("claude", current_objective="obj", phase="p1",
                              todo_snapshot=["t1"], uncommitted_changes=["f.py"],
                              resume_hint="do x")
        proj = rp.project_resume()
        # aq-resume reads these exact top-level keys.
        for k in ("current_objective", "phase", "todo_snapshot", "uncommitted_changes", "resume_hint", "written_at"):
            assert k in proj, f"aq-resume compatibility broken: missing {k}"
        assert proj["written_at"] is not None
        print("PASS backward-compatible RESUME.json shape")


if __name__ == "__main__":
    test_envelope_idempotency_and_signing()
    test_append_and_idempotent_read()
    test_corrupt_line_skipped()
    test_per_field_merge_no_clobber()
    test_same_field_lww_preserves_loser()
    test_concurrent_clobber_resistance()
    test_projector_honors_output_override()
    test_backward_compatible_resume_shape()
    print("ALL PASS")
