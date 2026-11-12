#!/usr/bin/env python3
"""Static regression checks for progressive context integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
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

    assert_true(
        "from multi_tier_loading import (" in text,
        "hybrid coordinator should import multi-tier context loading primitives",
    )
    assert_true(
        "from lazy_context import ContextDependencyGraph, ContextNode, LazyContextLoader" in text,
        "hybrid coordinator should import lazy context loading primitives",
    )
    assert_true(
        "from relevance_prediction import NegativeContextFilter, RelevancePredictor" in text,
        "hybrid coordinator should import relevance prediction primitives",
    )
    assert_true(
        'os.getenv("DISCLOSURE_CONTEXT_DIR", "/var/lib/ai-stack/hybrid/context-tiers")' in text,
        "hybrid coordinator should keep disclosure runtime state in writable AI stack storage by default",
    )
    assert_true(
        "async def _apply_progressive_context(" in text,
        "hybrid coordinator should define progressive context attachment helper",
    )
    assert_true(
        "progressive_context, progressive_context_meta = await _apply_progressive_context(" in text,
        "delegate handler should apply progressive context before dispatch",
    )
    assert_true(
        '"progressive_context": progressive_context_meta' in text,
        "delegate response should expose progressive context metadata",
    )
    assert_true(
        '"progressive_context_applied": bool(progressive_context_meta.get("applied"))' in text,
        "delegate audit metadata should track progressive context application",
    )

    print("PASS: delegated routing integrates progressive disclosure context loading")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
