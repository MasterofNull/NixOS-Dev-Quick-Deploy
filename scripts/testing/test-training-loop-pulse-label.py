#!/usr/bin/env python3
"""aq-local-training-loop PULSE lines carry the Simurg@<lane>/<model>#<session> label, never the bare script name."""
from __future__ import annotations

import importlib.machinery
import os
import re
import tempfile
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-local-training-loop"


def main() -> int:
    mod = importlib.machinery.SourceFileLoader("aq_local_training_loop_pulse_test", str(MODULE_PATH)).load_module()
    for k in ("AQ_INSTANCE_MODEL", "PERSONA"):
        os.environ.pop(k, None)
    with tempfile.TemporaryDirectory(prefix="training-loop-pulse-") as tmp:
        log = Path(tmp) / "PULSE.log"
        with mock.patch.object(mod, "PULSE_LOG", log):
            mod._pulse("run done", "loop-20261115-121750")
        line = log.read_text(encoding="utf-8")
    if not re.search(r"\] \[Simurg@local/local#121750\] \[run\]: run done", line):
        raise AssertionError(f"unlabeled PULSE writer: {line!r}")
    print("PASS: training-loop PULSE writer is labeled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
