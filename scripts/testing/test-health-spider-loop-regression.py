#!/usr/bin/env python3
"""Verify closed-loop eval regression detection in aq-health-spider."""

import importlib.machinery
import json
from pathlib import Path

SPIDER = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-health-spider"
health_spider = importlib.machinery.SourceFileLoader("aq_health_spider", str(SPIDER)).load_module()


def test_loop_eval_regression_detects_threshold_drop(tmp_path):
    results = tmp_path / "training-loop-results.jsonl"
    results.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"run_id": "loop-a", "pass_rate": 0.92},
                {"run_id": "loop-b", "pass_rate": 0.78},
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = health_spider._read_training_results(results)
    anomaly = health_spider._loop_eval_regression(rows)

    assert anomaly is not None
    assert anomaly["type"] == "loop_eval_regression"
    assert anomaly["previous_run"] == "loop-a"
    assert anomaly["latest_run"] == "loop-b"
    assert anomaly["drop"] == 0.14


def test_loop_eval_regression_ignores_small_drop(tmp_path):
    results = tmp_path / "training-loop-results.jsonl"
    results.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"run_id": "loop-a", "pass_rate": 0.92},
                {"run_id": "loop-b", "pass_rate": 0.86},
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = health_spider._read_training_results(results)

    assert health_spider._loop_eval_regression(rows) is None


def test_closed_loop_check_includes_eval_regression(tmp_path, monkeypatch):
    results = tmp_path / "training-loop-results.jsonl"
    results.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"run_id": "loop-a", "pass_rate": 0.91},
                {"run_id": "loop-b", "pass_rate": 0.70},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(health_spider, "_TRAINING_RESULTS_PATHS", [results])
    monkeypatch.setattr(health_spider, "_TRAINING_SPOOL_PATHS", [tmp_path / "missing.jsonl"])
    monkeypatch.setattr(health_spider, "_CODEX_BIN", __file__)

    anomalies = health_spider._closed_loop_check()

    assert "loop_eval_regression" in {a["type"] for a in anomalies}
    assert "loop_never_ran" not in {a["type"] for a in anomalies}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
