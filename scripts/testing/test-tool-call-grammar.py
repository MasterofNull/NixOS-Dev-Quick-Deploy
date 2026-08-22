#!/usr/bin/env python3
"""Regression test for the F2.2 GBNF `_object_rule` fix (grammar_cache.py).

Root cause verified live (2026-08-18): `tool_call_grammar(['read_file', 'edit_file',
'write_file'])` forced `{ arguments: {} , function: "read_file" }` — INVALID JSON,
because `_object_rule`:
  1. stripped the JSON quotes off property-name literals (`json.dumps(name)[1:-1]`),
     so the GBNF matched *unquoted* keys instead of `"key"`.
  2. returned the empty-only rule `'"{" ws "}"'` for a free-form object (a schema
     with `"type": "object"` and no `properties`, e.g. the tool-call `arguments`
     payload), forbidding every tool call from carrying any arguments at all.

This test asserts the fixed grammar (a) uses quoted-key literals, (b) allows a
non-empty free-form `arguments` object, and (c) actually ACCEPTS a hand-written
valid JSON envelope and REJECTS the old unquoted-key shape — via a small
self-contained GBNF matcher (the in-repo `llama-gbnf-validator` binary at
~/.local/share/nixos-ai-stack/bitnet-benchmark/BitNet/build/bin/ is unusable here:
it's linked against a glibc/libstdc++ generation no longer present in the nix
store, so a real compile+match check is done in pure Python instead).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import grammar_cache  # noqa: E402
import tool_grammar  # noqa: E402


# --------------------------------------------------------------------------
# Minimal GBNF parser + matcher (subset: literals, char classes w/ ranges and
# negation, rule refs, sequence, alternation, grouping, *، +، ?، {n} quantifiers).
# Enough to validate the grammars this module actually emits.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Lit:
    text: str


@dataclass(frozen=True)
class CharClass:
    negate: bool
    ranges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RuleRef:
    name: str


@dataclass(frozen=True)
class Seq:
    items: tuple[object, ...]


@dataclass(frozen=True)
class Alt:
    options: tuple[object, ...]


@dataclass(frozen=True)
class Rep:
    expr: object
    kind: object  # '*' | '+' | '?' | ('exact', n)


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f"}
_HEX_ESCAPE_SIZES = {"x": 2, "u": 4, "U": 8}


def _decode_escape(text: str, i: int) -> tuple[str, int]:
    """Decode one GBNF escape at text[i] == '\\', mirroring llama.cpp's real
    grammar parser (llama-grammar.cpp `parse_char`): \\x XX / \\u XXXX / \\U
    XXXXXXXX hex escapes (used by the Codex #6 control-char fix, e.g. `\\x1f`),
    plus the existing \\n \\t \\r and self-escaped literals. Returns (char, next_i).
    """
    esc = text[i + 1]
    size = _HEX_ESCAPE_SIZES.get(esc)
    if size is not None:
        start = i + 2
        return chr(int(text[start : start + size], 16)), start + size
    return _ESCAPES.get(esc, esc), i + 2


class _GbnfParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0
        self.n = len(text)

    def parse_rules(self) -> dict[str, object]:
        rules: dict[str, object] = {}
        self._skip_ws()
        while self.i < self.n:
            name = self._parse_ident()
            self._skip_ws()
            if self.text[self.i : self.i + 3] != "::=":
                raise ValueError(f"expected ::= after rule name {name!r} at {self.i}")
            self.i += 3
            self._skip_ws()
            rules[name] = self._parse_alternation()
            self._skip_ws()
        return rules

    def _skip_ws(self) -> None:
        while self.i < self.n:
            c = self.text[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "#":
                while self.i < self.n and self.text[self.i] != "\n":
                    self.i += 1
            else:
                break

    def _peek(self) -> str:
        return self.text[self.i] if self.i < self.n else ""

    def _parse_ident(self) -> str:
        start = self.i
        while self.i < self.n and (self.text[self.i].isalnum() or self.text[self.i] in "_-"):
            self.i += 1
        if self.i == start:
            raise ValueError(f"expected identifier at {self.i}: {self.text[self.i:self.i+20]!r}")
        return self.text[start : self.i]

    def _at_next_rule(self) -> bool:
        if not (self._peek().isalpha() or self._peek() == "_"):
            return False
        save = self.i
        try:
            self._parse_ident()
            self._skip_ws()
            return self.text[self.i : self.i + 3] == "::="
        finally:
            self.i = save

    def _parse_alternation(self) -> object:
        options = [self._parse_sequence()]
        self._skip_ws()
        while self._peek() == "|":
            self.i += 1
            self._skip_ws()
            options.append(self._parse_sequence())
            self._skip_ws()
        return options[0] if len(options) == 1 else Alt(tuple(options))

    def _parse_sequence(self) -> object:
        items: list[object] = []
        while True:
            self._skip_ws()
            c = self._peek()
            if c == "" or c in "|)" or self._at_next_rule():
                break
            items.append(self._parse_term())
        if not items:
            raise ValueError(f"empty sequence at {self.i}")
        return items[0] if len(items) == 1 else Seq(tuple(items))

    def _parse_term(self) -> object:
        atom = self._parse_atom()
        q = self._peek()
        if q in "*+?":
            self.i += 1
            return Rep(atom, q)
        if q == "{":
            self.i += 1
            start = self.i
            while self.i < self.n and self.text[self.i].isdigit():
                self.i += 1
            count = int(self.text[start : self.i])
            if self._peek() != "}":
                raise ValueError(f"unterminated {{n}} quantifier at {self.i}")
            self.i += 1
            return Rep(atom, ("exact", count))
        return atom

    def _parse_atom(self) -> object:
        c = self._peek()
        if c == '"':
            return self._parse_literal()
        if c == "[":
            return self._parse_charclass()
        if c == "(":
            self.i += 1
            self._skip_ws()
            expr = self._parse_alternation()
            self._skip_ws()
            if self._peek() != ")":
                raise ValueError(f"expected ) at {self.i}")
            self.i += 1
            return expr
        if c.isalpha() or c == "_":
            return RuleRef(self._parse_ident())
        raise ValueError(f"unexpected char {c!r} at {self.i}")

    def _parse_literal(self) -> Lit:
        self.i += 1  # opening quote
        out: list[str] = []
        while self.i < self.n and self.text[self.i] != '"':
            c = self.text[self.i]
            if c == "\\":
                ch, self.i = _decode_escape(self.text, self.i)
                out.append(ch)
            else:
                out.append(c)
                self.i += 1
        if self._peek() != '"':
            raise ValueError("unterminated string literal")
        self.i += 1  # closing quote
        return Lit("".join(out))

    def _parse_charclass(self) -> CharClass:
        self.i += 1  # '['
        negate = False
        if self._peek() == "^":
            negate = True
            self.i += 1
        ranges: list[tuple[str, str]] = []
        while self.i < self.n and self.text[self.i] != "]":
            c = self._read_class_char()
            if self._peek() == "-" and self.i + 1 < self.n and self.text[self.i + 1] != "]":
                self.i += 1
                c2 = self._read_class_char()
                ranges.append((c, c2))
            else:
                ranges.append((c, c))
        if self._peek() != "]":
            raise ValueError("unterminated char class")
        self.i += 1  # ']'
        return CharClass(negate, tuple(ranges))

    def _read_class_char(self) -> str:
        c = self.text[self.i]
        if c == "\\":
            ch, self.i = _decode_escape(self.text, self.i)
            return ch
        self.i += 1
        return c


def _positions_after(expr: object, rules: dict[str, object], text: str, pos: int) -> set[int]:
    if isinstance(expr, Lit):
        return {pos + len(expr.text)} if text.startswith(expr.text, pos) else set()
    if isinstance(expr, CharClass):
        if pos >= len(text):
            return set()
        c = text[pos]
        in_range = any(lo <= c <= hi for lo, hi in expr.ranges)
        matched = (not in_range) if expr.negate else in_range
        return {pos + 1} if matched else set()
    if isinstance(expr, RuleRef):
        target = rules.get(expr.name)
        if target is None:
            raise ValueError(f"undefined rule {expr.name!r}")
        return _positions_after(target, rules, text, pos)
    if isinstance(expr, Seq):
        current = {pos}
        for item in expr.items:
            nxt: set[int] = set()
            for p in current:
                nxt |= _positions_after(item, rules, text, p)
            current = nxt
            if not current:
                break
        return current
    if isinstance(expr, Alt):
        result: set[int] = set()
        for opt in expr.options:
            result |= _positions_after(opt, rules, text, pos)
        return result
    if isinstance(expr, Rep):
        if expr.kind == "?":
            return {pos} | _positions_after(expr.expr, rules, text, pos)
        if expr.kind in ("*", "+"):
            frontier = _positions_after(expr.expr, rules, text, pos) if expr.kind == "+" else {pos}
            seen = set(frontier)
            while frontier:
                nxt = set()
                for p in frontier:
                    for q in _positions_after(expr.expr, rules, text, p):
                        if q not in seen:
                            nxt.add(q)
                seen |= nxt
                frontier = nxt
            return seen
        kind, count = expr.kind
        assert kind == "exact"
        current = {pos}
        for _ in range(count):
            nxt = set()
            for p in current:
                nxt |= _positions_after(expr.expr, rules, text, p)
            current = nxt
            if not current:
                break
        return current
    raise TypeError(f"unhandled expr {expr!r}")


def gbnf_matches(gbnf_text: str, candidate: str, root: str = "root") -> bool:
    """Return True iff `candidate` is fully matched by rule `root` in `gbnf_text`."""

    rules = _GbnfParser(gbnf_text).parse_rules()
    ends = _positions_after(rules[root], rules, candidate, 0)
    return len(candidate) in ends


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def _grammar() -> str:
    gbnf, _hit = tool_grammar.tool_call_grammar(["read_file", "edit_file", "write_file"])
    return gbnf


def test_grammar_parses_as_valid_gbnf():
    # "compiles": the parser above accepts the emitted grammar without error and
    # produces a non-empty rule set including root + the new generic object/array rules.
    rules = _GbnfParser(_grammar()).parse_rules()
    for expected in ("root", "string", "number", "boolean", "null", "ws", "member", "value", "object", "array"):
        assert expected in rules, f"missing rule {expected!r}"


def test_property_keys_are_quoted_in_grammar_source():
    gbnf = _grammar()
    # Bug #1: keys must be emitted as the GBNF literal for `"arguments"` / `"function"`
    # (quote characters included in the generated text), not the bare word.
    assert '"\\"arguments\\""' in gbnf, gbnf
    assert '"\\"function\\""' in gbnf, gbnf
    # and NOT the old quote-stripped form (a literal that matches the bare word).
    assert '"arguments" ws' not in gbnf
    assert '"function" ws' not in gbnf


def test_arguments_uses_generic_nonempty_capable_object_not_empty_only():
    gbnf = _grammar()
    # Bug #2: the old code forced arguments to `'"{" ws "}"'` (empty only). The fixed
    # grammar must route arguments through the free-form `object` rule instead.
    assert '"\\"arguments\\"" ws ":" ws object' in gbnf, gbnf
    assert '"{" ws "}"' not in gbnf, gbnf


def test_function_is_constrained_to_the_enum_of_tool_names():
    gbnf = _grammar()
    for name in ("read_file", "edit_file", "write_file"):
        assert json.dumps(name) in gbnf.replace("\\", "")


def test_grammar_accepts_a_real_valid_envelope_with_nonempty_arguments():
    gbnf = _grammar()
    envelope = '{"arguments":{"file_path":"a.py"},"function":"read_file"}'
    assert json.loads(envelope) == {"arguments": {"file_path": "a.py"}, "function": "read_file"}
    assert gbnf_matches(gbnf, envelope), "grammar must accept a valid multi-arg tool-call envelope"


def test_grammar_accepts_multi_key_nested_arguments():
    gbnf = _grammar()
    envelope = (
        '{"arguments":{"file_path":"a.py","old_string":"x","new_string":"y"},'
        '"function":"edit_file"}'
    )
    assert json.loads(envelope)  # sanity: real JSON
    assert gbnf_matches(gbnf, envelope)


def test_grammar_accepts_empty_arguments_too():
    gbnf = _grammar()
    envelope = '{"arguments":{},"function":"write_file"}'
    assert json.loads(envelope)
    assert gbnf_matches(gbnf, envelope), "free-form object must still permit {}"


def test_grammar_rejects_unquoted_keys_the_old_bug_shape():
    gbnf = _grammar()
    # The exact invalid shape reported live before the fix.
    old_bug_output = '{arguments:{},function:"read_file"}'
    with_ws = '{ arguments: {} , function: "read_file" }'
    assert not gbnf_matches(gbnf, old_bug_output)
    assert not gbnf_matches(gbnf, with_ws)


def test_grammar_rejects_unknown_function_name():
    gbnf = _grammar()
    envelope = '{"arguments":{},"function":"delete_everything"}'
    assert not gbnf_matches(gbnf, envelope)


# --------------------------------------------------------------------------
# Codex #6 regression tests — the grammar accepted strings json.loads rejects.
# See .agent/collaboration/codex-review-local-agent-batch-20260821.md finding 6.
# --------------------------------------------------------------------------


def test_string_rule_excludes_raw_control_chars_in_grammar_source():
    gbnf = _grammar()
    # Defect 1: the string body's unescaped char class must explicitly exclude
    # U+0000-U+001F, not just `"` and `\`.
    assert "\\x00-\\x1f" in gbnf, gbnf


def test_string_rule_rejects_raw_control_char_but_accepts_escaped_form():
    gbnf = _grammar()
    # A bare/raw newline inside a JSON string is exactly what `json.loads`
    # rejects (json.decoder.JSONDecodeError: Invalid control character).
    raw_control_char = '{"arguments":{"note":"line1' + "\n" + 'line2"},"function":"read_file"}'
    escaped = '{"arguments":{"note":"line1\\nline2"},"function":"read_file"}'

    assert json.loads(escaped) == {"arguments": {"note": "line1\nline2"}, "function": "read_file"}
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw_control_char)

    assert not gbnf_matches(gbnf, raw_control_char), "grammar must reject a bare control char in a string"
    assert gbnf_matches(gbnf, escaped), "grammar must still accept the properly \\n-escaped form"


def test_object_rule_parenthesizes_untyped_property_alternation():
    # Defect 2 reproduction: before the fix, an untyped property ("a": {}) built
    # the rule text "string | number | boolean | null" and spliced it UNPARENTHESIZED
    # into the object sequence. That top-level `|` leaked precedence across the
    # whole enclosing rule, so `root` degraded into an alternation where one
    # branch was the bare `number` rule alone — meaning a lone `5` (or `true`)
    # satisfied `root` even though the schema demands a 2-key object.
    schema = {
        "type": "object",
        "properties": {
            "a": {},  # no "type" -> untyped/any-value fallback
            "b": {"type": "string"},
        },
        "required": ["a", "b"],
    }
    gbnf, _hit = grammar_cache.GrammarCache().get_or_build(schema, "zt")

    assert not gbnf_matches(gbnf, "5"), "bare number must not satisfy the whole object grammar"
    assert not gbnf_matches(gbnf, "true"), "bare boolean must not satisfy the whole object grammar"

    valid_string_a = '{"a":"anything","b":"x"}'
    valid_number_a = '{"a":5,"b":"x"}'
    assert json.loads(valid_string_a) and json.loads(valid_number_a)
    assert gbnf_matches(gbnf, valid_string_a)
    assert gbnf_matches(gbnf, valid_number_a), "untyped property must still accept a number value"


def test_nested_object_and_heterogeneous_array_schema_round_trips():
    # Defect 2, functional form: nested object + an array whose items are a
    # JSON-Schema type-union ("heterogeneous array"). Both nested-object
    # property splicing and type-union alternation splicing must be
    # parenthesized correctly for this to compile into a working grammar.
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "meta": {
                "type": "object",
                "properties": {"count": {"type": "number"}},
                "required": ["count"],
            },
            "tags": {"type": "array", "items": {"type": ["string", "number"]}},
        },
        "required": ["id", "meta", "tags"],
    }
    gbnf, _hit = grammar_cache.GrammarCache().get_or_build(schema, "zt")

    sample = '{"id":"x1","meta":{"count":3},"tags":["a",2,"b"]}'
    assert json.loads(sample) == {"id": "x1", "meta": {"count": 3}, "tags": ["a", 2, "b"]}
    assert gbnf_matches(gbnf, sample)

    # Syntactically valid JSON that violates the declared item type-union
    # (bool is not in ["string", "number"]) must still be rejected — proves the
    # union is a real constraint, not a degenerate "any value" grammar.
    bad_item_type = '{"id":"x1","meta":{"count":3},"tags":[true]}'
    assert json.loads(bad_item_type)
    assert not gbnf_matches(gbnf, bad_item_type)


def test_object_rule_rejects_schema_with_partial_required_properties():
    # Defect 3: a schema where "b" is optional (declared in properties but not
    # in required) must be explicitly rejected rather than silently forcing it
    # as mandatory (which would mis-model the schema).
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
    }
    with pytest.raises(ValueError):
        grammar_cache.default_json_schema_to_gbnf(schema, "zt")


def test_object_rule_rejects_schema_with_no_required_key_at_all():
    # Absent "required" means "everything optional" per JSON Schema — same
    # unsupported shape as a partial list, must reject the same way.
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
    }
    with pytest.raises(ValueError):
        grammar_cache.default_json_schema_to_gbnf(schema, "zt")


def test_object_rule_still_forces_all_properties_when_all_required_no_regression():
    # The tool-call envelope shape (function+arguments, both required) must keep
    # working exactly as before: every declared property mandatory.
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a", "b"],
    }
    gbnf = grammar_cache.default_json_schema_to_gbnf(schema, "zt")

    assert gbnf_matches(gbnf, '{"a":"x","b":"y"}')
    assert not gbnf_matches(gbnf, '{"a":"x"}'), "b omitted -> still rejected, both are required"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
