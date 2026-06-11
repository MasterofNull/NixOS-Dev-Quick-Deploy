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
        "aq-chat should treat local-tool-calling as a local switchboard profile",
    )
    assert_true(
        "switchboard_local_tools = self._uses_switchboard_local_tools()" in text,
        "aq-chat should use a single switchboard local-tools routing decision",
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
        "if switchboard_local_tools and not local_snapshot and not tool_free_turn:" in text,
        "aq-chat should bypass local tool loops when deterministic snapshot or explicit tool-free grounding is available",
    )
    assert_true(
        'payload["max_tokens"] = 1024' in text,
        "aq-chat snapshot/tool-free turns should stay bounded without being too restrictive for local reasoning",
    )
    assert_true(
        'headers["X-AI-Profile"] = "local-tool-calling"' in text,
        "aq-chat should send the local-tool-calling switchboard profile header",
    )
    assert_true(
        'payload["stream"] = False' in text,
        "aq-chat should keep local-tool-calling non-streaming so switchboard executes the tool loop",
    )
    assert_true(
        "response = await self.client.post(target_url, json=payload, headers=headers)" in text,
        "aq-chat should consume local-tool-calling as a completed JSON response, not raw token SSE",
    )
    assert_true(
        'if switchboard_local_tools and not local_snapshot and not tool_free_turn:' in text,
        "aq-chat should post local-tool-calling requests to switchboard, not hybrid orchestration",
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
    print("PASS: aq-chat local-tool-calling profile routes through switchboard")


if __name__ == "__main__":
    main()
