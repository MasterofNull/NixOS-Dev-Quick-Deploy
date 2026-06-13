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
        '"stream": False' in text,
        "aq-chat should consume coordinator local delegation as a completed JSON response",
    )
    assert_true(
        "response = await self.client.post(target_url, json=payload, headers=headers)" in text,
        "aq-chat should consume local delegation as a completed JSON response, not raw token SSE",
    )
    assert_true(
        'target_url = f"{self.hybrid_url}/control/ai-coordinator/delegate"' in text,
        "aq-chat local profile should route through the hybrid coordinator delegate endpoint",
    )
    assert_true(
        'target_url = f"{self.switchboard_url}/v1/chat/completions"' not in text,
        "aq-chat local profile should not bypass coordinator governance through switchboard chat completions",
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
        'parser.add_argument("--max-tools", type=int, default=40,' in text,
        "aq-chat should default to enough local tool calls for broad analysis turns (Phase 164: 16→40)",
    )
    assert_true(
        'local tool budget exhausted; answer finalized from completed tool outputs' in text,
        "aq-chat should surface when a response was forced after local tool budget exhaustion",
    )
    print("PASS: aq-chat local-tool-calling profile routes through coordinator delegation")


if __name__ == "__main__":
    main()
