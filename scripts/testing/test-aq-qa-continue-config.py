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
        '0.5.2" "Continue config targets switchboard ingress with local harness chat lane and continue-local tab lane"' in script,
        "aq-qa phase 0 should describe the switchboard ingress contract for Continue config",
    )
    assert_true(
        script.count('http://127.0.0.1:8085/v1') >= 2,
        "aq-qa should validate switchboard ingress for the chat model, tab autocomplete, and related editor surfaces",
    )
    assert_true(
        '/health' in script and 'expected_chat_context' in script and 'minimum_chat_max_tokens' in script and 'expected_tab_context' in script,
        "aq-qa should derive Continue context and token expectations from live switchboard profile health instead of hardcoded floors",
    )
    assert_true(
        'local_agent_profile' in script and 'continue_profile' in script and 'bounded_chat_context' in script,
        "aq-qa should treat interactive Continue chat budgets separately from compact continue-local defaults",
    )
    assert_true(
        '"local-agent"' in script and '"continue-local"' in script,
        "aq-qa should validate the local-agent chat lane while keeping continue-local for compact editor traffic",
    )
    assert_true(
        'HYBRID_URL}/hints?q=test' in script or "/hints?q=test" in script,
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
        '0.5.7" "Editor-local agent corpus stays within bounded budgets"' in script,
        "aq-qa phase 0 should expose an explicit editor-state budget gate",
    )
    assert_true(
        '_editor_state_budget_ok()' in script and 'AQ_QA_SKIP_REPORT_BACKED_CHECKS' in script,
        "aq-qa should validate editor-state budgets through aq-report while avoiding recursive self-invocation",
    )
    assert_true(
        'localAgentProfile =' in home_base and '"local-agent"' in home_base and 'switchboardProfiles;' in home_base,
        "Continue config generation should derive a dedicated local-agent profile view from switchboard config",
    )
    assert_true(
        "localAgentContextLength =" in home_base and 'lib.attrByPath ["maxInputTokens"] null localAgentProfile' in home_base,
        "Continue config generation should cap the harness-aware editor model context to the local-agent input budget",
    )
    assert_true(
        '"contextLength": ${toString localAgentContextLength}' in home_base
        and '"maxTokens": ${toString localAgentChatMaxTokens}' in home_base,
        "Continue config should render the harness-aware editor model with profile-specific context and output bounds",
    )
    assert_true(
        "RETRY BUDGET: After 2 failed retries" in home_base
        and "TRANSCRIPT HYGIENE: Do not paste large logs" in home_base,
        "Continue config should steer repeated editor failures toward checkpoint-and-fresh-session recovery",
    )
    assert_true(
        "WRAPPER-FIRST: Prefer Continue MCP tools and aq-* wrappers over raw curl" in home_base
        and "SHELL SAFETY: In zsh, always quote URLs containing ?, &, *, [, or ]" in home_base,
        "Continue config should prevent direct raw HTTP misuse and unquoted shell URL failures",
    )
    assert_true(
        "CONTINUE MCP NAMING: In Continue, Harness MCP tools are exposed with an `mcp_server_` prefix." in home_base
        and "mcp_server_recall_memory" in home_base
        and "aq-operational-perspective --task" in home_base,
        "Continue config should document the real Continue MCP naming surface, fallback memory tool, and operational introspection CLI path",
    )
    assert_true(
        "LANE SELECTION: Use local-agent for bounded repo/runtime checks" in home_base
        and "CONTEXT STRATEGY: Local lanes must aggressively offload to harness memory" in home_base,
        "Continue config should distinguish constrained local lanes from larger-context remote lanes",
    )
    assert_true(
        '"__configVersion": "34.0"' in home_base,
        "Continue config version should advance when the generated operator contract changes",
    )
    assert_true(
        '"34.0"' in script,
        "aq-qa should accept the current Continue config schema version",
    )

    print("PASS: aq-qa Continue config validation stays pinned to switchboard ingress")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
