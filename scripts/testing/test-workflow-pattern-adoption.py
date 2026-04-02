#!/usr/bin/env python3
"""Static regression checks for Phase 4.1 workflow pattern adoption."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        "def _select_reasoning_pattern(" in text,
        "workflow planning should define a reasoning-pattern selector",
    )
    assert_true(
        'reasoning_pattern = _select_reasoning_pattern(query, prompt_coaching, continuation_query)' in text,
        "workflow plan should select a reasoning pattern from live prompt context",
    )
    assert_true(
        '"reasoning_pattern": reasoning_pattern["phase_recommendations"].get("discover", "react")' in text,
        "workflow discover phase should carry an adopted reasoning pattern",
    )
    assert_true(
        '"reasoning_pattern": reasoning_pattern["phase_recommendations"].get("validate", "reflexion")' in text,
        "workflow validate phase should carry reflexion guidance",
    )
    assert_true(
        '"selected_pattern": primary' in text,
        "reasoning-pattern selector should persist the selected primary pattern",
    )
    assert_true(
        '"boost_multiplier": round(float(_get_pattern_boost(primary)), 3)' in text,
        "pattern selection should incorporate pattern effectiveness boosts",
    )
    assert_true(
        '"reasoning_pattern": reasoning_pattern,' in text,
        "workflow metadata should preserve reasoning-pattern selection",
    )
    assert_true(
        '"reasoning_pattern": reasoning_pattern.get("selected_pattern", "")' in text,
        "workflow trajectory should record the selected pattern at run start",
    )
    assert_true(
        '"reasoning_pattern": session.get("reasoning_pattern", {})' in text,
        "detailed team inspection should expose runtime reasoning-pattern context",
    )
    assert_true(
        'primary = "self_consistency"' in text,
        "reasoning-pattern selector should recognize self-consistency cues",
    )
    assert_true(
        'primary = "plan_and_solve"' in text,
        "reasoning-pattern selector should recognize plan-and-solve cues",
    )
    assert_true(
        'primary = "chain_of_verification"' in text,
        "reasoning-pattern selector should recognize chain-of-verification cues",
    )
    assert_true(
        'primary = "debate"' in text,
        "reasoning-pattern selector should recognize debate cues",
    )
    assert_true(
        '"chain_of_verification"' in text and '"self_consistency"' in text and '"plan_and_solve"' in text and '"debate"' in text,
        "selector alternatives should enumerate the expanded reasoning-pattern set",
    )

    print("PASS: workflow pattern adoption is wired into live planning and runtime sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
