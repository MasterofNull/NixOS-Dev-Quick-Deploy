"""
chat_intent.py — Shared chat turn classifier for aq-chat and ai_coordinator_handlers.

Pure Python. No service imports. No HTTP calls. Importable by both the CLI and the
coordinator service without side effects.

Conservative classifier default: "agentic".
  False conversational → tools stripped → model can't call tools → hallucination.
  False agentic → coordinator overhead (~50s). Asymmetric failure cost → default agentic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional


class ToolMode(Enum):
    """Three-state tool availability flag for a chat session."""
    ENABLED = "enabled"
    DISABLED_SESSION = "disabled_session"   # /notoolsession or --no-tools flag
    DISABLED_TURN = "disabled_turn"          # this turn only, from user phrase


@dataclass
class TurnClassification:
    """Result of classify_chat_intent()."""
    mode: Literal["conversational", "agentic"]
    confidence: float
    matched_phrase: Optional[str]


# ---------------------------------------------------------------------------
# Phrase sets — migrated verbatim from scripts/ai/aq-chat lines 60-74.
# These are the single source of truth; aq-chat imports from here.
# ---------------------------------------------------------------------------

TOOL_FREE_PHRASES: frozenset[str] = frozenset({
    "do not call tools",
    "don't call tools",
    "no tools",
    "without tools",
    "tool-free",
    "tool free",
})

TOOL_FREE_SPEC_PHRASES: frozenset[str] = frozenset({
    "acceptance criteria",
    "tests only",
    "spec only",
    "code-ready spec",
    "produce a spec",
})

# ---------------------------------------------------------------------------
# Full-phrase conversational patterns — safe to substring-match because they
# are specific enough to not fire on agentic queries.
# Removed from prior version: "explain ", "what does", "what is", "what are",
# "how does", "why does", "can you explain", "describe ", "summarize " — these
# are too broad and fired on system-context queries like "what are the open
# issues?", sending them to fast-path without tools.
# ---------------------------------------------------------------------------

_CONVERSATIONAL_INTENTS: frozenset[str] = frozenset({
    "what time is it",
    "what's the date",
    "what is the date",
    "tell me a joke",
    "how are you",
    "hello",
    "hi there",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
    "cheers",
})

# Short affirmatives — standalone continuation replies. Only match when the ENTIRE
# utterance is ≤ 3 words so "ok, implement the endpoint" (4+ words) falls through
# to the agentic default instead of being fast-pathed without tools.
_CONVERSATIONAL_AFFIRMATIVES: frozenset[str] = frozenset({
    "yes",
    "yeah",
    "sure",
    "ok",
    "okay",
    "sounds good",
    "go ahead",
    "let's go",
    "proceed",
    "perfect",
    "great",
})

# System-context keywords: queries about live system state always require tool calls.
# Pre-empts any conversational phrase match to ensure correct routing to coordinator.
_SYSTEM_CONTEXT_KEYWORDS: frozenset[str] = frozenset({
    "current state",
    "current status",
    "recent commit",
    "recent change",
    "recent error",
    "open issue",
    "last commit",
    "last run",
    "how many",
    "is it running",
    "is the service",
    "are there any",
    "list the",
    "show me the",
    "find the",
    "check the",
    "what port",
    "what version",
    "which file",
    "does it exist",
    "does the file",
    "what's happening",
    "what is happening",
})

# Phrases that force agentic even when a conversational phrase matched earlier
# in the same message. "how are you? what would you like to start working on?"
# contains "how are you" (conversational) but also "start working on" (agentic
# override) — the agent needs discover_objectives, not a fast-path response.
_AGENTIC_OVERRIDE_PHRASES: frozenset[str] = frozenset({
    "start working on",
    "what to work on",
    "what should we work",
    "what would you like to start",
    "what would you like to work",
    "what to do next",
    "where should we start",
    "what are we working on",
})


def classify_chat_intent(text: str) -> TurnClassification:
    """Classify a chat turn as 'conversational' or 'agentic'.

    Conservative: defaults to 'agentic'. Only returns 'conversational' when an
    explicit tool-free phrase is matched. This prevents tools from being stripped
    when the model needs them, which causes hallucination.

    Args:
        text: The user's raw chat input.

    Returns:
        TurnClassification with mode, confidence, and matched_phrase.
    """
    lower = " ".join(text.lower().split())
    word_count = len(lower.split())

    # Explicit tool-free directives — highest confidence
    for phrase in TOOL_FREE_PHRASES:
        if phrase in lower:
            return TurnClassification("conversational", 0.95, phrase)

    # Spec-style phrases (conversational unless user also mentions "tool")
    if "tool" not in lower:
        for phrase in TOOL_FREE_SPEC_PHRASES:
            if phrase in lower:
                return TurnClassification("conversational", 0.85, phrase)

    # System-context gate: queries about live system state always need tools.
    # Takes precedence over any matching conversational phrase below.
    for kw in _SYSTEM_CONTEXT_KEYWORDS:
        if kw in lower:
            return TurnClassification("agentic", 0.95, None)

    # Greeting / purely conversational full-phrase matches
    for phrase in _CONVERSATIONAL_INTENTS:
        if phrase in lower:
            # Agentic override: some prompts mix a greeting with a task directive
            # (e.g. "how are you? what would you like to start working on?").
            # If an agentic-override phrase is present, the agent needs tools —
            # route agentic even though a conversational phrase also matched.
            for override in _AGENTIC_OVERRIDE_PHRASES:
                if override in lower:
                    return TurnClassification("agentic", 0.90, None)
            return TurnClassification("conversational", 0.80, phrase)

    # Short affirmatives — only when the ENTIRE utterance is ≤ 3 words.
    # "ok" (1 word) → conversational. "ok, implement the endpoint" (4 words) → agentic.
    if word_count <= 3:
        for phrase in _CONVERSATIONAL_AFFIRMATIVES:
            if phrase in lower:
                for override in _AGENTIC_OVERRIDE_PHRASES:
                    if override in lower:
                        return TurnClassification("agentic", 0.90, None)
                return TurnClassification("conversational", 0.80, phrase)

    # Conservative default: agentic
    return TurnClassification("agentic", 1.0, None)


def is_conversational(text: str) -> bool:
    """Return True if the turn is classified as conversational (tools not needed).

    Convenience wrapper around classify_chat_intent().
    """
    return classify_chat_intent(text).mode == "conversational"
