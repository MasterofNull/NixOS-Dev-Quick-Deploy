#!/usr/bin/env python3
"""Decision Point Detector for Advisor Strategy.

Detects when an executor model should consult an advisor for guidance on
complex decisions, following the advisor strategy from:
https://claude.com/blog/the-advisor-strategy

The detector identifies five types of decision points:
- Architecture: Design patterns, system structure, API design
- Security: Authentication, authorization, input validation, vulnerabilities
- Ambiguity: Unclear requirements, multiple valid approaches
- Tradeoff: Comparing alternatives, pros/cons analysis
- Planning: Multi-step workflows, complex sequences, roadmaps

Unlike failure-based escalation, advisor consultation is proactive - the executor
asks for guidance before attempting complex decisions.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionPoint:
    """Represents a decision point requiring advisor consultation."""

    task_id: str
    decision_type: str  # architecture, security, ambiguity, tradeoff, planning
    question: str  # Question to ask advisor
    context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # Confidence that this needs advisor (0-1)
    detected_signals: List[str] = field(default_factory=list)
    executor_tier: str = ""  # Tier of executor that detected decision point


class DecisionPointDetector:
    """Detects when executor should consult advisor for guidance."""

    # Decision signal patterns (keyword-based detection)
    DECISION_SIGNALS = {
        "architecture": [
            "design pattern",
            "architecture decision",
            "system structure",
            "organization",
            "module design",
            "api design",
            "interface design",
            "data model",
            "schema design",
            "component structure",
            "service architecture",
            "microservice",
            "monolith",
        ],
        "security": [
            "security",
            "authentication",
            "authorization",
            "encryption",
            "vulnerability",
            "sanitize",
            "validate input",
            "xss",
            "sql injection",
            "csrf",
            "owasp",
            "secure",
            "threat model",
            "attack vector",
            "zero trust",
            "privilege",
        ],
        "ambiguity": [
            "unclear",
            "ambiguous",
            "multiple approaches",
            "not sure",
            "which way",
            "should i",
            "alternative",
            "best practice",
            "recommendation",
            "what's the right",
            "how should",
            "clarify",
            "uncertain",
        ],
        "tradeoff": [
            "tradeoff",
            "trade-off",
            "versus",
            " vs ",
            " vs.",
            "compare approaches",
            "pros and cons",
            "advantages",
            "disadvantages",
            "benefits",
            "drawbacks",
            "which is better",
            "performance vs",
            "cost vs",
            "latency vs",
        ],
        "planning": [
            "multi-step",
            "complex workflow",
            "sequence of",
            "phase",
            "roadmap",
            "implementation plan",
            "step-by-step",
            "migration plan",
            "deployment strategy",
            "rollout plan",
            "orchestration",
            "coordination",
        ],
    }

    # Patterns that reduce confidence (task is likely straightforward)
    STRAIGHTFORWARD_SIGNALS = [
        "simple",
        "trivial",
        "straightforward",
        "basic",
        "just",
        "only",
        "quick",
        "easy",
        "small change",
        "minor fix",
    ]

    # Regex patterns for more sophisticated detection
    _ARCHITECTURE_PATTERN = re.compile(
        r"\b(design|architect|structure|organize|schema|interface|component)\s+(the|a|an)\s+\w+",
        re.IGNORECASE,
    )
    _SECURITY_PATTERN = re.compile(
        r"\b(secure|protect|validate|sanitize|authenticate|authorize)\s+(the|a|an|this)\s+\w+",
        re.IGNORECASE,
    )
    _COMPARISON_PATTERN = re.compile(
        r"\b(compare|evaluate|choose between|which is better|pros.?cons)\b",
        re.IGNORECASE,
    )
    _MULTI_OPTION_PATTERN = re.compile(
        r"\b(option|alternative|approach|way|method)\s*[123]",
        re.IGNORECASE,
    )

    def __init__(self, decision_threshold: float = 0.7):
        """
        Initialize detector.

        Args:
            decision_threshold: Minimum confidence to trigger advisor (0-1)
        """
        self.decision_threshold = decision_threshold

    def detect(
        self,
        task: str,
        context: Dict[str, Any],
        executor_tier: str,
        task_id: str = "",
    ) -> Optional[DecisionPoint]:
        """
        Detect if task has decision points requiring advisor consultation.

        Args:
            task: Task description
            context: Execution context
            executor_tier: Current executor tier (local, free, paid)
            task_id: Unique task identifier

        Returns:
            DecisionPoint if detected and confidence >= threshold, None otherwise
        """
        task_lower = task.lower()

        # Score each decision type
        decision_scores: Dict[str, List[str]] = {
            decision_type: [] for decision_type in self.DECISION_SIGNALS.keys()
        }

        # Keyword-based signal detection
        for decision_type, signals in self.DECISION_SIGNALS.items():
            for signal in signals:
                if signal in task_lower:
                    decision_scores[decision_type].append(signal)

        # Regex pattern detection (adds weight)
        if self._ARCHITECTURE_PATTERN.search(task):
            decision_scores["architecture"].append("PATTERN:design_structure")
        if self._SECURITY_PATTERN.search(task):
            decision_scores["security"].append("PATTERN:security_action")
        if self._COMPARISON_PATTERN.search(task):
            decision_scores["tradeoff"].append("PATTERN:comparison")
        if self._MULTI_OPTION_PATTERN.search(task):
            decision_scores["ambiguity"].append("PATTERN:multiple_options")

        # Find highest scoring decision type
        sorted_types = sorted(
            decision_scores.items(), key=lambda x: len(x[1]), reverse=True
        )

        if not sorted_types or len(sorted_types[0][1]) == 0:
            # No decision signals detected
            return None

        primary_type = sorted_types[0][0]
        primary_signals = sorted_types[0][1]
        signal_count = len(primary_signals)

        # Calculate base confidence from signal density
        total_signals = sum(len(signals) for signals in decision_scores.values())
        base_confidence = signal_count / max(total_signals, 1)

        # Adjust confidence based on context
        confidence = self._adjust_confidence(
            base_confidence, task_lower, context, executor_tier
        )

        # Only return decision point if confidence exceeds threshold
        if confidence < self.decision_threshold:
            return None

        # Build advisor question
        question = self._build_advisor_question(task, primary_type, context)

        return DecisionPoint(
            task_id=task_id or "unknown",
            decision_type=primary_type,
            question=question,
            context=context,
            confidence=confidence,
            detected_signals=primary_signals,
            executor_tier=executor_tier,
        )

    def _adjust_confidence(
        self,
        base_confidence: float,
        task_lower: str,
        context: Dict[str, Any],
        executor_tier: str,
    ) -> float:
        """
        Adjust confidence based on additional context.

        Factors that increase confidence:
        - Lower-tier executors (local/free more likely to need advisor)
        - Longer, more complex tasks
        - Context indicates high stakes

        Factors that decrease confidence:
        - Straightforward signals present
        - Very short tasks
        - Context indicates low complexity
        """
        confidence = base_confidence

        # Straightforward signals reduce confidence
        straightforward_count = sum(
            1 for signal in self.STRAIGHTFORWARD_SIGNALS if signal in task_lower
        )
        if straightforward_count > 0:
            confidence *= 0.7  # Reduce by 30% per straightforward signal

        # Task length adjustment (longer = more complex = higher confidence)
        word_count = len(task_lower.split())
        if word_count > 50:
            confidence = min(1.0, confidence * 1.2)
        elif word_count < 10:
            confidence *= 0.8

        # Executor tier adjustment (lower tiers benefit more from advisor)
        tier_multipliers = {"local": 1.3, "free": 1.1, "paid": 0.9, "critical": 0.7}
        confidence *= tier_multipliers.get(executor_tier, 1.0)

        # Context complexity signals
        complexity = context.get("complexity", "medium")
        if complexity in ("complex", "architecture"):
            confidence = min(1.0, confidence * 1.2)
        elif complexity == "simple":
            confidence *= 0.7

        # Explicit user request for guidance
        guidance_keywords = ["help me decide", "what should", "recommend", "advise"]
        if any(keyword in task_lower for keyword in guidance_keywords):
            confidence = min(1.0, confidence * 1.3)

        return min(1.0, max(0.0, confidence))

    def _build_advisor_question(
        self, task: str, decision_type: str, context: Dict[str, Any]
    ) -> str:
        """
        Build focused question for advisor based on decision type.

        The question should be concise and focused on the decision, not the
        entire task execution.
        """
        question_templates = {
            "architecture": f"What's the recommended architecture approach for: {task[:200]}?",
            "security": f"What are the security considerations for: {task[:200]}?",
            "ambiguity": f"How should I approach this ambiguous requirement: {task[:200]}?",
            "tradeoff": f"What are the key tradeoffs to consider for: {task[:200]}?",
            "planning": f"What's the recommended implementation plan for: {task[:200]}?",
        }

        return question_templates.get(
            decision_type, f"How should I approach: {task[:200]}?"
        )
