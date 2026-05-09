"""
safe_command_executor.py — Code-level guardrail for all agent terminal command execution.

All run_terminal_command invocations in mcp-bridge-hybrid.py MUST go through
check_command() before subprocess execution. Blocked commands are logged and
return a structured error instead of executing.

Audit log: /var/log/nixos-ai-stack/agent-commands.jsonl
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Tuple

# ---------------------------------------------------------------------------
# Blocklist — patterns that are NEVER allowed from agent-initiated commands
# ---------------------------------------------------------------------------
BLOCKLIST: list[tuple[str, str]] = [
    # Destructive filesystem operations
    (r"\brm\s+-rf\b", "destructive-rm-rf"),
    (r"\brm\s+--recursive\s+--force\b", "destructive-rm-recursive-force"),
    (r"\bshred\b", "destructive-shred"),
    (r"\btruncate\b.*--size[= ]*0", "destructive-truncate-zero"),
    # Raw disk / format operations
    (r"\bdd\s+if=", "disk-dd"),
    (r"\bmkfs\b", "disk-mkfs"),
    (r">\s*/dev/sd[a-z]", "disk-raw-write"),
    (r">\s*/dev/nvme", "disk-raw-write-nvme"),
    # Privilege escalation + destructive combos
    (r"\bsudo\s+rm\b", "sudo-rm"),
    (r"\bsudo\s+dd\b", "sudo-dd"),
    (r"\bsudo\s+mkfs\b", "sudo-mkfs"),
    # Git force operations (can destroy history)
    (r"\bgit\s+push\s+.*--force\b", "git-force-push"),
    (r"\bgit\s+push\s+.*-f\b", "git-force-push-short"),
    (r"\bgit\s+reset\s+--hard\b", "git-reset-hard"),
    (r"\bgit\s+clean\s+.*-f\b", "git-clean-force"),
    # Overly permissive chmod
    (r"\bchmod\s+777\b", "chmod-777"),
    (r"\bchmod\s+-R\s+777\b", "chmod-recursive-777"),
    # Network firewall flush
    (r"\biptables\s+-F\b", "iptables-flush"),
    (r"\bnft\s+flush\b", "nftables-flush"),
    # NixOS system mutations (must go through proper nix tools)
    (r"\bnixos-rebuild\s+switch\b", "nixos-rebuild-switch-direct"),
    (r"\bhome-manager\s+switch\b", "home-manager-switch-direct"),
    # Wrapper-first AIDB policy for agent-initiated terminal commands.
    (r"\bcurl\b[^\n]*https?://(?:localhost|127\.0\.0\.1):8002(?:/|\b)", "aidb-loopback-raw-curl"),
]

AUDIT_LOG = Path("/var/log/nixos-ai-stack/agent-commands.jsonl")


def check_command(command: str) -> Tuple[bool, str]:
    """
    Check whether a command is safe to execute.

    Returns:
        (True, "ok")                          — command is allowed
        (False, "Blocked by safety policy…")  — command is blocked

    Side effect: always appends a JSONL entry to AUDIT_LOG.
    """
    command_stripped = command.strip()

    for pattern, tag in BLOCKLIST:
        if re.search(pattern, command_stripped, re.IGNORECASE):
            _log(command_stripped, allowed=False, blocked_by=tag, pattern=pattern)
            return (False, _blocked_reason(tag))

    _log(command_stripped, allowed=True, blocked_by=None, pattern=None)
    return True, "ok"


def _blocked_reason(tag: str) -> str:
    if tag == "aidb-loopback-raw-curl":
        return (
            "Command blocked by agent safety policy (rule: aidb-loopback-raw-curl). "
            "Use harness wrappers first: MCP `query_aidb`, `get_working_memory`, "
            "`aq-memory search`, or documented AIDB endpoints such as "
            "`GET /documents?search=...` instead of raw curl probing."
        )
    return (
        f"Command blocked by agent safety policy (rule: {tag}). "
        f"If this action is required, perform it manually outside the agent."
    )


def _log(
    command: str,
    allowed: bool,
    blocked_by: str | None,
    pattern: str | None,
) -> None:
    """Append a structured audit entry to AUDIT_LOG (best-effort, never raises)."""
    entry = {
        "ts": time.time(),
        "command": command[:512],
        "allowed": allowed,
        "blocked_by": blocked_by,
        "pattern": pattern,
    }
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Quick self-test (run directly: python3 safe_command_executor.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _cases = [
        ("ls -la /tmp", True),
        ("git status", True),
        ("rm -rf /tmp/test-dir", False),
        ("sudo rm /etc/nixos/configuration.nix", False),
        ("git push origin main --force", False),
        ("git reset --hard HEAD~1", False),
        ("chmod 777 /tmp/foo", False),
        ("dd if=/dev/zero of=/dev/sda", False),
        ("iptables -F", False),
        ("nixos-rebuild switch", False),
        ("home-manager switch", False),
        ("curl -s 'http://localhost:8002/search?query=test'", False),
        ("curl -s http://127.0.0.1:8002/openapi.json", False),
    ]

    all_ok = True
    for cmd, expected_allowed in _cases:
        allowed, reason = check_command(cmd)
        status = "OK" if allowed == expected_allowed else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"[{status}] allowed={allowed} | {cmd[:60]}")
        if not allowed:
            print(f"       reason: {reason}")

    print()
    print("Self-test:", "PASSED" if all_ok else "FAILED")
