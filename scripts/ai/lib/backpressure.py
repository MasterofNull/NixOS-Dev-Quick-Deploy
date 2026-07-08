#!/usr/bin/env python3
"""Typed back-pressure signals for local lane admission.

LOCAL_DELAYED is a typed admissible state, not a failure, abstain, or timeout.
Callers that receive LOCAL_DELAYED for a local lane must keep that lane in the
round and wait for quorum policy to include it; this is the never-skip-local
contract.
"""

from __future__ import annotations

from enum import StrEnum

SLO_WAIT_THRESHOLD_S = 15.0


class Signal(StrEnum):
    """Back-pressure assessment result for a measured local lane."""

    OK = "ok"
    LOCAL_DELAYED = "local-delayed"
    REJECT = "reject"


def assess(
    queue_wait_s: float,
    expected_infer_s: float,
    remaining_deadline_s: float | None,
    *,
    slo_wait_threshold_s: float = SLO_WAIT_THRESHOLD_S,
) -> Signal:
    """Return the typed admission signal for measured queue and deadline inputs."""

    if remaining_deadline_s is not None and remaining_deadline_s <= 0:
        return Signal.REJECT
    if remaining_deadline_s is not None and expected_infer_s > remaining_deadline_s:
        return Signal.LOCAL_DELAYED
    if queue_wait_s > slo_wait_threshold_s:
        return Signal.LOCAL_DELAYED
    return Signal.OK


def is_admissible(signal: Signal) -> bool:
    """Return whether a signal keeps the lane eligible for round quorum."""

    return signal in {Signal.OK, Signal.LOCAL_DELAYED}
