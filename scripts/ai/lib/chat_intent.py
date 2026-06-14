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
# Phrases that are clearly conversational (no tool needed).
# These are additional signals beyond the "tool free" directives above.
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
    "explain ",
    "what does",
    "what is",
    "what are",
    "how does",
    "why does",
    "can you explain",
    "describe ",
    "summarize ",
    "what would you",
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

    # Explicit tool-free directives — highest confidence
    for phrase in TOOL_FREE_PHRASES:
        if phrase in lower:
            return TurnClassification("conversational", 0.95, phrase)

    # Spec-style phrases (conversational unless user also mentions "tool")
    if "tool" not in lower:
        for phrase in TOOL_FREE_SPEC_PHRASES:
            if phrase in lower:
                return TurnClassification("conversational", 0.85, phrase)

    # Conservative default: agentic
    return TurnClassification("agentic", 1.0, None)


def is_conversational(text: str) -> bool:
    """Return True if the turn is classified as conversational (tools not needed).

    Convenience wrapper around classify_chat_intent().
    """
    return classify_chat_intent(text).mode == "conversational"
