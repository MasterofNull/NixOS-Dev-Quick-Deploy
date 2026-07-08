#!/usr/bin/env python3
"""Tests for P1.3 failure correction (ai-stack/local-agents/failure_correction.py)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))

import failure_correction as fc  # noqa: E402


def _rec(**kw):
    base = {"kind": "failure_sample", "prompt": "p", "bad_output": "prose",
            "failure_class": "text_as_tool_call", "tools_available": ["read_file", "write_file"]}
    base.update(kw)
    return base


def test_is_pending():
    assert fc.is_pending(_rec())
    assert not fc.is_pending(_rec(corrected_output="x"))
    assert not fc.is_pending({"kind": "other"})


def test_correction_prompt_has_context():
    p = fc.build_correction_prompt(_rec(prompt="call read_file on foo"))
    assert "call read_file on foo" in p
    assert "read_file, write_file" in p
    assert "text_as_tool_call" in p
    assert "TEACHER" in p


def test_valid_toolcall_correction_accepted():
    r = fc.corrected_record(_rec(), '{"function":"read_file","arguments":{"path":"foo"}}')
    assert r is not None
    assert r["corrected_output"] == '{"function":"read_file","arguments":{"path":"foo"}}'
    assert r["correction_source"] == "remote-teacher"


def test_invalid_toolcall_correction_rejected():
    # not JSON
    assert fc.corrected_record(_rec(), "I would call read_file") is None
    # JSON but tool not in available set
    assert fc.corrected_record(_rec(), '{"function":"delete_everything","arguments":{}}') is None
    # empty
    assert fc.corrected_record(_rec(), "  ") is None


def test_non_toolcall_class_accepts_text():
    r = fc.corrected_record(_rec(failure_class="reasoning"), "The answer is 42.")
    assert r is not None and r["corrected_output"] == "The answer is 42."


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
