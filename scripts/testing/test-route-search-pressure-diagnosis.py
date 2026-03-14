#!/usr/bin/env python3
"""Targeted checks for route_search pressure diagnosis and remediation hints."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")

AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
AQ_REPORT_SPEC = importlib.util.spec_from_loader(
    "aq_report_route_pressure",
    SourceFileLoader("aq_report_route_pressure", str(AQ_REPORT_PATH)),
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
    now = datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc)
    breadth_entries = [
        {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {
                "retrieval_profile": "detailed",
                "retrieval_collection_count": 6,
            },
        },
        {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {
                "retrieval_profile": "detailed",
                "retrieval_collection_count": 5,
            },
        },
    ]
    breadth = aq_report.route_retrieval_breadth(breadth_entries)
    assert_true(breadth.get("diagnosis") == "broad_scanning", "expected broad_scanning diagnosis")
    assert_true(
        any("narrow route_search collection selection" in action for action in (breadth.get("actions") or [])),
        "expected retrieval breadth remediation action",
    )

    fallback_entries = [
        {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {
                "fallback_reason": "remote_4xx_local_fallback",
                "fallback_status_code": 429,
            },
        },
        {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "metadata": {
                "fallback_reason": "remote_4xx_local_fallback",
                "fallback_status_code": 400,
            },
        },
    ]
    fallback = aq_report.route_provider_fallback_health(fallback_entries)
    assert_true(
        fallback.get("diagnosis") == "provider_fallback_pressure",
        "expected provider_fallback_pressure diagnosis",
    )
    assert_true(
        any("prefer local-first routing" in action for action in (fallback.get("actions") or [])),
        "expected provider fallback remediation action",
    )

    with tempfile.TemporaryDirectory(prefix="route-search-pressure-") as tmpdir:
        report_path = Path(tmpdir) / "latest-aq-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "route_retrieval_breadth": {
                        "available": True,
                        "avg_collection_count": breadth.get("avg_collection_count"),
                        "top_profiles": breadth.get("top_profiles"),
                        "diagnosis": breadth.get("diagnosis"),
                        "actions": breadth.get("actions"),
                    },
                    "provider_fallback_recovery": {
                        "available": True,
                        "recovered_count": fallback.get("recovered_count"),
                        "status_counts": fallback.get("status_counts"),
                        "diagnosis": fallback.get("diagnosis"),
                        "actions": fallback.get("actions"),
                    },
                }
            ),
            encoding="utf-8",
        )
        engine = HintsEngine(report_json_path=report_path)
        hints = engine._hints_from_latest_report("optimize route_search and routing pressure", [])
        hint_ids = [item.id for item in hints]
        assert_true("runtime_retrieval_breadth_optimize" in hint_ids, "expected route breadth hint")
        assert_true("runtime_provider_fallback_pressure" in hint_ids, "expected provider fallback hint")

    print("PASS: route_search pressure emits diagnosis and hints consume it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
