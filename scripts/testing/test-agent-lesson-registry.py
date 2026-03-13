#!/usr/bin/env python3
"""Targeted checks for aq-report persistent agent-lesson registry sync."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-report"
SPEC = importlib.util.spec_from_loader("aq_report", SourceFileLoader("aq_report", str(MODULE_PATH)))
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
MODULE = importlib.util.module_from_spec(SPEC)
os.environ.setdefault("AI_STRICT_ENV", "false")
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_hint_path = MODULE.HINT_FEEDBACK_PATH
    original_registry_path = MODULE.AGENT_LESSON_REGISTRY_PATH
    tmp_hint_path = ROOT / ".tmp-agent-lesson-registry-feedback.jsonl"
    tmp_registry_path = ROOT / ".tmp-agent-lesson-registry.json"
    try:
        tmp_hint_path.write_text(
            "\n".join(
                [
                    '{"timestamp":"2026-03-13T12:00:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true}',
                    '{"timestamp":"2026-03-13T12:05:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true}',
                    '{"timestamp":"2026-03-13T12:10:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        MODULE.HINT_FEEDBACK_PATH = tmp_hint_path
        MODULE.AGENT_LESSON_REGISTRY_PATH = tmp_registry_path
        since = datetime.now(tz=timezone.utc) - timedelta(days=7)
        lessons = MODULE.agent_lesson_candidates(since)
        registry = MODULE.sync_agent_lesson_registry(lessons)

        counts = registry.get("counts") or {}
        assert_true(counts.get("total") == 1, "expected one registry lesson")
        assert_true(counts.get("pending_review") == 1, "expected one pending lesson")
        saved = json.loads(tmp_registry_path.read_text(encoding="utf-8"))
        entries = saved.get("entries") or []
        assert_true(len(entries) == 1, "registry file should contain one entry")
        assert_true(entries[0].get("state") == "pending_review", "new lessons should default to pending_review")
    finally:
        MODULE.HINT_FEEDBACK_PATH = original_hint_path
        MODULE.AGENT_LESSON_REGISTRY_PATH = original_registry_path
        if tmp_hint_path.exists():
            tmp_hint_path.unlink()
        if tmp_registry_path.exists():
            tmp_registry_path.unlink()

    print("PASS: aq-report persists agent lesson candidates into the durable registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
