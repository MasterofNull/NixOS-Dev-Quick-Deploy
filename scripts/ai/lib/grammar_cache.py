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
            # Control chars (U+0000-U+001F) are excluded from the raw/unescaped
            # branch — real JSON only permits them as `\n` `\t` `\r` `\b` `\f`
            # `\"` `\\` `\/` or `\uXXXX`. Without this exclusion the grammar admits
            # a bare newline/tab inside a string body, which `json.loads` rejects
            # (Codex #6 defect 1).
            'string ::= "\\"" ([^"\\\\\\x00-\\x1f] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\\""',
            'number ::= "-"? ([0-9] | [1-9][0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
            'boolean ::= "true" | "false"',
            'null ::= "null"',
            "ws ::= [ \\t\\n\\r]*",
            # Generic JSON object/array/value rules. Used by _object_rule for schemas
            # that declare `"type": "object"` with NO `properties` (free-form objects,
            # e.g. a tool-call's `arguments` payload) — allows zero-or-more members
            # of arbitrary JSON value type instead of forcing an empty "{}" body.
            # Also used by _rule_for_schema as the fallback for an untyped property
            # (referenced by name, i.e. a single atom — see the comment there for
            # why that matters for GBNF `|` precedence).
            'member ::= string ws ":" ws value',
            "value ::= string | number | boolean | null | object | array",
            'object ::= "{" ws (member (ws "," ws member)*)? ws "}"',
            'array ::= "[" ws (value (ws "," ws value)*)? ws "]"',
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
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        # Constrain to the exact enumerated literals (e.g. the leased tool-name set)
        # instead of falling through to an unconstrained `string`/`number` rule.
        # Parenthesized: GBNF `|` has lower precedence than sequencing, so an
        # unparenthesized alternation embedded inline (e.g. inside _object_rule's
        # "key" ws ":" ws <this> sequence) would leak across the whole enclosing
        # rule instead of binding to just this property's value.
        alternatives = " | ".join(_gbnf_literal(json.dumps(v, separators=(",", ":"))) for v in enum_values)
        return f"({alternatives})"
    schema_type = schema.get("type")
    if isinstance(schema_type, list) and schema_type:
        # JSON Schema type-union, e.g. {"type": ["string", "null"]}. Same
        # parenthesization requirement as `enum` above: this text is spliced
        # inline into the caller's sequence (a property value, an array item
        # rule, ...), so a bare top-level `|` would leak precedence into that
        # surrounding sequence instead of binding to just this alternation
        # (Codex #6 defect 2).
        alternatives = " | ".join(_rule_for_schema({**schema, "type": t}) for t in schema_type)
        return f"({alternatives})"
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
    # No declared type (or one we don't special-case): JSON Schema treats an
    # untyped property as "any JSON value". Reference the already-defined
    # `value` rule — a single atom (a rule name) — instead of re-splicing a
    # hand-written "string | number | boolean | null" alternation here. A bare
    # rule reference can never leak `|` precedence into the caller's
    # surrounding sequence, which is exactly how the old unparenthesized
    # fallback broke nested objects and heterogeneous arrays (Codex #6 defect
    # 2). `value` also correctly includes object/array, which the old
    # hand-written list silently omitted.
    return "value"


def _object_rule(schema: Mapping[str, Any]) -> str:
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping) or not properties:
        # Free-form object (schema is `{"type": "object"}` with no declared
        # `properties`, e.g. a tool-call's `arguments` payload): allow zero-or-more
        # arbitrary JSON members instead of forcing an empty "{}" body, which made
        # every tool call emit useless empty arguments.
        return "object"

    required = schema.get("required", [])
    required_names = set(required) if isinstance(required, list) else set()
    declared_names = set(properties)
    if required_names != declared_names:
        # This builder only knows how to emit a fixed, sorted-order body where
        # EVERY declared property is mandatory (the tool-call envelope —
        # `function` + `arguments`, both required — is exactly that shape and
        # still works below). A schema with optional properties (required is a
        # strict subset of properties, or required is unset/empty while
        # properties exist) needs real optional-member support: allowed-but-
        # not-forced, order-independent presence — which plain sequential GBNF
        # concatenation can't express without either permutation-exploding the
        # grammar or accepting members out of declared order. Rather than
        # silently force optional properties as mandatory (Codex #6 defect 3 —
        # mis-modeling the schema), reject at build time so the caller finds
        # out instead of shipping a grammar that contradicts its own schema.
        raise ValueError(
            "grammar_cache._object_rule: schema declares optional properties "
            f"(properties={sorted(declared_names)!r}, required={sorted(required_names)!r}); "
            "partial/absent 'required' is not supported by this GBNF builder — "
            "declare every property required, or extend _object_rule with real "
            "optional-member support before using this schema."
        )

    parts: list[str] = []
    for name in sorted(properties):
        prop_schema = _schema_mapping(properties[name])
        key_literal = _gbnf_literal(json.dumps(name, separators=(",", ":")))
        parts.append(f'{key_literal} ws ":" ws {_rule_for_schema(prop_schema)}')
    return '"{" ws ' + ' ws "," ws '.join(parts) + ' ws "}"'


def _gbnf_literal(text: str) -> str:
    """Return a GBNF double-quoted literal that generates `text` verbatim.

    `text` is the exact raw output text desired (e.g. a JSON-encoded key/value
    like `"function"`, quote characters included). Backslashes and double quotes
    in `text` are backslash-escaped so they survive as literal characters inside
    the GBNF string rather than terminating it early — the fix for the bug where
    `json.dumps(name)[1:-1]` stripped the JSON quotes and produced an unquoted
    GBNF literal (matching bare `arguments` instead of `"arguments"`).
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _schema_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
