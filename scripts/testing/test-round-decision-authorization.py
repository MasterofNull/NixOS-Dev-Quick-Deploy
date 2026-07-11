#!/usr/bin/env python3
"""C0.1 evidence-bound decision and implementation authorization tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import round_aggregate  # noqa: E402
import round_contribution  # noqa: E402
import round_state  # noqa: E402

SUBJECT = "sha-256:" + "a" * 64


def review(
    agent: str,
    family: str,
    principal: str,
    verdict: round_contribution.Verdict = round_contribution.Verdict.APPROVE,
    **updates: object,
) -> round_contribution.Contribution:
    values = {
        "agent_id": agent,
        "model_provenance": round_contribution.ModelProvenance(
            model_name=f"{family}-model",
            model_version="1",
            model_family=family,
            execution_principal=principal,
            assurance="ORCHESTRATOR_ATTESTED",
        ),
        "verdict": verdict,
        "subject_hash": SUBJECT,
        "fresh": True,
        "producer_verified": True,
        "evidence_condition": "VALID",
    }
    values.update(updates)
    return round_contribution.Contribution(**values)


def authorization() -> round_state.ImplementationAuthorization:
    return round_state.ImplementationAuthorization(
        authorization_id="auth-1",
        state=round_state.AuthorizationState.AUTHORIZED,
        direction_hash="sha-256:" + "b" * 64,
        plan_hash=SUBJECT,
        package_hash="sha-256:" + "c" * 64,
        ownership_hash="sha-256:" + "d" * 64,
        idempotency_key="single-use",
        expires_at="2026-07-17T00:00:00Z",
        owner_principal="owner",
    )


def current_hashes(auth: round_state.ImplementationAuthorization) -> dict[str, str]:
    return {name: getattr(auth, name) for name in (
        "direction_hash", "plan_hash", "package_hash", "ownership_hash"
    )}


def test_positive_direction_plan_authorization_assignment_cascade() -> None:
    reviews = {
        "claude": review("claude", "anthropic", "oauth-anthropic"),
        "gemini": review("gemini", "google", "oauth-google"),
    }
    quorum, eligible, reasons = round_aggregate.evaluate_approval_quorum(reviews, SUBJECT)
    assert quorum and eligible == ["claude", "gemini"] and reasons == []

    # Direction/plan approval is intentionally not assignment authority.
    with pytest.raises(ValueError, match="LEGACY_STATE_NOT_AUTHORIZATION"):
        round_aggregate.validate_assignment_source(round_state.RoundState.CONSENSUS_LOCKED)

    auth = authorization()
    consumed, assignment = round_aggregate.consume_authorization(
        auth,
        idempotency_key="single-use",
        principal="codex",
        assignment_id="assignment-1",
        current_hashes=current_hashes(auth),
        now="2026-07-11T00:00:00Z",
    )
    assert consumed.state == round_state.AuthorizationState.CONSUMED
    assert assignment.authorization_id == auth.authorization_id
    suspended = round_aggregate.suspend_assignment(assignment, "LATE_CRITICAL_REJECT")
    assert suspended.state == "SUSPENDED" and not suspended.effects_allowed
    cancelled = round_aggregate.abort_assignment(suspended, "owner", "bounded cancellation")
    assert cancelled.state == "CANCELLED" and not cancelled.cancellation_pending
    assert assignment.state == "ASSIGNED"  # immutable audit/reopen uses a new attempt
    with pytest.raises(ValueError, match="LEGACY_STATE_NOT_AUTHORIZATION"):
        round_aggregate.consume_authorization(
            consumed,
            idempotency_key="single-use",
            principal="codex",
            assignment_id="assignment-2",
            current_hashes=current_hashes(auth),
            now="2026-07-11T00:00:01Z",
        )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"verdict": round_contribution.Verdict.ABSTAIN}, "VERDICT_ABSTAIN"),
        ({"verdict": round_contribution.Verdict.REJECT}, "VERDICT_REJECT"),
        ({"verdict": round_contribution.Verdict.APPROVE_WITH_CHANGES}, "VERDICT_APPROVE_WITH_CHANGES"),
        ({"fresh": False}, "STALE_REVIEW"),
        ({"subject_hash": "sha-256:" + "f" * 64}, "SUBJECT_HASH_MISMATCH"),
        ({"producer_verified": False}, "UNVERIFIED_PRODUCER"),
        ({"proxy": True}, "PROXY_ZERO_WEIGHT"),
        ({"self_review": True}, "SELF_REVIEW_ZERO_WEIGHT"),
    ],
)
def test_negative_review_matrix_has_zero_approval_weight(
    mutation: dict[str, object], expected: str
) -> None:
    bad = review("bad", "anthropic", "one", **mutation)
    ok, reason = round_contribution.approval_eligibility(bad, SUBJECT)
    assert not ok and reason == expected


def test_same_family_or_principal_cannot_satisfy_diversity() -> None:
    for reviews in (
        {"a": review("a", "same", "p1"), "b": review("b", "same", "p2")},
        {"a": review("a", "f1", "same"), "b": review("b", "f2", "same")},
    ):
        quorum, _, reasons = round_aggregate.evaluate_approval_quorum(reviews, SUBJECT)
        assert not quorum and reasons


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"now": "2026-07-18T00:00:00Z"}, "AUTHORIZATION_EXPIRED"),
        ({"idempotency_key": "wrong"}, "IDEMPOTENCY_KEY_MISMATCH"),
        ({"hash_name": "plan_hash"}, "PLAN_HASH_MISMATCH"),
    ],
)
def test_assignment_blocks_expiry_retry_and_hash_drift(change: dict[str, str], error: str) -> None:
    auth = authorization()
    hashes = current_hashes(auth)
    if "hash_name" in change:
        hashes[change["hash_name"]] = "sha-256:" + "0" * 64
    with pytest.raises(ValueError, match=error):
        round_aggregate.consume_authorization(
            auth,
            idempotency_key=change.get("idempotency_key", "single-use"),
            principal="codex",
            assignment_id="assignment-x",
            current_hashes=hashes,
            now=change.get("now", "2026-07-11T00:00:00Z"),
        )


def test_canonical_vectors_and_atomic_cas_recovery_rollback(tmp_path: Path) -> None:
    value = {"z": "e\u0301", "a": 1, "ratio": {"numerator": 1, "denominator": 2}}
    assert round_state.canonical_bytes(value) == (
        '{"a":1,"ratio":{"denominator":2,"numerator":1},"z":"é"}'.encode()
    )
    with pytest.raises(ValueError, match="FLOAT_FORBIDDEN"):
        round_state.canonical_bytes({"score": 0.5})

    manifest = tmp_path / "manifest.json"
    first_hash = round_state.commit_manifest_cas(value, manifest, None)
    before = manifest.read_bytes()
    with pytest.raises(RuntimeError, match="CAS_MISMATCH"):
        round_state.commit_manifest_cas({"a": 2}, manifest, "sha-256:" + "0" * 64)
    assert manifest.read_bytes() == before
    second_hash = round_state.commit_manifest_cas(value, manifest, first_hash)
    assert second_hash == first_hash

    # Rollback/read compatibility: v1 manifests remain readable and immutable.
    v1 = tmp_path / "round-v1.json"
    original = round_state.RoundManifest(
        round_id="legacy", state=round_state.RoundState.CREATED,
        task=round_state.RoundTask(prompt="legacy", target="", scope_files=[]),
        opened_at="2026-07-01T00:00:00Z",
        quorum_policy=round_state.QuorumPolicy(
            min_lanes=1, required_agents=[], timeout_seconds=None, deadline=None
        ),
        lanes=[], consensus_hash=None, aggregate_path=None, aggregate_hash=None, locked_at=None,
    )
    round_state.save(original, v1)
    raw = v1.read_bytes()
    assert round_state.load(v1) == original
    assert v1.read_bytes() == raw
