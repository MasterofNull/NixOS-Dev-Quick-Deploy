#!/usr/bin/env python3
"""Regression checks for aq-context-manage checkpoint persistence and resume guidance."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_CONTEXT_MANAGE = ROOT / "scripts" / "ai" / "aq-context-manage"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aq-context-manage-checkpoint-") as tmpdir:
        storage = Path(tmpdir) / "temporal_facts.json"
        result = subprocess.run(
            [
                "python3",
                str(AQ_CONTEXT_MANAGE),
                "--json",
                "--memory-storage",
                str(storage),
                "checkpoint",
                "--task",
                "resume ide stability phase",
                "--decision",
                "Bound editor-local corpus budgets in aq-report and aq-qa",
                "--next-step",
                "Start a fresh session from harness memory",
                "--open-question",
                "Which editor surfaces still replay raw transcripts?",
                "--fact",
                "VSCodium freezes correlate with oversized local session corpora",
                "--created-by",
                "codex",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert_true(result.returncode == 0, f"checkpoint command failed: {(result.stderr or result.stdout).strip()}")
        payload = json.loads(result.stdout)
        assert_true(payload.get("fact_count") == 5, "expected event plus four checkpoint entries")
        resume_commands = payload.get("resume_commands") or []
        assert_true(any("aq-memory search" in command for command in resume_commands), "expected aq-memory recall guidance")
        assert_true(any("aq-context-bootstrap" in command for command in resume_commands), "expected bootstrap resume guidance")

        stored = json.loads(storage.read_text(encoding="utf-8"))
        assert_true(len(stored) == 5, "expected five stored temporal facts")
        types = {item.get("type") for item in stored}
        assert_true({"event", "decision", "advice", "discovery", "fact"}.issubset(types), "expected structured checkpoint fact types")
        checkpoint_tags = {tag for item in stored for tag in (item.get("tags") or [])}
        assert_true("checkpoint" in checkpoint_tags and "resume" in checkpoint_tags, "expected checkpoint tags on stored facts")

    print("PASS: aq-context-manage checkpoint stores structured facts and resume guidance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
