"""sync_query_gaps_to_jsonl logs an unwritable path once, then recovers quietly."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

it = pytest.importorskip("extensions.interaction_tracker")


class _PG:
    async def fetch_all(self, *_a, **_k):
        return [{"query_text": "q", "occurrences": 2, "avg_score": 0.1}]


def test_warns_once_then_recovers(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(it, "_postgres", _PG())
    monkeypatch.setattr(it, "_gap_sync_last_error", None)
    d = tmp_path / "ro"
    d.mkdir()
    target = d / "query-gaps.jsonl"
    d.chmod(0o500)
    try:
        with caplog.at_level(logging.INFO, logger="hybrid-coordinator"):
            for _ in range(3):
                asyncio.run(it.sync_query_gaps_to_jsonl(str(target)))
            warns = [r for r in caplog.records if "sync_query_gaps_failed" in r.getMessage()]
            if not warns:
                pytest.skip("running as a user that bypasses DAC")
            assert len(warns) == 1
            d.chmod(0o700)
            assert asyncio.run(it.sync_query_gaps_to_jsonl(str(target))) == 1
            assert any("gap_sync_recovered" in r.getMessage() for r in caplog.records)
    finally:
        d.chmod(0o700)
