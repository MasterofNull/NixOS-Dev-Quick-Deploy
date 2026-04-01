#!/usr/bin/env python3
"""Static regression checks for meta-learning integration in delegated routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

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
