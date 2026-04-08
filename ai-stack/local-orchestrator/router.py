#!/usr/bin/env python3
"""
Task Router for Local Orchestrator

Analyzes incoming prompts and routes to appropriate agent backend.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AgentBackend(Enum):
    """Available agent backends."""
    LOCAL = "local"  # Gemma 4 via llama-cpp
    QWEN = "qwen"  # Qwen/Codex for implementation
    CLAUDE_SONNET = "claude-sonnet"  # Claude Sonnet for complex tasks
    CLAUDE_OPUS = "claude-opus"  # Claude Opus for architecture/security


class TaskCategory(Enum):
    """High-level task categories."""
    QUERY = "query"  # Simple information lookup
    IMPLEMENTATION = "implementation"  # Code writing
    REFACTORING = "refactoring"  # Code restructuring
    DOCUMENTATION = "documentation"  # Docs/comments
    TESTING = "testing"  # Test creation
    ANALYSIS = "analysis"  # Code review/analysis
    PLANNING = "planning"  # Architecture/planning
    SECURITY = "security"  # Security audit
    CONFIGURATION = "configuration"  # Config/Nix changes


@dataclass
class RouteDecision:
    """Routing decision for a task."""
    backend: AgentBackend
    category: TaskCategory
    confidence: float
    reasoning: str
    estimated_complexity: str  # "trivial", "simple", "moderate", "complex"
    estimated_tokens: int
    estimated_cost_usd: float
    context_needed: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)


class TaskRouter:
    """
    Routes tasks to appropriate agent backends based on analysis.

    Uses heuristics and context to determine optimal routing.
    """

    # Keywords that suggest different task types
    IMPLEMENTATION_KEYWORDS = [
        "implement", "create", "add", "build", "write code", "code this",
        "make a function", "add feature", "new feature", "add method",
    ]

    REFACTORING_KEYWORDS = [
        "refactor", "restructure", "reorganize", "clean up", "simplify",
        "extract", "rename", "move", "split", "merge",
    ]

    DOCUMENTATION_KEYWORDS = [
        "document", "add comments", "write docs", "explain", "describe",
        "readme", "docstring", "jsdoc", "typedoc",
    ]

    TESTING_KEYWORDS = [
        "test", "add tests", "write tests", "unit test", "integration test",
        "test coverage", "spec", "mock",
    ]

    ANALYSIS_KEYWORDS = [
        "review", "analyze", "audit", "check", "find bugs", "look at",
        "what does", "how does", "why does", "explain code",
    ]

    PLANNING_KEYWORDS = [
        "plan", "design", "architect", "strategy", "approach", "how should",
        "what's the best way", "roadmap", "phase",
    ]

    SECURITY_KEYWORDS = [
        "security", "vulnerability", "cve", "exploit", "injection", "xss",
        "csrf", "authentication", "authorization", "secrets", "credentials",
    ]

    CONFIG_KEYWORDS = [
        "configure", "config", "nix", "module", "option", "setting",
        "environment", "deploy", "systemd", "service",
    ]

    QUERY_PATTERNS = [
        r"^what (is|are|does)",
        r"^how (do|does|to|can)",
        r"^where (is|are|can)",
        r"^when (should|do|does)",
        r"^why (is|are|does|do)",
        r"^can (you|i|we)",
        r"^show me",
        r"^list",
        r"^find",
        r"^search",
    ]

    def __init__(
        self,
        default_complexity_threshold: int = 100,  # LOC for "complex"
        cost_budget_usd: float = 5.0,
    ):
        """
        Initialize router.

        Args:
            default_complexity_threshold: LOC above which task is "complex"
            cost_budget_usd: Session cost budget
        """
        self.complexity_threshold = default_complexity_threshold
        self.cost_budget = cost_budget_usd
        self.cost_spent = 0.0
        self._routing_history: List[RouteDecision] = []

    def analyze_prompt(self, prompt: str) -> Tuple[TaskCategory, float]:
        """
        Analyze prompt to determine task category.

        Args:
            prompt: User prompt

        Returns:
            Tuple of (category, confidence)
        """
        prompt_lower = prompt.lower()

        # Check for query patterns first (highest priority for local handling)
        for pattern in self.QUERY_PATTERNS:
            if re.search(pattern, prompt_lower):
                return TaskCategory.QUERY, 0.9

        # Check keyword matches
        scores = {
            TaskCategory.IMPLEMENTATION: self._score_keywords(
                prompt_lower, self.IMPLEMENTATION_KEYWORDS
            ),
            TaskCategory.REFACTORING: self._score_keywords(
                prompt_lower, self.REFACTORING_KEYWORDS
            ),
            TaskCategory.DOCUMENTATION: self._score_keywords(
                prompt_lower, self.DOCUMENTATION_KEYWORDS
            ),
            TaskCategory.TESTING: self._score_keywords(
                prompt_lower, self.TESTING_KEYWORDS
            ),
            TaskCategory.ANALYSIS: self._score_keywords(
                prompt_lower, self.ANALYSIS_KEYWORDS
            ),
            TaskCategory.PLANNING: self._score_keywords(
                prompt_lower, self.PLANNING_KEYWORDS
            ),
            TaskCategory.SECURITY: self._score_keywords(
                prompt_lower, self.SECURITY_KEYWORDS
            ),
            TaskCategory.CONFIGURATION: self._score_keywords(
                prompt_lower, self.CONFIG_KEYWORDS
            ),
        }

        # Get highest scoring category
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        # If no clear signal, default to query
        if best_score < 0.3:
            return TaskCategory.QUERY, 0.5

        return best_category, min(best_score, 1.0)

    def _score_keywords(self, text: str, keywords: List[str]) -> float:
        """Score text against keyword list."""
        matches = sum(1 for kw in keywords if kw in text)
        return min(matches / max(len(keywords) * 0.2, 1), 1.0)

    def estimate_complexity(
        self,
        prompt: str,
        category: TaskCategory,
        file_count: int = 0,
    ) -> Tuple[str, int]:
        """
        Estimate task complexity.

        Args:
            prompt: User prompt
            category: Task category
            file_count: Number of files mentioned/involved

        Returns:
            Tuple of (complexity_level, estimated_tokens)
        """
        prompt_len = len(prompt)

        # Base token estimate from prompt length
        base_tokens = max(500, prompt_len * 2)

        # Adjust by category
        category_multipliers = {
            TaskCategory.QUERY: 0.5,
            TaskCategory.DOCUMENTATION: 1.0,
            TaskCategory.TESTING: 1.5,
            TaskCategory.REFACTORING: 1.5,
            TaskCategory.IMPLEMENTATION: 2.0,
            TaskCategory.PLANNING: 1.5,
            TaskCategory.ANALYSIS: 1.2,
            TaskCategory.SECURITY: 2.0,
            TaskCategory.CONFIGURATION: 1.0,
        }

        estimated_tokens = int(base_tokens * category_multipliers.get(category, 1.0))

        # Adjust by file count
        if file_count > 0:
            estimated_tokens += file_count * 500

        # Determine complexity level
        if estimated_tokens < 1000:
            return "trivial", estimated_tokens
        elif estimated_tokens < 3000:
            return "simple", estimated_tokens
        elif estimated_tokens < 8000:
            return "moderate", estimated_tokens
        else:
            return "complex", estimated_tokens

    def select_backend(
        self,
        category: TaskCategory,
        complexity: str,
        estimated_cost: float,
    ) -> AgentBackend:
        """
        Select appropriate backend for task.

        Args:
            category: Task category
            complexity: Complexity level
            estimated_cost: Estimated cost

        Returns:
            Selected AgentBackend
        """
        # Security and architecture always go to Opus
        if category in (TaskCategory.SECURITY, TaskCategory.PLANNING):
            if complexity in ("moderate", "complex"):
                return AgentBackend.CLAUDE_OPUS

        # Simple queries and analysis stay local
        if category == TaskCategory.QUERY:
            return AgentBackend.LOCAL

        if category == TaskCategory.ANALYSIS and complexity in ("trivial", "simple"):
            return AgentBackend.LOCAL

        # Trivial tasks stay local
        if complexity == "trivial":
            return AgentBackend.LOCAL

        # Implementation tasks
        if category == TaskCategory.IMPLEMENTATION:
            if complexity in ("trivial", "simple"):
                return AgentBackend.QWEN
            elif complexity == "moderate":
                return AgentBackend.CLAUDE_SONNET
            else:
                return AgentBackend.CLAUDE_OPUS

        # Testing and documentation go to Qwen
        if category in (TaskCategory.TESTING, TaskCategory.DOCUMENTATION):
            return AgentBackend.QWEN

        # Refactoring
        if category == TaskCategory.REFACTORING:
            if complexity in ("trivial", "simple"):
                return AgentBackend.QWEN
            else:
                return AgentBackend.CLAUDE_SONNET

        # Configuration
        if category == TaskCategory.CONFIGURATION:
            if complexity in ("trivial", "simple"):
                return AgentBackend.LOCAL
            else:
                return AgentBackend.QWEN

        # Default to local for unknown
        return AgentBackend.LOCAL

    def estimate_cost(
        self,
        backend: AgentBackend,
        estimated_tokens: int,
    ) -> float:
        """
        Estimate cost for backend and tokens.

        Args:
            backend: Target backend
            estimated_tokens: Estimated token usage

        Returns:
            Estimated cost in USD
        """
        # Pricing estimates (input + output per MTok)
        pricing = {
            AgentBackend.LOCAL: 0.0,  # Free
            AgentBackend.QWEN: 0.002,  # ~$2/MTok total
            AgentBackend.CLAUDE_SONNET: 0.018,  # ~$18/MTok total
            AgentBackend.CLAUDE_OPUS: 0.090,  # ~$90/MTok total
        }

        return estimated_tokens / 1_000_000 * pricing.get(backend, 0.0)

    def route(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RouteDecision:
        """
        Route a prompt to the appropriate backend.

        Args:
            prompt: User prompt
            context: Optional context (files, hints, etc.)

        Returns:
            RouteDecision with routing details
        """
        context = context or {}

        # Analyze prompt
        category, confidence = self.analyze_prompt(prompt)

        # Estimate complexity
        file_count = len(context.get("files", []))
        complexity, estimated_tokens = self.estimate_complexity(
            prompt, category, file_count
        )

        # Select backend
        backend = self.select_backend(category, complexity, 0.0)

        # Estimate cost
        estimated_cost = self.estimate_cost(backend, estimated_tokens)

        # Check budget
        if self.cost_spent + estimated_cost > self.cost_budget:
            # Downgrade to cheaper option
            if backend == AgentBackend.CLAUDE_OPUS:
                backend = AgentBackend.CLAUDE_SONNET
                estimated_cost = self.estimate_cost(backend, estimated_tokens)
            elif backend == AgentBackend.CLAUDE_SONNET:
                backend = AgentBackend.QWEN
                estimated_cost = self.estimate_cost(backend, estimated_tokens)

        # Build context needs
        context_needed = []
        if category in (TaskCategory.IMPLEMENTATION, TaskCategory.REFACTORING):
            context_needed.append("relevant_files")
            context_needed.append("hints")
        if category == TaskCategory.SECURITY:
            context_needed.append("security_patterns")
        if category == TaskCategory.CONFIGURATION:
            context_needed.append("nix_modules")

        # Build reasoning
        reasoning = (
            f"Task categorized as {category.value} with {confidence:.0%} confidence. "
            f"Complexity: {complexity} (~{estimated_tokens} tokens). "
            f"Selected {backend.value} backend (est. ${estimated_cost:.4f})."
        )

        decision = RouteDecision(
            backend=backend,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            estimated_complexity=complexity,
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost,
            context_needed=context_needed,
            constraints={
                "max_files": 10 if complexity in ("trivial", "simple") else 20,
                "require_tests": category == TaskCategory.IMPLEMENTATION,
                "safety_level": "high" if category == TaskCategory.SECURITY else "medium",
            },
        )

        self._routing_history.append(decision)
        return decision

    def record_cost(self, amount: float) -> None:
        """Record actual cost spent."""
        self.cost_spent += amount

    def get_routing_history(self) -> List[RouteDecision]:
        """Get routing history."""
        return list(self._routing_history)

    def get_budget_status(self) -> Dict[str, float]:
        """Get budget status."""
        return {
            "budget": self.cost_budget,
            "spent": self.cost_spent,
            "remaining": self.cost_budget - self.cost_spent,
        }


# Example usage
if __name__ == "__main__":
    router = TaskRouter()

    test_prompts = [
        "What does the hybrid_search function do?",
        "Add a new endpoint for user authentication",
        "Refactor the MCP client to use async/await",
        "Write unit tests for the router module",
        "Review this code for security vulnerabilities",
        "Plan the implementation of a caching layer",
    ]

    for prompt in test_prompts:
        decision = router.route(prompt)
        print(f"\nPrompt: {prompt}")
        print(f"  Category: {decision.category.value}")
        print(f"  Backend: {decision.backend.value}")
        print(f"  Complexity: {decision.estimated_complexity}")
        print(f"  Est. Cost: ${decision.estimated_cost_usd:.4f}")
