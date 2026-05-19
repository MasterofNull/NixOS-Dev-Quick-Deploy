#!/usr/bin/env python3
"""Targeted checks for route_search telemetry-backed retrieval metrics."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        audit_path = tmp_path / "tool-audit.jsonl"
        fallback_path = tmp_path / "sidecar-audit.jsonl"
        telemetry_path = tmp_path / "hybrid-events.jsonl"

        # Legacy wrapper row: useful for call volume, but not enough for the
        # acceptance metric because it lacks retrieval metadata.
        audit_path.write_text(
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                    "service": "hybrid-coordinator-tool-security",
                    "tool_name": "route_search",
                    "outcome": "success",
                    "metadata": {"transport": "http"},
                }
            )
            + "\n"
        )
        fallback_path.write_text("")
        telemetry_path.write_text(
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=4)).isoformat().replace("+00:00", "Z"),
                    "event_type": "route_search",
                    "route": "local",
                    "backend": "qwen",
                    "generate_response": False,
                    "retrieval_profile": {
                        "profile": "code-focused-compact",
                        "collection_count": 2,
                        "collections": ["codebase-context", "error-solutions"],
                        "keyword_pool": 16,
                    },
                }
            )
            + "\n"
        )

        os.environ["TOOL_AUDIT_LOG_PATH"] = str(audit_path)
        os.environ["TOOL_AUDIT_LOG_PATH_FALLBACK"] = str(fallback_path)
        os.environ["HYBRID_TELEMETRY_PATH"] = str(telemetry_path)
        aq_report = SourceFileLoader("aq_report_route_telemetry", str(AQ_REPORT_PATH)).load_module()

        entries = aq_report.read_tool_audit(now - timedelta(hours=1))
        summary = aq_report.route_retrieval_breadth(entries)

        assert_true(len(entries) == 2, "expected audit row plus telemetry row")
        assert_true(summary.get("route_calls") == 2, "expected both route_search calls counted")
        assert_true(summary.get("measured_route_calls") == 1, "expected telemetry row measured")
        assert_true(summary.get("avg_collection_count") == 2.0, "expected avg collection count from telemetry")
        assert_true(summary.get("telemetry_route_calls") == 1, "expected telemetry source accounting")
        assert_true(summary.get("diagnosis") == "healthy", "expected healthy diagnosis from telemetry metadata")

    print("PASS: aq-report consumes route_search telemetry for retrieval breadth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
