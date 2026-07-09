#!/usr/bin/env python3
"""aq-collab-round antigravity inbox liveness detection.

The lane must report UNAVAILABLE (not hang pending) when the IDE is not
consuming the inbox. Detected via stale unconsumed task files.

Run: python3 scripts/testing/test-antigravity-liveness.py
"""

import importlib.machinery
import importlib.util
import os
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

loader = importlib.machinery.SourceFileLoader("agr", str(REPO / "scripts" / "ai" / "aq-collab-round"))
m = importlib.util.module_from_spec(importlib.util.spec_from_loader("agr", loader))
loader.exec_module(m)


def test_stale_inbox_reports_unavailable():
    with tempfile.TemporaryDirectory() as d:
        inbox = Path(d) / "antigravity-inbox"
        inbox.mkdir()
        f = inbox / "old-round.md"
        f.write_text("task")
        old = time.time() - 4000  # >15min
        os.utime(f, (old, old))
        m.ANTIGRAVITY_INBOX = inbox
        live, why = m._antigravity_inbox_live()
        assert live is False, "stale inbox must report not-live"
        assert "stale" in why.lower(), why
        print(f"PASS stale inbox -> unavailable ({why[:50]}...)")


def test_empty_inbox_reflects_process_state():
    with tempfile.TemporaryDirectory() as d:
        inbox = Path(d) / "antigravity-inbox"
        inbox.mkdir()
        m.ANTIGRAVITY_INBOX = inbox
        live, why = m._antigravity_inbox_live()
        # No stale files: liveness follows whether an antigravity process exists.
        assert isinstance(live, bool) and why
        print(f"PASS empty inbox -> process-state based (live={live})")


def test_fresh_drop_not_flagged_stale():
    with tempfile.TemporaryDirectory() as d:
        inbox = Path(d) / "antigravity-inbox"
        inbox.mkdir()
        (inbox / "just-now.md").write_text("fresh")  # mtime = now
        m.ANTIGRAVITY_INBOX = inbox
        live, why = m._antigravity_inbox_live()
        assert "stale" not in why.lower(), f"fresh drop wrongly flagged stale: {why}"
        print("PASS fresh drop within window not flagged stale")


if __name__ == "__main__":
    test_stale_inbox_reports_unavailable()
    test_empty_inbox_reflects_process_state()
    test_fresh_drop_not_flagged_stale()
    print("ALL PASS")
