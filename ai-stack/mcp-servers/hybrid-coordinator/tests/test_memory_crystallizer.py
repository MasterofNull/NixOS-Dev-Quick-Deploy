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


class _FakeBroker:
    def __init__(self):
        self.writes = []

    async def write(self, memory_type: str, content: str, context: dict, source: str):
        self.writes.append({"memory_type": memory_type, "content": content})
        return {"status": "stored"}


class _FakeLlamaClient:
    def __init__(self, response_text: str = "- user sent message text\n- assistant replied message"):
        self.calls = []
        self.response_text = response_text

    async def create_message(self, prompt: str, max_tokens: int, temperature: float, system: str):
        self.calls.append({"prompt": prompt})

        class FakeResponse:
            def __init__(self, content):
                self.content = content

        return FakeResponse(self.response_text)


def test_crystallizer_ddl_tracks_session_hash():
    assert "CREATE TABLE IF NOT EXISTS crystallized_sessions" in DDL_CRYSTALLIZED_SESSIONS
    assert "session_hash" in DDL_CRYSTALLIZED_SESSIONS


def test_crystallizer_is_idempotent(tmp_path: Path):
    # Create a session with enough messages to avoid skipping
    session = tmp_path / "session.jsonl"
    session.write_text(
        '{"type":"user","message":{"content":"hello"}}\n'
        '{"type":"assistant","message":{"content":"response"}}\n'
        '{"type":"user","message":{"content":"more"}}\n'
        '{"type":"assistant","message":{"content":"more response"}}\n'
    )
    pg = _FakePostgres()
    crystallizer = MemoryCrystallizer(
        postgres_client=pg,
        llama_client=_FakeLlamaClient(),
        broker=_FakeBroker(),
    )

    first = asyncio.run(crystallizer.crystallize_session(str(session)))
    second = asyncio.run(crystallizer.crystallize_session(str(session)))

    assert first["status"] == "complete"
    assert second["status"] == "already_processed"
    assert any("CREATE TABLE IF NOT EXISTS crystallized_sessions" in query for query, _ in pg.executed)


def test_crystallizer_emits_runtime_learning_metadata(tmp_path: Path):
    session = tmp_path / "session.jsonl"
    session.write_text(
        '{"type":"user","message":{"content":"hello world"}}\n'
        '{"type":"assistant","message":{"content":"response here"}}\n'
        '{"type":"user","message":{"content":"more"}}\n'
        '{"type":"assistant","message":{"content":"more response"}}\n'
    )

    broker = _FakeBroker()
    llama_client = _FakeLlamaClient(
        response_text="- fact user said hello world response\n- fact assistant provided more response"
    )
    crystallizer = MemoryCrystallizer(
        postgres_client=None,
        llama_client=llama_client,
        broker=broker,
    )

    asyncio.run(crystallizer.crystallize_session(str(session)))

    assert len(broker.writes) > 0
    # Verify facts were extracted and stored via broker
    stored_facts = [w["content"] for w in broker.writes]
    assert any("fact" in f for f in stored_facts)
