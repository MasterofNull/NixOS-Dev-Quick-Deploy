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
        "Do not recommend a rebuild unless a check reports pending activation or failed units." in text,
        "aq-chat snapshot contract should prevent stale rebuild recommendations",
    )
    assert_true(
        "if switchboard_local_tools and not local_snapshot:" in text,
        "aq-chat should bypass local tool loops when deterministic snapshot grounding is available",
    )
    assert_true(
        'payload["max_tokens"] = 512' in text,
        "aq-chat snapshot-grounded turns should have a bounded interactive response budget",
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
        'if switchboard_local_tools:' in text,
        "aq-chat should post local-tool-calling requests to switchboard, not hybrid orchestration",
    )
    assert_true(
        'parser.add_argument("--max-tools", type=int, default=16,' in text,
        "aq-chat should default to enough local tool calls for broad analysis turns",
    )
    assert_true(
        'local tool budget exhausted; answer finalized from completed tool outputs' in text,
        "aq-chat should surface when a response was forced after local tool budget exhaustion",
    )
    print("PASS: aq-chat local-tool-calling profile routes through switchboard")


if __name__ == "__main__":
    main()
