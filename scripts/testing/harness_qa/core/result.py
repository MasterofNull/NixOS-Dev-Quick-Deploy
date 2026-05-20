"""CheckResult dataclass and helpers for building pass/fail/skip results."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    status: Status
    layer: int
    id: str
    description: str
    reason: str = ""
    duration_ms: float = 0.0
    phase: str = "0"

    def to_dict(self) -> dict:
        d = {
            "layer": self.layer,
            "id": self.id,
            "status": self.status.value,
            "description": self.description,
        }
        if self.reason:
            d["description"] = f"{self.description} ({self.reason})"
        return d


def passed(layer: int, id: str, description: str, phase: str = "0") -> CheckResult:
    return CheckResult(Status.PASS, layer, id, description, phase=phase)


def failed(layer: int, id: str, description: str, reason: str = "", phase: str = "0") -> CheckResult:
    return CheckResult(Status.FAIL, layer, id, description, reason=reason, phase=phase)


def skipped(layer: int, id: str, description: str, reason: str = "", phase: str = "0") -> CheckResult:
    return CheckResult(Status.SKIP, layer, id, description, reason=reason, phase=phase)


@dataclass
class ResultSet:
    phase: str
    results: list[CheckResult] = field(default_factory=list)
    duration_s: int = 0
    layer_filter: int = 0
    causality_mode: bool = False

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == Status.SKIP)

    @property
    def degraded_confidence(self) -> bool:
        if not (self.causality_mode and self.layer_filter > 0):
            return False
        layers: dict[int, list[CheckResult]] = {}
        for r in self.results:
            layers.setdefault(r.layer, []).append(r)
        return any(
            any(r.status == Status.FAIL for r in layers[l])
            for l in layers
            if l < self.layer_filter
        )
