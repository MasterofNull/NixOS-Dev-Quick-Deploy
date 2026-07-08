#!/usr/bin/env python3
"""Fast tests for typed local back-pressure and F1 quorum behavior."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import backpressure  # noqa: E402
import round_aggregate  # noqa: E402
import round_contribution  # noqa: E402
import round_state  # noqa: E402


def test_wait_over_slo_returns_local_delayed() -> None:
    assert (
        backpressure.assess(
            queue_wait_s=15.1,
            expected_infer_s=1.0,
            remaining_deadline_s=30.0,
        )
        == backpressure.Signal.LOCAL_DELAYED
    )


def test_expected_infer_over_remaining_deadline_returns_local_delayed() -> None:
    assert (
        backpressure.assess(
            queue_wait_s=0.0,
            expected_infer_s=31.0,
            remaining_deadline_s=30.0,
        )
        == backpressure.Signal.LOCAL_DELAYED
    )


def test_elapsed_deadline_returns_reject() -> None:
    assert (
        backpressure.assess(
            queue_wait_s=20.0,
            expected_infer_s=1.0,
            remaining_deadline_s=0.0,
        )
        == backpressure.Signal.REJECT
    )


def test_nominal_returns_ok() -> None:
    assert (
        backpressure.assess(
            queue_wait_s=5.0,
            expected_infer_s=1.0,
            remaining_deadline_s=30.0,
        )
        == backpressure.Signal.OK
    )


def test_threshold_override_is_respected() -> None:
    assert (
        backpressure.assess(
            queue_wait_s=10.1,
            expected_infer_s=1.0,
            remaining_deadline_s=None,
            slo_wait_threshold_s=10.0,
        )
        == backpressure.Signal.LOCAL_DELAYED
    )
    assert (
        backpressure.assess(
            queue_wait_s=10.1,
            expected_infer_s=1.0,
            remaining_deadline_s=None,
            slo_wait_threshold_s=11.0,
        )
        == backpressure.Signal.OK
    )


def test_local_delayed_is_admissible_not_failure() -> None:
    assert backpressure.is_admissible(backpressure.Signal.OK)
    assert backpressure.is_admissible(backpressure.Signal.LOCAL_DELAYED)
    assert not backpressure.is_admissible(backpressure.Signal.REJECT)


def test_f1_quorum_does_not_lock_while_required_local_lane_is_pending() -> None:
    prompt = "Review F2.3 back-pressure"
    manifest = round_state.RoundManifest(
        round_id="round-f23",
        state=round_state.RoundState.COLLECTED,
        task=round_state.RoundTask(
            prompt=prompt,
            target="backpressure.py",
            scope_files=[
                "scripts/ai/lib/backpressure.py",
                "scripts/testing/test-backpressure.py",
            ],
        ),
        opened_at="2026-07-08T01:00:00Z",
        quorum_policy=round_state.QuorumPolicy(
            min_lanes=3,
            required_agents=["claude", "codex", "local"],
            timeout_seconds=None,
            deadline=None,
        ),
        lanes=[
            round_state.Lane(
                agent="claude",
                dispatch_id=None,
                idempotency_hash=round_state.idempotency_hash("round-f23", "claude", prompt),
                status=round_state.LaneStatus.submitted,
                landed_at="2026-07-08T01:01:00Z",
            ),
            round_state.Lane(
                agent="codex",
                dispatch_id=None,
                idempotency_hash=round_state.idempotency_hash("round-f23", "codex", prompt),
                status=round_state.LaneStatus.submitted,
                landed_at="2026-07-08T01:02:00Z",
            ),
            round_state.Lane(
                agent="local",
                dispatch_id=None,
                idempotency_hash=round_state.idempotency_hash("round-f23", "local", prompt),
                status=round_state.LaneStatus.pending,
                landed_at=None,
            ),
        ],
        consensus_hash=None,
        aggregate_path=None,
        aggregate_hash=None,
        locked_at=None,
    )
    contributions = {
        agent: round_contribution.Contribution(
            agent_id=agent,
            model_provenance=round_contribution.ModelProvenance(
                model_name=f"{agent}-model",
                model_version=None,
            ),
            verdict=round_contribution.Verdict.APPROVE,
            required_changes=[],
        )
        for agent in ["claude", "codex"]
    }

    assert not round_aggregate.quorum_met(manifest)
    updated = round_aggregate.aggregate(manifest, contributions)

    assert updated.state != round_state.RoundState.CONSENSUS_LOCKED
    assert updated.state == round_state.RoundState.CONFLICTS_IDENTIFIED
    assert updated.locked_at is None
