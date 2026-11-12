#!/usr/bin/env python3
"""Static regression checks for Continue -> switchboard authoritative ingress wiring."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"
OPENAI_A2A_HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "openai_a2a_handlers.py"
AI_COORDINATOR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "ai_coordinator.py"
AGENT_SERVICE = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "agent" / "agent_service.py"
ROUTER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "router.py"
HOME_BASE = ROOT / "nix" / "home" / "base.nix"
CONTINUE_CONFIG = ROOT / "ai-stack" / "continue" / "config.json"
OPTIONS_NIX = ROOT / "nix" / "modules" / "core" / "options.nix"


def switchboard_api_base() -> str:
    """Derive the expected Continue apiBase from the options.nix switchboard port SSOT."""
    text = OPTIONS_NIX.read_text(encoding="utf-8")
    match = re.search(
        r"switchboard\s*=\s*\{.*?port\s*=\s*lib\.mkOption\s*\{[^}]*?default\s*=\s*(\d+);",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("options.nix switchboard port default not found")
    return f"http://127.0.0.1:{match.group(1)}/v1"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    http_server_text = HTTP_SERVER.read_text(encoding="utf-8")
    openai_a2a_text = OPENAI_A2A_HANDLERS.read_text(encoding="utf-8")
    coordinator_text = AI_COORDINATOR.read_text(encoding="utf-8")
    home_base_text = HOME_BASE.read_text(encoding="utf-8")
    continue_config_text = CONTINUE_CONFIG.read_text(encoding="utf-8")

    assert_true(
        'http_app.router.add_post("/v1/chat/completions", handle_openai_chat_completions)' in openai_a2a_text,
        "hybrid coordinator should expose OpenAI-compatible chat ingress",
    )
    assert_true(
        "import openai_a2a_handlers" in http_server_text
        and "openai_a2a_handlers.init(" in http_server_text,
        "http server should initialize the authoritative OpenAI/A2A ingress module",
    )
    assert_true(
        "import openai_a2a_handlers as _a2a" in AGENT_SERVICE.read_text(encoding="utf-8")
        and "_a2a.register_routes(app)" in AGENT_SERVICE.read_text(encoding="utf-8")
        and "agent_service" in ROUTER.read_text(encoding="utf-8"),
        "router should register OpenAI/A2A ingress routes through agent_service",
    )
    assert_true(
        'http_app.router.add_post("/v1/completions", handle_openai_completions)' in openai_a2a_text,
        "hybrid coordinator should expose OpenAI-compatible completions ingress",
    )
    assert_true(
        'http_app.router.add_get("/v1/models", handle_openai_models)' in openai_a2a_text,
        "hybrid coordinator should expose OpenAI-compatible model listing ingress",
    )
    assert_true(
        "async def _proxy_openai_request_via_coordinator(" in openai_a2a_text,
        "hybrid coordinator should centralize Continue/OpenAI ingress proxying",
    )
    assert_true(
        'response.headers["X-Coordinator-Task-Archetype"]' in openai_a2a_text,
        "coordinator ingress should expose selected task archetype in response headers",
    )
    assert_true(
        'response.headers["X-Coordinator-Model-Class"]' in openai_a2a_text,
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
    continue_config = json.loads(continue_config_text)
    models = continue_config["models"]
    profiles = {m["requestOptions"]["headers"]["X-AI-Profile"]: m for m in models}
    assert_true(
        all(m["apiBase"] == switchboard_api_base() for m in models + [continue_config["tabAutocompleteModel"]]),
        "repo Continue config should route every model through the switchboard ingress",
    )
    assert_true(
        "Switchboard" in profiles["remote-coding"]["title"]
        and "Switchboard" in profiles["remote-reasoning"]["title"],
        "repo Continue config should label remote lanes as switchboard-backed",
    )
    assert_true(
        "remote-coding" in profiles,
        "repo Continue config should expose switchboard-backed remote coding lane",
    )
    assert_true(
        "remote-reasoning" in profiles,
        "repo Continue config should expose switchboard-backed remote reasoning lane",
    )
    assert_true(
        '"X-AI-Profile": "continue-local"' in continue_config_text,
        "Continue tab autocomplete should remain pinned to the local continue lane",
    )
    assert_true(
        'apiKey": "sk-or-v1-' not in home_base_text,
        "Home Manager Continue config must not embed hardcoded remote API keys",
    )

    print("PASS: Continue authoritative coordinator ingress wiring is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
