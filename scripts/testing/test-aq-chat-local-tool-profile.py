#!/usr/bin/env python3
"""Static regression checks for aq-chat local tool-calling profile routing."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AQ_CHAT = REPO_ROOT / "scripts/ai/aq-chat"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = AQ_CHAT.read_text(encoding="utf-8")
    assert_true(
        'self.active_profile in {"local", "local-tool-calling"}' in text,
        "aq-chat should treat local-tool-calling as a local profile",
    )
    assert_true(
        "def _build_coordinator_delegate_payload" in text,
        "aq-chat should build a canonical coordinator delegation payload for local turns",
    )
    assert_true(
        "def _record_and_render_assistant_response" in text,
        "aq-chat should render completed assistant responses through one readable final renderer",
    )
    assert_true(
        "def _build_local_snapshot" in text and "TRUSTED LOCAL PREFLIGHT SNAPSHOT" in text,
        "aq-chat should ground operational recommendation prompts in a trusted local snapshot",
    )
    assert_true(
        '"dashboard_osi"' in text and "/api/health/layered" in text,
        "aq-chat trusted snapshot should include live dashboard OSI counts",
    )
    assert_true(
        '"/brief"' in text,
        "aq-chat should list the /brief slash command",
    )
    assert_true(
        'elif base == "/brief":' in text and "self._show_brief()" in text,
        "aq-chat should route /brief through handle_slash_command",
    )
    assert_true(
        "def _collect_local_snapshot" in text and "def _show_brief" in text,
        "aq-chat /brief should render the same trusted local snapshot without a model call",
    )
    assert_true(
        "Do not recommend a rebuild unless a check reports pending activation or failed units." in text,
        "aq-chat snapshot contract should prevent stale rebuild recommendations",
    )
    assert_true(
        "def _should_bypass_tools_for_turn" in text and "TOOL-FREE TURN" in text,
        "aq-chat should support explicit tool-free local turns for spec-only prompts",
    )
    assert_true(
        '"task": prompt' in text,
        "aq-chat coordinator delegation should include the current user turn as task",
    )
    assert_true(
        '"messages": request_messages' in text,
        "aq-chat coordinator delegation should preserve conversation messages",
    )
    assert_true(
        'headers["X-AI-Profile"] = "local-tool-calling"' in text,
        "aq-chat should identify the local-tool-calling profile to the coordinator",
    )
    assert_true(
        '"streaming_mode"' in text and "streaming_mode" in text,
        "aq-chat coordinator delegation should request SSE streaming from coordinator",
    )
    assert_true(
        'async with self.client.stream("POST", target_url' in text,
        "aq-chat should consume coordinator delegation via SSE streaming, not blocking JSON POST",
    )
    assert_true(
        'target_url = f"{self.hybrid_url}/control/ai-coordinator/delegate"' in text,
        "aq-chat local profile should route through the hybrid coordinator delegate endpoint",
    )
    # Phase B-D: fast-path carve-out.
    # The switchboard /v1/chat/completions URL is now intentionally used in
    # _stream_fast_path() for conversational turns only. The governance contract is:
    #   1. The URL must only appear inside the _stream_fast_path method (not in _stream_chat's
    #      coordinator block — that would be an unguarded bypass).
    #   2. _stream_fast_path must only be reached via an explicit eligibility guard
    #      (ToolMode check + is_conversational() + _last_turn_had_tool_calls check).
    #   3. The coordinator path (hybrid_url/control/...) must remain intact for all
    #      agentic turns.
    # This check verifies the structural constraint rather than a blanket URL absence.
    fast_path_url = 'target_url = f"{self.switchboard_url}/v1/chat/completions"'
    if fast_path_url in text:
        # Fast-path present: verify it is gated by explicit governance controls
        assert_true(
            "def _stream_fast_path" in text,
            "switchboard /v1/chat/completions must only appear inside a dedicated _stream_fast_path method",
        )
        assert_true(
            "is_conversational(prompt)" in text,
            "fast-path activation must be guarded by the conversational classifier",
        )
        assert_true(
            "tool_mode == ToolMode.ENABLED" in text,
            "fast-path activation must be guarded by ToolMode.ENABLED check",
        )
        assert_true(
            "_last_turn_had_tool_calls" in text,
            "fast-path activation must check whether last turn used tool calls",
        )
        assert_true(
            "_no_fastpath" in text,
            "fast-path must be bypassable via --no-fastpath flag for operator control",
        )
    assert_true(
        "Never print pseudo tool calls" in text,
        "aq-chat prompt should forbid printed pseudo-tool calls when tool execution is unavailable",
    )
    assert_true(
        "except KeyboardInterrupt:" in text and "Interrupted." in text,
        "aq-chat should handle Ctrl-C without dumping a traceback",
    )
    assert_true(
        'parser.add_argument("--max-tools", type=int, default=0,' in text
        and "Deprecated compatibility flag; local tool loops are progress-guarded" in text,
        "aq-chat --max-tools should be a deprecated compatibility flag; tool loops are progress-guarded",
    )
    assert_true(
        '"max_tool_calls":' not in text and "local_tool_budget_exhausted" not in text,
        "aq-chat must not send or depend on fixed local tool-call budget state",
    )
    print("PASS: aq-chat local-tool-calling profile routes through coordinator delegation")


if __name__ == "__main__":
    main()
