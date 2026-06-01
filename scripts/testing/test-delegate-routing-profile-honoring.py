#!/usr/bin/env python3
"""Static regression checks for delegate profile honoring and local routing."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HANDLERS_PATH = REPO_ROOT / "ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    handlers_text = HANDLERS_PATH.read_text(encoding="utf-8")

    assert_true(
        'requested_profile = _ai_coordinator_infer_profile(task, requested_profile=requested_profile)' in handlers_text,
        "expected delegate handler to normalize explicit requested profiles before routing",
    )
    assert_true(
        'auto_prefer_local = not requested_profile and not tools_present and timeout_s <= _AUTO_PREFER_LOCAL_MAX_TIMEOUT_S' in handlers_text,
        "expected short-timeout delegate calls without tools to prefer local routing",
    )
    assert_true(
        'routing_decision["recommended_profile"] = requested_profile' in handlers_text,
        "expected explicit requested profiles to override auto-selected delegate routing",
    )
    assert_true(
        'local_profiles = {"default", "continue-local", "embedded-assist", "local-tool-calling"}' in handlers_text,
        "expected embedded-assist delegate fallbacks to be routed over the local switchboard lane",
    )
    assert_true(
        "_build_delegation_fallback_chain(\n                task,\n                requested_profile,\n                routing_prefer_local," in handlers_text,
        "expected delegate failover chains to preserve the effective local preference",
    )

    print("PASS: delegate handler honors explicit profiles and routes local fallback lanes correctly")


if __name__ == "__main__":
    main()
