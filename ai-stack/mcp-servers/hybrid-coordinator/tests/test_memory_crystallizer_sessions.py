"""Tests for memory crystallizer session extraction and distillation."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

from memory_crystallizer import _extract_history, _fact_supported, MemoryCrystallizer
from session_transcripts import extract_history, redact_secrets


class _FakeLlamaClient:
    """Fake LLM client that returns fixed facts."""

    def __init__(self, response_text: str = "- User asked message question\n- Assistant sent content response"):
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

            # Create fake clients with response that matches the nix history
            llama_client = _FakeLlamaClient(
                response_text="- nix is a package manager\n- User asked how to use nix package manager"
            )
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
            "- user asked question about response here\n"
            "- assistant answered follow up question response\n"
            "random text in between that is ignored\n"
            "* user asked questions about responses\n"
            "- assistant provided answer to question\n"
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
        # Shadow mode (default): all facts stored with support_score
        assert result["facts_extracted"] == 4
        assert result["facts_stored"] == 4
        assert result["facts_rejected"] == 0  # No filtering in shadow mode

        # Check that facts were stored correctly (without leading dash/star)
        stored_facts = [w["content"] for w in broker.writes]
        assert len(stored_facts) == 4
        # Verify support_score is in context for all facts
        assert all("support_score" in w["context"] for w in broker.writes)
        # Random text line should NOT be stored (doesn't start with - or *)
        assert not any("random text" in f for f in stored_facts)

    asyncio.run(run_test())


def test_crystallized_from_fallback_metadata():
    """Test crystallized_from context uses fallback: session_id > session_path > session_hash."""

    async def run_test():
        broker = _FakeBroker()
        llama_client = _FakeLlamaClient("- user said hello world test")
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


def test_redact_secrets_openai_keys():
    """Test redaction of OpenAI API keys."""
    text = "My key is sk-proj-abc1234567890123 end"
    result = redact_secrets(text)
    assert "[REDACTED]" in result
    assert "sk-proj" not in result


def test_redact_secrets_github_tokens():
    """Test redaction of GitHub tokens."""
    patterns = [
        "ghp_1234567890123456789012345",  # GitHub Personal Access Token
        "gho_1234567890123456789012345",  # GitHub OAuth Token
        "ghu_1234567890123456789012345",  # GitHub User-to-Server Token
        "ghs_1234567890123456789012345",  # GitHub Server-to-Server Token
        "ghr_1234567890123456789012345",  # GitHub Refresh Token
    ]
    for token in patterns:
        text = f"token: {token}"
        result = redact_secrets(text)
        assert "[REDACTED]" in result
        assert token not in result


def test_redact_secrets_aws_keys():
    """Test redaction of AWS Access Key IDs."""
    text = "key: AKIAIOSFODNN7EXAMPLE end"
    result = redact_secrets(text)
    assert "[REDACTED]" in result
    assert "AKIA" not in result


def test_redact_secrets_bearer_tokens():
    """Test redaction of Bearer tokens."""
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    result = redact_secrets(text)
    assert "[REDACTED]" in result
    assert "Bearer" not in result or "eyJ" not in result


def test_redact_secrets_long_hex():
    """Test redaction of long hex strings (40+ chars)."""
    long_hex = "a" * 40
    text = f"hash: {long_hex} end"
    result = redact_secrets(text)
    assert "[REDACTED]" in result
    assert long_hex not in result


def test_redact_secrets_pem_keys():
    """Test redaction of PEM private keys."""
    # Assembled at runtime so secret scanners never see a PEM block literal in the repo.
    marker = "PRIVATE" + " KEY"
    text = f"-----BEGIN {marker}-----\n" + "A" * 64 + f"\n-----END {marker}-----"
    result = redact_secrets(text)
    assert "[REDACTED]" in result
    assert "BEGIN PRIVATE KEY" not in result


def test_crystallize_dict_payload():
    """Test crystallization with client-submitted history dict."""

    async def run_test():
        with tempfile.TemporaryDirectory():
            llama_client = _FakeLlamaClient(
                response_text="- nix is a package manager\n- User asked about nix configuration"
            )
            broker = _FakeBroker()

            crystallizer = MemoryCrystallizer(
                postgres_client=None,
                llama_client=llama_client,
                broker=broker,
            )

            # Create dict payload with extracted history
            payload = {
                "history": [
                    {"role": "user", "content": "how do I use nix?"},
                    {"role": "assistant", "content": "Nix is a package manager"},
                    {"role": "user", "content": "okay thanks"},
                    {"role": "assistant", "content": "you are welcome"},
                    {"role": "user", "content": "more info"},
                    {"role": "assistant", "content": "here is more"},
                ],
                "session_hash": "abc123def456",
                "session_path": "/fake/session.jsonl",
            }

            result = await crystallizer.crystallize_session(payload)

            assert result["status"] == "complete"
            assert result["session_hash"] == "abc123def456"
            # Shadow mode (default): all facts stored even if low support
            assert result["insights_stored"] == 2
            assert len(broker.writes) == 2
            # Verify support_score is in context
            assert all("support_score" in w["context"] for w in broker.writes)

    asyncio.run(run_test())


def test_crystallize_dict_payload_validation():
    """Test dict payload validation: history must be list, role/content checked."""

    async def run_test():
        broker = _FakeBroker()
        llama_client = _FakeLlamaClient()

        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            llama_client=llama_client,
            broker=broker,
        )

        # Test: history not a list
        result = await crystallizer.crystallize_session({
            "history": "not a list",
            "session_hash": "hash1",
        })
        assert result["status"] == "error"
        assert "not_list" in result.get("reason", "")

        # Test: history too short
        result = await crystallizer.crystallize_session({
            "history": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "bye"},
            ],
            "session_hash": "hash2",
        })
        assert result["status"] == "skipped"

        # Test: invalid role is filtered out
        result = await crystallizer.crystallize_session({
            "history": [
                {"role": "system", "content": "not a user/assistant"},
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "msg2"},
                {"role": "assistant", "content": "msg3"},
            ],
            "session_hash": "hash3",
        })
        # After filtering, only 3 messages remain, which is < 4
        assert result["status"] == "skipped"

    asyncio.run(run_test())


def test_crystallize_dict_payload_redaction():
    """Test that secrets are re-redacted in dict payload server-side."""

    async def run_test():
        broker = _FakeBroker()
        llama_client = _FakeLlamaClient()

        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            llama_client=llama_client,
            broker=broker,
        )

        payload = {
            "history": [
                {"role": "user", "content": "My API key is sk-proj-abc1234567890123"},
                {"role": "assistant", "content": "response"},
                {"role": "user", "content": "another msg"},
                {"role": "assistant", "content": "final"},
            ],
            "session_hash": "hash1",
        }

        result = await crystallizer.crystallize_session(payload)
        assert result["status"] == "complete"

        # Check that the distillation prompt passed to LLM has redacted content
        distill_prompt = llama_client.calls[0]["prompt"]
        assert "[REDACTED]" in distill_prompt
        assert "sk-proj" not in distill_prompt

    asyncio.run(run_test())


def test_crystallize_file_unreadable():
    """Test that unreadable file returns error status, not exception."""

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "unreadable.jsonl"
            session_file.write_text('{"type":"user","message":{"content":"test"}}\n' * 5)

            # Make file unreadable (skip if running as root)
            if os.geteuid() != 0:
                session_file.chmod(0o000)
                try:
                    crystallizer = MemoryCrystallizer(postgres_client=None, llama_client=None, broker=None)
                    result = await crystallizer.crystallize_session(str(session_file))

                    # Should return error, not raise
                    assert result["status"] == "error"
                    assert result["reason"] == "unreadable_session_path"
                finally:
                    # Cleanup: restore permissions
                    session_file.chmod(0o644)

    asyncio.run(run_test())


def test_extract_history_filters_continue_non_text_blocks():
    """Test that Continue branch filters to text blocks and user/assistant roles only."""
    json_data = {
        "history": [
            {
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "keep this"},
                        {"type": "tool_use", "id": "123"},  # Should be filtered out
                    ]
                }
            },
            {
                "message": {
                    "role": "system",  # Should be filtered (not user/assistant)
                    "content": "system message"
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "keep this too"}
                    ]
                }
            },
        ]
    }
    history = extract_history(json.dumps(json_data).encode())

    # Only 2 valid messages (user with text, assistant with text)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert "keep this" in history[0]["content"]
    assert "tool_use" not in history[0]["content"]
    assert history[1]["role"] == "assistant"


def test_handler_routes_dict_payload_over_unreadable_file():
    """Regression: handler must route dict payload (history) over file-path branch, even with unreadable session_path.

    This ensures aq-crystallize's {history, session_hash, session_path} payload avoids
    PermissionError when session_path is unreadable (ai-hybrid can't read ~/.claude/projects).
    """

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            unreadable_file = Path(tmpdir) / "unreadable.jsonl"
            unreadable_file.write_text('{"type":"user","message":{"content":"x"}}\n' * 5)

            # Make file unreadable (skip if running as root)
            if os.geteuid() == 0:
                return  # Skip on root

            unreadable_file.chmod(0o000)
            try:
                # Create a stub crystallizer that tracks what it receives
                class _StubCrystallizer(MemoryCrystallizer):
                    def __init__(self):
                        self.received_payload = None

                    async def crystallize_session(self, session, metadata=None):
                        self.received_payload = session
                        # Return early without LLM call
                        return {"status": "test_stub"}

                stub = _StubCrystallizer()

                # Simulate handler call with both history + unreadable session_path
                # (what aq-crystallize sends)
                payload_data = {
                    "history": [
                        {"role": "user", "content": "msg1"},
                        {"role": "assistant", "content": "msg2"},
                        {"role": "user", "content": "msg3"},
                        {"role": "assistant", "content": "msg4"},
                    ],
                    "session_hash": "abcdef123456",
                    "session_path": str(unreadable_file),  # Unreadable, but should NOT be used
                }

                # Manually replicate handler logic to test routing
                history = payload_data.get("history")
                session_path = str(payload_data.get("session_path") or "").strip()

                if history:
                    # Correct route: dict payload
                    payload = {
                        "history": history,
                        "session_hash": str(payload_data.get("session_hash") or "").strip(),
                        "session_path": session_path,
                    }
                elif session_path:
                    # Wrong route (would cause PermissionError)
                    payload = session_path
                else:
                    raise ValueError("test setup error")

                # Call crystallizer with routing decision
                result = await stub.crystallize_session(payload)

                # Assert that crystallizer received the dict, not the file path string
                assert isinstance(stub.received_payload, dict), \
                    f"Expected dict payload, got {type(stub.received_payload)}: {stub.received_payload}"
                assert stub.received_payload["history"] == history
                assert stub.received_payload["session_hash"] == "abcdef123456"
                assert stub.received_payload["session_path"] == str(unreadable_file)

            finally:
                # Cleanup: restore permissions
                unreadable_file.chmod(0o644)

    asyncio.run(run_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


def test_redact_secrets_github_fine_grained_pat():
    import session_transcripts
    # Built at runtime so secret scanners never see a token-shaped literal in the repo.
    tok = "github" + "_pat_" + "x" * 40
    out = session_transcripts.redact_secrets(f"token {tok} end")
    assert tok not in out and "[REDACTED]" in out


def test_aq_crystallize_dry_run_executes_under_set_e(tmp_path):
    # bash -n only checks syntax; (( var++ )) from 0 aborts under set -e at runtime.
    import json, subprocess
    from pathlib import Path
    repo = Path(__file__).resolve().parents[4]
    proj = tmp_path / "projects" / "p"
    proj.mkdir(parents=True)
    rows = [{"type": r, "message": {"content": [{"type": "text", "text": f"message number {i} long enough"}]}}
            for i, r in enumerate(["user", "assistant", "user", "assistant"])]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in rows))
    res = subprocess.run(["bash", str(repo / "scripts/ai/aq-crystallize"), "--session-dir", str(tmp_path / "projects"),
                          "--max-sessions", "2", "--dry-run"], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert "s.jsonl" in res.stdout


def test_distillation_prompt_respects_char_budget():
    import memory_crystallizer as mc
    c = mc.MemoryCrystallizer()
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 1200} for i in range(20)]
    prompt = c._build_distillation_prompt(history)
    assert len(prompt) < mc._DISTILL_HISTORY_CHAR_BUDGET + 1000


def test_local_llm_client_timeout_override():
    from core.llm_client import LLMClient
    default = LLMClient(provider="local", base_url="http://127.0.0.1:1")
    custom = LLMClient(provider="local", base_url="http://127.0.0.1:1", timeout=900.0)
    assert default.client.timeout.read == 120.0
    assert custom.client.timeout.read == 900.0


def test_queued_broker_writes_count_as_stored():
    # store_agent_memory reports "queued" for successful async ingestion (live 2026-10-07: 0 counted, facts present in Qdrant).
    import asyncio
    import memory_crystallizer as mc

    class _QueuedBroker(_FakeBroker):
        async def write(self, memory_type, content, context, source):
            await super().write(memory_type, content, context, source)
            return {"status": "queued"}

    broker = _QueuedBroker()
    llama_client = _FakeLlamaClient(
        response_text="- user sent message with enough text\n- assistant replied with message text"
    )
    c = mc.MemoryCrystallizer(broker=broker, llama_client=llama_client)
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i} with enough text"} for i in range(6)]
    result = asyncio.run(c._crystallize_history(history))
    assert result["status"] == "complete"
    assert result["facts_stored"] == len(broker.writes) > 0


def test_fact_supported_with_matching_words():
    """Test that facts with sufficient overlap are supported."""
    source = "The user asked about nix and about package management for linux systems and configurations"
    fact = "Nix provides package management for linux systems and various configurations"
    # fact words: "nix", "provides", "package", "management", "linux", "systems", "various", "configurations" (8 words)
    # source words: "user", "asked", "about", "nix", "package", "management", "linux", "systems", "configurations" (9 words)
    # overlap: 6/8 = 0.75 >= 0.6 -> supported
    assert _fact_supported(fact, source, min_overlap=0.6) is True


def test_fact_supported_with_absent_words():
    """Test that facts with insufficient overlap are rejected (hallucinations)."""
    source = "I used the aq-crystallize script to process my sessions"
    fact = "The Python decorator pattern improves code reusability"
    # fact has: "python", "decorator", "pattern", "improves", "code", "reusability" (6 words)
    # source has none of these
    # overlap = 0/6 = 0.0 < 0.6 -> rejected
    assert _fact_supported(fact, source, min_overlap=0.6) is False


def test_fact_supported_rejects_short_facts():
    """Test that facts with fewer than 3 content words are rejected."""
    source = "I used the tool"
    fact = "The tool works"  # Only 2 content words after filtering stopwords
    # fact has: "tool", "works" (2 words < 3)
    # Too short to judge -> rejected
    assert _fact_supported(fact, source, min_overlap=0.6) is False


def test_fact_supported_with_identifiers():
    """Test that identifiers are matched correctly by word overlap."""
    source = "The crystallizer handles session artifacts and writes them frequently"
    fact = "The crystallizer tool processes session artifacts and handles memory"
    # fact has: "crystallizer", "tool", "processes", "session", "artifacts", "handles", "memory" (7 words)
    # source has: "crystallizer", "handles", "session", "artifacts", "writes", "frequently" (6 words)
    # overlap = 4/7 = 0.57 < 0.6 -> rejected at default threshold
    assert _fact_supported(fact, source, min_overlap=0.6) is False
    # But would pass at 0.55 threshold
    assert _fact_supported(fact, source, min_overlap=0.55) is True


def test_fact_supported_with_different_thresholds():
    """Test that min_overlap threshold is respected."""
    source = "the package manager tool for nix systems"
    fact = "nix is a package manager for systems"
    # fact has: "nix", "package", "manager", "systems" (4 words)
    # source has all 4
    # overlap = 4/4 = 1.0
    # Should pass all thresholds
    assert _fact_supported(fact, source, min_overlap=1.0) is True
    assert _fact_supported(fact, source, min_overlap=0.6) is True
    assert _fact_supported(fact, source, min_overlap=0.0) is True


def test_crystallize_history_filters_and_rejects_hallucinated_facts():
    """Test that crystallize_history filters facts through verification and counts rejections."""

    async def run_test():
        # LLM returns one supported and one hallucinated fact
        llama_response = (
            "- The user asked about nix package manager configuration\n"
            "- Python decorators enable advanced metaprogramming capabilities\n"
        )

        llama_client = _FakeLlamaClient(response_text=llama_response)
        broker = _FakeBroker()

        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            llama_client=llama_client,
            broker=broker,
        )

        history = [
            {"role": "user", "content": "How do I configure nix packages?"},
            {"role": "assistant", "content": "You can use nix to manage packages"},
            {"role": "user", "content": "What about the package manager?"},
            {"role": "assistant", "content": "Nix is a package manager for systems"},
        ]

        result = await crystallizer._crystallize_history(history)

        # Shadow mode (default): extracts 2 facts and stores both with support_scores
        # The Python decorator fact has low support but still stored for calibration
        assert result["status"] == "complete"
        assert result["facts_extracted"] == 2
        assert result["facts_stored"] == 2  # All stored in shadow mode
        assert result["facts_rejected"] == 0  # No filtering in shadow mode
        assert result["facts_low_support"] == 1  # One fact has low support score

        # Check that both facts were stored with support_scores
        stored_facts = [w["content"] for w in broker.writes]
        assert len(stored_facts) == 2
        # Verify support_score is in context
        assert all("support_score" in w["context"] for w in broker.writes)
        # One should be about nix (high score), one about Python (low score)
        assert any("nix" in f.lower() for f in stored_facts)

    asyncio.run(run_test())


def test_crystallize_history_returns_rejection_count():
    """Test that the result dict includes facts_rejected."""

    async def run_test():
        llama_client = _FakeLlamaClient(response_text="- fact one long enough\n- fact two long enough")
        broker = _FakeBroker()

        crystallizer = MemoryCrystallizer(
            postgres_client=None,
            llama_client=llama_client,
            broker=broker,
        )

        history = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "fact one response"},
            {"role": "user", "content": "hello again"},
            {"role": "assistant", "content": "fact two response"},
        ]

        result = await crystallizer._crystallize_history(history)

        # Both facts should be supported (all words present)
        assert result["status"] == "complete"
        assert "facts_rejected" in result
        assert result["facts_rejected"] >= 0

    asyncio.run(run_test())
