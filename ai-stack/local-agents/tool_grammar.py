#!/usr/bin/env python3
"""Function-coupled, bounded GBNF construction for local tool calls.

The grammar is deliberately derived from the *enabled* tool parameter schemas.
It is a producer-side guard, not a replacement for runtime authorization or
handler validation.  Invalid/ambiguous schemas fail while building rather than
silently falling back to the older free-form ``arguments`` object.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
import grammar_cache  # noqa: E402

MAX_VARIANTS_PER_TOOL = 32
_SUPPORTED_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def canonical_tool_schemas(tool_schemas: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate and canonically copy enabled ``name -> parameters`` schemas.

    Every parameters schema must be a closed object.  This is intentionally
    narrower than general JSON Schema: emitting a grammar that admits unknown
    arguments would negate the guard this module provides.
    """
    if not isinstance(tool_schemas, Mapping):
        raise ValueError("tool_schemas must be an enabled name-to-parameters mapping")
    normalized: dict[str, dict[str, Any]] = {}
    for name in sorted(tool_schemas):
        if not isinstance(name, str) or not name:
            raise ValueError("tool schema names must be non-empty strings")
        raw = tool_schemas[name]
        if not isinstance(raw, Mapping):
            raise ValueError(f"parameters schema for tool {name!r} must be an object")
        if raw.get("type") != "object":
            raise ValueError(f"parameters schema for tool {name!r} must have type=object")
        properties = raw.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError(f"properties for tool {name!r} must be an object")
        # ToolRegistry's historical schemas commonly omit this JSON-Schema
        # default.  The grammar is intentionally stricter: omission is
        # canonicalized to closed, while an explicit open schema is rejected.
        if raw.get("additionalProperties") is True:
            raise ValueError(f"parameters schema for tool {name!r} must not open additionalProperties")
        required_raw = raw.get("required", [])
        if not isinstance(required_raw, list) or any(not isinstance(key, str) for key in required_raw):
            raise ValueError(f"required for tool {name!r} must be a list of strings")
        required = sorted(set(required_raw))
        if len(required) != len(required_raw) or not set(required).issubset(properties):
            raise ValueError(f"required keys for tool {name!r} must be unique declared properties")
        copied_props: dict[str, dict[str, Any]] = {}
        for key in sorted(properties):
            value = properties[key]
            if not isinstance(key, str) or not key or not isinstance(value, Mapping):
                raise ValueError(f"properties for tool {name!r} must have non-empty string keys and object schemas")
            _validate_value_schema(value, tool_name=name, key=key)
            copied_props[key] = json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))
        optional = sorted(set(copied_props) - set(required))
        if 1 << len(optional) > MAX_VARIANTS_PER_TOOL:
            raise ValueError(
                f"tool {name!r} has {len(optional)} optional arguments; "
                f"would exceed {MAX_VARIANTS_PER_TOOL} grammar variants"
            )
        normalized[name] = {
            "type": "object",
            "properties": copied_props,
            "required": required,
            "additionalProperties": False,
        }
    return normalized


def _validate_value_schema(schema: Mapping[str, Any], *, tool_name: str, key: str) -> None:
    """Reject shapes that grammar_cache cannot faithfully compile."""
    if "const" in schema:
        raise ValueError(f"const for {tool_name!r}.{key} is not supported by the grammar builder")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError(f"enum for {tool_name!r}.{key} must be a non-empty list")
    if "oneOf" in schema:
        variants = schema["oneOf"]
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"oneOf for {tool_name!r}.{key} must be a non-empty list")
        for variant in variants:
            if not isinstance(variant, Mapping):
                raise ValueError(f"oneOf for {tool_name!r}.{key} must contain schemas")
            _validate_value_schema(variant, tool_name=tool_name, key=key)
        return
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if not schema_type or any(item not in _SUPPORTED_TYPES for item in schema_type):
            raise ValueError(f"type union for {tool_name!r}.{key} is unsupported")
        if any(item in {"object", "array"} for item in schema_type):
            raise ValueError(f"container type union for {tool_name!r}.{key} is unsupported")
    elif schema_type not in _SUPPORTED_TYPES:
        raise ValueError(f"type for {tool_name!r}.{key} is required and unsupported")
    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping) or schema.get("additionalProperties") is True:
            raise ValueError(f"nested object {tool_name!r}.{key} must be closed")
        required = schema.get("required", [])
        if not isinstance(required, list) or set(required) != set(properties):
            raise ValueError(f"nested object {tool_name!r}.{key} must require all declared properties")
        for nested_key, nested_schema in properties.items():
            if not isinstance(nested_key, str) or not isinstance(nested_schema, Mapping):
                raise ValueError(f"nested object {tool_name!r}.{key} is malformed")
            _validate_value_schema(nested_schema, tool_name=tool_name, key=f"{key}.{nested_key}")
    if schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise ValueError(f"array {tool_name!r}.{key} must declare one items schema")
        _validate_value_schema(items, tool_name=tool_name, key=f"{key}[]")


def tool_schema_cache_key(tool_schemas: Mapping[str, Any]) -> str:
    """Return a stable identity binding tool names and canonical parameter schemas."""
    canonical = canonical_tool_schemas(tool_schemas)
    material = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def tool_call_schema(tool_schemas: Mapping[str, Any]) -> dict[str, Any]:
    """Build a function-coupled envelope ``oneOf`` for each allowed argument subset."""
    canonical = canonical_tool_schemas(tool_schemas)
    alternatives: list[dict[str, Any]] = []
    for name, parameters in canonical.items():
        properties = parameters["properties"]
        required = parameters["required"]
        optional = sorted(set(properties) - set(required))
        for count in range(len(optional) + 1):
            for subset in itertools.combinations(optional, count):
                selected = sorted(set(required).union(subset))
                arguments = {
                    "type": "object",
                    "properties": {key: properties[key] for key in selected},
                    "required": selected,
                    "additionalProperties": False,
                }
                alternatives.append(
                    {
                        "type": "object",
                        "properties": {
                            "function": {"type": "string", "enum": [name]},
                            "arguments": arguments,
                        },
                        "required": ["arguments", "function"],
                        "additionalProperties": False,
                    }
                )
    if not alternatives:
        raise ValueError("cannot build a tool-call grammar with no enabled tools")
    return {"oneOf": alternatives}


def tool_call_grammar(
    tool_schemas: Mapping[str, Any],
    zero_trust_state: Any = None,
    cache: "grammar_cache.GrammarCache | None" = None,
) -> tuple[str, bool]:
    """Build/cache GBNF for exact enabled schemas; build errors are deliberate."""
    c = cache if cache is not None else grammar_cache.GrammarCache()
    return c.get_or_build(tool_call_schema(tool_schemas), zero_trust_state)
