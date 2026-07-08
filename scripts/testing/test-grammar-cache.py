#!/usr/bin/env python3
"""Tests for the pure GBNF grammar LRU cache and its canonical versioned key."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai" / "lib"))

from grammar_cache import GrammarCache, cache_key  # noqa: E402


def test_cache_key_stable_for_schema_whitespace_and_key_order():
    compact = '{"type":"object","properties":{"b":{"type":"number"},"a":{"type":"string"}}}'
    spaced = """
    {
      "properties": {
        "a": {"type": "string"},
        "b": {"type": "number"}
      },
      "type": "object"
    }
    """

    assert cache_key(compact, {"mode": "strict"}) == cache_key(spaced, {"mode": "strict"})


def test_different_schema_changes_cache_key():
    first = {"type": "object", "properties": {"a": {"type": "string"}}}
    second = {"type": "object", "properties": {"a": {"type": "number"}}}

    assert cache_key(first, {"mode": "strict"}) != cache_key(second, {"mode": "strict"})


def test_different_zero_trust_state_changes_cache_key():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}

    assert cache_key(schema, {"policy": "alpha"}) != cache_key(schema, {"policy": "beta"})


def test_cache_hit_reuses_built_grammar():
    calls = []

    def builder(schema_json, zero_trust_state):
        calls.append((schema_json, zero_trust_state))
        return "root ::= string"

    cache = GrammarCache(builder=builder, max_size=2)

    first, first_hit = cache.get_or_build({"type": "string"}, {"policy": "alpha"})
    second, second_hit = cache.get_or_build('{"type":"string"}', {"policy": "alpha"})

    assert first == second == "root ::= string"
    assert first_hit is False
    assert second_hit is True
    assert len(calls) == 1
    assert cache.stats() == {"hits": 1, "misses": 1, "size": 1, "evictions": 0}


def test_lru_eviction_removes_oldest_entry():
    calls = []

    def builder(schema_json, zero_trust_state):
        calls.append(schema_json["name"])
        return f"root ::= {schema_json['name']}"

    cache = GrammarCache(builder=builder, max_size=2)

    cache.get_or_build({"name": "a"}, "zt-digest")
    cache.get_or_build({"name": "b"}, "zt-digest")
    cache.get_or_build({"name": "a"}, "zt-digest")
    cache.get_or_build({"name": "c"}, "zt-digest")
    _, hit = cache.get_or_build({"name": "b"}, "zt-digest")

    assert hit is False
    assert calls == ["a", "b", "c", "b"]
    assert cache.stats() == {"hits": 1, "misses": 4, "size": 2, "evictions": 2}


def test_versioned_separators_prevent_naive_concat_collision():
    schema_a = {"schema": "ab", "policy_hint": "c"}
    schema_b = {"schema": "a", "policy_hint": "bc"}

    assert cache_key(schema_a, "digest") != cache_key(schema_b, "digest")


def test_zero_trust_string_digest_matches_canonical_dict_digest_namespace():
    schema = {"type": "string"}
    dict_key = cache_key(schema, {"policy": "alpha"})
    digest_key = cache_key(schema, "policy-alpha")

    assert dict_key != digest_key


def test_invalid_max_size_rejected():
    with pytest.raises(ValueError):
        GrammarCache(max_size=0)
