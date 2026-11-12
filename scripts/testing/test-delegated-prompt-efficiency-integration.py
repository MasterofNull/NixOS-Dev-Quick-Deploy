#!/usr/bin/env python3
"""Static regression checks for delegated prompt efficiency integration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"


# Explicit live owners of the asserted behavior; coordinator_source() fails if http_server_impl.py
# (first entry) does not reference an owner module, so dormant files cannot satisfy assertions.
COORDINATOR_OWNERS = (
    "http_server_impl.py",
    "extensions/ai_coordinator_handlers.py",
    "workflow/delegation_handlers.py",
)


def coordinator_source() -> str:
    root = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
    http_text = (root / COORDINATOR_OWNERS[0]).read_text(encoding="utf-8")
    for owner in COORDINATOR_OWNERS[1:]:
        if Path(owner).stem not in http_text:
            raise AssertionError(f"{owner} is not referenced by {COORDINATOR_OWNERS[0]}; owner is not wired")
    return "\n".join((root / owner).read_text(encoding="utf-8") for owner in COORDINATOR_OWNERS)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = coordinator_source()

    owner = (HC / "workflow" / "delegation_handlers.py").read_text(encoding="utf-8")
    http_text = (HC / "http_server_impl.py").read_text(encoding="utf-8")
    assert_true(
        "from prompt_compression import CompressionStrategy" in owner
        and "from prompt_compression import PromptCompressor" in http_text,
        "hybrid coordinator should import delegated prompt compression primitives",
    )
    assert_true(
        "from context_management import ContextChunk" in owner
        and "from context_management import ContextPruner" in http_text,
        "hybrid coordinator should import delegated context pruning primitives",
    )
    assert_true(
        "import delegation_handlers" in http_text
        and "delegation_handlers.init(" in http_text
        and "_optimize_delegated_messages" in http_text,
        "http server should wire the delegation handler owner that provides message optimization",
    )
    assert_true(
        "def _optimize_delegated_messages(" in owner,
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
