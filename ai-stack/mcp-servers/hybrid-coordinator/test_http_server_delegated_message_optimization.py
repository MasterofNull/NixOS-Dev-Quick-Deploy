import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


HTTP_SERVER_PATH = Path(__file__).with_name("http_server.py")
TARGET_FUNCTIONS = {
    "_message_content_text",
    "_content_has_only_text_blocks",
    "_message_content_can_be_rewritten",
    "_build_text_message",
    "_replace_message_content",
    "_estimate_message_tokens",
    "_optimize_delegated_messages",
}


@dataclass
class _ContextChunk:
    chunk_id: str
    content: str
    tokens: int
    source: str


class _FakeCompressor:
    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()))

    def compress(self, text: str, strategy: str) -> SimpleNamespace:
        compressed_text = " ".join(text.split()[: min(8, len(text.split()))])
        return SimpleNamespace(
            compressed_text=compressed_text,
            original_tokens=max(1, len(text.split())),
            compressed_tokens=max(1, len(compressed_text.split())),
        )


class _FakePruner:
    def prune(self, candidate_chunks, keep_budget, query=None):
        kept = []
        pruned = []
        spent = 0
        for chunk in candidate_chunks:
            if spent + chunk.tokens <= keep_budget:
                kept.append(chunk)
                spent += chunk.tokens
            else:
                pruned.append(chunk)
        return kept, pruned


class _NoopCompressor(_FakeCompressor):
    def compress(self, text: str, strategy: str) -> SimpleNamespace:
        token_count = max(1, len(text.split()))
        return SimpleNamespace(
            compressed_text=text,
            original_tokens=token_count,
            compressed_tokens=token_count,
        )


def _load_http_server_helpers() -> Dict[str, Any]:
    source = HTTP_SERVER_PATH.read_text()
    tree = ast.parse(source, filename=str(HTTP_SERVER_PATH))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGET_FUNCTIONS
    ]
    module = ast.Module(body=selected, type_ignores=[])
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "ContextChunk": _ContextChunk,
        "CompressionStrategy": SimpleNamespace(
            ABBREVIATE="abbreviate",
            REMOVE_STOPWORDS="remove_stopwords",
        ),
        "_DELEGATED_PROMPT_COMPRESSOR": _FakeCompressor(),
        "_DELEGATED_CONTEXT_PRUNER": _FakePruner(),
    }
    exec(compile(module, str(HTTP_SERVER_PATH), "exec"), namespace)
    return namespace


def test_structured_assistant_messages_are_not_rewritten():
    helpers = _load_http_server_helpers()
    optimize = helpers["_optimize_delegated_messages"]

    structured_assistant = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "internal reasoning"},
            {"type": "redacted_thinking", "data": "opaque"},
            {"type": "text", "text": "Visible answer " * 40},
        ],
    }
    messages = [
        {"role": "system", "content": "S " * 220},
        {"role": "user", "content": "U " * 220},
        structured_assistant,
        {"role": "user", "content": "follow up question"},
    ]

    optimized, meta = optimize(messages, "remote-gemini")

    assert optimized[2]["content"] == structured_assistant["content"]
    assert meta["compressed_messages"] >= 1


def test_structured_assistant_messages_are_not_pruned_under_budget_pressure():
    helpers = _load_http_server_helpers()
    helpers["_DELEGATED_PROMPT_COMPRESSOR"] = _NoopCompressor()
    optimize = helpers["_optimize_delegated_messages"]

    structured_assistant = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "internal reasoning"},
            {"type": "text", "text": "assistant context " * 60},
        ],
    }
    messages = [
        {"role": "system", "content": "sys " * 260},
        {"role": "user", "content": "history " * 260},
        {"role": "user", "content": "older context " * 260},
        structured_assistant,
        {"role": "user", "content": "mid context " * 260},
        {"role": "user", "content": "latest request"},
    ]

    optimized, meta = optimize(messages, "remote-gemini")

    assert any(message.get("role") == "assistant" for message in optimized)
    assert structured_assistant["content"] in [message.get("content") for message in optimized]
    assert meta["pruned_messages"] >= 1
