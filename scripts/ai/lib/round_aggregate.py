#!/usr/bin/env python3
"""Pure aggregation helpers for typed collaboration rounds."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from round_contribution import Contribution, RequiredChange, Verdict
from round_contribution import approval_eligibility, substantive_evidence_eligibility
from round_state import (
    AssignmentRecord,
    AuthorizationState,
    Conflict,
    Lane,
    LaneStatus,
    RoundManifest,
    RoundState,
    idempotency_hash,
    transition,
    utc_iso,
)

LANDED_STATUSES = {LaneStatus.submitted, LaneStatus.amended}
ACTIVE_IDEMPOTENT_STATUSES = {
    LaneStatus.running,
    LaneStatus.submitted,
    LaneStatus.amended,
}


@dataclass
class MergedChange:
    """One deterministic required-change group with agent provenance."""

    file_path: str
    line_range: str | None
    description: str
    severity: str
    agents: list[str] = field(default_factory=list)


def register_lane(manifest: RoundManifest, agent: str, role: str, task_prompt: str) -> Lane:
    """Register one lane unless the agent or idempotency key is already active."""

    # A lane is one-per-agent. The idempotency key MUST include the agent identity, not just the role:
    # in the flat collaborative model every agent shares role "reviewer", so hashing on role alone
    # collides distinct agents into a single lane (only the first would ever register). Fold the agent in
    # so re-dispatching the SAME agent's lane stays idempotent while different agents get distinct lanes.
    lane_hash = idempotency_hash(manifest.round_id, f"{agent}:{role}", task_prompt)
    for lane in sorted(manifest.lanes, key=lambda item: item.agent):
        if lane.agent == agent and lane.status in ACTIVE_IDEMPOTENT_STATUSES:
            return lane
        if lane.idempotency_hash == lane_hash:
            return lane

    lane = Lane(
        agent=agent,
        dispatch_id=None,
        idempotency_hash=lane_hash,
        status=LaneStatus.pending,
        landed_at=None,
    )
    manifest.lanes.append(lane)
    return lane


def aggregate(
    manifest: RoundManifest,
    contributions: dict[str, Contribution],
) -> RoundManifest:
    """Aggregate landed contributions into a deterministic round state."""

    landed = _landed_contributions(manifest, contributions)
    merged_changes, conflicts = _merge_changes(landed)
    consensus_hash = _consensus_hash(_verdict_tally(landed), merged_changes)

    substantive = {
        agent: item for agent, item in landed.items()
        if item.subject_hash and substantive_evidence_eligibility(item, item.subject_hash)
    }
    subject_hashes = {item.subject_hash for item in substantive.values() if item.subject_hash}
    evidence_quorum = False
    if len(subject_hashes) == 1:
        evidence_quorum, _eligible, _evidence_reasons = evaluate_approval_quorum(
            landed, next(iter(subject_hashes))
        )
        for agent, item in sorted(substantive.items()):
            if item.verdict in {Verdict.REJECT, Verdict.APPROVE_WITH_CHANGES}:
                conflicts.append(
                    Conflict(
                        file_path="",
                        line_range=None,
                        description=f"{agent}:ELIGIBLE_{item.verdict.value}_BLOCKS",
                        competing=[agent],
                    )
                )
        if not evidence_quorum and not conflicts:
            conflicts.append(Conflict(
                file_path="", line_range=None, description="EVIDENCE_QUORUM_NOT_MET", competing=[]
            ))
    else:
        conflicts.append(
            Conflict(
                file_path="",
                line_range=None,
                description="MISSING_OR_CONFLICTING_SUBJECT_HASH",
                competing=sorted(landed),
            )
        )

    if not conflicts and evidence_quorum:
        updated = transition(manifest, RoundState.CONSENSUS_LOCKED, "round_aggregate")
        return updated.model_copy(
            update={
                "conflicts": [],
                "consensus_hash": consensus_hash,
                "locked_at": utc_iso(),
            }
        )

    updated = transition(manifest, RoundState.CONFLICTS_IDENTIFIED, "round_aggregate")
    return updated.model_copy(update={"conflicts": conflicts, "consensus_hash": consensus_hash})


def amend(
    manifest: RoundManifest,
    late: Contribution,
    consensus_verdict: Verdict,
    locked_changes: list[RequiredChange],
) -> RoundManifest:
    """Apply a late lane through durable AMEND concurrence or conflict handling."""

    if manifest.state != RoundState.CONSENSUS_LOCKED:
        raise ValueError("AMEND requires CONSENSUS_LOCKED manifest")

    amended = transition(manifest, RoundState.AMEND, "round_aggregate")
    subject_hash = late.subject_hash or ""
    eligible, _reason = approval_eligibility(late, subject_hash)
    if eligible and consensus_verdict == Verdict.APPROVE and all(
        _change_is_subset(change, locked_changes) for change in late.required_changes
    ):
        relocked = _mark_lane(amended, late.agent_id, LaneStatus.amended)
        relocked = transition(relocked, RoundState.CONSENSUS_LOCKED, "round_aggregate")
        return relocked.model_copy(update={"locked_at": utc_iso()})

    conflicts = _amend_conflicts(late, locked_changes)
    conflicted = transition(amended, RoundState.CONFLICTS_IDENTIFIED, "round_aggregate")
    return conflicted.model_copy(update={"conflicts": conflicts})


def quorum_met(manifest: RoundManifest) -> bool:
    """Return whether enough landed lanes and all required agents are present."""

    landed_agents = {lane.agent for lane in manifest.lanes if lane.status in LANDED_STATUSES}
    return (
        len(landed_agents) >= manifest.quorum_policy.min_lanes
        and set(manifest.quorum_policy.required_agents).issubset(landed_agents)
    )


def evaluate_approval_quorum(
    contributions: dict[str, Contribution], subject_hash: str
) -> tuple[bool, list[str], list[str]]:
    """Evaluate substantive evidence, never lane status, for two-family/two-principal approval."""

    eligible: list[str] = []
    reasons: list[str] = []
    families: set[str] = set()
    principals: set[str] = set()
    for agent, contribution in sorted(contributions.items()):
        ok, reason = approval_eligibility(contribution, subject_hash)
        if ok:
            eligible.append(agent)
            families.add(contribution.model_provenance.model_family or "")
            principals.add(contribution.model_provenance.execution_principal or "")
        else:
            reasons.append(f"{agent}:{reason}")
        if contribution.verdict == Verdict.REJECT and substantive_evidence_eligibility(
            contribution, subject_hash
        ):
            reasons.append(f"{agent}:ELIGIBLE_REJECT_BLOCKS")
    quorum = len(eligible) >= 2 and len(families) >= 2 and len(principals) >= 2
    if len(families) < 2:
        reasons.append("MODEL_FAMILY_DIVERSITY_NOT_MET")
    if len(principals) < 2:
        reasons.append("PRINCIPAL_DIVERSITY_NOT_MET")
    if any(reason.endswith("ELIGIBLE_REJECT_BLOCKS") for reason in reasons):
        quorum = False
    return quorum, eligible, sorted(set(reasons))


def consume_authorization(
    authorization,
    *,
    idempotency_key: str,
    principal: str,
    assignment_id: str,
    current_hashes: dict[str, str],
    now: str,
) -> tuple[object, AssignmentRecord]:
    """Atomically-composable pure authorization consumption validator."""

    if authorization.state != AuthorizationState.AUTHORIZED:
        raise ValueError("LEGACY_STATE_NOT_AUTHORIZATION")
    if authorization.idempotency_key != idempotency_key:
        raise ValueError("IDEMPOTENCY_KEY_MISMATCH")
    if now >= authorization.expires_at:
        raise ValueError("AUTHORIZATION_EXPIRED")
    for name in ("direction_hash", "plan_hash", "package_hash", "ownership_hash"):
        if current_hashes.get(name) != getattr(authorization, name):
            raise ValueError(f"{name.upper()}_MISMATCH")
    consumed = authorization.model_copy(
        update={"state": AuthorizationState.CONSUMED, "consumed_by": assignment_id}
    )
    assignment = AssignmentRecord(
        assignment_id=assignment_id,
        authorization_id=authorization.authorization_id,
        principal=principal,
        subject_hash=authorization.plan_hash,
        created_at=now,
    )
    return consumed, assignment


def validate_assignment_source(source: object) -> None:
    """Reject every legacy CONSENSUS_LOCKED-only assignment path."""

    if not hasattr(source, "state") or getattr(source, "state") != AuthorizationState.AUTHORIZED:
        raise ValueError("LEGACY_STATE_NOT_AUTHORIZATION")


def suspend_assignment(assignment: AssignmentRecord, reason: str) -> AssignmentRecord:
    """Revoke effects immediately when late evidence invalidates active execution."""

    return assignment.model_copy(update={
        "state": "SUSPENDED",
        "effects_allowed": False,
        "cancellation_pending": True,
        "audit": [*assignment.audit, f"SUSPEND:{reason}"],
    })


def abort_assignment(assignment: AssignmentRecord, actor: str, reason: str) -> AssignmentRecord:
    if assignment.state != "SUSPENDED":
        raise ValueError("ABORT_REQUIRES_SUSPENDED")
    return assignment.model_copy(update={
        "state": "CANCELLED",
        "effects_allowed": False,
        "cancellation_pending": False,
        "audit": [*assignment.audit, f"ABORT:{actor}:{reason}"],
    })


def _landed_contributions(
    manifest: RoundManifest,
    contributions: dict[str, Contribution],
) -> dict[str, Contribution]:
    landed_agents = {lane.agent for lane in manifest.lanes if lane.status in LANDED_STATUSES}
    return {
        agent: contributions[agent]
        for agent in sorted(contributions)
        if agent in landed_agents
    }


def _verdict_tally(contributions: dict[str, Contribution]) -> dict[str, int]:
    tally = Counter(contribution.verdict.value for contribution in contributions.values())
    return dict(sorted(tally.items()))


def _merge_changes(
    contributions: dict[str, Contribution],
) -> tuple[list[MergedChange], list[Conflict]]:
    groups: dict[tuple[str, str | None], list[tuple[str, RequiredChange]]] = defaultdict(list)
    for agent in sorted(contributions):
        for change in contributions[agent].required_changes:
            groups[(change.file_path, change.line_range)].append((agent, change))

    merged: list[MergedChange] = []
    conflicts: list[Conflict] = []
    for (file_path, line_range), entries in sorted(groups.items(), key=lambda item: _key_sort(item[0])):
        descriptions: list[str] = []
        for _, change in entries:
            if not any(_descriptions_compatible(change.description, existing) for existing in descriptions):
                descriptions.append(change.description)

        agents = sorted({agent for agent, _ in entries})
        if len(descriptions) > 1:
            conflicts.append(
                Conflict(
                    file_path=file_path,
                    line_range=line_range,
                    description="Competing required changes: " + " | ".join(sorted(descriptions)),
                    competing=agents,
                )
            )
            continue

        representative = sorted(entries, key=lambda item: (item[1].description, item[0]))[0][1]
        merged.append(
            MergedChange(
                file_path=file_path,
                line_range=line_range,
                description=representative.description,
                severity=representative.severity.value,
                agents=agents,
            )
        )
    return merged, conflicts


def _consensus_hash(verdict_tally: dict[str, int], merged_changes: list[MergedChange]) -> str:
    payload = {
        "verdict_tally": verdict_tally,
        "required_changes": [
            {
                "file_path": change.file_path,
                "line_range": change.line_range,
                "description": change.description,
                "severity": change.severity,
                "agents": change.agents,
            }
            for change in sorted(merged_changes, key=lambda item: _key_sort((item.file_path, item.line_range)))
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _descriptions_compatible(left: str, right: str) -> bool:
    left_norm = _normalize_description(left)
    right_norm = _normalize_description(right)
    return left_norm in right_norm or right_norm in left_norm


def _normalize_description(description: str) -> str:
    return " ".join(description.casefold().split())


def _change_is_subset(change: RequiredChange, locked_changes: list[RequiredChange]) -> bool:
    return any(
        change.file_path == locked.file_path
        and change.line_range == locked.line_range
        and _descriptions_compatible(change.description, locked.description)
        for locked in locked_changes
    )


def _mark_lane(manifest: RoundManifest, agent: str, status: LaneStatus) -> RoundManifest:
    lanes = [
        lane.model_copy(update={"status": status, "landed_at": lane.landed_at or utc_iso()})
        if lane.agent == agent
        else lane
        for lane in manifest.lanes
    ]
    if not any(lane.agent == agent for lane in lanes):
        lanes.append(
            Lane(
                agent=agent,
                dispatch_id=None,
                idempotency_hash=idempotency_hash(
                    manifest.round_id,
                    agent,
                    manifest.task.prompt,
                ),
                status=status,
                landed_at=utc_iso(),
            )
        )
    return manifest.model_copy(update={"lanes": lanes})


def _amend_conflicts(late: Contribution, locked_changes: list[RequiredChange]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    locked_keys = {(change.file_path, change.line_range) for change in locked_changes}
    for change in sorted(late.required_changes, key=lambda item: _key_sort((item.file_path, item.line_range))):
        if (change.file_path, change.line_range) not in locked_keys or not _change_is_subset(
            change,
            locked_changes,
        ):
            conflicts.append(
                Conflict(
                    file_path=change.file_path,
                    line_range=change.line_range,
                    description=change.description,
                    competing=[late.agent_id],
                )
            )
    if not conflicts:
        conflicts.append(
            Conflict(
                file_path="",
                line_range=None,
                description=f"Late verdict {late.verdict.value} does not match locked consensus",
                competing=[late.agent_id],
            )
        )
    return conflicts


def _key_sort(key: tuple[str, str | None]) -> tuple[str, str]:
    return key[0], key[1] or ""
