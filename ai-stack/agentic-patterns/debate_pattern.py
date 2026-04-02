#!/usr/bin/env python3
"""
Debate Pattern

Coordinate multiple debaters with opposing or complementary perspectives and
let a judge synthesize a final recommendation.

Part of Phase 4: Advanced Agentic Pattern Library
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class DebateTurn:
    """A single debater turn."""
    debater_id: str
    position: str
    argument: str


@dataclass
class DebateResult:
    """Final debate synthesis."""
    prompt: str
    turns: List[DebateTurn] = field(default_factory=list)
    judgment: str = ""
    winning_position: str = ""


class DebateAgent:
    """Run a structured multi-perspective debate."""

    def __init__(
        self,
        debaters: List[Callable[[str, str], Awaitable[DebateTurn | Dict[str, Any]] | DebateTurn | Dict[str, Any]]],
        positions: List[str],
        judge: Callable[[str, List[DebateTurn]], Awaitable[Dict[str, Any] | str] | Dict[str, Any] | str],
    ) -> None:
        self.debaters = debaters
        self.positions = positions
        self.judge = judge

    async def solve(self, prompt: str) -> DebateResult:
        """Collect debate turns and synthesize a judgment."""
        turns: List[DebateTurn] = []
        for index, debater in enumerate(self.debaters):
            position = self.positions[index % len(self.positions)]
            turn = debater(prompt, position)
            if asyncio.iscoroutine(turn):
                turn = await turn
            if isinstance(turn, DebateTurn):
                turns.append(turn)
            else:
                turns.append(
                    DebateTurn(
                        debater_id=str(turn.get("debater_id", f"debater-{index + 1}")),
                        position=str(turn.get("position", position)),
                        argument=str(turn.get("argument", "")),
                    )
                )

        judgment = self.judge(prompt, turns)
        if asyncio.iscoroutine(judgment):
            judgment = await judgment

        if isinstance(judgment, dict):
            return DebateResult(
                prompt=prompt,
                turns=turns,
                judgment=str(judgment.get("judgment", "")),
                winning_position=str(judgment.get("winning_position", "")),
            )
        return DebateResult(prompt=prompt, turns=turns, judgment=str(judgment))
