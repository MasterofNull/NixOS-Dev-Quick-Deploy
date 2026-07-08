#!/usr/bin/env python3
"""Pure in-memory GBNF grammar cache keyed by schema and zero-trust policy."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, Field, PositiveInt


Builder = Callable[[Any, Any], str]


class GrammarCacheConfig(BaseModel):
    """Runtime-independent cache sizing."""

    max_size: PositiveInt = Field(default=128)


def cache_key(schema_json: Any, zero_trust_state: Any) -> str:
    """Return the canonical versioned key for a schema and zero-trust state."""

    key_material = (
        b"gbnf:v1\0"
        + _canonical_bytes(schema_json)
        + b"\0zt:"
        + _canonical_zt_digest(zero_trust_state).encode("utf-8")
    )
    return hashlib.sha256(key_material).hexdigest()


class GrammarCache:
    """Bounded LRU cache for deterministic schema-to-grammar builders."""

    def __init__(
        self,
        builder: Builder | None = None,
        max_size: int = 128,
    ) -> None:
        self.config = GrammarCacheConfig(max_size=max_size)
        self._builder = builder or default_json_schema_to_gbnf
        self._entries: OrderedDict[str, str] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_build(self, schema_json: Any, zero_trust_state: Any) -> tuple[str, bool]:
        """Return a cached grammar or build and store a new one."""

        key = cache_key(schema_json, zero_trust_state)
        if key in self._entries:
            self._hits += 1
            self._entries.move_to_end(key)
            return self._entries[key], True

        self._misses += 1
        grammar = self._builder(schema_json, zero_trust_state)
        self._entries[key] = grammar
        self._entries.move_to_end(key)
        while len(self._entries) > self.config.max_size:
            self._entries.popitem(last=False)
            self._evictions += 1
        return grammar, False

    def stats(self) -> dict[str, int]:
        """Return cache counters without exposing mutable state."""

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._entries),
            "evictions": self._evictions,
        }


def default_json_schema_to_gbnf(schema_json: Any, zero_trust_state: Any) -> str:
    """Build a small deterministic GBNF grammar for common JSON schema types."""

    schema = _parse_json_value(schema_json)
    if not isinstance(schema, Mapping):
        raise ValueError("schema_json must describe a JSON object schema")

    root = _rule_for_schema(schema)
    return "\n".join(
        [
            f"root ::= {root}",
            'string ::= "\\"" ([^"\\\\] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\\""',
            'number ::= "-"? ([0-9] | [1-9][0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
            'boolean ::= "true" | "false"',
            'null ::= "null"',
            "ws ::= [ \\t\\n\\r]*",
        ]
    )


def _canonical_zt_digest(zero_trust_state: Any) -> str:
    if isinstance(zero_trust_state, str):
        digest = zero_trust_state.strip()
        if not digest:
            raise ValueError("zero_trust_state digest must not be empty")
        return digest
    return hashlib.sha256(_canonical_bytes(zero_trust_state)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    parsed = _parse_json_value(value)
    return json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, bytes | bytearray):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def _rule_for_schema(schema: Mapping[str, Any]) -> str:
    schema_type = schema.get("type")
    if schema_type == "object":
        return _object_rule(schema)
    if schema_type == "array":
        item_rule = _rule_for_schema(_schema_mapping(schema.get("items", {})))
        return f'"[" ws ({item_rule} (ws "," ws {item_rule})*)? ws "]"'
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    return "string | number | boolean | null"


def _object_rule(schema: Mapping[str, Any]) -> str:
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping) or not properties:
        return '"{" ws "}"'

    parts: list[str] = []
    for name in sorted(properties):
        prop_schema = _schema_mapping(properties[name])
        encoded_name = json.dumps(name, separators=(",", ":"))
        parts.append(f'"{encoded_name[1:-1]}" ws ":" ws {_rule_for_schema(prop_schema)}')
    return '"{" ws ' + ' ws "," ws '.join(parts) + ' ws "}"'


def _schema_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
