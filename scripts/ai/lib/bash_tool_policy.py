"""Shared Bash tool-contract policy (docs/agent-guides/47-AGENT-TOOL-CONTRACT.md).

evaluate(command) -> (decision, reason). Deny only when the first command of a
simple segment is bare cat/ls/find/grep used for reading. Kill switch:
AQ_BASH_POLICY=0.
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


def _split_segments(text: str) -> list[str]:
    """Return the first command of each pipeline, splitting on && || ; and newlines outside quotes."""
    out: list[str] = []
    cur: list[str] = []
    quote = ""
    pipeline_pos = 0

    def flush(is_pipe: bool) -> None:
        nonlocal cur, pipeline_pos
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
            cur.append(ch)
        elif text.startswith("||", i) or text.startswith("&&", i):
            flush(False)
            i += 1
        elif ch == "|":
            flush(True)
        elif ch in ";\n":
            flush(False)
        else:
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
    if "<<" in command:  # heredoc bodies are data, not commands
        idx = command.index("<<")
        eol = command.find("\n", idx)
        command = command if eol < 0 else command[:eol]
    for seg in _split_segments(command):
        name, toks = _first_token(seg)
        if name not in _REPLACEMENT:
            continue
        if name == "cat" and (">" in seg or "<<" in seg or len(toks) == 1):
            continue
        return "deny", (
            f"bare `{name}` is denied by the agent tool contract "
            f"(docs/agent-guides/47-AGENT-TOOL-CONTRACT.md); use {_REPLACEMENT[name]}. "
            "Override: AQ_BASH_POLICY=0."
        )
    return "allow", "ok"
