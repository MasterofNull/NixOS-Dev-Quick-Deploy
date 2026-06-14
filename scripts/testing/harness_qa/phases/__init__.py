"""Phase registry — maps phase IDs to their run() functions."""
from __future__ import annotations

from typing import Callable
from ..core.context import RunContext
from ..core.result import CheckResult

PhaseRunner = Callable[[RunContext], list[CheckResult]]


def _load_phases() -> dict[str, PhaseRunner]:
    # Lazy imports to avoid circular dependencies and keep startup fast
    from . import (
        phase0, phase1, phase2, phase3, phase4, phase5,
        phase6, phase7, phase8, phase9, phase10,
        phase54, phase55, phase56, phase57, phase58, phase59,
        phase68, phase69, phase70, phase71, phase72, phase73,
    )
    return {
        "0":  phase0.run,
        "1":  phase1.run,
        "2":  phase2.run,
        "3":  phase3.run,
        "4":  phase4.run,
        "5":  phase5.run,
        "6":  phase6.run,
        "7":  phase7.run,
        "8":  phase8.run,
        "9":  phase9.run,
        "10": phase10.run,
        "54": phase54.run,
        "55": phase55.run,
        "56": phase56.run,
        "57": phase57.run,
        "58": phase58.run,
        "59": phase59.run,
        "68": phase68.run,
        "69": phase69.run,
        "70": phase70.run,
        "71": phase71.run,
        "72": phase72.run,
        "73": phase73.run,
    }


_PHASE_MAP: dict[str, PhaseRunner] | None = None


def get_phase_map() -> dict[str, PhaseRunner]:
    global _PHASE_MAP
    if _PHASE_MAP is None:
        _PHASE_MAP = _load_phases()
    return _PHASE_MAP


ALL_PHASES = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "54", "55", "56", "57", "58", "59", "68", "69", "70", "71", "72", "73",
]
