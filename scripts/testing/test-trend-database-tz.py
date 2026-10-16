#!/usr/bin/env python3
"""Regression: collect_all_metrics must sort naive (sqlite) + aware (run-event) times."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_AI_STACK = Path(__file__).resolve().parents[2] / "ai-stack" / "autonomous-improvement"
sys.path.insert(0, str(_AI_STACK))

import trend_database as td


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "routing.db"
        now = datetime.now(timezone.utc)
        fmt = "%Y-%m-%d %H:%M:%S"  # SQLite CURRENT_TIMESTAMP: UTC, naive, space
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE routing_decisions (timestamp TEXT, tier TEXT, success INT, response_time_ms REAL)")
            c.execute("INSERT INTO routing_decisions VALUES (?, 'local', 1, 10.0)",
                      ((now - timedelta(minutes=30)).strftime(fmt),))
            c.execute("INSERT INTO routing_decisions VALUES (?, 'remote', 1, 10.0)",
                      ((now - timedelta(hours=25)).strftime(fmt),))
        exp = Path(tmp) / "exp.sqlite"
        with sqlite3.connect(exp) as c:
            c.execute("CREATE TABLE experiments (created_at TEXT, accepted INT)")
            c.execute("INSERT INTO experiments VALUES (?, 1)", ((now - timedelta(minutes=30)).isoformat(),))
            c.execute("INSERT INTO experiments VALUES (?, 0)", ((now - timedelta(hours=25)).isoformat(),))

        aware = td.MetricSnapshot(
            time=datetime.now(timezone.utc), metric_name="x", metric_value=1.0,
            metric_unit="pct", service="s", component="c",
        )
        orig = td._collect_run_events
        td._collect_run_events = lambda *_a, **_k: ([aware], {})
        try:
            tdb = td.TrendDatabase(routing_metrics_db=db)
            tdb.experiments_db = exp
            metrics = tdb.collect_all_metrics(24)
        finally:
            td._collect_run_events = orig

        assert any(m.metric_name == "local_routing_pct" for m in metrics), "naive source missing"
        routing = [m for m in metrics if m.component == "routing"]
        assert len(routing) == 1 or len({m.metric_name for m in routing}) >= 1
        assert all(m.metric_value == 1.0 for m in routing if m.metric_name == "local_routing_pct"), "25h row leaked"
        expm = [m for m in metrics if m.metric_name == "experiment_success_rate"]
        assert len(expm) == 1 and expm[0].metric_value == 1.0, expm
        for m in routing + expm:
            assert abs((now - m.time).total_seconds() - 1800) < 120, m.time
        assert aware in metrics, "aware source missing"
        assert all(m.time.tzinfo is not None and m.time.utcoffset() == timedelta(0) for m in metrics)
        assert [m.time for m in metrics] == sorted(m.time for m in metrics)

    assert td._to_utc(datetime(2026, 1, 1)).tzinfo is timezone.utc
    print("PASS test-trend-database-tz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
