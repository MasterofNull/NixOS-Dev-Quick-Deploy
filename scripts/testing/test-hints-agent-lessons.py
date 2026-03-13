#!/usr/bin/env python3
"""Targeted checks for promoted agent lesson hint surfacing."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from hints_engine import HintsEngine  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hints-agent-lessons-") as tmpdir:
        report_path = Path(tmpdir) / "latest-aq-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "agent_lessons": {
                        "available": True,
                        "candidates": [
                            {
                                "agent": "codex",
                                "hint_id": "runtime_rag_low_sample",
                                "direction": "promote",
                                "registry_state": "pending_review",
                                "comments": ["candidate feedback"],
                            }
                        ],
                        "registry": {
                            "available": True,
                            "active_lessons": [
                                {
                                    "lesson_key": "codex::runtime-rag-low-sample::promote",
                                    "agent": "codex",
                                    "hint_id": "runtime_rag_low_sample",
                                    "state": "promoted",
                                    "materialization": "quick_reference",
                                }
                            ],
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        engine = HintsEngine(report_json_path=report_path)
        hints = engine._hints_from_latest_report("improve rag retrieval and review hints", [])
        hint_ids = [item.id for item in hints]
        assert_true(
            any(hint_id.startswith("runtime_agent_lesson_active_codex_promoted") for hint_id in hint_ids),
            "expected promoted active lesson hint",
        )
        assert_true(
            any(hint_id.startswith("runtime_agent_lesson_codex_promote") for hint_id in hint_ids),
            "expected pending review lesson hint",
        )

    print("PASS: hints engine surfaces active and pending agent lessons from the live report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
