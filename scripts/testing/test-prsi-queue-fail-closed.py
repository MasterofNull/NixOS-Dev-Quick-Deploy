#!/usr/bin/env python3
"""prsi-orchestrator must refuse to load (and later overwrite) a malformed action queue."""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / "scripts" / "automation" / "prsi-orchestrator.py"


def load(queue_path: Path):
    os.environ["PRSI_ACTION_QUEUE_PATH"] = str(queue_path)
    spec = importlib.util.spec_from_file_location("prsi_orchestrator_under_test", ORCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def expect_refusal(mod, label: str) -> None:
    try:
        mod._load_queue()
    except RuntimeError:
        return
    print(f"FAIL: {label} was loaded instead of refused")
    sys.exit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        q = Path(tmp) / "action-queue.json"
        mod = load(q)
        if mod._load_queue()["actions"] != []:
            print("FAIL: missing queue should load as empty")
            return 1
        q.write_text(json.dumps({"actions": [{"id": "a"}], "meta": {}}))
        if [a["id"] for a in mod._load_queue()["actions"]] != ["a"]:
            print("FAIL: valid queue not loaded")
            return 1
        q.write_text(json.dumps([{"actions": [{"id": "a"}]}, {"type": "maintenance"}]))
        expect_refusal(mod, "list-wrapped queue (aq-throttler shape)")
        q.write_text('{"actions": [')
        expect_refusal(mod, "truncated JSON")
        q.write_text(json.dumps({"actions": {"id": "a"}}))
        expect_refusal(mod, "non-list actions")
    print("PASS: prsi-orchestrator refuses malformed action queues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
