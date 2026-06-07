"""
knowledge/gap_analyzer.py — Gap detection and deduplication utilities.

Extracted from hints_engine.py (Phase R3 decomposition).
Zero dependencies on other knowledge modules.
"""
from __future__ import annotations

import re


_CURATED_STALE_GAP_PATTERNS = (
    "lib mkforce",
    "lib mkif",
    "flake inputs follows",
    "nixos module options",
    "nixos systemd service options",
    "configure nixos services",
    "how do i configure a nixos systemd service",
    "postgresql nixos module setup",
    "tc3 feedback validation",
    "tc3 final feedback loop validation",
    "how does the hybrid coordinator route queries",
    "what is nixos",
    "explain what nixos is",
    "nixos flake",
    "nixos flake build system",
    "create a workflow plan for diagnosing continue chat hangs",
    "verify switchboard response headers for profile routing",
    "reduce token overhead through progressive disclosure defaults",
    "progressive disclosure token discipline",
    "progressive-disclosure token discipline",
    "intent contract fields for workflow start",
    "workflow start intent contract",
    "show workflow run start intent contract requirements",
    "how to configure qdrant and hybrid routing in this repo",
    "qdrant hybrid routing configuration",
    "programs git settings credential helper conflicting definition values",
    "home manager git credential helper conflict",
    "systemd oneshot permission denied var lib",
    "tmpfiles z rules ownership reset",
    "nixos declarative runtime tool security policy pattern for hybrid coor",
    "verify semantic tool calling and tool security metadata",
    "continue agent mode still says message exceeds context limit",
    "message exceeds context limit return a compact diagnosis path",
    "continue editor rescue message exceeds context limit",
    # Session-continuity meta-queries — handled by RESUME.json, not RAG import
    "what open items remain from previous session",
    "what tasks remain from previous session",
    "open items from previous session",
    "continue from previous session",
    "continuation from last session",
    "next steps from last session",
    "what was left unfinished",
    "resume previous session",
    "current session status",
    "what is the current status of",
    "summarize current session",
    # Greetings / small-talk — not knowledge gaps (patterns must be normalized: no punctuation)
    "how are you today",
    "hello who are you",
    "hello what are your core capabilities",
    "what are your core capabilities",
    # Test probes — not knowledge gaps (short probes covered by _is_synthetic_gap exact-match)
    "test concurrency gate",
    "reply with the single word working",
    "reply with the single word",
    # Orchestration artifacts / aider feedback injections — not knowledge gaps
    "we are preparing a new project prd",
    "feedback on your last task",
    "feedback on the implementation",
    "unleash expert systems mode",
    "unleash the expert systems architecture",
    "you are implementation agent",
    # Capability introspection — not actionable knowledge gaps
    "list the available tools you can use",
    "what are your capabilities",
    "what tools do you have",
)


def _normalize_gap_text(query_text: str) -> str:
    """Normalize gap text for deduplication comparisons."""
    return re.sub(r"[^a-z0-9]+", " ", (query_text or "").strip().lower()).strip()


def _is_synthetic_gap(query_text: str) -> bool:
    """Return True if the query text looks like a synthetic/test gap that should be filtered."""
    text = (query_text or "").strip().lower()
    if not text:
        return True
    if text in {"test", "nix", "ping", "health", "hello!", "hello", "hi", "status", "ok", "etimedout"}:
        return True
    synthetic_prefixes = (
        "analysis only task ",
        "analysis only:",
        "analysis task ",
        "analyze docs/",
        "please analyze and summarize docs/",
        "analyze and summarize docs/",
        "read docs/",
        "read and summarize docs/",
        "summarize docs/",
        "summarize file ",
        "summarize the file ",
        "analyze file ",
        "nixos-rag-test-probe-unique-sentinel",
        "fetch http://127.0.0.1",
        "fetch https://127.0.0.1",
        "fetch http://localhost",
        "curl http://127.0.0.1",
        "curl http://localhost",
        "get http://127.0.0.1",
        "get http://localhost",
    )
    return text.startswith(synthetic_prefixes)


def _is_curated_stale_gap(query_text: str) -> bool:
    """Return True if the gap matches a known stale/resolved pattern that should be suppressed."""
    normalized = _normalize_gap_text(query_text)
    if not normalized:
        return True
    return any(pattern in normalized for pattern in _CURATED_STALE_GAP_PATTERNS)


def _longest_common_substring_len(a: str, b: str) -> int:
    """Return the length of the longest common substring of a and b."""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    best = 0
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
                if dp[j] > best:
                    best = dp[j]
            else:
                dp[j] = 0
            prev = temp
    return best
