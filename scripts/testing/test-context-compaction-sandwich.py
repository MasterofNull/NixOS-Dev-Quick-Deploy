#!/usr/bin/env python3
"""Regression checks for context-risk routing through artifact compaction."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ai" / "lib" / "context_risk.py"
SWITCHBOARD = ROOT / "ai-stack" / "switchboard" / "switchboard.py"
AGENT_EXECUTOR = ROOT / "ai-stack" / "local-agents" / "agent_executor.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="context-compaction-sandwich-") as tmp:
        artifact_dir = Path(tmp)
        os.environ["SWB_CONTEXT_ARTIFACT_DIR"] = str(artifact_dir)
        os.environ["SWB_CONTEXT_OUTPUT_GC_MIN_CHARS"] = "256"
        os.environ["SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS"] = "120"
        context_risk = load_module(LIB, "context_risk_under_test")
        payload = "pytest log line\n" + ("Traceback (most recent call last)\n" * 10) + ("x" * 600)

        compact, meta = context_risk.compact_context_if_needed(
            payload,
            source="pytest-log",
            label="large pytest log",
            kind="log",
            min_chars=256,
            summary_chars=120,
            artifact_dir=artifact_dir,
        )
        envelope = json.loads(compact)
        artifact = json.loads(Path(envelope["artifact_path"]).read_text(encoding="utf-8"))
        assert_true(meta["context_risk"] is True, "payload should be context-risk")
        assert_true(envelope["context_route"] == "switchboard-artifact+aq-context-manage", "route should name existing compaction path")
        assert_true(envelope["raw_output_compacted"] is True, "envelope should mark compaction")
        assert_true("aq-context-manage summary" in envelope["resume_command"], "envelope should include aq-context-manage resume command")
        assert_true(artifact["content"] == payload, "artifact must preserve raw payload")
        assert_true(len(compact) < len(payload), "compact envelope should be smaller than raw payload")

        switchboard = load_module(SWITCHBOARD, "switchboard_context_sandwich_under_test")
        stats = switchboard._context_gc_empty_stats()
        swb_compact = switchboard._compact_tool_result_if_needed("pytest-log", "call-ctx", payload, stats)
        swb_envelope = json.loads(swb_compact)
        assert_true(swb_envelope["context_risk"] is True, "switchboard should route high-risk tool output")
        assert_true(stats["context_risk_routes"] == 1, "switchboard should count context-risk routes")
        assert_true(stats["tool_observations_compacted"] == 1, "switchboard should count compacted tool observations")

    agent_src = AGENT_EXECUTOR.read_text(encoding="utf-8")
    assert_true("compact_context_if_needed" in agent_src, "local-agent executor should use shared context compaction")
    assert_true('"context_compaction"' in agent_src, "local-agent executor should emit context_compaction event")
    print("PASS: context-risk routing uses switchboard artifacts and aq-context-manage resume guidance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
