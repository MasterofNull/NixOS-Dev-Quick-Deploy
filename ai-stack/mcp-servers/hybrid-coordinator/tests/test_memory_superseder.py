import asyncio

from memory_superseder import DDL_MEMORY_SUPERSESSIONS, MemorySuperseder


class _FakePostgres:
    def __init__(self):
        self.executed = []
        self.rows = []

    async def execute(self, query, *params):
        self.executed.append((query, params))

    async def fetch_all(self, _query, limit):
        return self.rows[:limit]


def test_memory_superseder_ddl_declares_ledger_table():
    assert "CREATE TABLE IF NOT EXISTS memory_supersessions" in DDL_MEMORY_SUPERSESSIONS
    assert "old_valid_until" in DDL_MEMORY_SUPERSESSIONS


def test_memory_superseder_records_event_with_postgres_ledger():
    pg = _FakePostgres()
    superseder = MemorySuperseder(postgres_client=pg)

    result = asyncio.run(
        superseder.supersede(
            fact_id="fact-1",
            replacement="new fact",
            reason="newer evidence",
        )
    )

    assert result["superseded"] is True
    assert result["fact_id"] == "fact-1"
    assert result["ledger"] == "postgres"
    assert any("CREATE TABLE IF NOT EXISTS memory_supersessions" in query for query, _ in pg.executed)
    assert any("INSERT INTO memory_supersessions" in query for query, _ in pg.executed)


def test_memory_superseder_rejects_incomplete_payload():
    superseder = MemorySuperseder()

    try:
        asyncio.run(superseder.supersede(fact_id="", replacement="new fact", reason="newer evidence"))
    except ValueError as exc:
        assert str(exc) == "fact_id required"
    else:
        raise AssertionError("expected ValueError")
