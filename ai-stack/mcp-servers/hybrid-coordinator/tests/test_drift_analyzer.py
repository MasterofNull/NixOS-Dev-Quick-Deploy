import asyncio

from drift_analyzer import DriftAnalyzer


class _FakePostgres:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, _query, _limit):
        return self.rows


def test_drift_analyzer_degrades_without_postgres():
    result = asyncio.run(DriftAnalyzer(None).compute_drift())

    assert result["drift_score"] is None
    assert result["error"] == "postgres_unavailable"
    assert result["alert_triggered"] is False


def test_drift_analyzer_scores_recent_trace_window():
    rows = [
        {"intent": "ops", "retrieval_hits": 3, "total_ms": 100},
        {"intent": "code", "retrieval_hits": 0, "total_ms": 160},
        {"intent": "ops", "retrieval_hits": 0, "total_ms": 260},
    ]
    result = asyncio.run(DriftAnalyzer(_FakePostgres(rows), threshold=0.5).compute_drift(window=3))

    assert result["window_size"] == 3
    assert 0.0 <= result["drift_score"] <= 1.0
    assert result["breakdown"]["intent_flip_rate"] == 1.0
    assert result["alert_triggered"] is True
