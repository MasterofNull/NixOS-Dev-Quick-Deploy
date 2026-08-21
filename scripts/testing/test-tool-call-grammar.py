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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

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
                self.i += 1
                esc = self.text[self.i]
                out.append(_ESCAPES.get(esc, esc))
                self.i += 1
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
            self.i += 1
            esc = self.text[self.i]
            self.i += 1
            return _ESCAPES.get(esc, esc)
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


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
