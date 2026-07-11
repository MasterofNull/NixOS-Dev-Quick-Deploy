#!/usr/bin/env python3
"""Golden lifecycle tests for collaboration rounds."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import round_aggregate  # noqa: E402
import round_contribution  # noqa: E402
import round_state  # noqa: E402

SUBJECT = "sha-256:" + "a" * 64


def manifest(
    *,
    round_id: str = "round-golden",
    min_lanes: int = 2,
    required_agents: list[str] | None = None,
    deadline: str | None = None,
) -> round_state.RoundManifest:
    prompt = "Review the F1 golden round lifecycle"
    return round_state.RoundManifest(
        round_id=round_id,
        state=round_state.RoundState.CREATED,
        task=round_state.RoundTask(
            prompt=prompt,
            target="round.json",
            scope_files=[
                "scripts/ai/lib/round_state.py",
                "scripts/ai/lib/round_contribution.py",
                "scripts/ai/lib/round_aggregate.py",
            ],
        ),
        opened_at="2026-07-08T01:00:00Z",
        quorum_policy=round_state.QuorumPolicy(
            min_lanes=min_lanes,
            required_agents=required_agents or ["claude", "codex"],
            timeout_seconds=30 if deadline else None,
            deadline=deadline,
        ),
        lanes=[],
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
    return round_contribution.Contribution(
        schema_version="2.0",
        agent_id=agent,
        model_provenance=round_contribution.ModelProvenance(
            model_name=f"{agent}-model",
            model_version=None,
            model_family=f"family-{agent}",
            execution_principal=f"principal-{agent}",
            assurance="ORCHESTRATOR_ATTESTED",
        ),
        verdict=verdict,
        subject_hash=SUBJECT,
        fresh=True,
        producer_verified=True,
        evidence_condition="VALID",
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


def dispatch_round(
    agents: list[str],
    *,
    min_lanes: int | None = None,
    required_agents: list[str] | None = None,
    deadline: str | None = None,
) -> round_state.RoundManifest:
    active = manifest(
        min_lanes=min_lanes or len(agents),
        required_agents=required_agents if required_agents is not None else agents,
        deadline=deadline,
    )
    for agent in agents:
        round_aggregate.register_lane(active, agent, agent, active.task.prompt)
    active = round_state.transition(active, round_state.RoundState.DISPATCHED, "pytest")
    active = round_state.transition(active, round_state.RoundState.CONTRIBUTING, "pytest")
    return active


def land(
    active: round_state.RoundManifest,
    landed: dict[str, round_contribution.Contribution],
    failed: set[str] | None = None,
    timed_out: set[str] | None = None,
) -> round_state.RoundManifest:
    failed = failed or set()
    timed_out = timed_out or set()
    lanes = []
    for lane in active.lanes:
        if lane.agent in landed:
            lanes.append(
                lane.model_copy(
                    update={
                        "status": round_state.LaneStatus.submitted,
                        "landed_at": "2026-07-08T01:10:00Z",
                    }
                )
            )
        elif lane.agent in failed:
            lanes.append(lane.model_copy(update={"status": round_state.LaneStatus.failed}))
        elif lane.agent in timed_out:
            lanes.append(lane.model_copy(update={"status": round_state.LaneStatus.timed_out}))
        else:
            lanes.append(lane)
    collected = active.model_copy(update={"lanes": lanes})
    return round_state.transition(collected, round_state.RoundState.COLLECTED, "pytest")


def test_clean_lock() -> None:
    contributions = {
        "claude": contribution("claude"),
        "codex": contribution("codex"),
        "gemini": contribution("gemini"),
    }
    collected = land(dispatch_round(list(contributions)), contributions)

    locked = round_aggregate.aggregate(collected, contributions)

    assert locked.state == round_state.RoundState.CONSENSUS_LOCKED
    assert locked.consensus_hash
    assert locked.conflicts == []
    assert [entry.transition for entry in locked.history] == [
        "CREATED->DISPATCHED",
        "DISPATCHED->CONTRIBUTING",
        "CONTRIBUTING->COLLECTED",
        "COLLECTED->CONSENSUS_LOCKED",
    ]


def test_idempotent_retry() -> None:
    active = dispatch_round(["claude", "codex"], min_lanes=2)
    for agent in ["claude", "codex"]:
        round_aggregate.register_lane(active, agent, agent, active.task.prompt)
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    collected = land(active, contributions)

    first = round_aggregate.aggregate(collected, contributions)
    second = round_aggregate.aggregate(collected.model_copy(deep=True), dict(contributions))

    assert [lane.agent for lane in active.lanes] == ["claude", "codex"]
    assert first.consensus_hash == second.consensus_hash
    assert first.state == second.state == round_state.RoundState.CONSENSUS_LOCKED


def test_late_local_concurrence() -> None:
    locked_change = round_contribution.RequiredChange(
        file_path="scripts/ai/lib/round_aggregate.py",
        line_range="120-140",
        description="Keep deterministic merge order",
        severity=round_contribution.Severity.minor,
    )
    contributions = {
        "claude": contribution("claude"),
        "codex": contribution(
            "codex",
            changes=[(locked_change.file_path, locked_change.line_range, locked_change.description)],
        ),
    }
    locked = round_aggregate.aggregate(land(dispatch_round(["claude", "codex"]), contributions), contributions)
    before_hash = locked.consensus_hash

    amended = round_aggregate.amend(
        locked,
        contribution("local", changes=[(locked_change.file_path, locked_change.line_range, locked_change.description)]),
        round_contribution.Verdict.APPROVE,
        [locked_change],
    )

    assert amended.state == round_state.RoundState.CONSENSUS_LOCKED
    assert amended.consensus_hash == before_hash
    assert any(lane.agent == "local" and lane.status == round_state.LaneStatus.amended for lane in amended.lanes)


def test_late_local_conflict() -> None:
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    locked = round_aggregate.aggregate(land(dispatch_round(["claude", "codex"]), contributions), contributions)

    amended = round_aggregate.amend(
        locked,
        contribution(
            "local",
            verdict=round_contribution.Verdict.REJECT,
            changes=[("scripts/ai/lib/round_state.py", "50-60", "Replace the locked transition path")],
        ),
        round_contribution.Verdict.APPROVE,
        [],
    )

    assert amended.state == round_state.RoundState.CONFLICTS_IDENTIFIED
    assert amended.conflicts
    assert isinstance(amended.conflicts[0], round_state.Conflict)


def test_quorum_timeout() -> None:
    active = dispatch_round(
        ["claude", "codex", "local"],
        min_lanes=3,
        required_agents=["claude", "codex", "local"],
        deadline="2026-07-08T01:00:01Z",
    )
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    collected = land(active, contributions, timed_out={"local"})

    updated = round_aggregate.aggregate(collected, contributions)

    assert not round_aggregate.quorum_met(collected)
    assert any(lane.agent == "local" and lane.status == round_state.LaneStatus.timed_out for lane in updated.lanes)
    # Timed-out lane has zero weight; two independent substantive approvals still satisfy policy.
    assert updated.state == round_state.RoundState.CONSENSUS_LOCKED


def test_invalid_schema(tmp_path: Path) -> None:
    active = dispatch_round(["claude", "codex"], min_lanes=2)
    (tmp_path / "codex.json").write_text('{"verdict":"APPROVE"}', encoding="utf-8")

    extracted, status = round_contribution.extract_contribution("codex", tmp_path)
    collected = land(active, {"claude": contribution("claude")}, failed={"codex"})

    assert extracted is None
    assert status == "failed:invalid-sidecar"
    assert any(lane.agent == "codex" and lane.status == round_state.LaneStatus.failed for lane in collected.lanes)
    assert not round_aggregate.quorum_met(collected)


def test_missing_lane() -> None:
    active = dispatch_round(["claude", "codex", "local"], min_lanes=2, required_agents=["claude", "codex"])
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    collected = land(active, contributions)

    locked = round_aggregate.aggregate(collected, contributions)

    assert any(lane.agent == "local" and lane.status == round_state.LaneStatus.pending for lane in locked.lanes)
    assert round_aggregate.quorum_met(collected)
    assert locked.state == round_state.RoundState.CONSENSUS_LOCKED


def test_dispatch_failure() -> None:
    active = dispatch_round(["claude", "codex", "gemini"], min_lanes=2, required_agents=["claude", "codex"])
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    collected = land(active, contributions, failed={"gemini"})

    locked = round_aggregate.aggregate(collected, {**contributions, "gemini": contribution("gemini")})

    assert any(lane.agent == "gemini" and lane.status == round_state.LaneStatus.failed for lane in locked.lanes)
    assert locked.state == round_state.RoundState.CONSENSUS_LOCKED
    assert locked.consensus_hash == round_aggregate.aggregate(collected.model_copy(deep=True), contributions).consensus_hash


def test_recovery_after_process_death(tmp_path: Path) -> None:
    contributions = {"claude": contribution("claude"), "codex": contribution("codex")}
    collected = land(dispatch_round(["claude", "codex"]), contributions)
    path = tmp_path / "round.json"

    round_state.save(collected, path)
    del collected
    recovered = round_state.load(path)
    locked = round_aggregate.aggregate(recovered, contributions)

    assert locked.state == round_state.RoundState.CONSENSUS_LOCKED
    assert locked.consensus_hash
    assert locked.history[-1].transition == "COLLECTED->CONSENSUS_LOCKED"


def test_legacy_round_read_only(tmp_path: Path) -> None:
    agents = ["claude", "codex", "local"]
    for agent in agents:
        (tmp_path / f"{agent}.md").write_text(
            f"Legacy markdown review from {agent}.\nAPPROVE in prose only.\n",
            encoding="utf-8",
        )
    before = {
        agent: ((tmp_path / f"{agent}.md").read_bytes(), (tmp_path / f"{agent}.md").stat().st_mtime_ns)
        for agent in agents
    }

    for agent in agents:
        contribution_result, status = round_contribution.extract_contribution(agent, tmp_path)
        assert status == "extracted-prose"
        assert contribution_result is not None

    after = {
        agent: ((tmp_path / f"{agent}.md").read_bytes(), (tmp_path / f"{agent}.md").stat().st_mtime_ns)
        for agent in agents
    }
    assert after == before
