#!/usr/bin/env python3
"""Regression checks for context-risk routing through artifact compaction."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Mock optional runtime dependencies to enable headless testing
for module_name in ['uvicorn', 'fastapi', 'fastapi.responses', 'pydantic']:
    sys.modules[module_name] = MagicMock()



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
        code = "    value = 'bound code'\n" * 120
        assert_true(len(code) == 3000, "code fixture should contain 3,000 characters")
        risk = context_risk.classify_context_risk(code, source="read_file", min_chars=16000)
        assert_true(not risk["context_risk"], "bounded 120-line code read should stay inline")
        html = "    <div>bounded HTML</div>\n" * 400
        risk = context_risk.classify_context_risk(html, source="read_file", min_chars=16000)
        assert_true(not risk["context_risk"], "bounded HTML read should stay inline")
        read_compact, _ = context_risk.compact_context_if_needed(
            code * 6,
            source="read_file",
            label="large code read",
            min_chars=16000,
            summary_chars=120,
            artifact_dir=artifact_dir,
        )
        assert_true(json.loads(read_compact)["summary"] == (code * 6)[:117].rstrip() + "...",
                    "compacted read preview should preserve newlines and indentation")
        assert_true(context_risk._preview("    x\x00\n    y", 100, preserve_newlines=True) == "    x\n    y",
                    "read preview should strip NUL without collapsing whitespace")

        sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))
        try:
            file_ops = load_module(
                ROOT / "ai-stack" / "local-agents" / "builtin_tools" / "file_operations.py",
                "file_operations_under_test",
            )
            single_file = artifact_dir / "single-file.py"
            single_file.write_text("first line\nneedle: matching text\n", encoding="utf-8")
            result = asyncio.run(file_ops.search_files_handler("needle", str(single_file)))
            assert_true(result["success"], "single-file search should succeed")
            assert_true(result["matches"] == [{"file": str(single_file), "line": 2, "text": "needle: matching text"}],
                        "single-file search should preserve path, line number, and text")
        finally:
            sys.path.pop(0)

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
    loop_src = (ROOT / "scripts" / "ai" / "aq-agent-loop").read_text(encoding="utf-8")
    assert_true("del max_calls" not in loop_src, "aq-agent-loop must not delete max_calls before forwarding")
    assert_true(
        "wall_budget_s=float(timeout_secs)" in loop_src and "max_tool_calls=max_calls" in loop_src,
        "aq-agent-loop must forward max_calls and timeout_secs to executor.execute_task",
    )
    print("PASS: context-risk routing uses switchboard artifacts and aq-context-manage resume guidance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
