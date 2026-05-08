"""
Blast-radius classifier for Phase 28 guarded execution.

Classifies action strings into risk tiers without ML:
  critical — irreversible at scale (data loss, production state change)
  high     — hard-to-reverse or externally visible operations
  medium   — local state changes, API mutations, file writes
  low      — read-only, diagnostic, validation operations
"""

from __future__ import annotations

import re
from typing import Sequence

# ---------------------------------------------------------------------------
# Pattern tables  (checked in order — first match wins per tier)
# ---------------------------------------------------------------------------

_CRITICAL_PATTERNS: list[str] = [
    r"rm\s+-[^\s]*r[^\s]*\s+-[^\s]*f",   # rm -rf (flags in any order)
    r"rm\s+-rf",
    r"rm\s+-fr",
    r"--force\b",
    r"force.push",
    r"git\s+push.*--force",
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\bTRUNCATE\b(?!\s+log)",           # truncate (not log truncation)
    r"\bdrop\s+database\b",
    r"nixos-rebuild\s+switch",           # production rebuild
    r"nixos-rebuild\s+boot",
    r"\bdd\s+if=",                       # disk dump
    r"mkfs\.",                           # format filesystem
    r"wipefs\b",
    r"shred\b",
    r":(){:\|:&};:",                     # fork bomb
    r"\beval\s+.*\$\(",                  # eval with command substitution
]

_HIGH_PATTERNS: list[str] = [
    r"git\s+push\b",
    r"git\s+reset\s+--hard",
    r"git\s+reset\s+--mixed",
    r"git\s+branch\s+-[dD]\b",
    r"git\s+clean\s+-[fdxX]",
    r"git\s+rebase\b",
    r"\bDELETE\s+FROM\b",
    r"\bDELETE\s+/api",
    r"DELETE\s+https?://",
    r"nixos-rebuild\b",                  # any rebuild not caught by critical
    r"systemctl\s+(stop|restart|disable|mask)\b",
    r"kill\s+-9\b",
    r"kill\s+-SIGKILL\b",
    r"pkill\b",
    r"service\s+\w+\s+(stop|restart)\b",
    r"\bchmod\s+[0-7]{3,4}\b",          # permission change (numeric)
    r"\bchown\b",
    r"sudo\s+rm\b",
    r"sudo\s+dd\b",
    r"\bdropdb\b",                       # postgres drop
    r"qdrant.*delete.*collection",
    r"redis-cli\s+flushall\b",
    r"redis-cli\s+flushdb\b",
]

_MEDIUM_PATTERNS: list[str] = [
    r"git\s+commit\b",
    r"git\s+merge\b",
    r"git\s+tag\b",
    r"git\s+add\b",
    r"\bPOST\s+/",
    r"\bPUT\s+/",
    r"\bPATCH\s+/",
    r"open\s*\([^,]+,\s*['\"]w",        # open(..., 'w')
    r"open\s*\([^,]+,\s*['\"]a",        # open(..., 'a')
    r"write_file\b",
    r"shutil\.copy\b",
    r"shutil\.move\b",
    r"os\.rename\b",
    r"os\.replace\b",
    r"pathlib.*\.write_text\b",
    r"pathlib.*\.write_bytes\b",
    r"\bmkdir\b",
    r"\btouch\b(?!\s+--help)",
    r"\bsed\s+-i\b",
    r"\bawk\b.*\bprint\b",
    r"\bcurl\b.*-[XOPD].*POST",
    r"\bcurl\b.*--data\b",
    r"psql\b.*-[cC].*INSERT",
    r"psql\b.*-[cC].*UPDATE",
    r"\bINSERT\s+INTO\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"pip\s+install\b",
    r"npm\s+install\b",
    r"nix-env\s+-i\b",
]

_LOW_PATTERNS: list[str] = [
    r"\bGET\s+/",
    r"\bcurl\b(?!.*--data|.*-[XOPD].*POST)",
    r"\bcat\b",
    r"\bls\b",
    r"\bgrep\b",
    r"\bfind\b",
    r"\bdiff\b",
    r"\bgit\s+(status|log|diff|show|describe|fetch|clone)\b",
    r"\bpython3?\s+-m\s+py_compile\b",
    r"\bpython3?\s+-c\b",
    r"aq-qa\b",
    r"aq-hints\b",
    r"aq-report\b",
    r"aq-prime\b",
    r"\bbash\s+-n\b",
    r"\bhead\b",
    r"\btail\b",
    r"\bwc\b",
    r"\becho\b",
    r"\bprintf\b",
    r"\bread\b",
    r"less\b",
    r"more\b",
]

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    "critical": [re.compile(p, re.IGNORECASE) for p in _CRITICAL_PATTERNS],
    "high":     [re.compile(p, re.IGNORECASE) for p in _HIGH_PATTERNS],
    "medium":   [re.compile(p, re.IGNORECASE) for p in _MEDIUM_PATTERNS],
    "low":      [re.compile(p, re.IGNORECASE) for p in _LOW_PATTERNS],
}


def classify(action: str) -> str:
    """Return the blast-radius tier for a single action string.

    Returns: 'critical' | 'high' | 'medium' | 'low'
    Defaults to 'medium' when no pattern matches (unknown = non-trivial).
    """
    if not action or not isinstance(action, str):
        return "low"
    for tier in ("critical", "high", "medium", "low"):
        for pat in _COMPILED[tier]:
            if pat.search(action):
                return tier
    return "medium"  # unknown actions are non-trivially risky


def batch_classify(actions: Sequence[str]) -> dict[str, str]:
    """Classify a list of action strings, returning {action: tier}."""
    return {a: classify(a) for a in actions}


def max_tier(actions: Sequence[str]) -> str:
    """Return the highest tier across all given actions."""
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tiers = [classify(a) for a in actions]
    if not tiers:
        return "low"
    return min(tiers, key=lambda t: order.get(t, 2))
