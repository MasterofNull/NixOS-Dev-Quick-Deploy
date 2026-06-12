#!/usr/bin/env python3
"""Regression test: aq-alerts --json emits parseable machine output."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_ALERTS = ROOT / "scripts" / "ai" / "aq-alerts"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["ATTENTION_QUEUE_DIR"] = tmp
        result = subprocess.run(
            [str(AQ_ALERTS), "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    payload = json.loads(result.stdout)
    assert payload == {"alerts": [], "pending": 0}, payload
    assert result.returncode == 0, result.returncode
    print("PASS: aq-alerts --json emits parseable empty queue payload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
