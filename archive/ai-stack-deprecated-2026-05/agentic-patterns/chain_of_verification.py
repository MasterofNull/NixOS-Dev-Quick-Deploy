#!/usr/bin/env python3
"""
Chain-of-Verification Pattern

Generate an answer, extract claims, and validate them through an explicit
verification chain before accepting the final response.

Part of Phase 4: Advanced Agentic Pattern Library
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class VerificationCheck:
    """Verification outcome for an individual claim."""
    claim: str
    verdict: str
    evidence: str = ""


@dataclass
class VerificationResult:
    """Full verification result for an answer."""
    prompt: str
    draft_answer: str
    checks: List[VerificationCheck] = field(default_factory=list)
    verified_answer: str = ""
    passed: bool = False


class ChainOfVerificationAgent:
    """Generate, verify, and revise an answer."""

    def __init__(
        self,
        answer_generator: Callable[[str], Awaitable[str] | str],
        verifier: Callable[[str], Awaitable[VerificationCheck | Dict[str, Any]] | VerificationCheck | Dict[str, Any]],
        reviser: Callable[[str, List[VerificationCheck]], Awaitable[str] | str] | None = None,
    ) -> None:
        self.answer_generator = answer_generator
        self.verifier = verifier
        self.reviser = reviser or self._default_reviser

    async def solve(self, prompt: str) -> VerificationResult:
        """Run answer generation, claim verification, and revision."""
        draft = self.answer_generator(prompt)
        if asyncio.iscoroutine(draft):
            draft = await draft

        checks: List[VerificationCheck] = []
        for claim in self._extract_claims(draft):
            check = self.verifier(claim)
            if asyncio.iscoroutine(check):
                check = await check
            if isinstance(check, VerificationCheck):
                checks.append(check)
            else:
                checks.append(
                    VerificationCheck(
                        claim=claim,
                        verdict=str(check.get("verdict", "unknown")),
                        evidence=str(check.get("evidence", "")),
                    )
                )

        passed = all(check.verdict == "pass" for check in checks)
        revised = self.reviser(draft, checks)
        if asyncio.iscoroutine(revised):
            revised = await revised

        return VerificationResult(
            prompt=prompt,
            draft_answer=draft,
            checks=checks,
            verified_answer=revised,
            passed=passed,
        )

    @staticmethod
    def _extract_claims(draft_answer: str) -> List[str]:
        claims = [segment.strip() for segment in str(draft_answer).split(".") if segment.strip()]
        return claims or [str(draft_answer).strip()]

    @staticmethod
    def _default_reviser(draft_answer: str, checks: List[VerificationCheck]) -> str:
        failing = [check.claim for check in checks if check.verdict != "pass"]
        if not failing:
            return draft_answer
        return f"{draft_answer}\n\nUnverified claims: {', '.join(failing)}"
