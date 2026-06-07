#!/usr/bin/env python3
"""
Phase 143 regression: RAGAS metrics panel (4b) in aq-report format_text and format_md.

Checks that both formatters accept ragas_metrics kwarg and emit the 4b section
with correct values or a no-data fallback.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_aq_report():
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("aq_report", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _minimal_args(mod):
    """Minimal positional args required by format_text / format_md."""
    no: dict = {"available": False}
    empty_list: list = []
    return (
        "7d",          # since_label
        {},            # tool_stats
        no,            # route
        no,            # recent_route
        {},            # routing_windows
        no,            # cache
        {},            # cache_prewarm
        no,            # eval_trend
        empty_list,    # leaderboard
        empty_list,    # top_prompts
        empty_list,    # gaps
        {},            # rag_posture_summary
        {},            # recent_health
        no,            # continue_editor
        {},            # continue_editor_windows
        {},            # editor_rescue_windows_summary
        {},            # shared_skill_registry
        {},            # delegated_prompt_failures
        {},            # delegated_prompt_failure_windows
        {},            # remote_profile_summary
        {},            # remote_profile_windows
        {},            # route_latency_decomposition
        {},            # retrieval_breadth
        {},            # retrieval_breadth_windows
        {},            # provider_fallbacks
        {},            # historical_watch
        empty_list,    # recs
    )


def test_format_text_ragas_panel_with_data():
    mod = _load_aq_report()
    rm = {
        "sample_count": 22,
        "answer_relevance_avg": 0.5194,
        "context_precision_avg": 0.2662,
        "faithfulness_avg": None,
        "faithfulness_enabled": True,
    }
    output = mod.format_text(*_minimal_args(mod), ragas_metrics=rm)
    assert_true("4b. RAGAS Metrics" in output, "4b section header missing from format_text")
    assert_true("Samples: 22" in output, "sample_count missing")
    assert_true("0.5194" in output, "answer_relevance_avg missing")
    assert_true("0.2662" in output, "context_precision_avg missing")
    assert_true("Qwen-judge" in output, "faithfulness enabled label missing")
    print("PASS  format_text with data")


def test_format_text_ragas_panel_no_data():
    mod = _load_aq_report()
    output = mod.format_text(*_minimal_args(mod), ragas_metrics={})
    assert_true("4b. RAGAS Metrics" in output, "4b section header missing when no data")
    assert_true("No RAGAS samples" in output, "no-data fallback message missing")
    print("PASS  format_text no data")


def test_format_text_ragas_panel_none():
    mod = _load_aq_report()
    output = mod.format_text(*_minimal_args(mod), ragas_metrics=None)
    assert_true("4b. RAGAS Metrics" in output, "4b section header missing when ragas_metrics=None")
    assert_true("No RAGAS samples" in output, "no-data fallback message missing")
    print("PASS  format_text ragas_metrics=None")


def test_format_md_ragas_panel_with_data():
    mod = _load_aq_report()
    rm = {
        "sample_count": 10,
        "answer_relevance_avg": 0.6000,
        "context_precision_avg": 0.3333,
        "faithfulness_avg": 0.7500,
        "faithfulness_enabled": True,
    }
    output = mod.format_md(*_minimal_args(mod), ragas_metrics=rm)
    assert_true("4b. RAGAS Metrics" in output, "4b section header missing from format_md")
    assert_true("0.6000" in output, "answer_relevance_avg missing in md")
    assert_true("0.7500" in output, "faithfulness_avg missing in md")
    assert_true("| Samples (n) | 10 |" in output, "sample_count row missing in md table")
    print("PASS  format_md with data")


def test_format_md_ragas_panel_no_data():
    mod = _load_aq_report()
    output = mod.format_md(*_minimal_args(mod), ragas_metrics={})
    assert_true("4b. RAGAS Metrics" in output, "4b section header missing in format_md no-data")
    assert_true("No RAGAS samples" in output, "no-data fallback missing in format_md")
    print("PASS  format_md no data")


def test_faithfulness_disabled_label():
    mod = _load_aq_report()
    rm = {
        "sample_count": 5,
        "answer_relevance_avg": 0.5,
        "context_precision_avg": 0.4,
        "faithfulness_avg": None,
        "faithfulness_enabled": False,
    }
    output = mod.format_text(*_minimal_args(mod), ragas_metrics=rm)
    assert_true("disabled" in output, "faithfulness disabled label missing")
    print("PASS  faithfulness disabled label")


def test_format_json_ragas_metrics_kwarg():
    """Phase 144: format_json accepts ragas_metrics kwarg and emits it in the JSON doc."""
    import json as _json
    mod = _load_aq_report()
    rm = {
        "sample_count": 22,
        "answer_relevance_avg": 0.5194,
        "context_precision_avg": 0.2662,
        "faithfulness_avg": None,
        "faithfulness_enabled": True,
    }
    # format_json takes *fmt_args[:-1] positionally — same as minimal_args minus last
    args = _minimal_args(mod)
    output = mod.format_json(*args, ragas_metrics=rm)
    doc = _json.loads(output)
    assert_true("ragas_metrics" in doc, "ragas_metrics key missing from format_json output")
    assert_true(doc["ragas_metrics"].get("sample_count") == 22, "sample_count wrong in format_json")
    assert_true(doc["ragas_metrics"].get("answer_relevance_avg") == 0.5194, "AR avg wrong in format_json")
    print("PASS  format_json ragas_metrics kwarg")


def test_format_json_ragas_metrics_no_data():
    """Phase 144: format_json emits empty ragas_metrics when kwarg is None."""
    import json as _json
    mod = _load_aq_report()
    args = _minimal_args(mod)
    output = mod.format_json(*args, ragas_metrics=None)
    doc = _json.loads(output)
    assert_true("ragas_metrics" in doc, "ragas_metrics key missing when None passed")
    assert_true(doc["ragas_metrics"] == {}, "ragas_metrics should be empty dict when None")
    print("PASS  format_json ragas_metrics no data")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_format_text_ragas_panel_with_data,
        test_format_text_ragas_panel_no_data,
        test_format_text_ragas_panel_none,
        test_format_md_ragas_panel_with_data,
        test_format_md_ragas_panel_no_data,
        test_faithfulness_disabled_label,
        test_format_json_ragas_metrics_kwarg,
        test_format_json_ragas_metrics_no_data,
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
