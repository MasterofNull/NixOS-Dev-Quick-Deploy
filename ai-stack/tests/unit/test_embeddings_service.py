import time
import importlib.util
from pathlib import Path
import types
import sys

import pytest


fake_sentence = types.ModuleType("sentence_transformers")


class FakeSentenceTransformer:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, _text):
        return [0.1]

    def get_sentence_embedding_dimension(self):
        return 1

    @property
    def max_seq_length(self):
        return 1


fake_sentence.SentenceTransformer = FakeSentenceTransformer
sys.modules["sentence_transformers"] = fake_sentence

SERVER_PATH = Path("ai-stack/mcp-servers/embeddings-service/server.py")
spec = importlib.util.spec_from_file_location("embeddings_server", SERVER_PATH)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_validate_input_single_string():
    assert server.validate_input("hello") == ["hello"]


def test_validate_input_list():
    assert server.validate_input(["a", "b"]) == ["a", "b"]


def test_validate_input_empty_string():
    with pytest.raises(server.ValidationError):
        server.validate_input("")


def test_validate_input_non_string():
    with pytest.raises(server.ValidationError):
        server.validate_input(["ok", 1])


def test_validate_input_too_long(monkeypatch):
    monkeypatch.setattr(server, "MAX_INPUT_LENGTH", 3)
    with pytest.raises(server.ValidationError):
        server.validate_input("toolong")


def test_validate_input_batch_size(monkeypatch):
    monkeypatch.setattr(server, "MAX_BATCH_SIZE", 2)
    with pytest.raises(server.ValidationError):
        server.validate_input(["a", "b", "c"])


def test_error_payload_contains_error_id():
    payload = server.error_payload("test_error", RuntimeError("boom"))
    assert payload["error"] == "test_error"
    assert len(payload["error_id"]) == 12


def test_timeout_decorator_times_out():
    @server.timeout_decorator(0.1)
    def slow():
        time.sleep(0.5)
        return True

    with pytest.raises(TimeoutError):
        slow()


def test_load_model_with_retry_success(monkeypatch):
    class FakeModel:
        def encode(self, text):
            return [1.0]

        def get_sentence_embedding_dimension(self):
            return 1

        @property
        def max_seq_length(self):
            return 1

    monkeypatch.setattr(server, "SentenceTransformer", lambda *_args, **_kw: FakeModel())
    monkeypatch.setattr(server, "MODEL_LOAD_RETRIES", 1)
    monkeypatch.setattr(server, "MODEL_LOAD_RETRY_DELAY", 0)
    server.model_instance = None
    server.model_loading = False
    model = server.load_model_with_retry()
    assert model is not None


def test_get_process_memory_bytes_returns_int():
    assert isinstance(server._get_process_memory_bytes(), int)
