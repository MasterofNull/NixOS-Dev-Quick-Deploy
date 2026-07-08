#!/usr/bin/env python3
"""Fast tests for the collaboration round manifest state machine."""

from __future__ import annotations

import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import round_state  # noqa: E402


def sample_manifest(state: round_state.RoundState = round_state.RoundState.CREATED) -> round_state.RoundManifest:
    """Build a minimal valid manifest for state-machine tests."""

    prompt = "Critique the F1 plan"
    return round_state.RoundManifest(
        round_id="round-f1",
        state=state,
        task=round_state.RoundTask(
            prompt=prompt,
            target="round.json",
            scope_files=["scripts/ai/lib/round_state.py"],
        ),
        opened_at="2026-07-08T01:00:00Z",
        quorum_policy=round_state.QuorumPolicy(
            min_lanes=2,
            required_agents=["claude", "codex"],
            timeout_seconds=None,
            deadline=None,
        ),
        lanes=[
            round_state.Lane(
                agent="codex",
                dispatch_id=None,
                idempotency_hash=round_state.idempotency_hash("round-f1", "codex", prompt),
                status=round_state.LaneStatus.pending,
                landed_at=None,
            )
        ],
        consensus_hash=None,
        aggregate_path=None,
        aggregate_hash=None,
        locked_at=None,
    )


def test_every_legal_transition_succeeds_and_appends_history() -> None:
    for from_state, to_states in round_state.ALLOWED_TRANSITIONS.items():
        for to_state in to_states:
            manifest = sample_manifest(from_state)
            updated = round_state.transition(manifest, to_state, "pytest")

            assert updated.state == to_state
            assert len(updated.history) == len(manifest.history) + 1
            assert updated.history[-1].transition == f"{from_state.value}->{to_state.value}"
            assert updated.history[-1].actor == "pytest"
            assert updated.history[-1].timestamp.endswith("Z")


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (round_state.RoundState.CREATED, round_state.RoundState.COLLECTED),
        (round_state.RoundState.DISPATCHED, round_state.RoundState.CLOSED),
        (round_state.RoundState.CLOSED, round_state.RoundState.CREATED),
        (round_state.RoundState.ABORTED, round_state.RoundState.DISPATCHED),
    ],
)
def test_illegal_transitions_raise(
    from_state: round_state.RoundState,
    to_state: round_state.RoundState,
) -> None:
    with pytest.raises(round_state.IllegalTransition):
        round_state.transition(sample_manifest(from_state), to_state, "pytest")


def test_conflicts_identified_cannot_return_to_collected() -> None:
    with pytest.raises(round_state.IllegalTransition):
        round_state.transition(
            sample_manifest(round_state.RoundState.CONFLICTS_IDENTIFIED),
            round_state.RoundState.COLLECTED,
            "pytest",
        )


def test_save_load_round_trips_manifest_identically(tmp_path: Path) -> None:
    manifest = round_state.transition(
        sample_manifest(round_state.RoundState.CREATED),
        round_state.RoundState.DISPATCHED,
        "pytest",
    )
    path = tmp_path / "round.json"

    round_state.save(manifest, path)
    loaded = round_state.load(path)

    assert loaded == manifest


def test_idempotency_hash_is_stable_and_prompt_sensitive() -> None:
    first = round_state.idempotency_hash("round-f1", "codex", "prompt one")
    second = round_state.idempotency_hash("round-f1", "codex", "prompt one")
    different_prompt = round_state.idempotency_hash("round-f1", "codex", "prompt two")

    assert first == second
    assert first != different_prompt
    assert len(first) == 64


def test_export_json_schema_is_valid_draft_2020_12_schema() -> None:
    schema = round_state.export_json_schema()

    jsonschema.Draft202012Validator.check_schema(schema)
