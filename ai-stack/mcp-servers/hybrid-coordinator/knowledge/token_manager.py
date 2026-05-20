"""
knowledge/token_manager.py — Context-aware token budget management.

Extracted from hints_engine.py (Phase R3 decomposition).
Zero dependencies on other knowledge modules.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_COMMAND_RE = re.compile(r"`[^`]+`|scripts/[a-zA-Z0-9._/-]+|/[a-zA-Z0-9._/-]+")


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count for LLM context (Phase 10.3).

    Uses ~4 chars/token heuristic typical for code-mixed content.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _compress_snippet(snippet: str, max_chars: int = 200) -> str:
    """
    Compress long snippets for token efficiency (Phase 10.3).

    Truncates and adds ellipsis for long snippets.
    """
    if not snippet or len(snippet) <= max_chars:
        return snippet
    truncated = snippet[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


def _tokenize(text: str) -> list:
    """Lowercase and split on whitespace / punctuation."""
    return _TOKEN_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# Context-Aware Token Budgeting (Phase 10.3 Extension)
# ---------------------------------------------------------------------------


class TokenBudgetContext:
    """
    Context-aware token budget calculator.

    Adjusts token limits based on:
    - Task phase: new_phase > continued_work > sub_task
    - Compaction state: post_compaction gets restored budget
    - Query complexity: complex queries get more tokens

    Usage:
        budget = TokenBudgetContext()
        tokens = budget.calculate(
            task_phase="new_phase",
            query_complexity="complex",
            post_compaction=False
        )
    """

    # Base budgets by task phase
    PHASE_BUDGETS = {
        "new_phase": 600,       # Starting new work - need full context
        "continued_work": 350,  # Already have context from previous turns
        "sub_task": 200,        # Delegated sub-task - parent has context
        "refinement": 150,      # Minor refinement - minimal context needed
    }

    # Multipliers for query complexity
    COMPLEXITY_MULTIPLIERS = {
        "simple": 0.6,          # Simple lookup/factual
        "medium": 1.0,          # Standard task
        "complex": 1.5,         # Multi-step reasoning
        "architecture": 2.0,    # Design/architecture decisions
    }

    # Post-compaction restoration factor
    COMPACTION_RESTORE_FACTOR = 1.8  # Restore ~80% more tokens after compaction

    # Escalation: when models request expanded context, suspend limits
    ESCALATION_MULTIPLIER = 4.0  # 4x budget when escalation detected
    ESCALATION_SIGNALS = [
        # Explicit expansion requests
        "deep dive", "more context", "expand", "more detail", "elaborate",
        "full context", "complete picture", "comprehensive", "thorough",
        # Information seeking patterns
        "need to understand", "help me understand", "explain fully",
        "all relevant", "everything about", "show me all",
        # Architecture/analysis triggers
        "analyze in depth", "full analysis", "detailed breakdown",
        "explore thoroughly", "investigate", "dig deeper",
        # Re-request patterns (model didn't get enough)
        "still need", "not enough", "missing context", "can you provide more",
        "i need more", "give me more", "tell me more",
    ]

    def __init__(self):
        self._session_turn_count = 0
        self._last_compaction_turn = 0

    def detect_escalation(self, query: str) -> bool:
        """
        Detect if the query contains escalation signals.

        When models request expanded context ("deep dive", "more context", etc.),
        we should suspend/increase token limits to let them consume needed info.
        Token limits are safeguards, not hard restrictions.
        """
        query_lower = query.lower()
        return any(signal in query_lower for signal in self.ESCALATION_SIGNALS)

    def calculate(
        self,
        task_phase: str = "continued_work",
        query_complexity: str = "medium",
        post_compaction: bool = False,
        turn_count: int = 0,
        escalation_requested: bool = False,
    ) -> int:
        """
        Calculate context-aware token budget.

        Args:
            task_phase: new_phase | continued_work | sub_task | refinement
            query_complexity: simple | medium | complex | architecture
            post_compaction: True if context was recently compacted
            turn_count: Current conversation turn (0 = auto-detect)
            escalation_requested: True if model requested expanded context

        Returns:
            Recommended token budget for hints
        """
        base = self.PHASE_BUDGETS.get(task_phase, self.PHASE_BUDGETS["continued_work"])
        multiplier = self.COMPLEXITY_MULTIPLIERS.get(query_complexity, 1.0)

        budget = int(base * multiplier)

        if escalation_requested:
            budget = int(budget * self.ESCALATION_MULTIPLIER)
            return min(budget, 4000)

        if post_compaction:
            budget = int(budget * self.COMPACTION_RESTORE_FACTOR)

        effective_turn = turn_count if turn_count > 0 else self._session_turn_count
        if effective_turn <= 2:
            budget = int(budget * 1.2)

        return min(budget, 1200)

    def detect_phase(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Auto-detect task phase from query and context."""
        query_lower = query.lower()

        new_phase_signals = [
            "implement", "create", "build", "add feature", "new",
            "design", "architect", "plan", "start", "begin"
        ]
        if any(s in query_lower for s in new_phase_signals):
            return "new_phase"

        subtask_signals = [
            "fix", "update", "modify", "change", "adjust",
            "then", "next", "also", "and then"
        ]
        if any(s in query_lower for s in subtask_signals):
            return "sub_task"

        refinement_signals = [
            "tweak", "polish", "cleanup", "format", "rename",
            "typo", "minor", "small"
        ]
        if any(s in query_lower for s in refinement_signals):
            return "refinement"

        return "continued_work"

    def detect_complexity(self, query: str) -> str:
        """Auto-detect query complexity."""
        query_lower = query.lower()
        word_count = len(query.split())

        arch_signals = [
            "architect", "design", "system", "infrastructure",
            "security", "scalab", "performance", "tradeoff"
        ]
        if any(s in query_lower for s in arch_signals):
            return "architecture"

        complex_signals = [
            "implement", "integrate", "migrate", "refactor",
            "debug", "troubleshoot", "multi-step", "complex"
        ]
        if any(s in query_lower for s in complex_signals) or word_count > 30:
            return "complex"

        simple_signals = [
            "what is", "how do", "where", "list", "show",
            "find", "get", "check"
        ]
        if any(s in query_lower for s in simple_signals) and word_count < 15:
            return "simple"

        return "medium"

    def increment_turn(self) -> None:
        """Increment session turn counter."""
        self._session_turn_count += 1

    def mark_compaction(self) -> None:
        """Mark that compaction occurred at current turn."""
        self._last_compaction_turn = self._session_turn_count

    def is_post_compaction(self, lookback_turns: int = 2) -> bool:
        """Check if we're in post-compaction recovery window."""
        return (self._session_turn_count - self._last_compaction_turn) <= lookback_turns


# Singleton for session-scoped budget tracking
_token_budget_context: Optional[TokenBudgetContext] = None


def get_token_budget_context() -> TokenBudgetContext:
    """Get or create singleton TokenBudgetContext."""
    global _token_budget_context
    if _token_budget_context is None:
        _token_budget_context = TokenBudgetContext()
    return _token_budget_context


def calculate_context_aware_budget(
    query: str,
    task_phase: Optional[str] = None,
    query_complexity: Optional[str] = None,
    post_compaction: bool = False,
    force_escalation: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function for context-aware token budget calculation.

    Args:
        query: The user/model query
        task_phase: Override phase detection
        query_complexity: Override complexity detection
        post_compaction: Force post-compaction mode
        force_escalation: Force escalation mode (bypass detection)

    Returns dict with budget and metadata for transparency.
    """
    ctx = get_token_budget_context()

    detected_phase = task_phase or ctx.detect_phase(query)
    detected_complexity = query_complexity or ctx.detect_complexity(query)
    is_post_compact = post_compaction or ctx.is_post_compaction()
    is_escalated = force_escalation or ctx.detect_escalation(query)

    budget = ctx.calculate(
        task_phase=detected_phase,
        query_complexity=detected_complexity,
        post_compaction=is_post_compact,
        escalation_requested=is_escalated,
    )

    return {
        "recommended_tokens": budget,
        "task_phase": detected_phase,
        "query_complexity": detected_complexity,
        "post_compaction": is_post_compact,
        "escalation_active": is_escalated,
        "limits_suspended": is_escalated,
        "rationale": _budget_rationale(
            detected_phase, detected_complexity, is_post_compact, is_escalated
        ),
    }


def _budget_rationale(
    phase: str, complexity: str, post_compact: bool, escalated: bool = False
) -> str:
    """Generate human-readable rationale for budget decision."""
    parts = []

    if escalated:
        parts.append("ESCALATION: model requested expanded context - limits suspended")

    if phase == "new_phase":
        parts.append("new work needs full context")
    elif phase == "sub_task":
        parts.append("sub-task inherits parent context")
    elif phase == "refinement":
        parts.append("minor refinement needs minimal context")

    if complexity == "architecture":
        parts.append("architecture requires comprehensive context")
    elif complexity == "complex":
        parts.append("complex task needs broader context")
    elif complexity == "simple":
        parts.append("simple query needs focused context")

    if post_compact:
        parts.append("post-compaction recovery boost applied")

    return "; ".join(parts) if parts else "standard context allocation"
