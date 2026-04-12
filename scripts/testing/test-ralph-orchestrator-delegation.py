#!/usr/bin/env python3
"""Focused regression coverage for Ralph delegation execution."""

import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "mcp-servers" / "ralph-wiggum" / "orchestrator.py"
SPEC = importlib.util.spec_from_file_location("ralph_orchestrator_module", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

RalphOrchestrator = MODULE.RalphOrchestrator
_backend_to_profile = MODULE._backend_to_profile


class FakeHybrid:
    def __init__(self, *, delegate_payload=None, delegate_error=None):
        self.delegate_payload = delegate_payload or {}
        self.delegate_error = delegate_error
        self.delegate_calls = []
        self.route_calls = []

    async def delegate_task(self, **kwargs):
        self.delegate_calls.append(kwargs)
        if self.delegate_error:
            raise self.delegate_error
        return self.delegate_payload

    async def route_search(self, **kwargs):
        self.route_calls.append(kwargs)
        return {"backend": "local", "response": "fallback result"}


class FakeAIDB:
    async def vector_search(self, **_kwargs):
        return [{"fact": "context"}]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def test_delegate_primary_path() -> None:
    hybrid = FakeHybrid(delegate_payload={
        "choices": [{"message": {"content": "delegated implementation result"}}]
    })
    orchestrator = RalphOrchestrator(hybrid, FakeAIDB())
    result = await orchestrator.execute_agent("aider", "implement feature", {"scope": "repo"}, 1)
    assert_true(result["exit_code"] == 0, "delegate path should succeed")
    assert_true(result["output"] == "delegated implementation result", "delegate content should be returned")
    assert_true(result["route"] == "delegate", "route should record delegate path")
    assert_true(len(hybrid.delegate_calls) == 1, "delegate_task should be used")
    assert_true(not hybrid.route_calls, "route_search should not run when delegate returns content")


async def test_delegate_falls_back_to_route_search() -> None:
    hybrid = FakeHybrid(delegate_payload={"choices": [{"message": {"content": ""}}]})
    orchestrator = RalphOrchestrator(hybrid, FakeAIDB())
    result = await orchestrator.execute_agent("continue", "analyze task", None, 2)
    assert_true(result["output"] == "fallback result", "fallback route_search output should be used")
    assert_true(result["route"] == "local", "fallback route should come from route_search")
    assert_true(len(hybrid.delegate_calls) == 1, "delegate_task should still be attempted first")
    assert_true(len(hybrid.route_calls) == 1, "route_search should run after empty delegate result")


def main() -> int:
    assert_true(_backend_to_profile("aider") == "local-tool-calling", "aider should map to local-tool-calling")
    assert_true(_backend_to_profile("continue-server") == "default", "continue-server should map to default")
    asyncio.run(test_delegate_primary_path())
    asyncio.run(test_delegate_falls_back_to_route_search())
    print("PASS: Ralph orchestrator prefers ai-coordinator delegation before retrieval fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
