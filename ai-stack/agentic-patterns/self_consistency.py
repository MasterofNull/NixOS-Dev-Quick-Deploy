#!/usr/bin/env python3
"""
Self-Consistency Pattern

Generates multiple independent reasoning candidates and selects the most
consistent answer by weighted consensus.

Part of Phase 4: Advanced Agentic Pattern Library
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyCandidate:
    """A single candidate answer generated independently."""
    answer: Any
    rationale: str = ""
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelfConsistencyResult:
    """Aggregated result of self-consistency solving."""
    prompt: str
    selected_answer: Any
    support_count: int
    total_samples: int
    agreement_ratio: float
    candidates: List[ConsistencyCandidate]


class SelfConsistencyAgent:
    """Sample multiple candidate answers and pick the strongest consensus."""

    def __init__(
        self,
        sampler: Callable[[str, int], Awaitable[ConsistencyCandidate] | ConsistencyCandidate],
        samples: int = 5,
        normalize_fn: Optional[Callable[[Any], str]] = None,
    ) -> None:
        self.sampler = sampler
        self.samples = max(1, int(samples))
        self.normalize_fn = normalize_fn or self._default_normalize

    async def solve(self, prompt: str) -> SelfConsistencyResult:
        """Generate multiple candidates and select the consensus answer."""
        candidates = await asyncio.gather(
            *(self._sample_once(prompt, index) for index in range(self.samples))
        )

        buckets: Dict[str, List[ConsistencyCandidate]] = {}
        for candidate in candidates:
            key = self.normalize_fn(candidate.answer)
            buckets.setdefault(key, []).append(candidate)

        ranked = sorted(
            buckets.items(),
            key=lambda item: (
                len(item[1]),
                mean(max(0.0, min(1.0, c.confidence)) for c in item[1]),
            ),
            reverse=True,
        )
        _, winning_group = ranked[0]
        selected = max(winning_group, key=lambda candidate: candidate.confidence)
        support_count = len(winning_group)

        logger.info(
            "Self-consistency selected answer with %s/%s supporting samples",
            support_count,
            len(candidates),
        )
        return SelfConsistencyResult(
            prompt=prompt,
            selected_answer=selected.answer,
            support_count=support_count,
            total_samples=len(candidates),
            agreement_ratio=round(support_count / max(1, len(candidates)), 3),
            candidates=candidates,
        )

    async def _sample_once(self, prompt: str, index: int) -> ConsistencyCandidate:
        result = self.sampler(prompt, index)
        if asyncio.iscoroutine(result):
            result = await result
        if isinstance(result, ConsistencyCandidate):
            return result
        if isinstance(result, dict):
            return ConsistencyCandidate(
                answer=result.get("answer"),
                rationale=str(result.get("rationale", "")),
                confidence=float(result.get("confidence", 0.5) or 0.5),
                metadata=dict(result.get("metadata", {}) or {}),
            )
        return ConsistencyCandidate(answer=result)

    @staticmethod
    def _default_normalize(value: Any) -> str:
        return " ".join(str(value).strip().lower().split())
