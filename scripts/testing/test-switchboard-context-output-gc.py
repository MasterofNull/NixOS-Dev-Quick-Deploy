#!/usr/bin/env python3
"""Regression coverage for Switchboard context-output GC and tool dedupe."""

import importlib.util
import json
import os
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_PATH = REPO_ROOT / "ai-stack" / "switchboard" / "switchboard.py"


def load_switchboard(artifact_dir: str):
    os.environ.setdefault("LLAMA_CTX_SIZE", "16384")
    os.environ["SWB_CONTEXT_ARTIFACT_DIR"] = artifact_dir
    os.environ["SWB_CONTEXT_OUTPUT_GC_MIN_CHARS"] = "256"
    os.environ["SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS"] = "160"
    spec = importlib.util.spec_from_file_location("switchboard_context_gc_under_test", SWITCHBOARD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        swb = load_switchboard(tmpdir)
        raw = json.dumps({
            "tool": "search_files",
            "status": "success",
            "result": ["line " + ("x" * 80) for _ in range(20)],
        })
        stats = swb._context_gc_empty_stats()
        compact = swb._compact_tool_result_if_needed("search_files", "call-1", raw, stats)
        compact_payload = json.loads(compact)

        assert_true(compact_payload["raw_output_compacted"] is True, "expected compacted tool observation")
        assert_true(compact_payload["artifact_path"].startswith(tmpdir), "artifact should be written under configured dir")
        assert_true(Path(compact_payload["artifact_path"]).exists(), "artifact file should exist")
        assert_true(stats["artifacts_written"] == 1, "expected one artifact")
        assert_true(stats["raw_chars_pruned"] > 0, "expected raw chars to be pruned from context")
        assert_true(len(compact) < len(raw), "compact observation should be smaller than raw output")

        artifact = json.loads(Path(compact_payload["artifact_path"]).read_text(encoding="utf-8"))
        assert_true(artifact["content"] == raw, "artifact must preserve raw tool result")
        assert_true(artifact["sha256"] == compact_payload["sha256"], "artifact digest mismatch")

        key_a = swb._tool_result_cache_key("read_file", '{"path":"a","limit":5}')
        key_b = swb._tool_result_cache_key("read_file", '{"limit":5,"path":"a"}')
        key_c = swb._tool_result_cache_key("read_file", '{"path":"b","limit":5}')
        assert_true(key_a == key_b, "tool dedupe key should canonicalize JSON arguments")
        assert_true(key_a != key_c, "tool dedupe key should differ for different arguments")

        health_text = SWITCHBOARD_PATH.read_text(encoding="utf-8")
        assert_true('"context_output_gc"' in health_text, "health endpoint should expose context-output GC policy")
        assert_true("X-AI-Context-GC-Artifacts" in health_text, "responses should expose context GC artifact telemetry")
        assert_true("X-AI-Tool-Duplicate-Calls" in health_text, "responses should expose tool dedupe telemetry")

    print("PASS: Switchboard compacts large tool outputs and deduplicates repeated tool calls")


if __name__ == "__main__":
    main()
