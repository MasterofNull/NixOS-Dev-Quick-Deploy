"""
Affective State Model — Phase 19: Values Signals

AffectiveState captures observable behavioral proxies (not emotions) that
modulate coordinator response style. All signals are floats in [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class AffectiveState:
    """Observable behavioral signals derived from query context and telemetry.

    Signals:
      empathy_signal    — 0=neutral, 1=high frustration proxies detected
      reciprocity_debt  — negative=system owes user, positive=user owes
      aesthetic_gap     — 0=high-quality output, 1=low quality detected
      compassion_level  — 0=neutral, 1=distress markers detected
    """

    empathy_signal: float = 0.0
    reciprocity_debt: float = 0.0
    aesthetic_gap: float = 0.0
    compassion_level: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def dominant_signal(self) -> str:
        """Return the name of the highest non-zero signal, or 'neutral'."""
        candidates = {
            "empathy": self.empathy_signal,
            "reciprocity": abs(self.reciprocity_debt),
            "aesthetic": self.aesthetic_gap,
            "compassion": self.compassion_level,
        }
        best = max(candidates, key=lambda k: candidates[k])
        if candidates[best] == 0.0:
            return "neutral"
        return best

    def as_modulation_hints(self) -> List[str]:
        """Return prompt modifier strings for each active signal."""
        hints: List[str] = []

        if self.empathy_signal > 0.7:
            hints.append("Use step-by-step explanations with numbered lists")
        elif self.empathy_signal > 0.4:
            hints.append("Keep explanations clear and avoid assumptions")

        if self.reciprocity_debt < -3:
            hints.append("Proactively offer additional resources or next steps")

        if self.aesthetic_gap > 0.6:
            hints.append("Add a brief note on code elegance or simplification")

        if self.compassion_level > 0.5:
            hints.append("Keep response concise and reduce jargon")

        return hints
