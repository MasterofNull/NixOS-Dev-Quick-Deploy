#!/usr/bin/env python3
"""Regression checks for aq-report multi-source tool audit ingestion."""

from __future__ import annotations

import importlib.util
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


def load_aq_report():
    os.environ.setdefault("AI_STRICT_ENV", "false")
    spec = importlib.util.spec_from_loader(
        "aq_report_tool_audit_sources",
        SourceFileLoader("aq_report_tool_audit_sources", str(AQ_REPORT_PATH)),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load aq-report")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    aq_report = load_aq_report()
    now = datetime(2026, 4, 24, 18, 30, tzinfo=timezone.utc)
    stale = now - timedelta(hours=4)
    fresh = now - timedelta(minutes=5)

    with tempfile.TemporaryDirectory(prefix="aq-report-audit-") as tmpdir:
        tmp = Path(tmpdir)
        primary = tmp / "tool-audit-primary.jsonl"
        sidecar = tmp / "tool-audit-sidecar.jsonl"

        primary.write_text(
            json.dumps(
                {
                    "timestamp": stale.isoformat().replace("+00:00", "Z"),
                    "tool_name": "discovery",
                    "service": "hybrid-coordinator-http",
                    "outcome": "success",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        fresh_entry = {
            "timestamp": fresh.isoformat().replace("+00:00", "Z"),
            "tool_name": "route_search",
            "service": "hybrid-coordinator-http",
            "outcome": "success",
            "metadata": {
                "retrieval_profile": "runtime-diagnostics-direct",
                "retrieval_collection_count": 2,
            },
        }
        sidecar.write_text(json.dumps(fresh_entry) + "\n", encoding="utf-8")

        aq_report.TOOL_AUDIT_PATH = primary
        aq_report.AUDIT_FALLBACK_PATH = sidecar

        entries = aq_report.read_tool_audit(now - timedelta(hours=1))
        assert_true(len(entries) == 1, "expected only fresh entry inside window")
        assert_true(entries[0]["tool_name"] == "route_search", "expected fresh sidecar route_search entry")

        breadth = aq_report.route_retrieval_breadth(entries)
        assert_true(breadth.get("route_calls") == 1, "expected route_calls=1 from fresh sidecar entry")
        assert_true(
            breadth.get("avg_collection_count") == 2.0,
            "expected retrieval breadth to use sidecar metadata",
        )
        assert_true(
            (breadth.get("top_profiles") or [])[0][0] == "runtime-diagnostics-direct",
            "expected runtime diagnostics profile from sidecar metadata",
        )

        latest_report = tmp / "latest-aq-report.json"
        aq_report.AQ_REPORT_LATEST_JSON = latest_report
        aq_report._persist_latest_report_json('{"generated_at":"2026-04-24T18:30:00Z"}')
        assert_true(latest_report.exists(), "expected latest aq-report cache file to be written")
        payload = json.loads(latest_report.read_text(encoding="utf-8"))
        assert_true(payload.get("generated_at") == "2026-04-24T18:30:00Z", "expected cached report payload")

    print("PASS: aq-report merges fresh tool-audit sidecar entries when primary log is stale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
