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


async def main_async() -> int:
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
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
