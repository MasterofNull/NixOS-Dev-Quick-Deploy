#!/usr/bin/env python3
"""Static regression for aq-optimizer gap-remediation support."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_OPTIMIZER = ROOT / "scripts" / "ai" / "aq-optimizer"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = AQ_OPTIMIZER.read_text(encoding="utf-8")

    assert_true(
        'def apply_gap_remediation(action: dict, dry_run: bool) -> dict:' in text,
        "aq-optimizer should implement gap remediation application",
    )
    assert_true(
        'elif atype == "gap_remediation" and aname == "remediate_gap":' in text,
        "aq-optimizer should handle structured gap remediation actions",
    )
    assert_true(
        '[str(script_path), "--limit", "5"]' in text,
        "gap remediation should use the existing aq-gap-auto-remediate script",
    )

    print("PASS: aq-optimizer supports structured gap remediation actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
