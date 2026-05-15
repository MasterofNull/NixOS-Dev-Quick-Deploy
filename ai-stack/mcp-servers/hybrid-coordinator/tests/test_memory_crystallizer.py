import asyncio
from pathlib import Path

from memory_crystallizer import DDL_CRYSTALLIZED_SESSIONS, MemoryCrystallizer


class _FakePostgres:
    def __init__(self):
        self.executed = []
        self.rows = []

    async def execute(self, query, *params):
        self.executed.append((query, params))

    async def fetch_all(self, query, *_params):
        if "count(*)" in query:
            return [{"sessions_processed": 1, "insights_stored": 1, "last_run": "2026-05-15"}]
        return self.rows


def test_crystallizer_ddl_tracks_session_hash():
    assert "CREATE TABLE IF NOT EXISTS crystallized_sessions" in DDL_CRYSTALLIZED_SESSIONS
    assert "session_hash" in DDL_CRYSTALLIZED_SESSIONS


def test_crystallizer_is_idempotent(tmp_path: Path):
    session = tmp_path / "session.json"
    session.write_text('{"messages":[{"role":"user","content":"hello"}]}', encoding="utf-8")
    pg = _FakePostgres()
    crystallizer = MemoryCrystallizer(postgres_client=pg)

    first = asyncio.run(crystallizer.crystallize_session(str(session)))
    second = asyncio.run(crystallizer.crystallize_session(str(session)))

    assert first["status"] == "crystallized"
    assert second["status"] == "already_processed"
    assert any("CREATE TABLE IF NOT EXISTS crystallized_sessions" in query for query, _ in pg.executed)


def test_crystallizer_emits_runtime_learning_metadata(tmp_path: Path):
    session = tmp_path / "session.json"
    session.write_text('{"messages":[{"role":"user","content":"hello"}]}', encoding="utf-8")
    stored = []

    async def _store(insight, metadata):
        stored.append((insight, metadata))
        return {"status": "stored"}

    asyncio.run(MemoryCrystallizer(store_insight_fn=_store).crystallize_session(str(session)))

    assert stored
    _insight, metadata = stored[0]
    assert metadata["promotion_status"] == "crystallized"
    assert metadata["source_event_id"].startswith("session:")
    assert metadata["scope"] == "episodic"
