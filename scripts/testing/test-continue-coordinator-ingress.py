#!/usr/bin/env python3
"""Static regression checks for Continue -> switchboard authoritative ingress wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
AI_COORDINATOR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "ai_coordinator.py"
HOME_BASE = ROOT / "nix" / "home" / "base.nix"
CONTINUE_CONFIG = ROOT / "ai-stack" / "continue" / "config.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    http_server_text = HTTP_SERVER.read_text(encoding="utf-8")
    coordinator_text = AI_COORDINATOR.read_text(encoding="utf-8")
    home_base_text = HOME_BASE.read_text(encoding="utf-8")
    continue_config_text = CONTINUE_CONFIG.read_text(encoding="utf-8")

    assert_true(
        'http_app.router.add_post("/v1/chat/completions", handle_openai_chat_completions)' in http_server_text,
        "hybrid coordinator should expose OpenAI-compatible chat ingress",
    )
    assert_true(
        'http_app.router.add_post("/v1/completions", handle_openai_completions)' in http_server_text,
        "hybrid coordinator should expose OpenAI-compatible completions ingress",
    )
    assert_true(
        'http_app.router.add_get("/v1/models", handle_openai_models)' in http_server_text,
        "hybrid coordinator should expose OpenAI-compatible model listing ingress",
    )
    assert_true(
        "async def _proxy_openai_request_via_coordinator(" in http_server_text,
        "hybrid coordinator should centralize Continue/OpenAI ingress proxying",
    )
    assert_true(
        'response.headers["X-Coordinator-Task-Archetype"]' in http_server_text,
        "coordinator ingress should expose selected task archetype in response headers",
    )
    assert_true(
        'response.headers["X-Coordinator-Model-Class"]' in http_server_text,
        "coordinator ingress should expose selected model class in response headers",
    )
    assert_true(
        "def route_openai_chat_payload(" in coordinator_text,
        "ai coordinator should classify OpenAI chat payloads directly",
    )
    assert_true(
        "def extract_task_from_openai_messages(" in coordinator_text,
        "ai coordinator should extract task text from OpenAI message lists",
    )
    assert_true(
        "continueApiBase = aiOpenAIBaseUrl;" in home_base_text,
        "Home Manager Continue config should point chat ingress at the switchboard OpenAI proxy",
    )
    assert_true(
        '"apiBase": "http://127.0.0.1:${SWITCHBOARD_PORT:-8085}/v1"' in continue_config_text,
        "repo Continue config should point at the switchboard ingress",
    )
    assert_true(
        '"title": "Switchboard Router (Authoritative)"' in continue_config_text,
        "repo Continue config should label the authoritative model path as switchboard-backed",
    )
    assert_true(
        '"X-AI-Profile": "continue-local"' in continue_config_text,
        "Continue tab autocomplete should remain pinned to the local continue lane",
    )

    print("PASS: Continue authoritative coordinator ingress wiring is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
