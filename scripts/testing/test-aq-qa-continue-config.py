#!/usr/bin/env python3
"""Static regression checks for Continue/editor aq-qa coordinator ingress rules."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_QA = ROOT / "scripts" / "ai" / "aq-qa"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    script = AQ_QA.read_text(encoding="utf-8")

    assert_true(
        '0.5.2" "Continue config targets coordinator ingress with continue-local lane"' in script,
        "aq-qa phase 0 should describe the coordinator ingress contract for Continue config",
    )
    assert_true(
        script.count('http://127.0.0.1:8003/v1') >= 3,
        "aq-qa should validate coordinator ingress for at least the base model, lane-specific model, and tab autocomplete",
    )
    assert_true(
        '"continue-local"' in script,
        "aq-qa should keep the continue-local lane requirement in the config validator",
    )
    assert_true(
        'http://127.0.0.1:8003/hints' in script,
        "aq-qa should require the aq-hints provider to stay on coordinator ingress",
    )

    print("PASS: aq-qa Continue config validation stays pinned to coordinator ingress")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
