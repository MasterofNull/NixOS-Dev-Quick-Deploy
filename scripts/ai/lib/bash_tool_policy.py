"""Shared Bash tool-contract policy (docs/agent-guides/47-AGENT-TOOL-CONTRACT.md).

CONTRACT: this is a best-effort efficiency nudge, NOT a security boundary.
It denies only when a command segment is CLEARLY a bare read: the first word of
a pipeline is exactly `cat`, `ls`, `find` or `grep` and, for `cat`, it reads
files (no stdout redirect to a file, no heredoc/stdin-only use). Whenever
tokenizing fails or is ambiguous (shlex ValueError, unbalanced quotes,
unterminated constructs, unusual syntax) the command is ALLOWED. False allows
are acceptable; false denies must be rare. Tokenizing uses stdlib shlex only.

evaluate(command) -> (decision, reason); evaluate_detail adds the offending
first word for telemetry. Kill switch: AQ_BASH_POLICY=0, honoured only from the
environment that launches the agent (owner act); a per-call `AQ_BASH_POLICY=0
cmd` prefix does NOT bypass the policy.
"""
from __future__ import annotations

import os
import re
import shlex

_REPLACEMENT = {
    "cat": "ctx_read (or `acat`)",
    "ls": "ctx_tree / ctx_glob (or `als`)",
    "find": "ctx_glob / ctx_tree (or `fd`)",
    "grep": "ctx_search (or `agrep` / `rg`)",
}
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PUNCT = frozenset("();<>|&")
_SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "|&", ";;"})
_PIPES = frozenset({"|", "|&"})
_STDOUT_REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>"})
_STDIN_REDIRECTS = frozenset({"<", "<<", "<<<"})

Token = tuple[str, bool]  # (text, is_unquoted_operator)


def _tokenize(text: str) -> list[Token]:
    """shlex-tokenize one logical line; raises ValueError when ambiguous."""
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = "#"
    toks: list[Token] = []
    while True:
        tok = lex.get_token()
        if tok is None:
            return toks
        op = False
        if tok and set(tok) <= _PUNCT:
            # Punctuation text is an operator only if it appears raw (unquoted, unescaped).
            end = lex.instream.tell() - len(getattr(lex, "_pushback_chars", ()))  # type: ignore[union-attr]
            raw = text[:end].rstrip(" \t")
            op = raw.endswith(tok) and not raw[: -len(tok)].endswith("\\")
        toks.append((tok, op))


def _heredoc_delim(toks: list[Token]) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    for i, (tok, op) in enumerate(toks):
        if op and tok == "<<" and i + 1 < len(toks):
            nxt = toks[i + 1][0]
            strip = nxt.startswith("-")
            if strip:
                nxt = nxt[1:] or (toks[i + 2][0] if i + 2 < len(toks) else "")
            if nxt:
                out.append((nxt, strip))
    return out


def _scan(text: str) -> list[list[Token]]:
    """Token lists per logical line, heredoc bodies dropped. On ambiguity, returns what was parsed so far."""
    lines = text.split("\n")
    out: list[list[Token]] = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        i += 1
        while True:
            m = len(cur) - len(cur.rstrip("\\"))
            if m % 2 == 1 and i < len(lines):  # line continuation
                cur = cur[:-1] + lines[i]
                i += 1
                continue
            try:
                toks = _tokenize(cur)
            except ValueError:
                if i >= len(lines):
                    return out  # unbalanced to the end: ambiguous, stop inspecting
                cur += "\n" + lines[i]  # maybe a multi-line quote
                i += 1
                continue
            break
        out.append(toks)
        for delim, strip in _heredoc_delim(toks):
            while i < len(lines):
                body = lines[i]
                i += 1
                if (body.lstrip("\t") if strip else body) == delim:
                    break
    return out


def _cat_reads_files(args: list[Token]) -> bool:
    """True when `cat` clearly reads named files (not a write, stdin or heredoc use)."""
    names: list[str] = []
    skip = False
    for i, (tok, op) in enumerate(args):
        if skip:
            skip = False
            continue
        if not op:
            names.append(tok)
        elif tok in _STDIN_REDIRECTS:
            return False
        elif tok in _STDOUT_REDIRECTS:
            prev = args[i - 1] if i else ("", True)
            if prev[1] or not prev[0].isdigit() or prev[0] == "1":
                return False  # stdout to a file: a write
            names.pop()  # `2>file`: stderr redirect, fd token was not a filename
            skip = True
        elif tok not in _SEPARATORS:
            skip = True  # `>&2`, `<&3`: target is not a filename
    return any(n != "-" and not n.startswith("-") for n in names)


def _offender(cmd: list[Token]) -> str:
    """Return the denied first word of a pipeline-head segment, else ''."""
    k = 0
    while k < len(cmd) and not cmd[k][1] and _ENV_ASSIGN.match(cmd[k][0]):
        k += 1
    if k >= len(cmd) or cmd[k][1]:
        return ""
    name = cmd[k][0]
    if name not in _REPLACEMENT:
        return ""
    if name == "cat" and not _cat_reads_files(cmd[k + 1 :]):
        return ""
    return name


def _first_word(cmd: list[Token]) -> str:
    k = 0
    while k < len(cmd) and not cmd[k][1] and _ENV_ASSIGN.match(cmd[k][0]):
        k += 1
    return cmd[k][0] if k < len(cmd) and not cmd[k][1] else ""


def evaluate_detail(command: str) -> tuple[str, str, str]:
    """(decision, reason, token): token is the offending first word on deny, else the first word seen."""
    if os.environ.get("AQ_BASH_POLICY") == "0":
        return "allow", "kill-switch", ""
    first = ""
    in_pipe = False
    for toks in _scan(command or ""):
        cmd: list[Token] = []

        def end(sep: str) -> str:
            nonlocal cmd, in_pipe, first
            hit = ""
            if cmd:
                if not first:
                    first = _first_word(cmd)
                if not in_pipe:
                    hit = _offender(cmd)
                in_pipe = sep in _PIPES
            elif sep:
                in_pipe = sep in _PIPES
            cmd = []
            return hit

        for tok, op in toks:
            if op and tok in _SEPARATORS:
                hit = end(tok)
            else:
                cmd.append((tok, op))
                continue
            if hit:
                return "deny", _deny_reason(hit), hit
        hit = end("") if cmd else ""
        if hit:
            return "deny", _deny_reason(hit), hit
    return "allow", "ok", first


def _deny_reason(name: str) -> str:
    return (
        f"bare `{name}` is denied by the agent tool contract "
        f"(docs/agent-guides/47-AGENT-TOOL-CONTRACT.md); use {_REPLACEMENT[name]}. "
        "Kill switch is environment-level only (owner act: set AQ_BASH_POLICY=0 in the environment that launches the agent); it is not a per-call override."
    )


def evaluate(command: str) -> tuple[str, str]:
    decision, reason, _ = evaluate_detail(command)
    return decision, reason
