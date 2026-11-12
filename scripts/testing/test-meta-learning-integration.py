#!/usr/bin/env python3
"""Static regression checks for meta-learning integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"


# Explicit live owners of the asserted behavior; coordinator_source() fails if http_server_impl.py
# (first entry) does not reference an owner module, so dormant files cannot satisfy assertions.
COORDINATOR_OWNERS = (
    "http_server_impl.py",
    "extensions/ai_coordinator_handlers.py",
    "extensions/real_time_learning_engine.py",
    "core/status_service.py",
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
        "from meta_learning import RapidAdaptor, Task, TaskDomain" in text,
        "hybrid coordinator should import meta-learning primitives",
    )
    assert_true(
        "_RAPID_ADAPTOR = RapidAdaptor()" in text,
        "hybrid coordinator should initialize the rapid adaptor",
    )
    assert_true(
        "async def _apply_meta_learning(" in text,
        "hybrid coordinator should define meta-learning helper",
    )
    assert_true(
        '"meta_learning": _meta_learning_status_snapshot()' in text,
        "status endpoint should expose meta-learning state",
    )
    assert_true(
        "meta_learning = await _apply_meta_learning(" in text,
        "delegate handler should apply meta-learning on successful delegated outcomes",
    )
    assert_true(
        '"meta_learning": meta_learning' in text,
        "delegate response should expose meta-learning metadata",
    )

    print("PASS: delegated routing integrates bounded meta-learning signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
