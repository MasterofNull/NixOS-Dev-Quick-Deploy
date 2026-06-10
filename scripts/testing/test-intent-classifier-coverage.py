#!/usr/bin/env python3
"""
Phase 160 regression: intent classifier coverage stat tile and aq-report section.

Tests:
- fetch_intent_distribution() returns expected structure
- format_text() emits 4c. Intent Classification section
- format_md() emits 4c table
- format_json() includes intent_distribution key
- Unknown intent rate thresholds (ok/warn/err)
- dashboard.html has statIntentUnknown tile
- dashboard.js wires vIntentUnknown from traceIntents
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_aq_report():
    loader = importlib.machinery.SourceFileLoader("aq_report", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _minimal_args(mod):
    no = {"available": False}
    empty: list = []
    return (
        "7d",
        {},
        no,
        no,
        {},
        no,
        {},
        no,
        empty,
        empty,
        empty,
        {},
        no,
        no,
        {},  # continue_editor_windows
        {},  # editor_rescue_windows_summary
        {},  # shared_skill_registry
        {},  # delegated_prompt_failures
        {},  # delegated_prompt_failure_windows
        {},  # remote_profile_summary
        {},  # remote_profile_windows
        {},  # route_latency_decomposition
        {},  # retrieval_breadth
        {},  # retrieval_breadth_windows
        {},  # provider_fallbacks
        {},  # historical_watch
        empty,  # recs
    )


def test_format_text_intent_section_with_data():
    mod = _load_aq_report()
    dist = {"total": 100, "unknown": 43, "unknown_pct": 43.0, "known": {"knowledge_lookup": 54, "systems_software": 3}}
    output = mod.format_text(*_minimal_args(mod), intent_dist=dist)
    assert_true("4c. Intent Classification" in output, "4c section header missing from format_text")
    assert_true("43" in output, "unknown count missing")
    assert_true("knowledge_lookup" in output, "known intent missing")
    assert_true("note: >20% unclassified" in output, "warn note missing for 43% unknown")
    print("PASS  format_text 4c with data")


def test_format_text_intent_section_no_data():
    mod = _load_aq_report()
    output = mod.format_text(*_minimal_args(mod), intent_dist={})
    assert_true("4c. Intent Classification" in output, "4c section missing when no data")
    assert_true("No trace data" in output or "coordinator offline" in output, "no-data fallback missing")
    print("PASS  format_text 4c no data")


def test_format_text_intent_high_unknown_warn():
    mod = _load_aq_report()
    dist = {"total": 50, "unknown": 40, "unknown_pct": 80.0, "known": {"planning": 10}}
    output = mod.format_text(*_minimal_args(mod), intent_dist=dist)
    assert_true("WARN" in output, "WARN label missing when unknown_pct > 50%")
    print("PASS  format_text 4c high-unknown WARN label")


def test_format_md_intent_section_with_data():
    mod = _load_aq_report()
    dist = {"total": 100, "unknown": 43, "unknown_pct": 43.0, "known": {"knowledge_lookup": 54}}
    output = mod.format_md(*_minimal_args(mod), intent_dist=dist)
    assert_true("4c. Intent Classification" in output, "4c section missing from format_md")
    assert_true("| Traces (n) | 100 |" in output, "traces row missing in md table")
    assert_true("knowledge lookup" in output or "knowledge_lookup" in output, "known intent missing in md")
    print("PASS  format_md 4c with data")


def test_format_json_intent_distribution():
    mod = _load_aq_report()
    dist = {"total": 100, "unknown": 43, "unknown_pct": 43.0, "known": {"knowledge_lookup": 54}}
    args = _minimal_args(mod)
    output = mod.format_json(*args, intent_dist=dist)
    doc = json.loads(output)
    assert_true("intent_distribution" in doc, "intent_distribution key missing from format_json output")
    assert_true(doc["intent_distribution"].get("total") == 100, "total wrong in format_json")
    assert_true(doc["intent_distribution"].get("unknown_pct") == 43.0, "unknown_pct wrong in format_json")
    print("PASS  format_json intent_distribution kwarg")


def test_format_json_intent_distribution_no_data():
    mod = _load_aq_report()
    args = _minimal_args(mod)
    output = mod.format_json(*args, intent_dist=None)
    doc = json.loads(output)
    assert_true("intent_distribution" in doc, "intent_distribution key missing when None")
    assert_true(doc["intent_distribution"] == {}, "intent_distribution should be empty dict when None")
    print("PASS  format_json intent_distribution no data")


def test_dashboard_html_intent_tile_present():
    html = (ROOT / "dashboard.html").read_text()
    assert_true("statIntentUnknown" in html, "statIntentUnknown tile missing from dashboard.html")
    assert_true("vIntentUnknown" in html, "vIntentUnknown value element missing")
    assert_true("vIntentUnknownDetail" in html, "vIntentUnknownDetail element missing")
    assert_true("Unknown Intent" in html, "tile label missing")
    print("PASS  dashboard.html has statIntentUnknown tile")


def test_dashboard_js_wires_intent_tile():
    js = (ROOT / "assets" / "dashboard.js").read_text()
    assert_true("vIntentUnknown" in js, "vIntentUnknown not wired in dashboard.js")
    assert_true("unknownCount" in js or "unknown_count" in js or "traceIntents.unknown" in js, "unknown count not computed in dashboard.js")
    assert_true("unknownPct" in js, "unknownPct not computed in dashboard.js")
    assert_true("statIntentUnknown" in js, "statIntentUnknown tile not updated in dashboard.js")
    print("PASS  dashboard.js wires vIntentUnknown tile")


def test_fetch_intent_distribution_in_aq_report():
    mod = _load_aq_report()
    assert_true(hasattr(mod, "fetch_intent_distribution"), "fetch_intent_distribution missing from aq-report")
    print("PASS  fetch_intent_distribution present in aq-report")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_format_text_intent_section_with_data,
        test_format_text_intent_section_no_data,
        test_format_text_intent_high_unknown_warn,
        test_format_md_intent_section_with_data,
        test_format_json_intent_distribution,
        test_format_json_intent_distribution_no_data,
        test_dashboard_html_intent_tile_present,
        test_dashboard_js_wires_intent_tile,
        test_fetch_intent_distribution_in_aq_report,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
