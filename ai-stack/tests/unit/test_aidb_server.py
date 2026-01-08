import asyncio
import importlib.util
from pathlib import Path
import sys
import types

import pytest


sys.path.insert(0, str(Path("ai-stack/mcp-servers/aidb")))
sys.path.insert(0, str(Path("ai-stack/mcp-servers")))

fake_sentence = types.ModuleType("sentence_transformers")


class FakeSentenceTransformer:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, _text, **_kwargs):
        return [0.1]

    def get_sentence_embedding_dimension(self):
        return 1

    @property
    def max_seq_length(self):
        return 1


fake_sentence.SentenceTransformer = FakeSentenceTransformer
sys.modules["sentence_transformers"] = fake_sentence

fake_otlp_pkg = types.ModuleType("opentelemetry.exporter.otlp.proto.grpc")
fake_otlp = types.ModuleType("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")


class FakeOTLPSpanExporter:
    def __init__(self, *_args, **_kwargs):
        pass


fake_otlp.OTLPSpanExporter = FakeOTLPSpanExporter
sys.modules["opentelemetry.exporter.otlp.proto.grpc"] = fake_otlp_pkg
sys.modules["opentelemetry.exporter.otlp.proto.grpc.trace_exporter"] = fake_otlp

fake_ml_engine = types.ModuleType("ml_engine")


class FakeMLEngine:
    pass


fake_ml_engine.MLEngine = FakeMLEngine
sys.modules["ml_engine"] = fake_ml_engine

fake_pgvector = types.ModuleType("pgvector")
fake_pgvector_sqlalchemy = types.ModuleType("pgvector.sqlalchemy")


class FakeVector:
    def __init__(self, *_args, **_kwargs):
        pass


fake_pgvector_sqlalchemy.Vector = FakeVector
fake_pgvector.sqlalchemy = fake_pgvector_sqlalchemy
sys.modules["pgvector"] = fake_pgvector
sys.modules["pgvector.sqlalchemy"] = fake_pgvector_sqlalchemy

SERVER_PATH = Path("ai-stack/mcp-servers/aidb/server.py")
spec = importlib.util.spec_from_file_location("aidb_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class FakeTime:
    def __init__(self):
        self.now = 1.0

    def time(self):
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_circuit_breaker_initial_state_closed():
    breaker = server.CircuitBreaker("test", failure_threshold=2, recovery_timeout=5)
    assert breaker.state == "CLOSED"


def test_circuit_breaker_opens_after_failures():
    breaker = server.CircuitBreaker("test", failure_threshold=2, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    with pytest.raises(RuntimeError):
        breaker.call(fail)
    assert breaker.state == "OPEN"


def test_circuit_breaker_open_fails_fast():
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    with pytest.raises(RuntimeError):
        breaker.call(lambda: "ok")


def test_circuit_breaker_half_open_after_timeout(monkeypatch):
    fake_time = FakeTime()
    monkeypatch.setattr(server.time, "time", fake_time.time)
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    fake_time.advance(6)
    assert breaker.state == "HALF_OPEN"


def test_circuit_breaker_stays_open_before_timeout(monkeypatch):
    fake_time = FakeTime()
    monkeypatch.setattr(server.time, "time", fake_time.time)
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    fake_time.advance(3)
    assert breaker.state == "OPEN"


def test_circuit_breaker_half_open_closes_on_success(monkeypatch):
    fake_time = FakeTime()
    monkeypatch.setattr(server.time, "time", fake_time.time)
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    fake_time.advance(6)
    assert breaker.state == "HALF_OPEN"
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state == "CLOSED"


def test_circuit_breaker_half_open_reopens_on_failure(monkeypatch):
    fake_time = FakeTime()
    monkeypatch.setattr(server.time, "time", fake_time.time)
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    fake_time.advance(6)
    assert breaker.state == "HALF_OPEN"
    with pytest.raises(RuntimeError):
        breaker.call(fail)
    assert breaker.state == "OPEN"


def test_circuit_breaker_manual_reset():
    breaker = server.CircuitBreaker("test", failure_threshold=1, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    breaker.reset()
    assert breaker.state == "CLOSED"


def test_retry_with_backoff_sync_success_first_try():
    assert server.retry_with_backoff(lambda: "ok", max_retries=2) == "ok"


def test_retry_with_backoff_sync_eventual_success():
    attempts = {"count": 0}

    def flakey():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ValueError("fail")
        return "ok"

    assert server.retry_with_backoff(flakey, max_retries=3, base_delay=0) == "ok"


def test_retry_with_backoff_sync_failure():
    def fail():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        server.retry_with_backoff(fail, max_retries=2, base_delay=0)


@pytest.mark.asyncio
async def test_retry_with_backoff_async_success_first_try():
    async def ok():
        return "ok"

    assert await server.retry_with_backoff(ok, max_retries=2) == "ok"


@pytest.mark.asyncio
async def test_retry_with_backoff_async_eventual_success():
    attempts = {"count": 0}

    async def flakey():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ValueError("fail")
        return "ok"

    assert await server.retry_with_backoff(flakey, max_retries=3, base_delay=0) == "ok"


@pytest.mark.asyncio
async def test_retry_with_backoff_async_failure():
    async def fail():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        await server.retry_with_backoff(fail, max_retries=2, base_delay=0)


def test_error_detail_contains_error_id():
    payload = server._error_detail("test_error", RuntimeError("boom"))
    assert payload["error"] == "test_error"
    assert len(payload["error_id"]) == 12


def test_get_process_memory_bytes_returns_int():
    assert isinstance(server._get_process_memory_bytes(), int)


def test_embedding_service_load_model_once(monkeypatch):
    calls = {"count": 0}

    class FakeModel:
        pass

    def fake_loader(*_args, **_kwargs):
        calls["count"] += 1
        return FakeModel()

    monkeypatch.setattr(server, "SentenceTransformer", fake_loader)
    service = server.EmbeddingService("test")
    first = service._load_model()
    second = service._load_model()
    assert first is second
    assert calls["count"] == 1


def test_circuit_breaker_failure_count_resets_on_success():
    breaker = server.CircuitBreaker("test", failure_threshold=2, recovery_timeout=5)

    def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state == "CLOSED"


def test_retry_with_backoff_max_delay(monkeypatch):
    delays = []

    def sleep_stub(duration):
        delays.append(duration)

    monkeypatch.setattr(server.time, "sleep", sleep_stub)

    attempts = {"count": 0}

    def flakey():
        attempts["count"] += 1
        raise ValueError("fail")

    with pytest.raises(ValueError):
        server.retry_with_backoff(flakey, max_retries=3, base_delay=5, max_delay=5)
    assert all(delay == 5 for delay in delays)


def test_get_process_memory_bytes_fallback(monkeypatch):
    def broken_open(*_args, **_kwargs):
        raise OSError("no proc")

    monkeypatch.setattr(server, "open", broken_open, raising=False)
    assert server._get_process_memory_bytes() == 0
