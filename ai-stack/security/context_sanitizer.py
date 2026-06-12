"""
ai-stack/security/context_sanitizer.py

MIC-G Phase 164: Context Sanitization Guard (P7 + P8 from threat catalogue)

P7 — Context Window Poisoning: malicious RAG-retrieved content or tool results
     containing adversarial instructions injected into agent context.
P8 — Prompt Injection via Tool Results: tool output containing [INST]/Human:/
     Assistant: directives that redirect agent mid-task.

Design doc: .agents/designs/MODEL-INTEGRITY-CAPABILITY-GUARD.md §3.4

Usage:
    from ai_stack.security.context_sanitizer import sanitize_tool_result, sanitize_rag_doc

    clean, flags = sanitize_tool_result(raw_output, source="shell")
    if flags:
        logger.warning("Injection pattern detected in tool result: %s", flags)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Injection pattern catalogue
# ---------------------------------------------------------------------------

# High-confidence injection attempts — always strip
_INJECTION_PATTERNS_HARD = [
    (re.compile(r'\[INST\]', re.IGNORECASE), "[INST] jailbreak wrapper"),
    (re.compile(r'<\|(?:system|im_start|im_end)\|>', re.IGNORECASE), "chat template injection"),
    (re.compile(r'(?:^|\n)\s*(?:Human|User|Assistant|AI)\s*:', re.MULTILINE), "role prefix injection"),
    (re.compile(r'IGNORE\s+(?:ALL\s+)?(?:PREVIOUS|PRIOR)\s+INSTRUCTIONS?', re.IGNORECASE), "classic ignore-previous"),
    (re.compile(r'SYSTEM\s+OVERRIDE', re.IGNORECASE), "system override"),
    (re.compile(r'NEW\s+INSTRUCTIONS?', re.IGNORECASE), "instruction replacement"),
    (re.compile(r'YOU\s+ARE\s+NOW\s+(?:A|AN)\s+', re.IGNORECASE), "persona replacement"),
    (re.compile(r'FORGET\s+(?:YOUR\s+)?(?:PREVIOUS|PRIOR|ALL)', re.IGNORECASE), "memory wipe"),
    (re.compile(r'DISREGARD\s+(?:YOUR\s+)?(?:PREVIOUS|PRIOR)', re.IGNORECASE), "disregard prior"),
    (re.compile(r'print\s*\(\s*["\'](?:password|secret|key|token)', re.IGNORECASE), "secret extraction probe"),
    (re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL), "embedded script"),
    (re.compile(r'<!--.*?-->', re.DOTALL), "HTML comment (possible payload)"),
]

# Medium-confidence: suspicious in tool results, should be logged but not stripped
_INJECTION_PATTERNS_SOFT = [
    (re.compile(r'(?:^|\n)\s*###\s*(?:SYSTEM|INSTRUCTION|COMMAND)\s*(?:PROMPT|MESSAGE)?', re.MULTILINE | re.IGNORECASE), "system/instruction header"),
    (re.compile(r'As\s+an\s+AI\s+assistant', re.IGNORECASE), "AI persona assertion"),
    (re.compile(r'your\s+(?:actual|true|real)\s+(?:goal|purpose|objective|instruction)', re.IGNORECASE), "goal override probe"),
    (re.compile(r'(?:reveal|show|output|print)\s+(?:your\s+)?system\s+prompt', re.IGNORECASE), "system prompt exfil"),
    (re.compile(r'(?:jailbreak|bypass|override|circumvent|ignore)\s+(?:safety|security|filter|policy|restriction)', re.IGNORECASE), "safety bypass"),
    (re.compile(r'DAN\s*(?:mode|prompt|\d)', re.IGNORECASE), "DAN jailbreak variant"),
]


@dataclass
class SanitizationResult:
    content: str
    flags: list[str] = field(default_factory=list)
    hard_violations: int = 0
    soft_violations: int = 0
    truncated: bool = False
    original_len: int = 0
    sanitized_len: int = 0
    source: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_clean(self) -> bool:
        return self.hard_violations == 0

    @property
    def is_suspicious(self) -> bool:
        return self.soft_violations > 0


# ---------------------------------------------------------------------------
# Core sanitization
# ---------------------------------------------------------------------------

_MAX_TOOL_RESULT_CHARS = 3000
_MAX_RAG_CONTENT_CHARS = 4000
_SUMMARY_PLACEHOLDER = "[CONTENT REDACTED: injection pattern detected. Raw length: {n} chars. Patterns: {p}]"
_TRUNCATION_NOTICE = "\n[...truncated at {n} chars to prevent context overflow]"


def sanitize_tool_result(
    content: str,
    source: str = "tool",
    max_chars: int = _MAX_TOOL_RESULT_CHARS,
    hard_block: bool = True,
) -> tuple[str, list[str]]:
    """
    Sanitize tool result content before injecting into LLM context.

    Args:
        content: Raw tool output string.
        source: Descriptive source label for logging.
        max_chars: Truncation limit (default 3000, matching Phase 159 tool result cap).
        hard_block: If True, replace hard-violation content with placeholder.
                   If False, log and pass through (useful for audit-only mode).

    Returns:
        (sanitized_content, list_of_violation_descriptions)
    """
    if not content:
        return content, []

    result = SanitizationResult(
        content=content,
        original_len=len(content),
        source=source,
    )

    # Check hard patterns
    for pattern, description in _INJECTION_PATTERNS_HARD:
        if pattern.search(content):
            result.hard_violations += 1
            result.flags.append(f"HARD:{description}")

    # Check soft patterns
    for pattern, description in _INJECTION_PATTERNS_SOFT:
        if pattern.search(content):
            result.soft_violations += 1
            result.flags.append(f"SOFT:{description}")

    if result.flags:
        logger.warning(
            "context_sanitizer: %s injection pattern(s) in tool result from '%s' "
            "(hard=%d soft=%d len=%d): %s",
            len(result.flags), source,
            result.hard_violations, result.soft_violations,
            result.original_len,
            result.flags[:3],  # log first 3 to avoid log flooding
        )

    # Hard violations: replace content entirely if hard_block is on
    if result.hard_violations > 0 and hard_block:
        sanitized = _SUMMARY_PLACEHOLDER.format(
            n=result.original_len,
            p=", ".join(result.flags[:3]),
        )
        return sanitized, result.flags

    # Soft violations: log only, keep content but truncate aggressively
    if result.soft_violations > 0:
        max_chars = min(max_chars, 1500)

    # Truncate
    if len(content) > max_chars:
        content = content[:max_chars] + _TRUNCATION_NOTICE.format(n=max_chars)
        result.truncated = True

    return content, result.flags


def sanitize_rag_doc(
    content: str,
    doc_id: Optional[str] = None,
    max_chars: int = _MAX_RAG_CONTENT_CHARS,
) -> tuple[str, list[str]]:
    """
    Sanitize a RAG-retrieved document before injecting into context.
    More lenient than tool results (legitimate docs can have instructional text),
    but hard patterns (role injection, persona replacement) are still blocked.
    """
    return sanitize_tool_result(
        content,
        source=f"rag:{doc_id or 'unknown'}",
        max_chars=max_chars,
        hard_block=True,
    )


def sanitize_external_content(
    content: str,
    source: str = "external",
    max_chars: int = _MAX_RAG_CONTENT_CHARS,
) -> tuple[str, list[str]]:
    """
    General-purpose sanitization for any externally-sourced content
    (web research results, API responses, etc.).
    """
    return sanitize_tool_result(
        content,
        source=source,
        max_chars=max_chars,
        hard_block=True,
    )


# ---------------------------------------------------------------------------
# Agent loop integration helper
# ---------------------------------------------------------------------------

def check_objective_drift(
    original_objective: str,
    current_response: str,
    source: str = "model_response",
) -> tuple[bool, float]:
    """
    Lightweight check for potential trust chain attack (P9):
    does the model's response after a tool call still align with the original task?

    Returns (drift_detected, similarity_score).
    Uses simple keyword overlap rather than embedding similarity for performance.
    """
    if not original_objective or not current_response:
        return False, 1.0

    obj_words = set(re.findall(r'\b\w{4,}\b', original_objective.lower()))
    resp_words = set(re.findall(r'\b\w{4,}\b', current_response.lower()[:500]))

    if not obj_words:
        return False, 1.0

    overlap = len(obj_words & resp_words) / len(obj_words)

    # Suspicious: response contains new task-like language not in objective
    redirect_signals = re.findall(
        r'(?:instead|actually|new task|different task|forget|ignore|now you|your new)',
        current_response[:500],
        re.IGNORECASE,
    )

    drift = overlap < 0.15 and len(redirect_signals) > 0
    return drift, round(overlap, 3)


# ---------------------------------------------------------------------------
# Batch sanitization for AIDB result sets
# ---------------------------------------------------------------------------

def sanitize_search_results(
    results: list[dict],
    content_fields: tuple[str, ...] = ("content", "text", "snippet", "body"),
) -> tuple[list[dict], int]:
    """
    Sanitize a list of AIDB/Qdrant search result dicts in place.
    Returns (sanitized_results, total_violations_found).
    """
    total_violations = 0
    for result in results:
        for field_name in content_fields:
            if field_name in result and isinstance(result[field_name], str):
                clean, flags = sanitize_rag_doc(result[field_name], doc_id=str(result.get("id", "?")))
                result[field_name] = clean
                total_violations += len([f for f in flags if f.startswith("HARD:")])
    return results, total_violations
