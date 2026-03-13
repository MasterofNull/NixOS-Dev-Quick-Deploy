#!/usr/bin/env python3
"""Targeted checks for RAG posture diagnosis and remediation hints."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")

AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
AQ_REPORT_SPEC = importlib.util.spec_from_loader(
    "aq_report_rag_diag",
    SourceFileLoader("aq_report_rag_diag", str(AQ_REPORT_PATH)),
)
if AQ_REPORT_SPEC is None or AQ_REPORT_SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
aq_report = importlib.util.module_from_spec(AQ_REPORT_SPEC)
AQ_REPORT_SPEC.loader.exec_module(aq_report)

sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))
from hints_engine import HintsEngine  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    unused = aq_report.rag_posture(
        tool_stats={
            "route_search": {"calls": 20},
            "tree_search": {"calls": 2},
            "recall_agent_memory": {"calls": 1},
        },
        recent_tool_stats={
            "route_search": {"calls": 16},
            "tree_search": {"calls": 1},
            "recall_agent_memory": {"calls": 1},
        },
        recent_audit_entries=[
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": False}},
        ],
        cache={"available": True, "hits": 80, "misses": 20, "hit_pct": 80.0},
        gaps=[],
        top_prompts=[],
    )
    assert_true(unused.get("memory_recall_diagnosis") == "unused", "expected unused memory recall diagnosis")
    assert_true(
        any("recall prior context before broad route_search" in action for action in (unused.get("memory_recall_actions") or [])),
        "expected explicit unused-memory remediation action",
    )

    weak = aq_report.rag_posture(
        tool_stats={
            "route_search": {"calls": 12},
            "tree_search": {"calls": 0},
            "recall_agent_memory": {"calls": 6},
        },
        recent_tool_stats={
            "route_search": {"calls": 8},
            "tree_search": {"calls": 0},
            "recall_agent_memory": {"calls": 6},
        },
        recent_audit_entries=[
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": True}},
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": True}},
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": True}},
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": True}},
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": False}},
            {"tool_name": "recall_agent_memory", "metadata": {"memory_recall_miss": False}},
        ],
        cache={"available": True, "hits": 80, "misses": 20, "hit_pct": 80.0},
        gaps=[],
        top_prompts=[],
    )
    assert_true(weak.get("memory_recall_diagnosis") == "weak", "expected weak memory recall diagnosis")
    assert_true(
        any("persist sharper milestone summaries" in action for action in (weak.get("memory_recall_actions") or [])),
        "expected explicit weak-memory remediation action",
    )

    with tempfile.TemporaryDirectory(prefix="rag-posture-diagnosis-") as tmpdir:
        report_path = Path(tmpdir) / "latest-aq-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "rag_posture": {
                        "available": True,
                        "status": "watch",
                        "recent_retrieval_calls": 17,
                        "memory_recall_share_pct": unused.get("memory_recall_share_pct"),
                        "memory_recall_miss_pct": unused.get("memory_recall_miss_pct"),
                        "memory_recall_diagnosis": "unused",
                        "memory_recall_actions": unused.get("memory_recall_actions"),
                    }
                }
            ),
            encoding="utf-8",
        )
        engine = HintsEngine(report_json_path=report_path)
        hints = engine._hints_from_latest_report("continue previous repo work with prior context", [])
        hint_ids = [item.id for item in hints]
        assert_true("runtime_resume_memory_first" in hint_ids, "expected unused-memory continuation hint")

        report_path.write_text(
            json.dumps(
                {
                    "rag_posture": {
                        "available": True,
                        "status": "watch",
                        "recent_retrieval_calls": 14,
                        "memory_recall_share_pct": weak.get("memory_recall_share_pct"),
                        "memory_recall_miss_pct": weak.get("memory_recall_miss_pct"),
                        "memory_recall_diagnosis": "weak",
                        "memory_recall_actions": weak.get("memory_recall_actions"),
                    }
                }
            ),
            encoding="utf-8",
        )
        weak_hints = engine._hints_from_latest_report("continue previous repo work with prior context", [])
        weak_ids = [item.id for item in weak_hints]
        assert_true("runtime_resume_memory_refresh" in weak_ids, "expected weak-memory continuation hint")

    print("PASS: rag posture emits explicit memory diagnosis and hints consume it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
