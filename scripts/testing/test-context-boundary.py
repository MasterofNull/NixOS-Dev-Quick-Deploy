#!/usr/bin/env python3
"""Focused tests for the context boundary meter."""
import importlib.util
import json
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "ai" / "lib" / "context_boundary.py"
spec = importlib.util.spec_from_file_location("context_boundary", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def main():
    assert mod.estimate_tokens(0) == 0
    assert mod.estimate_tokens(9) == 3
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = mod.record_boundary(root, "tool", 320, session_id="s1", native_limit=100)
        assert first["status"] == "handoff_recommended"
        assert Path(first["handoff"]).exists()
        handoff = Path(first["handoff"]).read_text()
        assert "Payload contents" in handoff
        assert "secret" not in handoff
        second = mod.record_boundary(root, "mcp", 4, session_id="s1", native_limit=100)
        assert second["event_count"] == 2
        reset = mod.record_boundary(root, "drop", 4, session_id="s2", native_limit=100)
        assert reset["event_count"] == 1
        state = json.loads((root / ".agent/collaboration/CONTEXT-BOUNDARY.json").read_text())
        assert state["session_id"] == "s2"

        default_root = root / "default-session"
        first_default = mod.record_boundary(default_root, "tool", 40, native_limit=1000)
        time.sleep(1.05)
        second_default = mod.record_boundary(default_root, "mcp", 40, native_limit=1000)
        assert second_default["event_count"] == 2
        assert second_default["cumulative_tokens"] == 20
        assert first_default["state_path"] == second_default["state_path"]

        explicit_new_id = mod.record_boundary(
            default_root, "drop", 4, session_id="new-session", native_limit=1000
        )
        assert explicit_new_id["event_count"] == 1
        state = json.loads(Path(explicit_new_id["state_path"]).read_text())
        assert state["session_id"] == "new-session"
    print("context boundary tests passed")


if __name__ == "__main__":
    main()
