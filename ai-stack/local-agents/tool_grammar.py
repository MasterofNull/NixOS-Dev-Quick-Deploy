#!/usr/bin/env python3
"""P2 — tool-call GBNF construction for the local agent lane.

The local 35B intermittently emits a tool call as PROSE ("I will call write_file...") instead of the
required JSON envelope, and ~15% of its tool-JSON is malformed. GBNF-constrained decoding forces the
output to a valid tool-call shape at generation time — the FAST producer-fix (no retrain) from the
closed-local-improvement-loop PRD (Phase 2).

This module is PURE: it builds the tool-call envelope JSON schema and hands it to F2.2's grammar_cache
(scripts/ai/lib/grammar_cache.py) to produce + cache the GBNF. Wiring the resulting grammar into the
live request (agent_executor -> build_llama_payload(grammar=...)) is flag-gated (AQ_LOCAL_GBNF) and
must be validated by a bench before default-on, so a too-strict grammar can never silently break
tool-calling.

The local tool-call envelope observed in the live stream is: {"function": "<name>", "arguments": {...}}.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# grammar_cache lives in scripts/ai/lib (F2.2).
_LIB = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
import grammar_cache  # noqa: E402


def tool_call_schema(tool_names: list[str]) -> dict[str, Any]:
    """JSON schema for the local tool-call envelope, constraining `function` to the AVAILABLE tools.

    {"function": <enum of tool_names>, "arguments": <object>}. Constraining the function name to the
    leased tool set (not free text) is what kills 'call a tool that doesn't exist' + prose-as-tool-call.
    """
    fn: dict[str, Any] = {"type": "string"}
    if tool_names:
        fn = {"type": "string", "enum": sorted(set(tool_names))}
    return {
        "type": "object",
        "properties": {
            "function": fn,
            "arguments": {"type": "object"},
        },
        "required": ["function", "arguments"],
        "additionalProperties": False,
    }


def tool_call_grammar(
    tool_names: list[str],
    zero_trust_state: Any = None,
    cache: "grammar_cache.GrammarCache | None" = None,
) -> tuple[str, bool]:
    """Build (or cache-hit) the GBNF for the tool-call envelope over `tool_names`.

    Returns (gbnf, was_cache_hit). `zero_trust_state` shares F2.2/F3's namespaced key so the grammar
    cache and the capability policy stay in one namespace. Pass a shared GrammarCache to persist across
    turns; a fresh one is created if None (still deterministic)."""
    c = cache if cache is not None else grammar_cache.GrammarCache()
    schema = tool_call_schema(tool_names)
    return c.get_or_build(schema, zero_trust_state)
