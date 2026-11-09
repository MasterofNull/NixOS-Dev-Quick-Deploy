#!/usr/bin/env python3
"""Targeted checks for aq-report persistent agent-lesson registry sync."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
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
    now = datetime.now(tz=timezone.utc)

    def feedback_line(timestamp: datetime) -> str:
        return json.dumps(
            {
                "timestamp": timestamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "hint_id": "runtime_rag_low_sample",
                "agent": "codex",
                "helpful": True,
            }
        )

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            tmp_hint_path = temporary_root / "agent-lesson-registry-feedback.jsonl"
            tmp_registry_path = temporary_root / "agent-lesson-registry.json"
            fresh_events = [now - timedelta(minutes=10), now - timedelta(minutes=5), now]
            expired_events = [
                now - timedelta(days=8, minutes=10),
                now - timedelta(days=8, minutes=5),
                now - timedelta(days=8),
            ]
            tmp_hint_path.write_text(
                "\n".join(feedback_line(timestamp) for timestamp in fresh_events + expired_events) + "\n",
                encoding="utf-8",
            )
            MODULE.HINT_FEEDBACK_PATH = tmp_hint_path
            MODULE.AGENT_LESSON_REGISTRY_PATH = tmp_registry_path
            lessons = MODULE.agent_lesson_candidates(now - timedelta(days=7))
            candidates = lessons.get("candidates") or []
            assert_true(lessons.get("total_events") == 3, "expired feedback must be excluded before grouping")
            assert_true(len(candidates) == 1, "expected one lesson candidate")
            assert_true(candidates[0].get("event_count") == 3, "expected only fresh event count")
            assert_true(candidates[0].get("evidence_count") == 3, "expected only fresh evidence count")

            registry = MODULE.sync_agent_lesson_registry(lessons, now=now)
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

    print("PASS: aq-report persists agent lesson candidates into the durable registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
