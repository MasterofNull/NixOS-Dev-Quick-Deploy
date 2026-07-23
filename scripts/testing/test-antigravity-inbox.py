#!/usr/bin/env python3
"""Regression checks for the Antigravity IDE inbox helper."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "aq-antigravity-inbox"

loader = importlib.machinery.SourceFileLoader("ag_inbox", str(SCRIPT))
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("ag_inbox", loader))
loader.exec_module(module)


class _FakePgrep:
    """Stand-in for subprocess.run(["pgrep","-fa","antigravity"], ...)."""

    def __init__(self, stdout: str, rc: int = 0):
        self.stdout = stdout
        self.returncode = rc


def _check_proc_live() -> None:
    """_antigravity_proc_live must ignore command lines that merely contain the
    word 'antigravity' (the harness's own helpers + the shell running the check)
    and report live ONLY for a genuine Antigravity IDE process."""
    real_run = module.subprocess.run

    # Only harness tooling matches -> NOT live (the bug: bare pgrep said live).
    harness_only = (
        "111 /bin/zsh -c ... aq-collab-round open --round r\n"
        "222 python3 scripts/ai/aq-antigravity-inbox status\n"
        "333 /bin/sh -c pgrep -fa antigravity\n"
    )
    module.subprocess.run = lambda *a, **k: _FakePgrep(harness_only, 0)
    try:
        assert module._antigravity_proc_live() is False, "harness tooling falsely counted as live IDE"

        # A real IDE process present -> live.
        with_ide = harness_only + "444 /run/current-system/sw/bin/antigravity chat --mode agent\n"
        module.subprocess.run = lambda *a, **k: _FakePgrep(with_ide, 0)
        assert module._antigravity_proc_live() is True, "genuine IDE process not detected"

        # pgrep found nothing (rc=1) -> not live.
        module.subprocess.run = lambda *a, **k: _FakePgrep("", 1)
        assert module._antigravity_proc_live() is False, "empty pgrep must be not-live"
    finally:
        module.subprocess.run = real_run


def main() -> int:
    _check_proc_live()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        module.REPO = tmp
        module.INBOX = tmp / ".agent" / "collaboration" / "antigravity-inbox"
        module.STATE = module.INBOX / ".lane-state.json"
        module.INBOX.mkdir(parents=True)
        task = module.INBOX / "round-a.md"
        task.write_text("# task\n", encoding="utf-8")
        module.STATE.write_text(json.dumps({"last_drop": {"name": "round-a.md", "ts": 1}}), encoding="utf-8")

        status = module._state_payload()
        assert status["pending_count"] == 1
        assert status["last_drop_consumed"] is False

        assert module.main(["complete", "round-a.md", "--json"]) == 0
        assert not task.exists()
        archived = list((tmp / ".agent" / "archive").glob("antigravity-inbox-*/*.md"))
        assert len(archived) == 1
        assert module._state_payload()["last_drop_consumed"] is True

    print("PASS: antigravity inbox helper checks (incl. proc-liveness excludes harness tooling)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
