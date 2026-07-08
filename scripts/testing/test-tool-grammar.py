#!/usr/bin/env python3
"""Tests for the P2 tool-call GBNF construction (ai-stack/local-agents/tool_grammar.py)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import tool_grammar  # noqa: E402
import grammar_cache  # noqa: E402
import agent_executor  # noqa: E402


def test_schema_constrains_function_to_available_tools():
    s = tool_grammar.tool_call_schema(["get_hint", "read_file", "write_file"])
    assert s["type"] == "object"
    assert s["required"] == ["function", "arguments"]
    assert s["properties"]["function"]["enum"] == ["get_hint", "read_file", "write_file"]
    assert s["properties"]["arguments"]["type"] == "object"
    assert s["additionalProperties"] is False


def test_schema_empty_tools_allows_any_string():
    s = tool_grammar.tool_call_schema([])
    assert "enum" not in s["properties"]["function"]
    assert s["properties"]["function"]["type"] == "string"


def test_grammar_is_nonempty_gbnf():
    gbnf, _hit = tool_grammar.tool_call_grammar(["get_hint", "read_file"])
    assert isinstance(gbnf, str) and gbnf.strip()
    assert "root ::=" in gbnf  # real GBNF from the F2.2 builder


def test_grammar_cache_hit_on_repeat():
    cache = grammar_cache.GrammarCache()
    g1, hit1 = tool_grammar.tool_call_grammar(["a", "b"], cache=cache)
    g2, hit2 = tool_grammar.tool_call_grammar(["a", "b"], cache=cache)
    assert g1 == g2
    assert hit1 is False and hit2 is True  # second call is a cache hit


def test_tool_order_and_zero_trust_are_stable_keys():
    cache = grammar_cache.GrammarCache()
    # tool order should not matter (schema sorts); same zt -> cache hit
    _g1, hit1 = tool_grammar.tool_call_grammar(["b", "a"], zero_trust_state="zt0", cache=cache)
    _g2, hit2 = tool_grammar.tool_call_grammar(["a", "b"], zero_trust_state="zt0", cache=cache)
    assert hit1 is False and hit2 is True
    # different zero_trust_state -> different key -> miss
    _g3, hit3 = tool_grammar.tool_call_grammar(["a", "b"], zero_trust_state="zt1", cache=cache)
    assert hit3 is False


def test_agent_executor_repair_mode_forces_grammar_only_for_repair(monkeypatch):
    executor = agent_executor.LocalAgentExecutor(tool_registry=_FakeRegistry(), enable_fallback=False)
    monkeypatch.setattr(agent_executor, "tool_grammar", _FakeGrammar)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_REPAIR_ENABLED", True)

    assert executor._tool_call_grammar() is None
    assert executor._tool_call_grammar(force_repair=True) == "root ::= object"


def test_agent_executor_gbnf_disabled_returns_no_repair_grammar(monkeypatch):
    executor = agent_executor.LocalAgentExecutor(tool_registry=_FakeRegistry(), enable_fallback=False)
    monkeypatch.setattr(agent_executor, "tool_grammar", _FakeGrammar)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_REPAIR_ENABLED", False)

    assert executor._tool_call_grammar() is None
    assert executor._tool_call_grammar(force_repair=True) is None


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.enabled = True


class _FakeRegistry:
    def __init__(self) -> None:
        self.tools = {"read_file": _FakeTool("read_file")}


class _FakeGrammar:
    @staticmethod
    def tool_call_grammar(names):
        assert names == ["read_file"]
        return "root ::= object", False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
