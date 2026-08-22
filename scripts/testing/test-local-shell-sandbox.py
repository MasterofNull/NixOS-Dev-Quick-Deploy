#!/usr/bin/env python3
"""Regression tests for local shell tool sandbox safety behavior."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents" / "builtin_tools"))

import shell_tools  # noqa: E402


class FailingSandbox:
    available = True
    required = True

    def build_argv(self, command: str, timeout_seconds: int) -> list[str]:
        raise RuntimeError("synthetic nsjail failure")


async def test_injection_and_sandbox_failure() -> None:
    injection = await shell_tools.run_command_handler("echo ok && cat /etc/passwd")
    assert injection["success"] is False, injection
    assert injection.get("safety_reason") == "shell_injection_guard", injection

    original = shell_tools._nsjail
    try:
        shell_tools._nsjail = FailingSandbox()
        failed = await shell_tools.run_command_handler("echo ok")
        assert failed["success"] is False, failed
        assert failed.get("safety_reason") == "sandbox_required_failed", failed
    finally:
        shell_tools._nsjail = original

    print("PASS: local shell sandbox fails closed for injection and required nsjail failures")


# ---------------------------------------------------------------------------
# Regression coverage for the artifact-strip narrowing (Codex #7 + Antigravity
# review, 2026-08-21, finding 7). The original safety net,
# `re.sub(r"[\s}\]\",]+$", "", command)`, stripped ANY trailing
# whitespace/brace/bracket/quote/comma — corrupting legitimate commands ending
# in those characters (e.g. `printf "%s" "]"` -> `printf "%s`, unterminated).
# The primary fix now lives at the JSON-parsing boundary
# (tool_registry.parse_tool_call_from_llama -> _strip_envelope_tail_artifacts);
# shell_tools.run_command_handler keeps only a narrowed defense-in-depth net
# that matches exclusively the leaked-envelope shape: a real embedded newline
# immediately followed by a closing brace and nothing after it but more
# braces/commas/whitespace to the end of the string.
# ---------------------------------------------------------------------------

async def test_legitimate_trailing_punctuation_unchanged() -> None:
    """Commands legitimately ending in "]"/"}"/'"'/"," execute unmodified."""
    result = await shell_tools.run_command_handler('printf "%s" "]"')
    assert result.get("success") is True, result
    assert result.get("stdout") == "]", result

    result = await shell_tools.run_command_handler('echo "}"')
    assert result.get("success") is True, result
    assert result.get("stdout").strip() == "}", result

    result = await shell_tools.run_command_handler('printf "%s" "a,b,"')
    assert result.get("success") is True, result
    assert result.get("stdout") == "a,b,", result

    # Task's canonical example: alternation pattern quoted with a literal
    # backslash-pipe, piped through head. The guard only matches a literal
    # unquoted "||" (double pipe) or other control tokens; a single "|" pipe
    # operator and the backslash-escaped "\|" inside the quoted grep pattern
    # are both untouched by it. Self-contained (printf | grep | head) so it
    # doesn't depend on a host filesystem path being visible inside a
    # required nsjail sandbox's isolated tmpfs.
    cmd = r"printf 'alpha\nbeta\ngamma\n' | grep -n 'a\|b' | head"
    result = await shell_tools.run_command_handler(cmd)
    assert result.get("safety_reason") != "shell_injection_guard", (cmd, result)
    assert result.get("success") is True, (cmd, result)
    assert "alpha" in result.get("stdout", "") and "beta" in result.get("stdout", ""), (cmd, result)

    print("PASS: legitimate commands ending in ]/}/\"/, execute unchanged")


async def test_genuine_envelope_tail_is_stripped() -> None:
    """A genuine leaked tool-call-envelope tail (real newline + brace/comma) is cleaned."""
    leaked = 'echo artifact-strip-fix-works\n},\n'
    result = await shell_tools.run_command_handler(leaked)
    assert result.get("success") is True, result
    assert "artifact-strip-fix-works" in (result.get("stdout") or ""), result
    print("PASS: genuine leaked envelope tail is stripped and the command executes")


async def test_real_injection_still_rejected() -> None:
    """Real shell-injection sequences, including embedded newlines that are NOT
    an envelope tail, are still rejected by the guard."""
    cases = [
        "echo a\necho b",  # cmd\ncmd2 — newline not followed solely by brace/comma/ws
        "echo ok; rm -rf /tmp/x",
        "echo ok && rm -rf /tmp/x",
        "echo ok || rm -rf /tmp/x",
        "echo `whoami`",
        "echo $(whoami)",
    ]
    for cmd in cases:
        result = await shell_tools.run_command_handler(cmd)
        assert result["success"] is False, (cmd, result)
        assert result.get("safety_reason") == "shell_injection_guard", (cmd, result)
    print("PASS: real shell-injection sequences (incl. embedded newlines) are still rejected")


async def main_async() -> int:
    await test_injection_and_sandbox_failure()
    await test_legitimate_trailing_punctuation_unchanged()
    await test_genuine_envelope_tail_is_stripped()
    await test_real_injection_still_rejected()
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
