#!/usr/bin/env python3
"""Static regression checks for delegated prompt efficiency integration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "from prompt_compression import CompressionStrategy, PromptCompressor" in text,
        "hybrid coordinator should import delegated prompt compression primitives",
    )
    assert_true(
        "from context_management import ContextChunk, ContextPruner" in text,
        "hybrid coordinator should import delegated context pruning primitives",
    )
    assert_true(
        "def _optimize_delegated_messages(" in text,
        "hybrid coordinator should define delegated message optimization helper",
    )
    assert_true(
        "messages, prompt_optimization = _optimize_delegated_messages(messages, selected_profile)" in text,
        "delegate handler should optimize delegated messages before dispatch",
    )
    assert_true(
        '"prompt_optimization": prompt_optimization' in text,
        "delegate response should expose prompt optimization metadata",
    )
    assert_true(
        '"prompt_optimization_applied": bool(prompt_optimization.get("applied"))' in text,
        "delegate audit metadata should record prompt optimization application",
    )

    print("PASS: delegated prompt compression and context pruning are integrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
