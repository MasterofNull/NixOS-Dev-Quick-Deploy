#!/usr/bin/env python3
"""Fast tests for typed collaboration round aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import round_aggregate  # noqa: E402
import round_contribution  # noqa: E402
import round_state  # noqa: E402


def sample_manifest(
    state: round_state.RoundState = round_state.RoundState.COLLECTED,
    lane_statuses: dict[str, round_state.LaneStatus] | None = None,
    required_agents: list[str] | None = None,
    min_lanes: int = 2,
) -> round_state.RoundManifest:
    """Build a minimal manifest for aggregate tests."""

    prompt = "Critique the F1.3 implementation"
    statuses = (
        {
            "claude": round_state.LaneStatus.submitted,
            "codex": round_state.LaneStatus.submitted,
        }
        if lane_statuses is None
        else lane_statuses
    )
    return round_state.RoundManifest(
        round_id="round-f13",
        state=state,
        task=round_state.RoundTask(
            prompt=prompt,
            target="round.json",
            scope_files=["scripts/ai/lib/round_aggregate.py"],
        ),
        opened_at="2026-07-08T01:00:00Z",
        quorum_policy=round_state.QuorumPolicy(
            min_lanes=min_lanes,
            required_agents=required_agents or ["claude", "codex"],
            timeout_seconds=None,
            deadline=None,
        ),
        lanes=[
            round_state.Lane(
                agent=agent,
                dispatch_id=None,
                idempotency_hash=round_state.idempotency_hash("round-f13", agent, prompt),
                status=status,
                landed_at="2026-07-08T01:10:00Z" if status in round_aggregate.LANDED_STATUSES else None,
            )
            for agent, status in sorted(statuses.items())
        ],
        consensus_hash=None,
        aggregate_path=None,
        aggregate_hash=None,
        locked_at=None,
    )


def contribution(
    agent: str,
    verdict: round_contribution.Verdict = round_contribution.Verdict.APPROVE,
    changes: list[tuple[str, str | None, str]] | None = None,
) -> round_contribution.Contribution:
    """Build a typed contribution with optional required changes."""

    return round_contribution.Contribution(
        agent_id=agent,
        model_provenance=round_contribution.ModelProvenance(
            model_name=f"{agent}-model",
            model_version=None,
        ),
        verdict=verdict,
        required_changes=[
            round_contribution.RequiredChange(
                file_path=file_path,
                line_range=line_range,
                description=description,
                severity=round_contribution.Severity.minor,
            )
            for file_path, line_range, description in changes or []
        ],
    )


def test_register_lane_is_idempotent_for_same_call() -> None:
    manifest = sample_manifest(
        round_state.RoundState.DISPATCHED,
        lane_statuses={},
        required_agents=[],
        min_lanes=1,
    )

    first = round_aggregate.register_lane(manifest, "local", "reviewer", manifest.task.prompt)
    second = round_aggregate.register_lane(manifest, "local", "reviewer", manifest.task.prompt)

    assert first == second
    assert len(manifest.lanes) == 1
    assert manifest.lanes[0].status == round_state.LaneStatus.pending


def test_register_lane_same_idempotency_hash_returns_existing_lane() -> None:
    manifest = sample_manifest(
        round_state.RoundState.DISPATCHED,
        lane_statuses={},
        required_agents=[],
        min_lanes=1,
    )

    first = round_aggregate.register_lane(manifest, "codex", "reviewer", manifest.task.prompt)
    second = round_aggregate.register_lane(manifest, "local", "reviewer", manifest.task.prompt)

    assert second == first
    assert len(manifest.lanes) == 1
    assert manifest.lanes[0].agent == "codex"


def test_register_lane_existing_running_agent_returns_existing_lane() -> None:
    manifest = sample_manifest(
        round_state.RoundState.DISPATCHED,
        lane_statuses={"codex": round_state.LaneStatus.running},
        required_agents=[],
        min_lanes=1,
    )

    existing = manifest.lanes[0]
    returned = round_aggregate.register_lane(manifest, "codex", "different-role", "different prompt")

    assert returned == existing
    assert len(manifest.lanes) == 1


def test_aggregate_all_approve_no_overlap_locks_with_stable_hash() -> None:
    manifest = sample_manifest()
    contributions = {
        "codex": contribution("codex", changes=[("a.py", "10", "Add deterministic sorting")]),
        "claude": contribution("claude", changes=[("b.py", "20", "Add AMEND coverage")]),
    }

    first = round_aggregate.aggregate(manifest, contributions)
    second = round_aggregate.aggregate(sample_manifest(), dict(reversed(list(contributions.items()))))

    assert first.state == round_state.RoundState.CONSENSUS_LOCKED
    assert first.conflicts == []
    assert first.consensus_hash is not None
    assert first.consensus_hash == second.consensus_hash
    assert first.locked_at is not None
    assert first.history[-1].transition == "COLLECTED->CONSENSUS_LOCKED"


def test_aggregate_competing_same_file_line_changes_conflicts() -> None:
    manifest = sample_manifest()
    contributions = {
        "codex": contribution("codex", changes=[("a.py", "10", "Use sha256 over tally")]),
        "claude": contribution("claude", changes=[("a.py", "10", "Use blake3 over tally")]),
    }

    updated = round_aggregate.aggregate(manifest, contributions)

    assert updated.state == round_state.RoundState.CONFLICTS_IDENTIFIED
    assert len(updated.conflicts) == 1
    assert updated.conflicts[0] == round_state.Conflict(
        file_path="a.py",
        line_range="10",
        description="Competing required changes: Use blake3 over tally | Use sha256 over tally",
        competing=["claude", "codex"],
    )
    assert updated.history[-1].transition == "COLLECTED->CONFLICTS_IDENTIFIED"


def test_amend_concur_marks_lane_amended_and_relocks() -> None:
    locked = round_aggregate.aggregate(
        sample_manifest(),
        {
            "codex": contribution("codex", changes=[("a.py", "10", "Add deterministic sorting")]),
            "claude": contribution("claude"),
        },
    )
    late = contribution("local", changes=[("a.py", "10", "Add deterministic sorting")])

    updated = round_aggregate.amend(
        locked,
        late,
        round_contribution.Verdict.APPROVE,
        locked_changes=late.required_changes,
    )

    assert updated.state == round_state.RoundState.CONSENSUS_LOCKED
    assert any(lane.agent == "local" and lane.status == round_state.LaneStatus.amended for lane in updated.lanes)
    assert [entry.transition for entry in updated.history[-2:]] == [
        "CONSENSUS_LOCKED->AMEND",
        "AMEND->CONSENSUS_LOCKED",
    ]


def test_amend_dissent_moves_to_conflicts_identified() -> None:
    locked = round_aggregate.aggregate(
        sample_manifest(),
        {
            "codex": contribution("codex"),
            "claude": contribution("claude"),
        },
    )
    late = contribution(
        "local",
        verdict=round_contribution.Verdict.REJECT,
        changes=[("a.py", "10", "Replace consensus path")],
    )

    updated = round_aggregate.amend(
        locked,
        late,
        round_contribution.Verdict.APPROVE,
        locked_changes=[],
    )

    assert updated.state == round_state.RoundState.CONFLICTS_IDENTIFIED
    assert updated.conflicts == [
        round_state.Conflict(
            file_path="a.py",
            line_range="10",
            description="Replace consensus path",
            competing=["local"],
        )
    ]
    assert [entry.transition for entry in updated.history[-2:]] == [
        "CONSENSUS_LOCKED->AMEND",
        "AMEND->CONFLICTS_IDENTIFIED",
    ]


def test_quorum_met_true_and_false_cases() -> None:
    assert round_aggregate.quorum_met(sample_manifest())
    assert not round_aggregate.quorum_met(
        sample_manifest(
            lane_statuses={
                "claude": round_state.LaneStatus.submitted,
                "codex": round_state.LaneStatus.running,
            }
        )
    )
    assert not round_aggregate.quorum_met(
        sample_manifest(required_agents=["claude", "codex", "local"])
    )
