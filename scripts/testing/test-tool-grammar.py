#!/usr/bin/env python3
"""Tests for fail-closed function-coupled local tool-call grammars."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import agent_executor  # noqa: E402
import grammar_cache  # noqa: E402
import tool_grammar  # noqa: E402


READ = {
    "type": "object",
    "properties": {"file_path": {"type": "string"}, "start_line": {"type": "integer"}},
    "required": ["file_path"],
    "additionalProperties": False,
}
PING = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def test_schema_couples_each_function_to_its_own_closed_arguments():
    schema = tool_grammar.tool_call_schema({"read_file": READ, "ping": PING})
    assert len(schema["oneOf"]) == 3  # read required + optional, then exact empty ping
    alternatives = schema["oneOf"]
    read_required = next(item for item in alternatives if item["properties"]["arguments"]["required"] == ["file_path"])
    assert read_required["properties"]["function"]["enum"] == ["read_file"]
    assert read_required["properties"]["arguments"]["additionalProperties"] is False
    ping = next(item for item in alternatives if item["properties"]["function"]["enum"] == ["ping"])
    assert ping["properties"]["arguments"] == PING


def test_optional_variants_are_bounded_and_malformed_schemas_fail_closed():
    too_many = {
        "type": "object",
        "properties": {f"optional_{index}": {"type": "string"} for index in range(6)},
        "required": [],
        "additionalProperties": False,
    }
    with pytest.raises(ValueError, match="exceed 32"):
        tool_grammar.tool_call_schema({"wide": too_many})
    with pytest.raises(ValueError, match="required keys"):
        tool_grammar.tool_call_schema({"bad": {**READ, "required": ["missing"]}})
    with pytest.raises(ValueError, match="must not open additionalProperties"):
        tool_grammar.tool_call_schema({"bad": {**READ, "additionalProperties": True}})
    # Existing registry schemas may omit the JSON-Schema default.  The grammar
    # canonicalizes that omission to closed rather than reopening arguments.
    omitted = {key: value for key, value in READ.items() if key != "additionalProperties"}
    normalized = tool_grammar.canonical_tool_schemas({"read_file": omitted})
    assert normalized["read_file"]["additionalProperties"] is False


def test_empty_enabled_mapping_fails_closed():
    with pytest.raises(ValueError, match="no enabled tools"):
        tool_grammar.tool_call_schema({})
    with pytest.raises(ValueError, match="no enabled tools"):
        tool_grammar.tool_call_grammar({})


def test_cache_identity_changes_when_same_tool_name_schema_changes():
    cache = grammar_cache.GrammarCache()
    first, first_hit = tool_grammar.tool_call_grammar({"read_file": READ}, cache=cache)
    changed = {**READ, "properties": {**READ["properties"], "encoding": {"type": "string"}}}
    second, second_hit = tool_grammar.tool_call_grammar({"read_file": changed}, cache=cache)
    assert first_hit is False and second_hit is False
    assert first != second
    assert tool_grammar.tool_schema_cache_key({"read_file": READ}) != tool_grammar.tool_schema_cache_key({"read_file": changed})


def test_executor_cache_is_schema_bound_and_requested_build_failure_is_closed(monkeypatch):
    registry = _FakeRegistry(READ)
    executor = agent_executor.LocalAgentExecutor(tool_registry=registry, enable_fallback=False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", True)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_REPAIR_ENABLED", True)
    lease = _lease("read_file", READ)
    first = executor._tool_call_grammar(lease)
    changed = {**READ, "properties": {"file_path": {"type": "string"}, "mode": {"type": "string"}}}
    second = executor._tool_call_grammar(_lease("read_file", changed))
    assert first != second
    with pytest.raises(RuntimeError, match="could not be built"):
        executor._tool_call_grammar(_lease("read_file", {**READ, "additionalProperties": True}))


def test_executor_uses_only_the_model_visible_lease_and_refreshes_on_hotswap(monkeypatch):
    registry = _FakeRegistry(READ)
    # A malformed enabled registry entry must not poison a lease that did not
    # expose it to the model.
    registry.tools["rogue"] = _FakeTool("rogue", {"type": "object", "additionalProperties": True})
    executor = agent_executor.LocalAgentExecutor(tool_registry=registry, enable_fallback=False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", True)
    base_lease = _lease("read_file", READ)
    base = executor._tool_call_grammar(base_lease)
    assert "rogue" not in base.replace("\\", "")

    expanded_lease = base_lease + _lease("ping", PING)
    expanded = executor._tool_call_grammar(expanded_lease)
    assert expanded != base
    assert json.dumps("ping") in expanded.replace("\\", "")


def test_requested_grammar_rejects_absent_empty_or_malformed_leases(monkeypatch):
    executor = agent_executor.LocalAgentExecutor(tool_registry=_FakeRegistry(READ), enable_fallback=False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", True)
    for lease in (None, [], [{"name": "read_file"}], [{"parameters": READ}]):
        with pytest.raises(RuntimeError, match="could not be built"):
            executor._tool_call_grammar(lease)


def test_executor_does_not_require_grammar_when_feature_is_disabled(monkeypatch):
    executor = agent_executor.LocalAgentExecutor(tool_registry=_FakeRegistry(READ), enable_fallback=False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_ALWAYS_ENABLED", False)
    monkeypatch.setattr(agent_executor, "_LOCAL_GBNF_REPAIR_ENABLED", False)
    assert executor._tool_call_grammar(None) is None
    assert executor._tool_call_grammar(None, force_repair=True) is None


def test_executor_threads_active_lease_to_all_grammar_enabled_retry_paths():
    source = Path(agent_executor.__file__).read_text(encoding="utf-8")
    # Normal, transient retry, empty-response retry, and constrained repair
    # all carry the exact active lease.  Verified completion stays explicitly
    # prose-only through allow_tool_grammar=False.
    assert source.count("active_tools=_active_tools") >= 5
    assert '"active_tools": _active_tools' in source
    assert "force_tool_grammar=True,\n                                active_tools=_active_tools" in source
    assert "allow_tool_grammar=False" in source


class _FakeTool:
    def __init__(self, name, parameters):
        self.name = name
        self.parameters = parameters
        self.enabled = True


class _FakeRegistry:
    def __init__(self, parameters):
        self.tools = {"read_file": _FakeTool("read_file", parameters)}


def _lease(name, parameters):
    return [{"name": name, "parameters": parameters}]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
