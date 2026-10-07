"""Tests for memory crystallizer session extraction and distillation."""

import asyncio
import json
import tempfile
from pathlib import Path

from memory_crystallizer import _extract_history, MemoryCrystallizer


class _FakeLlamaClient:
    """Fake LLM client that returns fixed facts."""

    def __init__(self, response_text: str = "- fact one long enough\n- fact two long enough"):
        self.response_text = response_text
        self.calls = []

    async def create_message(self, prompt: str, max_tokens: int, temperature: float, system: str):
        self.calls.append({
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
        })

        class FakeResponse:
            def __init__(self, content):
                self.content = content

        return FakeResponse(self.response_text)


class _FakeBroker:
    """Fake memory broker that records writes."""

    def __init__(self):
        self.writes = []

    async def write(self, memory_type: str, content: str, context: dict, source: str):
        self.writes.append({
            "memory_type": memory_type,
            "content": content,
            "context": context,
            "source": source,
        })
        return {"status": "stored"}


def test_extract_history_claude_jsonl():
    """Test extraction from Claude Code JSONL format."""
    jsonl_data = (
        '{"type":"user","message":{"content":"hello world"}}\n'
        '{"type":"assistant","message":{"content":"response text"}}\n'
    )
    history = _extract_history(jsonl_data.encode())

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello world"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "response text"


def test_extract_history_claude_jsonl_with_blocks():
    """Test extraction from Claude Code JSONL with mixed block types."""
    jsonl_data = (
        '{"type":"assistant","message":{"content":[{"type":"text","text":"answer here"},{"type":"tool_use","id":"123"}]}}\n'
    )
    history = _extract_history(jsonl_data.encode())

    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert "answer here" in history[0]["content"]
    assert "tool_use" not in history[0]["content"]


def test_extract_history_codex_jsonl():
    """Test extraction from Codex JSONL format."""
    jsonl_data = (
        '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"codex user input"}]}}\n'
        '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"codex output"}]}}\n'
    )
    history = _extract_history(jsonl_data.encode())

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert "codex user input" in history[0]["content"]
    assert history[1]["role"] == "assistant"
    assert "codex output" in history[1]["content"]


def test_extract_history_continue_json():
    """Test extraction from Continue JSON format."""
    json_data = {
        "history": [
            {"message": {"role": "user", "content": "continue user"}},
            {"message": {"role": "assistant", "content": "continue assistant"}},
        ]
    }
    history = _extract_history(json.dumps(json_data).encode())

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert "continue user" in history[0]["content"]
    assert history[1]["role"] == "assistant"
    assert "continue assistant" in history[1]["content"]


def test_extract_history_truncates_to_1200_chars():
    """Test that messages are truncated to 1200 characters."""
    long_text = "x" * 2000
    jsonl_data = f'{{"type":"user","message":{{"content":"{long_text}"}}}}'
    history = _extract_history(jsonl_data.encode())

    assert len(history) == 1
    assert len(history[0]["content"]) == 1200


def test_extract_history_returns_last_20_messages():
    """Test that only the last 20 messages are returned."""
    messages = []
    for i in range(30):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(f'{{"type":"{role}","message":{{"content":"message {i}"}}}}')
    jsonl_data = "\n".join(messages)

    history = _extract_history(jsonl_data.encode())

    assert len(history) == 20
    assert "message 10" in history[0]["content"]  # First of last 20
    assert "message 29" in history[19]["content"]  # Last message


def test_extract_history_skips_empty_content():
    """Test that empty messages are skipped."""
    jsonl_data = (
        '{"type":"user","message":{"content":""}}\n'
        '{"type":"user","message":{"content":"non-empty"}}\n'
    )
    history = _extract_history(jsonl_data.encode())

    assert len(history) == 1
    assert history[0]["content"] == "non-empty"


def test_crystallize_file_session_with_llama():
    """Test session crystallization with fake LLM client."""

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample session file
            session_file = Path(tmpdir) / "session.jsonl"
            session_file.write_text(
                '{"type":"user","message":{"content":"how do I use nix?"}}\n'
                '{"type":"assistant","message":{"content":"Nix is a package manager"}}\n'
                '{"type":"user","message":{"content":"okay thanks"}}\n'
                '{"type":"assistant","message":{"content":"you are welcome"}}\n'
                '{"type":"user","message":{"content":"more info"}}\n'
                '{"type":"assistant","message":{"content":"here is more"}}\n'
            )

            # Create fake clients
            llama_client = _FakeLlamaClient()
            broker = _FakeBroker()

            # Create crystallizer
            crystallizer = MemoryCrystallizer(
                postgres_client=None,
                llama_client=llama_client,
                broker=broker,
            )

            # Crystallize
            result = await crystallizer.crystallize_session(str(session_file))

            assert result["status"] == "complete"
            assert result["insights_stored"] == 2  # Two facts from fake response
            assert len(llama_client.calls) == 1
            assert len(broker.writes) == 2

    asyncio.run(run_test())


def test_crystallize_file_session_with_error():
    """Test that hash is NOT recorded on LLM error."""

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "session.jsonl"
            session_file.write_text(
                '{"type":"user","message":{"content":"msg"}}\n'
                '{"type":"assistant","message":{"content":"response"}}\n'
                '{"type":"user","message":{"content":"more"}}\n'
                '{"type":"assistant","message":{"content":"more response"}}\n'
            )

            # Create fake LLM that raises error
            class _FailingLlamaClient:
                async def create_message(self, **kwargs):
                    raise RuntimeError("LLM unavailable")

            crystallizer = MemoryCrystallizer(
                postgres_client=None,
                llama_client=_FailingLlamaClient(),
                broker=_FakeBroker(),
            )

            result = await crystallizer.crystallize_session(str(session_file))

            # Should return error, not record hash (allows retry)
            assert result["status"] == "error"
            assert result["insights_stored"] == 0

            # Calling again should NOT skip it (hash not recorded)
            result2 = await crystallizer.crystallize_session(str(session_file))
            assert result2["status"] == "error"  # Still tries, not "already_processed"

    asyncio.run(run_test())


def test_crystallize_history_filters_facts():
    """Test that only facts starting with - or * are kept, max 10."""

    async def run_test():
        llama_response = (
            "- this is a much longer fact one here\n"
            "- this is a much longer fact two here\n"
            "random text in between that is ignored\n"
            "* this is a much longer fact three here\n"
            "- this is a much longer fact four here\n"
        )

        llama_client = _FakeLlamaClient(response_text=llama_response)
        broker = _FakeBroker()

        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            llama_client=llama_client,
            broker=broker,
        )

        history = [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "follow up"},
            {"role": "assistant", "content": "response"},
        ]

        result = await crystallizer._crystallize_history(history)

        # Should have extracted 4 facts (random text line skipped, filtered by > 10 chars)
        assert result["facts_extracted"] == 4
        assert result["facts_stored"] == 4

        # Check that facts were stored correctly (without leading dash/star)
        stored_facts = [w["content"] for w in broker.writes]
        assert any("much longer fact one" in f for f in stored_facts)
        assert any("much longer fact two" in f for f in stored_facts)
        assert any("much longer fact three" in f for f in stored_facts)
        # Random text line should NOT be stored (doesn't start with - or *)
        assert not any("random text" in f for f in stored_facts)

    asyncio.run(run_test())


def test_crystallized_from_fallback_metadata():
    """Test crystallized_from context uses fallback: session_id > session_path > session_hash."""

    async def run_test():
        broker = _FakeBroker()
        llama_client = _FakeLlamaClient("- fact one long enough")
        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            broker=broker,
            llama_client=llama_client,
        )

        # History for testing
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "ok"},
        ]

        # Test 1: metadata with session_id should use session_id
        result = await crystallizer._crystallize_history(
            history,
            metadata={"session_id": "id123", "session_path": "/path/to/session", "session_hash": "hash456"}
        )
        assert result["status"] == "complete"
        assert broker.writes[-1]["context"]["crystallized_from"] == "id123"
        assert broker.writes[-1]["context"]["session_path"] == "/path/to/session"

        # Test 2: metadata without session_id should fallback to session_path
        broker.writes.clear()
        result = await crystallizer._crystallize_history(
            history,
            metadata={"session_path": "/path/to/session", "session_hash": "hash456"}
        )
        assert result["status"] == "complete"
        assert broker.writes[-1]["context"]["crystallized_from"] == "/path/to/session"
        assert broker.writes[-1]["context"]["session_path"] == "/path/to/session"

        # Test 3: metadata without session_id or session_path should fallback to session_hash
        broker.writes.clear()
        result = await crystallizer._crystallize_history(
            history,
            metadata={"session_hash": "hash456"}
        )
        assert result["status"] == "complete"
        assert broker.writes[-1]["context"]["crystallized_from"] == "hash456"
        assert "session_path" not in broker.writes[-1]["context"]

        # Test 4: empty metadata should use "unknown"
        broker.writes.clear()
        result = await crystallizer._crystallize_history(
            history,
            metadata={}
        )
        assert result["status"] == "complete"
        assert broker.writes[-1]["context"]["crystallized_from"] == "unknown"

        # Test 5: None metadata should use "unknown"
        broker.writes.clear()
        result = await crystallizer._crystallize_history(
            history,
            metadata=None
        )
        assert result["status"] == "complete"
        assert broker.writes[-1]["context"]["crystallized_from"] == "unknown"

    asyncio.run(run_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
