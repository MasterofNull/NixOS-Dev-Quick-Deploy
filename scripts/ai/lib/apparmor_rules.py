"""Strict allowlist validation for AppArmor rule lines written into Nix source.

Only the rule forms emitted by scripts/automation/apparmor-fix-agent.py are
accepted. Anything else is rejected (never sanitized): the text lands inside a
Nix indented string, so `${`, `''`, newlines and backticks are injection vectors.
"""
import re
from typing import Optional

_PATH_CHARS = r"(?:[A-Za-z0-9_.+:@*/-]|@\{pids\})+"
_PERMS = r"(?:r|w|rw|ix|k|rwk)"
_PEER = r"[A-Za-z0-9_.:/@-]+"

_PATH_RULE = re.compile(rf"^/{_PATH_CHARS}? {_PERMS},$|^/ {_PERMS},$")
_PTRACE_RULE = re.compile(rf"^ptrace (?:read|trace|readby|tracedby) peer={_PEER},$")
_SIGNAL_RULE = re.compile(rf"^signal \([a-z0-9]+(?: [a-z0-9]+)*\) peer={_PEER},$")
_COMMENT = re.compile(r"^[A-Za-z0-9 _/.()<>@{}*,+→-]{1,120}$")
_FORBIDDEN = ("$", "`", '"', "'", "#", "\n", "\r", "\x00", "\t", "\\", "..")


def rule_error(rule: object) -> Optional[str]:
    """Return None if the rule line is acceptable, else a short rejection reason."""
    if not isinstance(rule, str):
        return "rule is not a string"
    if len(rule) > 400:
        return "rule too long"
    body = rule.lstrip(" ")
    if body != body.strip():
        return "trailing whitespace"
    for bad in _FORBIDDEN:
        if bad in body:
            return f"forbidden sequence {bad!r}"
    # braces are only legal as the literal @{pids} variable
    if "{" in body.replace("@{pids}", "") or "}" in body.replace("@{pids}", ""):
        return "forbidden brace"
    if _PATH_RULE.match(body) or _PTRACE_RULE.match(body) or _SIGNAL_RULE.match(body):
        return None
    return "does not match an allowed AppArmor rule form"


def comment_error(comment: object) -> Optional[str]:
    if not isinstance(comment, str) or not _COMMENT.match(comment):
        return "comment contains disallowed characters"
    if "${" in comment or "''" in comment:
        return "comment contains Nix string metacharacters"
    return None
