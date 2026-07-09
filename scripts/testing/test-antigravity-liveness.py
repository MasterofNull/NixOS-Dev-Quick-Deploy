#!/usr/bin/env python3
"""aq-collab-round antigravity lane: consumption-based liveness + self-cleaning.

The lane must judge liveness by whether the LAST drop was consumed (deleted),
NOT by the presence of unrelated old backlog — the flaw that created a
self-reinforcing UNAVAILABLE loop (diagnosed by the antigravity lane itself).
It must also archive stale backlog so it stops growing.

Run: python3 scripts/testing/test-antigravity-liveness.py
"""

import importlib.machinery
import importlib.util
import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

loader = importlib.machinery.SourceFileLoader("agr", str(REPO / "scripts" / "ai" / "aq-collab-round"))
m = importlib.util.module_from_spec(importlib.util.spec_from_loader("agr", loader))
loader.exec_module(m)


def _setup(tmp: Path):
    inbox = tmp / "antigravity-inbox"
    inbox.mkdir()
    m.ANTIGRAVITY_INBOX = inbox
    m._ANTIGRAVITY_STATE = inbox / ".lane-state.json"
    m.REPO = tmp  # isolate the archive destination from the real repo
    return inbox


def test_consumed_previous_drop_is_live(tmp_factory):
    tmp = tmp_factory()
    inbox = _setup(tmp)
    # Record a prior drop that was consumed (file absent).
    m._ANTIGRAVITY_STATE.write_text(json.dumps(
        {"last_drop": {"name": "round-a.md", "ts": time.time() - 60}}))
    live, why = m._antigravity_inbox_live()
    assert live is True, why
    assert "consumed" in why.lower()
    print("PASS consumed previous drop -> live")


def test_unconsumed_previous_drop_unavailable(tmp_factory):
    tmp = tmp_factory()
    inbox = _setup(tmp)
    (inbox / "round-b.md").write_text("task")  # still present
    m._ANTIGRAVITY_STATE.write_text(json.dumps(
        {"last_drop": {"name": "round-b.md", "ts": time.time() - 4000}}))  # > window
    live, why = m._antigravity_inbox_live()
    assert live is False, why
    assert "unconsumed" in why.lower()
    print("PASS unconsumed previous drop past window -> unavailable")


def test_unrelated_backlog_does_not_poison(tmp_factory):
    tmp = tmp_factory()
    inbox = _setup(tmp)
    # Old unrelated files exist, but the LAST tracked drop was consumed.
    old = inbox / "ancient-round.md"
    old.write_text("old")
    import os
    os.utime(old, (time.time() - 100000, time.time() - 100000))
    m._ANTIGRAVITY_STATE.write_text(json.dumps(
        {"last_drop": {"name": "recent.md", "ts": time.time() - 60}}))  # recent.md absent = consumed
    live, why = m._antigravity_inbox_live()
    assert live is True, f"unrelated backlog wrongly poisoned liveness: {why}"
    print("PASS unrelated old backlog does not poison liveness")


def test_archive_stops_backlog_growth(tmp_factory):
    tmp = tmp_factory()
    inbox = _setup(tmp)
    import os
    for n in ("old1.md", "old2.md"):
        p = inbox / n
        p.write_text("x")
        os.utime(p, (time.time() - 100000, time.time() - 100000))
    (inbox / "current.md").write_text("keep me")  # fresh, in keep-set
    moved = m._archive_stale_inbox(keep={"current.md"})
    assert moved == 2, moved
    assert (inbox / "current.md").exists(), "current round file must be kept"
    assert not (inbox / "old1.md").exists(), "stale file should be archived"
    print("PASS stale backlog archived, current kept (Rule 12)")


if __name__ == "__main__":
    import tempfile
    _dirs = []

    def tmp_factory():
        d = tempfile.mkdtemp()
        _dirs.append(d)
        return Path(d)

    test_consumed_previous_drop_is_live(tmp_factory)
    test_unconsumed_previous_drop_unavailable(tmp_factory)
    test_unrelated_backlog_does_not_poison(tmp_factory)
    test_archive_stops_backlog_growth(tmp_factory)
    print("ALL PASS")
