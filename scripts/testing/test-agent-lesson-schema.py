#!/usr/bin/env python3
"""Targeted checks for aq-report agent lesson schema enrichment."""

from __future__ import annotations

import importlib.util
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
    original_path = MODULE.HINT_FEEDBACK_PATH
    original_registry_path = MODULE.AGENT_LESSON_REGISTRY_PATH
    tmp_path = ROOT / ".tmp-agent-lesson-schema.jsonl"
    tmp_registry_path = ROOT / ".tmp-agent-lessons-registry.json"
    try:
        tmp_path.write_text(
            "\n".join(
                [
                    '{"timestamp":"2026-03-13T12:00:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true,"agent_preferences":{"preferred_tools":["route_search"],"preferred_tags":["retrieval","research"]}}',
                    '{"timestamp":"2026-03-13T12:05:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true,"agent_preferences":{"preferred_tools":["route_search"],"preferred_tags":["retrieval","research"]}}',
                    '{"timestamp":"2026-03-13T12:10:00Z","hint_id":"runtime_rag_low_sample","agent":"codex","helpful":true,"agent_preferences":{"preferred_tools":["route_search"],"preferred_tags":["retrieval","research"]}}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        MODULE.HINT_FEEDBACK_PATH = tmp_path
        MODULE.AGENT_LESSON_REGISTRY_PATH = tmp_registry_path
        since = datetime.now(tz=timezone.utc) - timedelta(days=7)
        lessons = MODULE.agent_lesson_candidates(since)
        registry = MODULE.sync_agent_lesson_registry(lessons)
        lessons["registry"] = registry
        candidates = lessons.get("candidates") or []
        assert_true(bool(candidates), "expected at least one lesson candidate")
        top = candidates[0]
        assert_true(top.get("state") == "promote", "expected promote state")
        assert_true(top.get("scope") == "retrieval_research", "expected retrieval scope")
        assert_true(top.get("evidence_count") == 3, "expected evidence count")
        assert_true(top.get("materialization") == "quick_reference", "expected quick reference materialization")
        traceability = top.get("traceability") or {}
        assert_true(traceability.get("source_type") == "hint_feedback", "expected hint feedback traceability")
        assert_true("reference" in (traceability.get("targets") or []), "expected reference target")
        assert_true(top.get("registry_state") == "pending_review", "expected pending review registry state")
        counts = registry.get("counts") or {}
        assert_true(counts.get("pending_review") == 1, "expected one pending review lesson")

        actions = MODULE.build_structured_actions({}, {"available": False}, {"available": False}, {"available": False}, [], None, lessons)
        assert_true(any(item.get("action") == "review_agent_lesson" for item in actions if isinstance(item, dict)), "expected review_agent_lesson structured action")
    finally:
        MODULE.HINT_FEEDBACK_PATH = original_path
        MODULE.AGENT_LESSON_REGISTRY_PATH = original_registry_path
        if tmp_path.exists():
            tmp_path.unlink()
        if tmp_registry_path.exists():
            tmp_registry_path.unlink()

    print("PASS: aq-report emits governed lesson schema and structured promotion actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
