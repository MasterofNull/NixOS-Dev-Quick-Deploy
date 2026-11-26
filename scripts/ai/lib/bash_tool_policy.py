"""Shared Bash tool-contract policy (docs/agent-guides/47-AGENT-TOOL-CONTRACT.md).

evaluate(command) -> (decision, reason). Deny only when the first command of a
simple segment is bare cat/ls/find/grep used for reading. Kill switch:
AQ_BASH_POLICY=0, honoured only from the environment that launches the agent
(owner act); a per-call `AQ_BASH_POLICY=0 cmd` prefix does NOT bypass the policy.
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
_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)\s*(?:\\([A-Za-z_][A-Za-z0-9_]*)|(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\3)")
# stdout redirect to a file: `>`, `>>`, `>|`, `1>`, `&>`; not `2>`, `2>&1`, `>&2`
_STDOUT_REDIRECT = re.compile(r"(?<![\w&<>])(?:1|&)?>>?(?!&)")


def _strip_heredoc_bodies(text: str) -> str:
    """Drop heredoc body lines (up to the terminator); keep the opening line and all later lines."""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in text.split("\n"):
        if pending:
            delim, strip = pending[0]
            if (line.lstrip("\t") if strip else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        pending = [(m.group(2) or m.group(4), m.group(1) == "-") for m in _HEREDOC.finditer(line)]
    return "\n".join(out)


def _split_segments(text: str) -> list[str]:
    """Return the first command of each pipeline, splitting on && || ; and newlines outside quotes."""
    out: list[str] = []
    cur: list[str] = []
    quote = ""
    pipeline_pos = 0
    after_pipe = False

    def flush(is_pipe: bool) -> None:
        nonlocal cur, pipeline_pos, after_pipe
        after_pipe = is_pipe
        piece = "".join(cur).strip()
        cur = []
        if piece and pipeline_pos == 0:
            out.append(piece)
        pipeline_pos = pipeline_pos + 1 if is_pipe else 0

    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
            after_pipe = False
            cur.append(ch)
        elif ch == "\\" and text.startswith("\n", i + 1):
            i += 1  # line continuation: command carries on
        elif text.startswith("||", i) or text.startswith("&&", i):
            flush(False)
            i += 1
        elif ch == "|":
            flush(True)
        elif ch == "\n" and after_pipe and not "".join(cur).strip():
            pass  # newline after a trailing `|` continues the pipeline
        elif ch in ";\n":
            flush(False)
        else:
            if not ch.isspace():
                after_pipe = False
            cur.append(ch)
        i += 1
    flush(False)
    return out


def _first_token(segment: str) -> tuple[str, list[str]]:
    try:
        toks = shlex.split(segment, posix=True)
    except ValueError:
        toks = segment.split()
    while toks and _ENV_ASSIGN.match(toks[0]):
        toks = toks[1:]
    return (os.path.basename(toks[0]) if toks else ""), toks


def first_token(command: str) -> str:
    segs = _split_segments(command)
    return _first_token(segs[0])[0] if segs else ""


def evaluate(command: str) -> tuple[str, str]:
    if os.environ.get("AQ_BASH_POLICY") == "0":
        return "allow", "kill-switch"
    command = command or ""
    command = _strip_heredoc_bodies(command)  # heredoc bodies are data, not commands
    for seg in _split_segments(command):
        name, toks = _first_token(seg)
        if name not in _REPLACEMENT:
            continue
        if name == "cat" and (_STDOUT_REDIRECT.search(seg) or "<<" in seg or len(toks) == 1):
            continue
        return "deny", (
            f"bare `{name}` is denied by the agent tool contract "
            f"(docs/agent-guides/47-AGENT-TOOL-CONTRACT.md); use {_REPLACEMENT[name]}. "
            "Kill switch is environment-level only (owner act: set AQ_BASH_POLICY=0 in the environment that launches the agent); it is not a per-call override."
        )
    return "allow", "ok"
