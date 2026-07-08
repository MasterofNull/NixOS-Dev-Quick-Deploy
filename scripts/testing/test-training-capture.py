#!/usr/bin/env python3
"""Tests for P1 failure capture (ai-stack/local-agents/training_capture.py)."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))

import training_capture  # noqa: E402


def test_capture_writes_labeled_sample(tmp_path):
    out = tmp_path / "training-samples.jsonl"
    p = training_capture.capture_failure(
        prompt="call read_file on x",
        bad_output="I will now read the file.",
        failure_class="text_as_tool_call",
        tools_available=["read_file", "write_file"],
        source="agent_executor",
        path=out,
    )
    assert p == out and out.exists()
    rec = json.loads(out.read_text().strip())
    assert rec["failure_class"] == "text_as_tool_call"
    assert rec["kind"] == "failure_sample"
    assert rec["tools_available"] == ["read_file", "write_file"]
    assert rec["bad_output"] == "I will now read the file."
    assert rec["corrected_output"] is None


def test_capture_appends_multiple(tmp_path):
    out = tmp_path / "s.jsonl"
    training_capture.capture_failure(prompt="a", bad_output="b", failure_class="parse_failed", path=out)
    training_capture.capture_failure(prompt="c", bad_output="d", failure_class="truncated", path=out)
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["failure_class"] == "truncated"


def test_secrets_are_scrubbed(tmp_path):
    out = tmp_path / "s.jsonl"
    training_capture.capture_failure(
        prompt="here is sk-ABCDEF0123456789ABCDEF my key",
        bad_output="api_key: 'ABCDEF0123456789'",
        failure_class="x",
        path=out,
    )
    rec = json.loads(out.read_text().strip())
    assert "sk-ABCDEF0123456789" not in rec["prompt"]
    assert "[REDACTED]" in rec["prompt"]


def test_corrected_output_enables_pair(tmp_path):
    out = tmp_path / "s.jsonl"
    training_capture.capture_failure(
        prompt="p", bad_output="prose", failure_class="text_as_tool_call",
        corrected_output='{"function":"read_file","arguments":{}}', path=out,
    )
    rec = json.loads(out.read_text().strip())
    assert rec["corrected_output"] == '{"function":"read_file","arguments":{}}'


def test_capture_never_raises_on_bad_path():
    # A capture to an unwritable path must return None, not raise.
    r = training_capture.capture_failure(
        prompt="p", bad_output="b", failure_class="x", path=Path("/proc/nonexistent/nope.jsonl")
    )
    assert r is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
