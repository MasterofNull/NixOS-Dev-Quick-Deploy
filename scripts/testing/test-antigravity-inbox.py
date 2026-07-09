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


def main() -> int:
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

    print("PASS: antigravity inbox helper checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
