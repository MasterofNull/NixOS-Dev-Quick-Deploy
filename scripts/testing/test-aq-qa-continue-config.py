#!/usr/bin/env python3
"""Static regression checks for Continue/editor aq-qa switchboard ingress rules."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_QA = ROOT / "scripts" / "ai" / "aq-qa"
HOME_BASE = ROOT / "nix" / "home" / "base.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    script = AQ_QA.read_text(encoding="utf-8")
    home_base = HOME_BASE.read_text(encoding="utf-8")

    assert_true(
        '0.5.2" "Continue config targets switchboard ingress with continue-local lane"' in script,
        "aq-qa phase 0 should describe the switchboard ingress contract for Continue config",
    )
    assert_true(
        script.count('http://127.0.0.1:8085/v1') >= 2,
        "aq-qa should validate switchboard ingress for the primary Continue chat model and tab autocomplete",
    )
    assert_true(
        '/health' in script and 'expected_context' in script and 'expected_chat_max_tokens' in script,
        "aq-qa should derive Continue context and token expectations from live switchboard profile health instead of hardcoded floors",
    )
    assert_true(
        '"continue-local"' in script,
        "aq-qa should keep the continue-local lane requirement in the config validator",
    )
    assert_true(
        'http://127.0.0.1:8003/hints' in script,
        "aq-qa should require the aq-hints provider to stay on coordinator ingress",
    )
    assert_true(
        '_primary_home()' in script and '_run_clean_primary_shell()' in script,
        "aq-qa should resolve the effective primary-user home and clean shell helpers for deploy-time checks",
    )
    assert_true(
        '_continue_extension_output' in script and 'AQ_PRIMARY_HOME="$(_primary_home)"' in script,
        "aq-qa should run Continue/editor smoke checks against the primary-user environment instead of the ambient HOME",
    )
    assert_true(
        '{"23.0", "24.0", "25.0", "26.0"}' in script,
        "aq-qa should accept the current Continue config schema version",
    )
    assert_true(
        '"title": "Continue Local (Primary)"' in home_base
        and '"X-AI-Profile": "continue-local"' in home_base,
        "Continue config should expose a single primary Continue chat model pinned to continue-local",
    )
    assert_true(
        '"Local Agent (Harness-Aware)"' not in home_base and 'localAgentProfile =' not in home_base,
        "Continue config generation should not expose the heavier harness-aware chat model by default",
    )
    assert_true(
        '_config_version="26.0"' in home_base and '"__configVersion": "26.0"' in home_base,
        "Continue config generation should bump the schema version when the rendered model bounds change",
    )

    print("PASS: aq-qa Continue config validation stays pinned to switchboard ingress")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
