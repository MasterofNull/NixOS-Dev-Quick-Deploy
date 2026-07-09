#!/usr/bin/env python3
"""Regression: local heartbeat sidecars with `ts` keep running tasks live."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

from task_registry import TaskRegistry  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        delegation = root / ".agents" / "delegation"
        outputs = delegation / "outputs"
        outputs.mkdir(parents=True)

        output = outputs / "local-test.log"
        output.write_text("Agent task started; waiting for aq-agent-loop output.\n", encoding="utf-8")
        Path(str(output) + ".heartbeat.json").write_text(
            json.dumps(
                {
                    "status": "agent-loop-waiting",
                    "pid": 99999999,
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            ),
            encoding="utf-8",
        )

        registry = TaskRegistry(delegation, repo_root=root)
        registry.append(
            "local-test",
            "heartbeat ts regression",
            str(output),
            mode="agent",
            role="reviewer",
            pid=99999999,
        )

        observed = registry.get("local-test")
        assert observed is not None
        status = registry._with_inferred_status(observed)
        assert status["status"] == "running", status
        assert status["pid_alive"] is True, status
        assert status["heartbeat_liveness"] is True, status

    print("PASS task registry accepts heartbeat ts field")


if __name__ == "__main__":
    main()
